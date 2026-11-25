"""Library for generating prelim test data."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
import csv
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from functools import cached_property
import json
from multiprocessing.pool import Pool
from pathlib import Path
from typing import Any, Literal, NamedTuple
import uuid

# Constants for estimating CSV file sizes

UUID_LENGTH = len(str(uuid.uuid4()))
TIMESTAMP_LENGTH = len(datetime.now().isoformat())


def write_file(filename: str | Path, content: str) -> None:
    """Write content to a file."""
    with open(filename, 'w') as f:
        f.write(content)


def write_csv(
    filename: str | Path,
    columns: Iterable[str],
    data: Iterator[tuple[str, ...]],
) -> None:
    """Write data to a CSV file."""
    with open(filename, 'w', newline='', buffering=1024*1024) as f:
        writer = csv.writer(f, doublequote=False, escapechar='\\')
        writer.writerow(columns)
        writer.writerows(data)


class Column(NamedTuple):
    """Represents a column in a table."""
    name: str
    type: str


@dataclass(frozen=True, kw_only=True)
class Config(ABC):
    """Base configuration for generating test data."""

    basedir: Path
    """Parent directory for storing all generated CSV and CQL files."""

    pk_type: Literal['text', 'uuid'] = field(default='uuid')
    """CQL type of the partition key column."""

    max_rows_per_file: int = field(default=1_000_000)
    """Maximum number of rows per CSV file."""

    max_file_size: int = field(default=0)
    """Maximum size of a CSV file in bytes. 0 means no limit."""

    @abstractmethod
    @cached_property
    def name(self) -> str:
        """Name of the configuration, used for naming files and tables."""
        pass

    @cached_property
    def path(self) -> Path:
        """Path to the directory for this configuration."""
        return self.basedir / self.name

    @abstractmethod
    @cached_property
    def columns(self) -> Iterable[Column]:
        """Columns of the table."""
        pass

    @abstractmethod
    @cached_property
    def primary_key(self) -> Iterable[str]:
        """Primary key columns of the table."""
        pass

    def generate_partition_key(self, idx: int) -> str:
        """Generate a partition key value based on the partition index and partition key type."""
        if self.pk_type == 'text':
            return f'partition_{idx}'
        elif self.pk_type == 'uuid':
            return str(uuid.uuid4())
        else:
            raise ValueError(f'Invalid pk_type: {self.pk_type}')


@dataclass(frozen=True)
class ChunkTask [C: Config] (ABC):
    """Task configuration for generating a chunk of data as a CSV file."""

    config: C
    """Configuration for the task."""

    chunk_idx: int
    """Index of the chunk."""

    @cached_property
    def filename(self) -> Path:
        """Path to the CSV file for this chunk."""
        return self.config.path / f'{self.chunk_idx:03d}.csv'


class Runner [C: Config, T: ChunkTask[C]] (ABC):
    """Base class for running data generation tasks."""

    _configs: list[C]
    """List of configurations for which tasks have been initialized."""

    tasks: dict[C, list[T]]
    """Mapping from configuration to list of tasks for that configuration."""

    @property
    def all_tasks(self) -> list[T]:
        """List of all tasks across all configurations."""
        return [task for tasks in self.tasks.values() for task in tasks]

    @classmethod
    @abstractmethod
    def prefix(cls) -> str:
        """Prefix for naming files and tables."""
        pass

    @classmethod
    def basedir(cls, path: str | Path) -> Path:
        """Get the parent directory for storing all generated CSV and CQL files."""
        return Path(path) / cls.prefix()

    @classmethod
    def tablename(cls, conf: C) -> str:
        """Get the table name for a given configuration."""
        return f'{cls.prefix()}_{conf.name}'

    def __init__(self) -> None:
        self._configs = []
        self.tasks = {}

    @classmethod
    def _drop_table_cql(cls, conf: C) -> str:
        """Generate CQL statement to drop the table for a given configuration."""
        tblname = cls.tablename(conf)
        return f'DROP TABLE IF EXISTS {tblname};'

    @classmethod
    def _create_table_cql(cls, conf: C) -> str:
        """Generate CQL statement to create the table for a given configuration."""
        tblname = cls.tablename(conf)
        columns = conf.columns
        primary_key = ', '.join(col for col in conf.primary_key)

        return (
            f'CREATE TABLE {tblname} (\n'
            + ',\n'.join(f'  {col.name} {col.type}' for col in columns) + ',\n'
            f'  PRIMARY KEY ({primary_key})\n'
            ');'
        )

    @classmethod
    @abstractmethod
    def _generate_ddl(cls, conf: C) -> tuple[str, str]:
        """Generate CQL statements for creating and dropping the table for a given configuration."""
        pass

    @classmethod
    @abstractmethod
    def _create_tasks(cls, conf: C) -> Iterable[T]:
        """Create tasks for generating data for a given configuration."""
        pass

    @classmethod
    @abstractmethod
    def _generate_data(cls, task: T) -> Iterator[tuple[str, ...]]:
        """Generate data for a given task."""
        pass

    @classmethod
    def _write_chunk(cls, task: T) -> T:
        """For a given task, generate data and write it to a CSV file."""
        write_csv(
            filename=task.filename,
            columns=[col.name for col in task.config.columns],
            data=cls._generate_data(task)
        )

        return task

    def init_config(self, conf: C) -> None:
        """Initialize a configuration by creating necessary directories and generating DDL files."""
        Path(conf.path).mkdir(parents=True, exist_ok=True)

        init, cleanup = self._generate_ddl(conf)
        write_file(conf.path / 'init.cql', init)
        write_file(conf.path / 'cleanup.cql', cleanup)
        write_file(conf.path / 'tblname.txt', self.tablename(conf))

        self.tasks[conf] = list(self._create_tasks(conf))
        self._configs.append(conf)

    def run_tasks(
        self,
        workers: int | None = None
    ) -> Iterator[T]:
        """Run all tasks across all configurations, optionally using multiple workers."""
        with Pool(processes=workers) as pool:
            yield from pool.imap_unordered(self._write_chunk, self.all_tasks)


class CollectionValue(ABC):
    """Base class for values in a collection column."""

    @abstractmethod
    def generate_value(self) -> Any:
        """Generate a value for the collection."""
        pass

    @property
    @abstractmethod
    def vtype(self) -> str:
        """CQL type of the value in the collection."""
        pass

    @abstractmethod
    def create_cql(self) -> str:
        """Generate CQL statement to create the type for the value in the collection."""
        pass

    @abstractmethod
    def drop_cql(self) -> str:
        """Generate CQL statement to drop the type for the value in the collection."""
        pass


@dataclass(frozen=True)
class Udt(CollectionValue):
    """User-defined type (UDT) for values in a collection column."""

    num_fields: int
    """Number of fields in the UDT."""

    @cached_property
    def name(self) -> str:
        """Get the name of the UDT."""
        return f'udt_{self.num_fields}f'

    @cached_property
    def fields(self) -> tuple[Column, ...]:
        """Get the fields of the UDT."""
        return tuple(
            Column(name=f'field_{j+1}', type='text')
            for j in range(self.num_fields)
        )

    @cached_property
    def vtype(self) -> str:
        return f'frozen<{self.name}>'

    def generate_value(self) -> dict[str, str]:
        return {
            f'field_{j+1}': f'value_{j+1:02d}'
            for j in range(self.num_fields)
        }

    def create_cql(self) -> str:
        return (
            f'CREATE TYPE {self.name} (\n'
            + ',\n'.join(f'  {field.name} {field.type}' for field in self.fields) + '\n'
            ');'
        )

    def drop_cql(self) -> str:
        return f'DROP TYPE IF EXISTS {self.name};'


class LiteralValue(CollectionValue):
    """UUID value for a collection column."""

    vtype: str = 'uuid'

    def generate_value(self) -> Any:
        return str(uuid.uuid4())

    def create_cql(self) -> str:
        return ''

    def drop_cql(self) -> str:
        return ''


class CollectionType(StrEnum):
    """CQL collection types."""
    SET = 'set'
    LIST = 'list'
    MAP = 'map'


@dataclass(frozen=True)
class Collection:
    """Collection column configuration for a table."""

    type: CollectionType
    """CQL collection type."""

    num_fields: int
    """Number of UDT fields in the values (0 = use simple value)."""

    num_values: int
    """Number of values in the collection."""

    num_columns: int
    """Number of collection columns in the table."""

    @cached_property
    def value(self) -> CollectionValue:
        """Get the value generator for the collection."""
        return Udt(self.num_fields) if self.num_fields > 0 else LiteralValue()

    @cached_property
    def column_type(self) -> str:
        """CQL type of the collection column."""
        if self.type == CollectionType.MAP:
            return f'map<uuid, {self.value.vtype}>'
        else:
            return f'{self.type.value}<{self.value.vtype}>'

    @cached_property
    def columns(self) -> tuple[Column, ...]:
        """List of collection columns for the table."""
        return tuple(
            Column(name=f'column_agg_{j + 1}', type=self.column_type)
            for j in range(self.num_columns)
        )

    def generate_value(self) -> str:
        """Generate value for one collection column."""
        if self.type == CollectionType.MAP:
            return json.dumps({
                str(uuid.uuid4()): self.value.generate_value()
                for _ in range(self.num_values)
            }, separators=(',', ':'))
        else:
            return json.dumps([
                self.value.generate_value()
                for _ in range(self.num_values)
            ], separators=(',', ':'))

    def generate_values(self) -> tuple[str, ...]:
        """Generate values for all collection columns."""
        return tuple(
            self.generate_value()
            for _ in range(self.num_columns)
        )