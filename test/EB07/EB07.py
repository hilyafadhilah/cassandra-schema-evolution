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
    users: int = 100_000
    bookmarks_per_user: int = 10

    total_bookmarks: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'total_bookmarks', self.users * self.bookmarks_per_user)


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

def gen_bookmarks(config: Config) -> Iterator[tuple[str, ...]]:
    bookmarks = faker.bookmarks(config.total_bookmarks, seed=config.seed)
    for bookmark in bookmarks:
        yield (
            bookmark['id'],
            bookmark['name'],
            bookmark['cover'],
            bookmark['updated_at'].isoformat(),
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
        Table(
            name='bookmarks',
            columns=(
                Column(name='bookmark_id', type='uuid'),
                Column(name='name', type='text'),
                Column(name='cover', type='ascii'),
                Column(name='updated_at', type='timestamp'),
            ),
            keys=TableKeys(partition=('bookmark_id',), clustering=()),
            type='create',
            factory=gen_bookmarks
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
        Udt(
            name='bookmark',
            fields=(
                Column(name='updated_at', type='timestamp'),
                Column(name='name', type='text'),
                Column(name='cover', type='ascii'),
            )
        ),
    )
)


def gen_cf1(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    bookmarks = faker.bookmarks(config.bookmarks_per_user, seed=config.seed)

    for user in users:
        for bookmark in bookmarks:
            yield (
                user['id'],
                bookmark['updated_at'].isoformat(),
                bookmark['id'],
                bookmark['name'],
                bookmark['cover'],
            )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='updated_at', type='timestamp'),
                Column(name='bookmark_id', type='uuid'),
                Column(name='name', type='text'),
                Column(name='cover', type='ascii'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(('updated_at', 'desc'),)
            ),
            type='create',
            factory=gen_cf1
        ),
    ),
)


def gen_cf3(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    bookmarks = faker.bookmarks(config.bookmarks_per_user, seed=config.seed)

    for user in users:
        yield (
            user['id'],
            utils.serialize({
                bookmark['id']: {
                    'updated_at': bookmark['updated_at'].isoformat(),
                    'name': bookmark['name'],
                    'cover': bookmark['cover'],
                } for bookmark in bookmarks
            })
        )


qmin_map = Group(
    name='qmin_map',
    tables=(
        Table(
            name='users',
            columns=(
                Column(name='bookmarks_map', type='map<uuid, frozen<bookmark>>'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf3
        ),
    )
)


def gen_cf4(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    bookmarks = faker.bookmarks(config.bookmarks_per_user, seed=config.seed)

    for user in users:
        yield (
            user['id'],
            utils.serialize([
                bookmark['id'] for bookmark in bookmarks
            ])
        )


qmin_set = Group(
    name='qmin_set',
    tables=(
        Table(
            name='users',
            columns=(
                Column(name='bookmarks_set', type='set<uuid>'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf4
        ),
    )
)


def gen_cf2(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    bookmarks = faker.bookmarks(config.bookmarks_per_user, seed=config.seed)

    for user in users:
        for bookmark in bookmarks:
            yield (
                user['id'],
                bookmark['id'],
                bookmark['name'],
                bookmark['cover'],
                bookmark['updated_at'].isoformat(),
            )


codevo = Group(
    name='codevo',
    tables=(
        Table(
            name='cf2',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='bookmark_id', type='uuid'),
                Column(name='name', type='text'),
                Column(name='cover', type='ascii'),
                Column(name='updated_at', type='timestamp'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(('bookmark_id', 'asc'),)
            ),
            type='create',
            factory=gen_cf2
        ),
    ),
)


tcg = TestCaseDataGenerator(Config)
tcg.register_groups((init, qbal, qmin_map, qmin_set, codevo))


if __name__ == '__main__':
    run.main(
        tcg,
        default_conf_file=Path(__file__).parent / 'in.yml',
        default_outdir=Path(__file__).parent / 'out' / 'data',
    )
