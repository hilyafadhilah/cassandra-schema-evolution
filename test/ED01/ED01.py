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
    for user in users:
        yield (
            user['id'],
            user['badge']['id'],
            user['handle'],
            user['email'],
            user['icon'],
            user['bio'],
            user['region'],
            utils.serialize(user['languages']),
            user['badge']['contents']
        )

codevo = Group(
    name='codevo',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='badge_id', type='uuid'),
                Column(name='handle', type='text'),
                Column(name='email', type='ascii'),
                Column(name='icon', type='text'),
                Column(name='bio', type='ascii'),
                Column(name='region', type='ascii'),
                Column(name='languages', type='set<ascii>'),
                Column(name='badge_contents', type='text')
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(('badge_id', 'asc'),)
            ),
            type='create',
            factory=gen_cf1
        ),
    ),
)


tcg = TestCaseDataGenerator(Config)
tcg.register_groups((init, codevo))


if __name__ == '__main__':
    run.main(
        tcg,
        default_conf_file=Path(__file__).parent / 'in.yml',
        default_outdir=Path(__file__).parent / 'out' / 'data',
    )
