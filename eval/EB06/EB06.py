from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from eval.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from eval.lib import faker, run
from eval.lib import utils


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF
    users: int = 100_000
    tags_per_post: int = 5


def gen_users(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    for user in users:
        yield (
            user['id'],
            user['handle'],
            user['email'],
            user['icon'],
            user['bio'],
            user['region'],
            utils.serialize(user['languages']),
            utils.serialize(user['badge'])
        )

init = Group(
    tables=(
        Table(
            name='users',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='handle', type='text'),
                Column(name='email', type='ascii'),
                Column(name='icon', type='text'),
                Column(name='bio', type='ascii'),
                Column(name='region', type='ascii'),
                Column(name='languages', type='set<ascii>'),
                Column(name='badge', type='badge')
            ),
            keys=TableKeys(partition=('user_id',), clustering=()),
            type='create',
            factory=gen_users
        ),
    ),
    udts=(
        Udt(
            name='badge',
            fields=(
                Column(name='id', type='uuid'),
                Column(name='contents', type='text')
            )
        ),
    )
)


def gen_cf1(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    posts = faker.posts(1, tags_per_post=config.tags_per_post, seed=config.seed)

    for user in users:
        for pin in posts:
            yield (
                user['id'],
                pin['id'],
                pin['title'],
                pin['contents'],
                pin['language'],
                pin['posted_at'].isoformat(),
                utils.serialize(pin['tags'])
            )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='users',
            columns=(
                Column(name='pin_id', type='uuid'),
                Column(name='pin_title', type='text'),
                Column(name='pin_contents', type='text'),
                Column(name='pin_language', type='text'),
                Column(name='pin_posted_at', type='timestamp'),
                Column(name='pin_tags', type='set<text>'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf1
        ),
    ),
)


def gen_cf2(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    posts = faker.posts(1, tags_per_post=config.tags_per_post, seed=config.seed)

    for user in users:
        for pin in posts:
            yield (
                user['id'],
                pin['id'],
            )


qmin = Group(
    name='qmin',
    tables=(
        Table(
            name='users',
            columns=(
                Column(name='pin_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf2
        ),
    ),
)


def gen_cf4(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    posts = faker.posts(1, tags_per_post=config.tags_per_post, seed=config.seed)

    for user in users:
        for pin in posts:
            yield (
                user['id'],
                pin['id'],
                user['handle'],
                user['email'],
                user['icon'],
                user['bio'],
                user['region'],
                utils.serialize(user['languages']),
                pin['title'],
                pin['contents'],
                pin['language'],
                pin['posted_at'].isoformat(),
            )


codevo = Group(
    name='codevo',
    tables=(
        Table(
            name='cf4',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='pin_id', type='uuid'),
                Column(name='handle', type='text'),
                Column(name='email', type='ascii'),
                Column(name='icon', type='text'),
                Column(name='bio', type='ascii'),
                Column(name='region', type='ascii'),
                Column(name='languages', type='set<ascii>'),
                Column(name='pin_title', type='text'),
                Column(name='pin_contents', type='text'),
                Column(name='pin_language', type='text'),
                Column(name='pin_posted_at', type='timestamp'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(('pin_id', 'asc'),)
            ),
            type='create',
            factory=gen_cf4
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
