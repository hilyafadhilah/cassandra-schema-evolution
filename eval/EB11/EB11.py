from dataclasses import field
from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from eval.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from eval.lib import faker, run
from eval.lib import utils


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF

    users: int = 5_000

    posts: int = 100_000
    comments_per_post: int = 5
    likes_per_comment: int = 5

    comments: int = field(init=False)
    likes: int = field(init=False)

    def __post_init__(self):
        comments = (
            self.posts * self.comments_per_post
        )
        object.__setattr__(self, 'comments', comments)

        likes = (
            self.comments * self.likes_per_comment
        )
        object.__setattr__(self, 'likes', likes)


def gen_likes(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed).create()
    for like in faker.likes(
        users=users,
        num_posts=config.posts,
        num_post_comments=config.comments_per_post,
        num_comment_likes=config.likes_per_comment,
        seed=config.seed
    ):
        yield (
            like['post_id'],
            like['comment_id'],
            like['user']['id'],
            like['user']['handle'],
            like['user']['icon']
        )


init = Group(
    tables=(
        Table(
            name='likes',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='comment_id', type='uuid'),
                Column(name='user_id', type='uuid'),
                Column(name='user_handle', type='text'),
                Column(name='user_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('post_id', 'comment_id'),
                clustering=(
                    ('user_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_likes
        ),
    ),
)


def gen_cf1(config: Config) -> Iterator[tuple[str, ...]]:
    like_id = faker.uuids(f'{config.seed}_likes')

    users = faker.users(config.users, seed=config.seed).create()
    for like in faker.likes(
        users=users,
        num_posts=config.posts,
        num_post_comments=config.comments_per_post,
        num_comment_likes=config.likes_per_comment,
        seed=config.seed
    ):
        yield (
            like['post_id'],
            like['comment_id'],
            like_id(),
            like['user']['id'],
            like['user']['handle'],
            like['user']['icon']
        )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='comment_id', type='uuid'),
                Column(name='like_id', type='uuid'),
                Column(name='user_id', type='uuid'),
                Column(name='user_handle', type='text'),
                Column(name='user_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('post_id', 'comment_id'),
                clustering=(
                    ('like_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf1
        ),
    ),
)


def gen_cf2(config: Config) -> Iterator[tuple[str, ...]]:
    like_id = faker.uuids(f'{config.seed}_likes')

    users = faker.users(config.users, seed=config.seed).create()
    for like in faker.likes(
        users=users,
        num_posts=config.posts,
        num_post_comments=config.comments_per_post,
        num_comment_likes=config.likes_per_comment,
        seed=config.seed
    ):
        yield (
            like['post_id'],
            like['comment_id'],
            like_id(),
            like['user']['id'],
        )


qmin = Group(
    name='qmin',
    tables=(
        Table(
            name='cf2',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='comment_id', type='uuid'),
                Column(name='like_id', type='uuid'),
                Column(name='user_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('post_id', 'comment_id'),
                clustering=(
                    ('like_id', 'asc'), 
                )
            ),
            type='create',
            factory=gen_cf2
        ),
    ),
)


def gen_cf4(config: Config) -> Iterator[tuple[str, ...]]:
    like_id = faker.uuids(f'{config.seed}_likes')

    for _ in range(config.likes):
        yield (
            like_id(),
        )


def gen_cf5(config: Config) -> Iterator[tuple[str, ...]]:
    like_id = faker.uuids(f'{config.seed}_likes')

    users = faker.users(config.users, seed=config.seed).create()
    for like in faker.likes(
        users=users,
        num_posts=config.posts,
        num_post_comments=config.comments_per_post,
        num_comment_likes=config.likes_per_comment,
        seed=config.seed
    ):
        yield (
            like['post_id'],
            like['comment_id'],
            like_id(),
        )


def gen_cf6(config: Config) -> Iterator[tuple[str, ...]]:
    like_id = faker.uuids(f'{config.seed}_likes')

    users = faker.users(config.users, seed=config.seed).create()
    for like in faker.likes(
        users=users,
        num_posts=config.posts,
        num_post_comments=config.comments_per_post,
        num_comment_likes=config.likes_per_comment,
        seed=config.seed
    ):
        yield (
            like_id(),
            like['user']['id'],
            like['user']['handle'],
            like['user']['icon'],
        )


codevo = Group(
    name='codevo',
    tables=(
        Table(
            name='cf4',
            columns=(
                Column(name='like_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('like_id',),
                clustering=()
            ),
            type='create',
            factory=gen_cf4
        ),
        Table(
            name='cf5',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='comment_id', type='uuid'),
                Column(name='like_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('post_id', 'comment_id'),
                clustering=(
                    ('like_id', 'asc'), 
                )
            ),
            type='create',
            factory=gen_cf5
        ),
        Table(
            name='cf6',
            columns=(
                Column(name='like_id', type='uuid'),
                Column(name='user_id', type='uuid'),
                Column(name='user_handle', type='text'),
                Column(name='user_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('like_id',),
                clustering=(
                    ('user_id', 'asc'), 
                )
            ),
            type='create',
            factory=gen_cf6
        ),
    ),
)


tcg = TestCaseDataGenerator(Config)
tcg.register_groups((init, qbal, qmin, codevo))


if __name__ == '__main__':
    run.main(
        tcg,
        default_conf_file=Path(__file__).parent / 'in.yml',
        default_outdir=Path(__file__).parent / 'out' / 'data',
    )
