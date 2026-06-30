import argparse
import csv
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

from collections.abc import Iterable, Iterator
import uuid


@dataclass(frozen=True)
class ChunkTask:
    filename: Path
    num_rows: int
    num_columns: int
    chunk_start: int
    chunk_end: int


def generate_columns(num_columns: int) -> list[tuple[str, str]]:
    return [('pk', 'text')] + [
        (f'column_{j + 1}', 'text') for j in range(num_columns)
    ]

def generate_data(
    num_rows: int,
    num_columns: int,
    row_start: int = 0,
) -> Iterator[tuple[str, ...]]:
    for i in range(row_start, row_start + num_rows):
        yield (str(uuid.uuid4()), *(
            f'value_{j+1:02d}' for j in range(num_columns)
        ))

def write_csv(
    filename: str | Path,
    columns: Iterable[str],
    data: Iterator[tuple[str, ...]],
) -> None:
    with open(filename, 'w', newline='', buffering=1024*1024) as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(data)

def write_chunk(task: ChunkTask) -> ChunkTask:
    write_csv(
        filename=task.filename,
        columns=[col for col, _ in generate_columns(task.num_columns)],
        data=generate_data(
            num_rows=task.chunk_end - task.chunk_start,
            num_columns=task.num_columns,
            row_start=task.chunk_start,
        )
    )

    return task

@dataclass(frozen=True)
class CQL:
    init: str
    cleanup: str
    tblname: str

def generate_cql(
    num_columns: int,
    num_rows: int,
    prefix: str = 'p1'
) -> CQL:
    tblname = f'{prefix}_{num_rows}r_{num_columns}c'
    columns = generate_columns(num_columns)

    init_cql = (
        f'DROP TABLE IF EXISTS {tblname};\n\n'
        f'CREATE TABLE {tblname} (\n'
        + ',\n'.join(f'  {col} {dtype}' for col, dtype in columns) + ',\n'
        '  PRIMARY KEY (pk)\n'
        ');'
    )

    cleanup_cql = f'DROP TABLE IF EXISTS {tblname};'

    return CQL(
        init=init_cql,
        cleanup=cleanup_cql,
        tblname=tblname,
    )

def write_file(filename: str | Path, content: str) -> None:
    with open(filename, 'w') as f:
        f.write(content)

def run(
    path: str,
    column_counts: list[int],
    row_counts: list[int],
    chunk_size: int = 1_000_000,
    workers: int | None = None,
) -> None:
    print(f'Generating CSV files in: {path}')
    print('Preparing tasks...')
    print()

    tasks = []
    for num_rows in row_counts:
        print(f'[-] {num_rows} rows')
        for num_columns in column_counts:
            print(f'  [-] {num_columns} columns')

            dirname = Path(path) / 'p1' / f'{num_rows}r_{num_columns}c'
            dirname.mkdir(parents=True, exist_ok=True)

            cql = generate_cql(num_columns=num_columns, num_rows=num_rows)
            write_file(dirname / 'init.cql', cql.init)
            write_file(dirname / 'cleanup.cql', cql.cleanup)
            write_file(dirname / 'tblname.txt', cql.tblname)

            for chunk_start in range(0, num_rows, chunk_size):
                chunk_end = min(chunk_start + chunk_size, num_rows)
                chunk_idx = chunk_start // chunk_size + 1

                filename = dirname / f'{chunk_idx:03d}.csv'
                tasks.append(ChunkTask(
                    filename=filename,
                    num_rows=num_rows,
                    num_columns=num_columns,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end
                ))

                print(
                    f'    '
                    f'Task: {filename} '
                    f'[{chunk_start}:{chunk_end}]'
                )

            

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
            2_500_000,
            5_000_000,
            7_500_000,
            10_000_000,
        ],
    )

    args = parser.parse_args()

    run(
        path=args.path,
        column_counts=args.column_counts,
        row_counts=args.row_counts
    )
