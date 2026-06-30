import argparse
import csv
from dataclasses import dataclass, field
from enum import Enum
import json
from multiprocessing import Pool
from pathlib import Path

from collections.abc import Iterable, Iterator
import uuid


UUID_LENGTH = len(str(uuid.uuid4()))


class CollectionType(Enum):
    SET = 'set'
    LIST = 'list'
    MAP = 'map'


@dataclass(frozen=True)
class Aggregation:
    collection_type: CollectionType
    num_fields: int

    udt: Udt = field(init=False)
    column: tuple[str, str] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'udt', Udt(self.num_fields))
        if self.collection_type == CollectionType.MAP:
            ctype = f'map<uuid, frozen<{self.udt.name}>>'
        else:
            ctype = f'{self.collection_type.value}<frozen<{self.udt.name}>>'
        object.__setattr__(self, 'column', (f'column_agg', ctype))

    def generate_values(self, num_values: int = 1) -> dict | list:
        if self.collection_type == CollectionType.MAP:
            return {
                str(uuid.uuid4()): self.udt.generate_value()
                for _ in range(num_values)
            }
        else:
            return [
                self.udt.generate_value()
                for _ in range(num_values)
            ]

# agg section

@dataclass(frozen=True)
class Udt:
    num_fields: int
    name: str = field(init=False)
    fields: tuple[tuple[str, str]] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'name', f'udt_{self.num_fields}f')
        object.__setattr__(self, 'fields', tuple(
            (f'field_{j+1}', 'text')
            for j in range(self.num_fields)
        ))

    def generate_value(self) -> dict:
        return {
            f'field_{j+1}': f'value_{j+1:02d}'
            for j in range(self.num_fields)
        }

# agg section end
# data section

def write_file(filename: str | Path, content: str) -> None:
    with open(filename, 'w') as f:
        f.write(content)


@dataclass(frozen=True)
class DataGen:
    basedir: str
    num_rows: int
    num_columns: int
    agg: Aggregation
    num_values: int

    path: str = field(init=False)
    name: str = field(init=False)
    columns: tuple[tuple[str, str], ...] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'name', '_'.join((
            f'{self.num_rows}r',
            f'{self.num_columns}c',
            f'{self.agg.num_fields}f',
            f'{self.num_values}v',
            f'{self.agg.collection_type.value}',
        )))
        object.__setattr__(self, 'path', str(Path(self.basedir) / self.name))
        object.__setattr__(self, 'columns', (
            ('pk', 'uuid'),
            *(
                (f'column_{j + 1}', 'text')
                for j in range(self.num_columns)
            ),
            self.agg.column,
        ))

    def csv_row_width(self) -> int:
        return (
            UUID_LENGTH + 1 +
            sum(
                len(f'value_{j+1:02d}') + 1
                for j in range(self.num_columns)
            ) + 1 +
            sum(
                len(json.dumps(agg_value, separators=(',', ':'))) + 1
                for agg_value in self.agg.generate_values(num_values=self.num_values)
            )
        )

    def generate_data(
        self,
        num_rows: int,
        row_start: int = 0
    ) -> Iterator[tuple[str, ...]]:
        for i in range(row_start, row_start + num_rows):
            yield (
                str(uuid.uuid4()),
                *(f'value_{j+1:02d}' for j in range(self.num_columns)),
                json.dumps(
                    self.agg.generate_values(num_values=self.num_values),
                    separators=(',', ':'),
                )
            )

    def write_cql(self, prefix: str = 'agg') -> None:
        tblname = f'{prefix}_{self.name}'
        columns = self.columns

        udt_name = self.agg.udt.name
        udt_fields = self.agg.udt.fields

        init_cql = (
            f'DROP TYPE IF EXISTS {udt_name};\n\n'
            f'CREATE TYPE {udt_name} (\n'
            + ',\n'.join(f'  {field} {dtype}' for field, dtype in udt_fields) + '\n'
            ');\n\n'
            f'DROP TABLE IF EXISTS {tblname};\n\n'
            f'CREATE TABLE {tblname} (\n'
            + ',\n'.join(f'  {col} {dtype}' for col, dtype in columns) + ',\n'
            '  PRIMARY KEY (pk)\n'
            ');'
        )

        cleanup_cql = (
            f'DROP TABLE IF EXISTS {tblname};\n'
            f'DROP TYPE IF EXISTS {udt_name};'
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
    chunk_start: int
    chunk_end: int

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
            num_rows=task.chunk_end - task.chunk_start,
            row_start=task.chunk_start,
        )
    )

    return task

# chunk section end
# main section


def create_tasks(
    gen: DataGen,
    chunk_size: int,
    max_file_size: int = 1024 * 1024 * 1024, # 1GB
) -> list[ChunkTask]:
    tasks = []

    row_width = gen.csv_row_width()
    total_size = row_width * gen.num_rows
    if total_size > max_file_size:
        chunk_size = min(chunk_size, max_file_size // row_width)

    for chunk_start in range(0, gen.num_rows, chunk_size):
        chunk_end = min(chunk_start + chunk_size, gen.num_rows)
        chunk_idx = chunk_start // chunk_size + 1

        tasks.append(ChunkTask(
            gen=gen,
            chunk_idx=chunk_idx,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
        ))
    return tasks

def run(
    path: str,
    column_counts: list[int],
    row_counts: list[int],
    field_counts: list[int],
    value_counts: list[int],
    chunk_size: int = 1_000_000,
    workers: int | None = None,
) -> None:
    collection_types = [
        CollectionType.SET,
        CollectionType.LIST,
        CollectionType.MAP
    ]

    print(f'Generating CSV files in: {path}')
    print('Preparing tasks...')
    print()

    tasks = []
    for num_rows in row_counts:
        print(f'[-] {num_rows} rows')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')
            for num_fields in field_counts:
                print(f'    [-] {num_fields} UDT fields')
                for collection_type in collection_types:
                    print(f'      [-] {collection_type.value}')
                    agg = Aggregation(collection_type, num_fields)
                    for num_values in value_counts:
                        print(f'        [-] {num_values} values')

                        gen = DataGen(
                            basedir=str(Path(path) / 'agg'),
                            num_rows=num_rows,
                            num_columns=num_columns,
                            agg=agg,
                            num_values=num_values,
                        )
                        gen.init()

                        subtasks = create_tasks(gen, chunk_size)

                        for task in subtasks:
                            print(
                                f'            '
                                f'Task: {task.filename} '
                                f'[{task.chunk_start}:{task.chunk_end}]'
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

    args = parser.parse_args()

    run(
        path=args.path,
        column_counts=args.column_counts,
        row_counts=args.row_counts,
        field_counts=args.field_counts,
        value_counts=args.value_counts,
    )

# end

"""
--row-counts 300_000 --column-counts 2 --field-counts 2 3 5 7 10 --value-counts 3
--row-counts 300_000 --column-counts 4 --field-counts 2 3 5 7 10 --value-counts 3
--row-counts 300_000 --column-counts 6 --field-counts 2 3 5 7 10 --value-counts 3
--row-counts 300_000 --column-counts 9 --field-counts 2 3 5 7 10 --value-counts 3

--row-counts 200_000 --column-counts 14 --field-counts 2 3 5 7 10 --value-counts 3
--row-counts 200_000 --column-counts 14 --field-counts 5 --value-counts 1 3 5 7 10 25
--row-counts 200_000 --column-counts 14 --field-counts 5 --value-counts 50 75
--row-counts 100_000 --column-counts 14 --field-counts 5 --value-counts 1 3 5 7 10 25
--row-counts 100_000 --column-counts 14 --field-counts 5 --value-counts 50 75

--row-counts 300_000 --column-counts 4 --field-counts 5 --value-counts 3 5 7 10
--row-counts 300_000 --column-counts 4 --field-counts 5 --value-counts 25 50 75 100 250
"""