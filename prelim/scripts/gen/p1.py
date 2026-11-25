"""
Script to generate CSV files for P1 (Simple Table) benchmark.

P1 structure:
    - Partition Key (pk)
    - Column 1 (column_01)
    - Column 2 (column_02)
    - ...

Usage:
    python -m gen.p1 --column-counts <list_of_column_counts> --row-counts <list_of_row_counts> [--path <output_basedir>] [--pk-text]
"""

import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property

from .lib import ChunkTask, Column, Config, Runner


@dataclass(frozen=True)
class P1Config(Config):
    num_rows: int
    num_columns: int

    @cached_property
    def name(self) -> str:
        return '_'.join((
            f'{self.num_rows}r',
            f'{self.num_columns}c'
        ))

    @cached_property
    def columns(self) -> tuple[Column, ...]:
        return (
            Column(name='pk', type=self.pk_type),
            *(
                Column(name=f'column_{j + 1}', type='text')
                for j in range(self.num_columns)
            ),
        )

    @cached_property
    def primary_key(self) -> tuple[str, ...]:
        return ('pk',)


@dataclass(frozen=True)
class P1Task(ChunkTask[P1Config]):
    row_start: int
    row_end: int


class P1(Runner[P1Config, P1Task]):
    @classmethod
    def prefix(cls) -> str:
        return 'p1'

    @classmethod
    def _generate_ddl(cls, conf: P1Config) -> tuple[str, str]:
        init = '\n\n'.join([
            cls._drop_table_cql(conf),
            cls._create_table_cql(conf),
        ])

        cleanup = cls._drop_table_cql(conf)

        return init, cleanup

    @classmethod
    def _generate_data(cls, task: P1Task) -> Iterator[tuple[str, ...]]:
        for i in range(task.row_start, task.row_end):
            yield (
                task.config.generate_partition_key(i),
                *(f'value_{j+1:02d}' for j in range(task.config.num_columns))
            )

    @classmethod
    def _csv_row_width(cls, conf: P1Config) -> int:
        return len(
            conf.generate_partition_key(conf.num_rows - 1) + ',' +
            ','.join(
                f'value_{j+1:02d}' for j in range(conf.num_columns)
            )
        )

    @classmethod
    def _create_tasks(cls, conf: P1Config) -> list[P1Task]:
        tasks = []

        rows_per_chunk = min(
            conf.max_rows_per_file,
            conf.max_file_size // cls._csv_row_width(conf)
        ) if conf.max_file_size else conf.max_rows_per_file

        for row_start in range(0, conf.num_rows, rows_per_chunk):
            row_end = min(row_start + rows_per_chunk, conf.num_rows)
            chunk_idx = row_start // rows_per_chunk + 1

            tasks.append(P1Task(
                config=conf,
                chunk_idx=chunk_idx,
                row_start=row_start,
                row_end=row_end
            ))

        return tasks


def main(
    path: str,
    column_counts: list[int],
    row_counts: list[int],
    pk_text: bool = False,
    max_file_rows: int = 1_000_000,
    workers: int | None = None,
) -> None:
    print(f'Generating CSV files in: {path}')
    print('Preparing tasks...')
    print()

    p1 = P1()
    for num_rows in row_counts:
        print(f'[-] {num_rows} rows')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')

            conf = P1Config(
                basedir=p1.basedir(path),
                num_rows=num_rows,
                num_columns=num_columns,
                pk_type='text' if pk_text else 'uuid',
                max_rows_per_file=max_file_rows,
            )

            p1.init_config(conf)

            for task in p1.tasks[conf]:
                print(
                    f'            '
                    f'Task: {task.filename} '
                    f'[{task.row_start}:{task.row_end}]'
                )

    tasks = p1.all_tasks
    tasks_count = len(tasks)

    print()
    print(f'Total tasks: {tasks_count}')
    print(f'Workers: {workers or "auto"}')
    print()

    print('Starting generation...')
    print()

    pad = len(str(tasks_count))
    for i, result in enumerate(p1.run_tasks(workers=workers), start=1):
        print(
            f'[{i:>{pad}}/{tasks_count}] '
            f'Completed: {result.filename}'
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Generate CSV files for P1 (Simple Table) benchmark.'
    )
    parser.add_argument(
        '--path',
        type=str,
        default='data',
        help='Base directory to store generated CSV files (default: ./%(default)s)'
    )

    parser.add_argument(
        '--column-counts',
        nargs='+',
        type=int,
        default=[
            1, 3, 5, 7, 10,
            12, 15, 17, 20,
        ],
        help='List of column counts to generate (default: %(default)s)'
    )
    parser.add_argument(
        '--row-counts',
        nargs='+',
        type=int,
        default=[
            10_000,
            50_000,
            100_000,
            250_000,
            500_000,
            750_000,
            1_000_000,
        ],
        help='List of row counts to generate (default: %(default)s)'
    )

    parser.add_argument(
        '--pk-text',
        action='store_true',
        help='Use text type for partition key instead of uuid',
    )

    args = parser.parse_args()

    main(
        path=args.path,
        column_counts=args.column_counts,
        row_counts=args.row_counts,
        pk_text=args.pk_text,
    )
