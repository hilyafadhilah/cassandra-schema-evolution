from dataclasses import field
from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from eval.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from eval.lib import faker
from eval.lib import utils
from eval.lib import run


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF

    users: int = 100_000
    interactions_per_user: int = 10
