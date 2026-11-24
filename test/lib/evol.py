from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
import csv
from pydantic import BaseModel, Field, field_validator
from pydantic.dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, NamedTuple, TypeVar

from test.lib.cost import EvolCostConfig, ReadConfig
from test.lib.res import EvolResultConfig, evol_result_config
from test.lib.utils import RunFilter


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int | None = None

    def __str__(self):
        return f'seed={self.seed:#X},' + ','.join(
            f'{field.name}={getattr(self, field.name)}'
            for field in self.__dataclass_fields__.values()
            if field.name != 'seed'
        )


GeneratorConfigType = TypeVar('GeneratorConfigType', bound=GeneratorConfig, contravariant=True)
GeneratorFactory = Callable[[GeneratorConfigType], Iterator[tuple[str, ...]]]


@dataclass(frozen=True)
class Column:
    name: str
    type: str


class TableKeys(NamedTuple):
    partition: tuple[str, ...]
    clustering: tuple[tuple[str, Literal['asc'] | Literal['desc']], ...]


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    keys: TableKeys
    type: Literal['create', 'alter']

    factory: GeneratorFactory

    def data_columns(self) -> list[str]:
        if self.type == 'alter':
            return [
                col for col in self.keys.partition
            ] + [
                col for col, _ in self.keys.clustering
            ] + [
                col.name for col in self.columns
            ]

        return [col.name for col in self.columns]

    def create_cql(self) -> str:
        columns = ',\n'.join(
            f'    {col.name} {col.type}'
            for col in self.columns
        )

        if self.type == 'alter':
            return (
                f'ALTER TABLE {self.name} ADD (\n'
                f'{columns}\n'
                ');'
            )
        else:
            pk = ', '.join(self.keys.partition)
            ck = ', '.join(
                name for name, _ in self.keys.clustering
            )

            key = (
                f'PRIMARY KEY ({pk})'
                if not ck
                else f'PRIMARY KEY (({pk}), {ck})'
            )

            if ck:
                clustering = (
                    ' WITH CLUSTERING ORDER BY (\n' +
                    ',\n'.join(
                        f'    {name} {order.upper()}'
                        for name, order in self.keys.clustering
                    ) +
                    '\n)'
                )
            else:
                clustering = ''

            return (
                f'CREATE TABLE {self.name} (\n'
                f'{columns},\n'
                f'\n'
                f'    {key}\n'
                f'){clustering};'
            )
    
    def drop_cql(self) -> str:
        if self.type == 'alter':
            columns = ',\n'.join(
                f'    {col.name}'
                for col in self.columns
            )

            return (
                f'ALTER TABLE {self.name} DROP (\n'
                f'{columns}\n'
                ');'
            )

        return f'DROP TABLE IF EXISTS {self.name};'


@dataclass(frozen=True)
class Udt:
    name: str
    fields: tuple[Column, ...]

    def create_cql(self) -> str:
        fields = ',\n'.join(
            f'    {field.name} {field.type}'
            for field in self.fields
        )

        return (
            f'CREATE TYPE {self.name} (\n'
            f'{fields}\n'
            ');'
        )
    
    def drop_cql(self) -> str:
        return f'DROP TYPE IF EXISTS {self.name};'


@dataclass(frozen=True)
class Group:
    tables: tuple[Table, ...]
    udts: tuple[Udt, ...] = ()
    name: str = 'init'


@dataclass(frozen=True)
class Task[C: GeneratorConfig]:
    path: Path
    subcase: str
    group: Group
    table: Table
    config: C

    def name(self) -> str:
        return f'{self.subcase}.{self.group.name}.{self.table.name}'


def _write_table(
    path: Path,
    table: Table,
    config: GeneratorConfigType
) -> None:
    with open(path, 'w', newline='', buffering=1024*1024) as f:
        writer = csv.writer(f)
        writer.writerow(table.data_columns())
        writer.writerows(table.factory(config))


def _write_file(path: Path, content: str) -> None:
    with open(path, 'w') as f:
        f.write(content)


class TestCaseConfig(BaseModel):
    subcases: dict[str, Any]
    seed: int | None = None

    cost: EvolCostConfig | None = None
    results: EvolResultConfig | None = None

    read: ReadConfig | None = None

    @field_validator('read', mode='before')
    @classmethod
    def validate_read(cls, v: Any) -> ReadConfig | None:
        if v is None:
            return None
        return ReadConfig.from_config(v)

    @field_validator('results', mode='before')
    @classmethod
    def validate_results(cls, v: Any) -> EvolResultConfig | None:
        if v is None:
            return None
        return evol_result_config(v)


class TestCaseDataGenerator[C: GeneratorConfig]:
    def __init__(self, conf_class: type[C]) -> None:
        self.conf_class = conf_class
        self._groups: list[Group] = []

    def build_subconfig(self, config_dict: dict[str, Any]) -> C:
        return self.conf_class(**config_dict)
    
    def register_group(self, group: Group) -> None:
        self._groups.append(group)

    def register_groups(self, groups: Iterable[Group]) -> None:
        self._groups.extend(groups)

    @property
    def groups(self) -> list[Group]:
        return self._groups

    @classmethod
    def _startup_cql(cls, group: Group) -> str:
        udts_create = '\n\n'.join(
            udt.create_cql()
            for udt in group.udts
        )

        tables_create = '\n\n'.join(
            table.create_cql()
            for table in group.tables
        )

        udts_drop = '\n'.join(
            udt.drop_cql()
            for udt in reversed(group.udts)
        )

        tables_drop = '\n'.join(
            table.drop_cql()
            for table in reversed(group.tables)
            if table.type == 'create'
        )

        return (
            (f'{tables_drop}\n\n' if tables_drop else '') +
            (f'{udts_drop}\n\n' if udts_drop else '') +
            '\n' +
            (f'{udts_create}\n\n' if udts_create else '') +
            f'{tables_create}\n'
        )

    @classmethod
    def _cleanup_cql(cls, group: Group) -> str:
        udts_drop = '\n'.join(
            udt.drop_cql()
            for udt in reversed(group.udts)
        )

        tables_drop = '\n'.join(
            table.drop_cql()
            for table in reversed(group.tables)
        )

        return (
            (f'{tables_drop}\n\n' if tables_drop else '') +
            (f'{udts_drop}\n' if udts_drop else '')
        )

    def prepare(
        self,
        base_dir: Path,
        subcase: str,
        config: C,
        tags: RunFilter | None = None
    ) -> tuple[list[Task[C]], dict[str, list[Path]]]:
        tasks = []
        files: dict[str, list[Path]] = defaultdict(list)

        for group in self._groups:
            if tags and not tags.should_run(group.name):
                continue

            tables = [
                table for table in group.tables
                if not (tags and not tags.should_run(table.name))
            ]

            if not tables:
                continue

            gdir = Path(base_dir) / group.name
            gdir.mkdir(parents=True, exist_ok=True)

            files[group.name] = [
                gdir / f'startup.cql',
                gdir / f'cleanup.cql',
            ]

            _write_file(
                gdir / f'startup.cql',
                self._startup_cql(group)
            )

            _write_file(
                gdir / f'cleanup.cql',
                self._cleanup_cql(group)
            )

            for table in tables:
                tbldir = gdir / table.name
                tbldir.mkdir(exist_ok=True)

                _write_file(
                    tbldir / 'tblname.txt',
                    table.name
                )

                tasks.append(Task(
                    path=tbldir / 'data.csv',
                    group=group,
                    table=table,
                    config=config,
                    subcase=subcase
                ))

                files[group.name].append(tbldir / 'tblname.txt')

        return tasks, files

    def run_tasks(
        self,
        tasks: Iterable[Task[C]],
        max_workers: int | None = None
    ) -> Iterator[tuple[int, Future[None], Task[C]]]:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_write_table, task.path, task.table, task.config): task
                for task in tasks
            }

            yield from (
                (i, fut, futures[fut])
                for i, fut in enumerate(as_completed(futures))
            )

