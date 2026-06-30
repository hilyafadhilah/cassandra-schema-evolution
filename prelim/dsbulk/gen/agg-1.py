import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from multiprocessing import Pool
from pathlib import Path

from collections.abc import Iterable, Iterator
import uuid


class CollectionType(Enum):
    SET = 'set'
    LIST = 'list'
    MAP = 'map'


# agg section

@dataclass(frozen=True)
class Aggregation:
    collection_type: CollectionType
    type: str = 'uuid'
    num_agg_columns: int = 1
    columns: tuple[tuple[str, str], ...] = field(init=False)

    def __post_init__(self):
        if self.collection_type == CollectionType.MAP:
            ctype = f'map<uuid, {self.type}>'
        else:
            ctype = f'{self.collection_type.value}<{self.type}>'
        object.__setattr__(self, 'columns', tuple(
            (f'column_agg_{j + 1}', ctype)
            for j in range(self.num_agg_columns)
        ))

    def generate_values(self, num_values: int = 1) -> tuple[dict | list, ...]:
        if self.collection_type == CollectionType.MAP:
            return tuple({
                str(uuid.uuid4()): str(uuid.uuid4())
                for _ in range(num_values)
            } for _ in range(self.num_agg_columns))
        else:
            return tuple([
                str(uuid.uuid4())
                for _ in range(num_values)
            ] for _ in range(self.num_agg_columns))


# agg section end
# data section

def write_file(filename: str | Path, content: str) -> None:
    with open(filename, 'w') as f:
        f.write(content)


@dataclass(frozen=True)
class DataGen:
    basedir: str
    num_partitions: int
    num_partition_rows: int
    num_columns: int
    agg: Aggregation
    num_values: int

    path: str = field(init=False)
    name: str = field(init=False)
    columns: tuple[tuple[str, str], ...] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'name', '_'.join((
            f'{self.num_partitions}p',
            f'{self.num_partition_rows}pr',
            f'{self.num_columns}c',
            f'{self.num_values}v',
            f'{self.agg.collection_type.value}',
        )))
        object.__setattr__(self, 'path', str(Path(self.basedir) / self.name))
        object.__setattr__(self, 'columns', (
            ('pk', 'uuid'),
            ('timestamp', 'timestamp'),
            ('row_id', 'uuid'),
            *(
                (f'column_{j + 1}', 'text')
                for j in range(self.num_columns)
            ),
            *self.agg.columns,
        ))

    def generate_data(
        self,
        num_partitions: int,
        partition_start: int = 0
    ) -> Iterator[tuple[str, ...]]:
        for i in range(partition_start, partition_start + num_partitions):
            partition_key = str(uuid.uuid4())
            for k in range(self.num_partition_rows):
                yield (
                    partition_key,
                    datetime.now().isoformat(),
                    str(uuid.uuid4()),
                    *(f'value_{j+1:02d}' for j in range(self.num_columns)),
                    *(
                        json.dumps(agg_value, separators=(',', ':'))
                        for agg_value in self.agg.generate_values(
                            num_values=self.num_values
                        )
                    )
                )

    def write_cql(self, prefix: str = 'agg') -> None:
        tblname = f'{prefix}_{self.name}'
        columns = self.columns

        init_cql = (
            f'DROP TABLE IF EXISTS {tblname};\n\n'
            f'CREATE TABLE {tblname} (\n'
            + ',\n'.join(f'  {col} {dtype}' for col, dtype in columns) + ',\n'
            '  PRIMARY KEY (pk)\n'
            ');'
        )

        cleanup_cql = (
            f'DROP TABLE IF EXISTS {tblname};'
        )

        path = Path(self.path)

        write_file(path / 'init.cql', init_cql)
        write_file(path / 'cleanup.cql', cleanup_cql)
        write_file(path / 'tblname.txt', tblname)

    def init(self) -> None:
        Path(self.path).mkdir(parents=True, exist_ok=True)
        self.write_cql()

# data section end
# chunk section

def write_csv(
    filename: str | Path,
    columns: Iterable[str],
    data: Iterator[tuple[str, ...]],
) -> None:
    with open(filename, 'w', newline='', buffering=1024*1024) as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(data)

@dataclass(frozen=True)
class ChunkTask:
    gen: DataGen
    chunk_idx: int
    partition_start: int
    partition_end: int

    filename: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'filename', str(
            Path(self.gen.path) / f'{self.chunk_idx:03d}.csv'
        ))

def write_chunk(task: ChunkTask) -> ChunkTask:
    write_csv(
        filename=task.filename,
        columns=[col for col, _ in task.gen.columns],
        data=task.gen.generate_data(
            num_partitions=task.partition_end - task.partition_start,
            partition_start=task.partition_start,
        )
    )

    return task

# chunk section end
# main section


def create_tasks(
    gen: DataGen,
    max_file_rows: int = 1_000_000,
) -> list[ChunkTask]:
    tasks = []

    partitions_per_file = max(1, max_file_rows // gen.num_partition_rows)
    for chunk_idx, partition_start in enumerate(
        range(0, gen.num_partitions, partitions_per_file),
        start=1,
    ):
        partition_end = min(
            partition_start + partitions_per_file,
            gen.num_partitions
        )
        tasks.append(ChunkTask(
            gen=gen,
            chunk_idx=chunk_idx,
            partition_start=partition_start,
            partition_end=partition_end,
        ))

    return tasks

def run(
    path: str,
    column_counts: list[int],
    num_partitions: int,
    partition_row_counts: list[int],
    value_counts: list[int],
    collection_types: list[CollectionType],
    num_agg_columns: int = 1,
    max_file_rows: int = 1_000_000,
    workers: int | None = None,
) -> None:
    print(f'Generating CSV files in: {path}')
    print('Preparing tasks...')
    print()

    tasks = []
    for num_partition_rows in partition_row_counts:
        print(f'[-] {num_partition_rows} rows per partition')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')
            for collection_type in collection_types:
                print(f'      [-] {collection_type.value}')
                agg = Aggregation(
                    collection_type=collection_type,
                    num_agg_columns=num_agg_columns,
                )

                for num_values in value_counts:
                    print(f'        [-] {num_values} values')

                    gen = DataGen(
                        basedir=str(Path(path) / 'agg'),
                        num_partitions=num_partitions,
                        num_partition_rows=num_partition_rows,
                        num_columns=num_columns,
                        agg=agg,
                        num_values=num_values,
                    )
                    gen.init()

                    subtasks = create_tasks(gen, max_file_rows)

                    for task in subtasks:
                        print(
                            f'            '
                            f'Task: {task.filename} '
                            f'[{task.partition_start}:{task.partition_end}]'
                        )

                    tasks.extend(subtasks)

            

    print()
    print(f'Total tasks: {len(tasks)}')
    print(f'Workers: {workers or "auto"}')
    print()

    print('Starting generation...')
    print()

    tasks_count = len(tasks)
    pad = len(str(tasks_count))
    with Pool(processes=workers) as pool:
        for i, result in enumerate(pool.imap_unordered(write_chunk, tasks), start=1):
            print(
                f'[{i:>{pad}}/{tasks_count}] '
                f'Completed: {result.filename}'
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--path',
        type=str,
        default='data',
    )

    parser.add_argument(
        '--column-counts',
        nargs='+',
        type=int,
        default=[
            1, 3, 5, 7, 10,
            12, 15, 17, 20,
        ],
    )
    parser.add_argument(
        '--num-partitions',
        type=int,
        default=100,
    )
    parser.add_argument(
        '--partition-row-counts',
        nargs='+',
        type=int,
        default=[
            100,
            200,
            300,
            500,
            750,
            1_000,
        ],
    )
    parser.add_argument(
        '--value-counts',
        nargs='+',
        type=int,
        default=[1, 3, 5, 7, 10, 25, 50, 75, 100, 250],
    )
    parser.add_argument(
        '--num-agg-columns',
        type=int,
        default=1,
    )
    parser.add_argument(
        '--agg-types',
        nargs='+',
        type=str,
        default=['set', 'list', 'map'],
    )

    args = parser.parse_args()

    run(
        path=args.path,
        column_counts=args.column_counts,
        num_partitions=args.num_partitions,
        partition_row_counts=args.partition_row_counts,
        value_counts=args.value_counts,
        num_agg_columns=args.num_agg_columns,
        collection_types=[
            CollectionType(collection_type)
            for collection_type in args.agg_types
        ],
    )

# end

"""
--num-partitions 100 --partition-row-counts 1000 --column-counts 14 --value-counts 1 3 5 7 10 25 50 75 100 250 --num-agg-columns 1 --agg-types set

"""