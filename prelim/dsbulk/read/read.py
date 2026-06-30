import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import time
import threading
import sys

import pandas as pd
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args


@dataclass(frozen=True)
class TableConfig:
    name: str
    num_columns: int
    num_partitions: int
    num_partition_rows: int

PATTERNS = [
    re.compile(
        r"^(?P<num_rows>\d+)r"
        r"_(?P<num_columns>\d+)c$"
    ),
    re.compile(
        r"^(?P<num_partitions>\d+)p"
        r"_(?P<num_partition_rows>\d+)pr"
        r"_(?P<num_columns>\d+)c$"
    ),
    re.compile(
        r"(?P<num_rows>\d+)r"
        r"_(?P<num_columns>\d+)c"
        r"_(?P<num_fields>\d+)f"
        r"_(?P<num_values>\d+)v"
        r"_(?P<agg_type>\w+)$"
    ),
    re.compile(
        r"(?P<num_partitions>\d+)p"
        r"_(?P<num_partition_rows>\d+)pr"
        r"_(?P<num_columns>\d+)c"
        r"_(?P<num_fields>\d+)f"
        r"_(?P<num_values>\d+)v"
        r"_(?P<agg_type>\w+)$"
    ),
    re.compile(
        r"(?P<num_partitions>\d+)p"
        r"_(?P<num_partition_rows>\d+)pr"
        r"_(?P<num_columns>\d+)c"
        r"_(?P<num_values>\d+)v"
        r"_(?P<agg_type>\w+)$"
    ),
]


class CassandraReadPerformanceTester:
    def __init__(
        self,
        contact_points=['localhost'],
        keyspace: str = 'test_keyspace',
        limit: int = 100,
    ) -> None:
        self.keyspace = keyspace
        self.cluster = Cluster(contact_points)
        self.session = self.cluster.connect(keyspace)

        self.limit = limit

    def run_queries(
        self,
        num_queries: int,
        table: TableConfig,
        concurrency: int = 50,
    ) -> float:
        query = self.session.prepare(f"""
            SELECT * FROM {self.keyspace}.{table.name}
            WHERE pk = ?
            LIMIT {self.limit}
        """)

        values = [
            (f'pk_{i % table.num_partitions}',)
            for i in range(num_queries)
        ]

        start_time = time.perf_counter_ns()
        execute_concurrent_with_args(
            session=self.session,
            statement=query,
            parameters=values,
            concurrency=concurrency,
        )
        end_time = time.perf_counter_ns()

        return (end_time - start_time) / 1_000_000
    
    def run_queries_with_background_load(
        self,
        num_queries: int,
        table: TableConfig,
        concurrency: int = 30,
        background_sessions: int = 3,
        background_num_queries: int = 10,
        background_concurrency: int = 10,
    ):
        stop_event = threading.Event()
        threads = [
            threading.Thread(
                target=self._background_load_worker,
                kwargs={
                    'stop_event': stop_event,
                    'table_name': table.name,
                    'num_queries': background_num_queries,
                    'concurrency': background_concurrency,
                    'num_partitions': table.num_partitions,
                    'limit': self.limit,
                },
                daemon=True,
            )
            for _ in range(background_sessions)
        ]

        for t in threads:
            t.start()

        time.sleep(0.5)  # Give background threads a moment to start

        time_ms = self.run_queries(
            num_queries=num_queries,
            table=table,
            concurrency=concurrency,
        )

        stop_event.set()
        for t in threads:
            t.join()

        return time_ms

    def _background_load_worker(
        self,
        stop_event: threading.Event,
        table_name: str,
        num_queries: int,
        concurrency: int = 10,
        num_partitions: int = 100,
        limit: int = 100,
    ):
        cluster = Cluster(self.cluster.contact_points)
        session = cluster.connect(self.keyspace)

        query = session.prepare(f"""
            SELECT * FROM {self.keyspace}.{table_name}
            WHERE pk = ?
            LIMIT {limit}
        """)

        try:
            while not stop_event.is_set():
                values = [
                    (f'partition_{i % num_partitions}',)
                    for i in range(num_queries)
                ]
                try:
                    execute_concurrent_with_args(
                        session=session,
                        statement=query,
                        parameters=values,
                        concurrency=concurrency
                    )
                except Exception:
                    pass
        finally:
            session.shutdown()
            cluster.shutdown()

    def run_performance_test(
        self,
        tables: list[TableConfig],
        query_counts: list[int],
        iterations: int = 100,
        concurrency: int = 30,
        background_num_queries: int = 10,
        background_concurrency: int = 10,
    ) -> pd.DataFrame:
        results = []

        i_pad = len(str(iterations))

        for table in tables:
            print(f'[-] Table {table.name} ({table.num_columns} columns)')
            for num_queries in query_counts:
                print(f'    [-] {num_queries} queries')
                for i in range(iterations):
                    execution_time = self.run_queries_with_background_load(
                        num_queries=num_queries,
                        table=table,
                        concurrency=concurrency,
                        background_num_queries=background_num_queries,
                        background_concurrency=background_concurrency,
                    )

                    results.append({
                        'n_queries': num_queries,
                        'n_columns': table.num_columns,
                        'time_ms': execution_time,
                    })

                    print((
                        '\r\033[K'
                        '        '
                        f'Iteration {i+1:{i_pad}}/{iterations}: '
                        f'{execution_time:.2f} ms'
                    ), end='', flush=True)

                print(
                    '\r\033[K'
                    '        '
                    f'Iteration {iterations}/{iterations}: '
                    'Done.'
                )

        return pd.DataFrame(results)

    def cleanup(self):
        self.session.shutdown()
        self.cluster.shutdown()


if __name__ == "__main__":
    query_counts = [
        1, 2, 3, 5, 7, 10,
        20, 30, 50, 75, 100,
    ]
    column_counts = [
        1, 3, 5, 10, 12, 15, 17, 20,
    ]

    parser = argparse.ArgumentParser(description='Cassandra Read Performance Tester')
    parser.add_argument(
        'input_dir',
        type=Path,
        help='Directory containing input data files'
    )
    parser.add_argument(
        '--contact-points',
        nargs='+',
        default=['localhost'],
        help='Cassandra contact points'
    )
    parser.add_argument(
        '--keyspace',
        default='test_keyspace',
        help='Cassandra keyspace to use'
    )
    parser.add_argument(
        '--output-file', '-o',
        default='results.csv',
        help='CSV file to save results'
    )
    args = parser.parse_args()

    tester = CassandraReadPerformanceTester(
        contact_points=args.contact_points,
        keyspace=args.keyspace,
    )

    # iterate over directory in input_dir
    input_dir: Path = args.input_dir

    tables: list[TableConfig] = []
    for input_file in input_dir.iterdir():
        if not input_file.is_dir():
            continue

        match = None
        for pattern in PATTERNS:
            match = pattern.match(input_file.name)
            if match:
                break

        if not match:
            print(f'[!] Skipping {input_file.name} - no pattern match', file=sys.stderr)
            continue

        tblname_file = input_file / 'tblname.txt'
        if not tblname_file.exists():
            print(f'[!] Skipping {input_file.name} - missing tblname.txt', file=sys.stderr)
            continue

        num_columns = int(match.group('num_columns'))
        if 'num_partitions' in match.groupdict():
            num_partitions = int(match.group('num_partitions'))
            num_partition_rows = int(match.group('num_partition_rows'))
        else:
            num_partitions = int(match.group('num_rows'))
            num_partition_rows = 1

        table_name = tblname_file.read_text().strip()
        tables.append(TableConfig(
            name=table_name,
            num_columns=num_columns,
            num_partitions=num_partitions,
            num_partition_rows=num_partition_rows,
        ))

    try:
        results = tester.run_performance_test(
            query_counts=query_counts,
            tables=tables,
        )
        results.to_csv(args.output_file, index=False)
    finally:
        tester.cleanup()
