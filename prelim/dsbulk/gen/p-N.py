import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

from collections.abc import Iterable, Iterator
import uuid


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

    pk_text: bool = False

    path: str = field(init=False)
    name: str = field(init=False)
    columns: tuple[tuple[str, str], ...] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'name', '_'.join((
            f'{self.num_partitions}p',
            f'{self.num_partition_rows}pr',
            f'{self.num_columns}c',
        )))
        object.__setattr__(self, 'path', str(Path(self.basedir) / self.name))
        object.__setattr__(self, 'columns', (
            ('pk', 'text') if self.pk_text else ('pk', 'uuid'),
            ('timestamp', 'timestamp'),
            ('row_id', 'uuid'),
            *(
                (f'column_{j + 1}', 'text')
                for j in range(self.num_columns)
            ),
        ))

    def generate_data(
        self,
        num_partitions: int,
        partition_start: int = 0
    ) -> Iterator[tuple[str, ...]]:
        for i in range(partition_start, partition_start + num_partitions):
            partition_key = str(uuid.uuid4()) if not self.pk_text else f'partition_{i}'
            for k in range(self.num_partition_rows):
                yield (
                    partition_key,
                    datetime.now().isoformat(),
                    str(uuid.uuid4()),
                    *(f'value_{j+1:02d}' for j in range(self.num_columns)),
                )

    def write_cql(self, prefix: str = 'pn') -> None:
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
        writer = csv.writer(f, doublequote=False, escapechar='\\')
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

            gen = DataGen(
                basedir=str(Path(path) / 'pn'),
                num_partitions=num_partitions,
                num_partition_rows=num_partition_rows,
                num_columns=num_columns,
                pk_text=args.pk_text,
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
        '--pk-text',
        action='store_true',
        help='Use text type for partition key instead of uuid',
    )
    args = parser.parse_args()

    run(
        path=args.path,
        column_counts=args.column_counts,
        num_partitions=args.num_partitions,
        partition_row_counts=args.partition_row_counts,
    )

# end