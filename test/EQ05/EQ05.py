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


def gen_comments(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.user_infos(config.users, seed=config.seed).create()
    comments = faker.comments(
        users=users,
        posts=config.posts,
        root_comments_per_post=config.root_comments_per_post,
        replies_per_comment=config.replies_per_comment,
        reply_levels=config.reply_levels,
        seed=config.seed
    )

    for comment in comments:
        yield (
            comment['post_id'],
            comment['parent_comment_id'],
            comment['commented_at'],
            comment['comment_id'],
            comment['contents'],
            comment['language'],
            comment['likes'],
            comment['user']['id'],
            comment['user']['handle'],
            comment['user']['icon'],
        )


init = Group(
    tables=(
        Table(
            name='comments',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='parent_comment_id', type='uuid'),
                Column(name='commented_at', type='timestamp'),
                Column(name='comment_id', type='uuid'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='likes', type='int'),
                Column(name='commenter_id', type='uuid'),
                Column(name='commenter_handle', type='text'),
                Column(name='commenter_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=(
                    ('parent_comment_id', 'asc'),
                    ('commented_at', 'asc'),
                    ('comment_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_comments,
        ),
    ),
)


def gen_rplus(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.user_infos(config.users, seed=config.seed).create()
    comments = faker.comments(
        users=users,
        posts=config.posts,
        root_comments_per_post=config.root_comments_per_post,
        replies_per_comment=config.replies_per_comment,
        reply_levels=config.reply_levels,
        seed=config.seed
    )

    rand = faker.Random(f'{config.seed}_comments')

    for comment in comments:
        yield (
            comment['post_id'],
            comment['parent_comment_id'],
            comment['commented_at'],
            comment['comment_id'],
            str(rand.randint(-100, 100)),  # commenter_rank
        )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='comments',
            columns=(
                Column(name='commenter_rank', type='int'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=(
                    ('parent_comment_id', 'asc'),
                    ('commented_at', 'asc'),
                    ('comment_id', 'asc'),
                )
            ),
            type='alter',
            factory=gen_rplus,
        ),
    ),
)


tcg = TestCaseDataGenerator(Config)
tcg.register_groups((init, qbal))


if __name__ == '__main__':
    run.main(
        tcg,
        default_conf_file=Path(__file__).parent / 'in.yml',
        default_outdir=Path(__file__).parent / 'out' / 'data',
    )