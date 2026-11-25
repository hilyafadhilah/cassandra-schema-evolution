import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
import uuid

from .lib import TIMESTAMP_LENGTH, UUID_LENGTH, ChunkTask, Collection, CollectionType, Column, Config, Runner


@dataclass(frozen=True)
class AggPnConfig(Config):
    num_partitions: int
    num_partition_rows: int
    num_columns: int
    collection: Collection

    @cached_property
    def name(self) -> str:
        return '_'.join((
            f'{self.num_partitions}p',
            f'{self.num_partition_rows}pr',
            f'{self.num_columns}c',
            f'{self.collection.num_columns}a',
            f'{self.collection.num_fields}f',
            f'{self.collection.num_values}v',
            f'{self.collection.type.value}',
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
            *self.collection.columns,
        )

    @cached_property
    def primary_key(self) -> tuple[str, ...]:
        return ('pk', 'timestamp', 'row_id')


@dataclass(frozen=True)
class AggPnTask(ChunkTask[AggPnConfig]):
    partition_start: int
    partition_end: int


class AggPn(Runner[AggPnConfig, AggPnTask]):
    @classmethod
    def prefix(cls) -> str:
        return 'aggpn'

    @classmethod
    def _generate_ddl(cls, conf: AggPnConfig) -> tuple[str, str]:
        init_lines = [
            conf.collection.value.drop_cql(),
            conf.collection.value.create_cql(),
            cls._drop_table_cql(conf),
            cls._create_table_cql(conf),
        ]
        init = '\n\n'.join(ln for ln in init_lines if ln)

        cleanup_lines = [
            cls._drop_table_cql(conf),
            conf.collection.value.drop_cql(),
        ]
        cleanup = '\n'.join(ln for ln in cleanup_lines if ln)

        return init, cleanup

    @classmethod
    def _generate_data(cls, task: AggPnTask) -> Iterator[tuple[str, ...]]:
        for i in range(task.partition_start, task.partition_end):
                    partition_key = task.config.generate_partition_key(i)
                    for k in range(task.config.num_partition_rows):
                        yield (
                            partition_key,
                            datetime.now().isoformat(),
                            str(uuid.uuid4()),
                            *(f'value_{j+1:02d}' for j in range(task.config.num_columns)),
                            *task.config.collection.generate_values()
                        )

    @classmethod
    def _csv_row_width(cls, conf: AggPnConfig) -> int:
        return (
            len(conf.generate_partition_key(conf.num_partitions - 1)) + 1 +
            TIMESTAMP_LENGTH + 1 +
            UUID_LENGTH + 1 +
            sum(len(f'value_{j+1:02d}') + 1 for j in range(conf.num_columns)) + 1 +
            sum(len(value) + 1 for value in conf.collection.generate_values())
        )

    @classmethod
    def _create_tasks(cls, conf: AggPnConfig) -> list[AggPnTask]:
        tasks = []

        partition_size = conf.num_partition_rows * cls._csv_row_width(conf)
        partitions_per_file = min(
            max(1, conf.max_rows_per_file // conf.num_partition_rows),
            max(1, conf.max_file_size // partition_size)
        )

        for chunk_idx, partition_start in enumerate(
            range(0, conf.num_partitions, partitions_per_file),
            start=1,
        ):
            partition_end = min(
                partition_start + partitions_per_file,
                conf.num_partitions
            )

            tasks.append(AggPnTask(
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
    field_counts: list[int],
    value_counts: list[int],
    collection_types: list[CollectionType],
    num_collection_columns: int = 1,
    max_file_rows: int = 1_000_000,
    max_file_size: int = 1024 * 1024 * 1024,  # 1GB
    workers: int | None = None,
    pk_text: bool = False,
) -> None:
    print(f'Generating CSV files in: {path}')
    print('Preparing tasks...')
    print()

    agg = AggPn()
    for num_partition_rows in partition_row_counts:
        print(f'[-] {num_partition_rows} rows per partition')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')
            for num_fields in field_counts:
                print(f'    [-] {num_fields} UDT fields')
                for collection_type in collection_types:
                    print(f'      [-] {collection_type.value}')
                    for num_values in value_counts:
                        print(f'        [-] {num_values} values')

                        coll = Collection(
                            type=collection_type,
                            num_fields=num_fields,
                            num_values=num_values,
                            num_columns=num_collection_columns,
                        )

                        conf = AggPnConfig(
                            basedir=agg.basedir(path),
                            num_partitions=num_partitions,
                            num_partition_rows=num_partition_rows,
                            num_columns=num_columns,
                            collection=coll,
                            pk_type='text' if pk_text else 'uuid',
                            max_rows_per_file=max_file_rows,
                            max_file_size=max_file_size,
                        )

                        agg.init_config(conf)

                        for task in agg.tasks[conf]:
                            print(
                                f'            '
                                f'Task: {task.filename} '
                                f'[{task.partition_start}:{task.partition_end}]'
                            )

    tasks = agg.all_tasks
    tasks_count = len(tasks)

    print()
    print(f'Total tasks: {tasks_count}')
    print(f'Workers: {workers or "auto"}')
    print()

    print('Starting generation...')
    print()

    pad = len(str(tasks_count))
    for i, result in enumerate(agg.run_tasks(workers=workers), start=1):
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
        '--field-counts',
        nargs='+',
        type=int,
        default=[1, 3, 5, 7, 10],
    )
    parser.add_argument(
        '--value-counts',
        nargs='+',
        type=int,
        default=[1, 3, 5, 7, 10, 25, 50, 75, 100, 250],
    )
    parser.add_argument(
        '--agg-types',
        nargs='+',
        type=CollectionType,
        default=list(CollectionType),
        choices=list(CollectionType),
    )
    parser.add_argument(
        '--num-agg-columns',
        type=int,
        default=1,
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
        field_counts=args.field_counts,
        value_counts=args.value_counts,
        collection_types=args.agg_types,
        num_collection_columns=args.num_agg_columns,
        pk_text=args.pk_text,
    )
