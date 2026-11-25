import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property

from .lib import ChunkTask, Collection, CollectionType, Column, Config, Runner


@dataclass(frozen=True)
class AggP1Config(Config):
    num_rows: int
    num_columns: int
    collection: Collection

    @cached_property
    def name(self) -> str:
        return '_'.join((
            f'{self.num_rows}r',
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
            *(
                Column(name=f'column_{j + 1}', type='text')
                for j in range(self.num_columns)
            ),
            *self.collection.columns,
        )

    @cached_property
    def primary_key(self) -> tuple[str, ...]:
        return ('pk',)


@dataclass(frozen=True)
class AggP1Task(ChunkTask[AggP1Config]):
    row_start: int
    row_end: int


class AggP1(Runner[AggP1Config, AggP1Task]):
    @classmethod
    def prefix(cls) -> str:
        return 'aggp1'

    @classmethod
    def _generate_ddl(cls, conf: AggP1Config) -> tuple[str, str]:
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
    def _generate_data(cls, task: AggP1Task) -> Iterator[tuple[str, ...]]:
        for i in range(task.row_start, task.row_end):
            yield (
                task.config.generate_partition_key(i),
                *(f'value_{j+1:02d}' for j in range(task.config.num_columns)),
                *task.config.collection.generate_values()
            )

    @classmethod
    def _csv_row_width(cls, conf: AggP1Config) -> int:
        return (
            len(conf.generate_partition_key(conf.num_rows - 1)) + 1 +
            sum(len(f'value_{j+1:02d}') + 1 for j in range(conf.num_columns)) + 1 +
            sum(len(value) + 1 for value in conf.collection.generate_values())
        )

    @classmethod
    def _create_tasks(cls, conf: AggP1Config) -> list[AggP1Task]:
        tasks = []

        rows_per_chunk = min(
            conf.max_rows_per_file,
            conf.max_file_size // cls._csv_row_width(conf)
        ) if conf.max_file_size else conf.max_rows_per_file

        for row_start in range(0, conf.num_rows, rows_per_chunk):
            row_end = min(row_start + rows_per_chunk, conf.num_rows)
            chunk_idx = row_start // rows_per_chunk + 1

            tasks.append(AggP1Task(
                config=conf,
                chunk_idx=chunk_idx,
                row_start=row_start,
                row_end=row_end
            ))

        return tasks


def run(
    path: str,
    column_counts: list[int],
    row_counts: list[int],
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

    agg = AggP1()
    for num_rows in row_counts:
        print(f'[-] {num_rows} rows')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')
            for num_values in value_counts:
                print(f'    [-] {num_values} values')
                for collection_type in collection_types:
                    print(f'      [-] {collection_type.value} collection')
                    for num_fields in field_counts:
                        print(f'        [-] {num_fields} UDT fields')

                        coll = Collection(
                            type=collection_type,
                            num_fields=num_fields,
                            num_values=num_values,
                            num_columns=num_collection_columns,
                        )

                        conf = AggP1Config(
                            basedir=agg.basedir(path),
                            num_rows=num_rows,
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
                                f'[{task.row_start}:{task.row_end}]'
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
            2_500_000,
            5_000_000,
            7_500_000,
            10_000_000,
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
        row_counts=args.row_counts,
        field_counts=args.field_counts,
        value_counts=args.value_counts,
        collection_types=args.agg_types,
        num_collection_columns=args.num_agg_columns,
        pk_text=args.pk_text,
    )
