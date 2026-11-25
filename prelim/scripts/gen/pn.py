import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
import uuid

from .lib import ChunkTask, Column, Config, Runner


@dataclass(frozen=True)
class PnConfig(Config):
    num_partitions: int
    num_partition_rows: int
    num_columns: int

    @cached_property
    def name(self) -> str:
        return '_'.join((
            f'{self.num_partitions}p',
            f'{self.num_partition_rows}pr',
            f'{self.num_columns}c'
        ))

    @cached_property
    def columns(self) -> tuple[Column, ...]:
        return (
            Column(name='pk', type=self.pk_type),
            Column(name='timestamp', type='timestamp'),
            Column(name='row_id', type='uuid'),
            *(
                Column(name=f'column_{j + 1}', type='text')
                for j in range(self.num_columns)
            ),
        )

    @cached_property
    def primary_key(self) -> tuple[str, ...]:
        return ('pk', 'timestamp', 'row_id')


@dataclass(frozen=True)
class PnTask(ChunkTask[PnConfig]):
    partition_start: int
    partition_end: int


class Pn(Runner[PnConfig, PnTask]):
    @classmethod
    def prefix(cls) -> str:
        return 'pn'

    @classmethod
    def _generate_ddl(cls, conf: PnConfig) -> tuple[str, str]:
        init = '\n\n'.join([
            cls._drop_table_cql(conf),
            cls._create_table_cql(conf),
        ])

        cleanup = cls._drop_table_cql(conf)

        return init, cleanup

    @classmethod
    def _generate_data(cls, task: PnTask) -> Iterator[tuple[str, ...]]:
        for i in range(task.partition_start, task.partition_end):
            partition_key = task.config.generate_partition_key(i)
            for k in range(task.config.num_partition_rows):
                yield (
                    partition_key,
                    datetime.now().isoformat(),
                    str(uuid.uuid4()),
                    *(f'value_{j+1:02d}' for j in range(task.config.num_columns)),
                )

    @classmethod
    def _create_tasks(cls, conf: PnConfig) -> list[PnTask]:
        tasks = []

        partitions_per_file = max(1, conf.max_rows_per_file // conf.num_partition_rows)
        for chunk_idx, partition_start in enumerate(
            range(0, conf.num_partitions, partitions_per_file),
            start=1,
        ):
            partition_end = min(
                partition_start + partitions_per_file,
                conf.num_partitions
            )

            tasks.append(PnTask(
                config=conf,
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
    pk_text: bool = False,
    max_file_rows: int = 1_000_000,
    workers: int | None = None,
) -> None:
    print(f'Generating CSV files in: {path}')
    print('Preparing tasks...')
    print()

    pn = Pn()
    for num_partition_rows in partition_row_counts:
        print(f'[-] {num_partition_rows} rows per partition')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')

            conf = PnConfig(
                basedir=pn.basedir(path),
                num_partitions=num_partitions,
                num_partition_rows=num_partition_rows,
                num_columns=num_columns,
                pk_type='text' if pk_text else 'uuid',
                max_rows_per_file=max_file_rows,
            )

            pn.init_config(conf)

            for task in pn.tasks[conf]:
                print(
                    f'            '
                    f'Task: {task.filename} '
                    f'[{task.partition_start}:{task.partition_end}]'
                )

    tasks = pn.all_tasks
    tasks_count = len(tasks)

    print()
    print(f'Total tasks: {tasks_count}')
    print(f'Workers: {workers or "auto"}')
    print()

    print('Starting generation...')
    print()

    pad = len(str(tasks_count))
    for i, result in enumerate(pn.run_tasks(workers=workers), start=1):
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
        pk_text=args.pk_text,
    )
