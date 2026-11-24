from dataclasses import field
from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from eval.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from eval.lib import faker
from eval.lib import utils


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF

    posts: int = 100_000
    tags_per_post: int = 5
    embeds_per_post: int = 3

    entries_per_post: int = 10
