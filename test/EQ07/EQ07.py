from dataclasses import field
from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from test.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from test.lib import faker
from test.lib import utils
from test.lib import run


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF

    users: int = 100_000
    posts: int = 1000
    root_comments_per_post: int = 10
    replies_per_comment: int = 5
    reply_levels: int = 3

    comments_per_post: int = field(init=False)
    total_comments: int = field(init=False)

    def __post_init__(self):
        R = self.replies_per_comment
        L = self.reply_levels

        replies_per_root = (R * (R**L - 1) // (R - 1)) if R > 1 else L
        comments_per_post = (
            self.root_comments_per_post * (replies_per_root + 1)
        )
        object.__setattr__(self, 'comments_per_post', comments_per_post)

        total_comments = self.posts * self.comments_per_post
        object.__setattr__(self, 'total_comments', total_comments)

