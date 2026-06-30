from dataclasses import field
from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from test.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from test.lib import faker, run
from test.lib import utils


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF

    tags_per_post: int = 5
    embeds_per_post: int = 3

    users: int = 100_000
    posts_per_user: int = 10

    communities: int = 100
    posts_per_community: int = 1000

    tags: int = 100

    followers_per_user: int = 10
    memberships_per_user: int = 10

    posts: int = field(init=False)
    posts_per_tag: int = field(init=False)

    def __post_init__(self):
        posts = self.users * self.posts_per_user
        posts_per_tag = posts * self.tags_per_post // self.tags
        object.__setattr__(self, 'posts', posts)
        object.__setattr__(self, 'posts_per_tag', posts_per_tag)
