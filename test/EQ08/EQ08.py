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

    communities: int = 100
    members_per_community: int = 1_000

    memberships_per_user: int = field(init=False)
    total_memberships: int = field(init=False)

    def __post_init__(self):
        memberships_per_user = (
            self.members_per_community * self.communities
        ) // self.users
        object.__setattr__(self, 'memberships_per_user', memberships_per_user)

        total_memberships = self.communities * self.members_per_community
        object.__setattr__(self, 'total_memberships', total_memberships)


def gen_mu(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    m = faker.Membership(seed=config.seed)

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            membership = m.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                user['id'],
                membership['joined_at'].isoformat(),
                community['id'],
                membership['role'],
                community['name'],
                community['icon'],
                community['description'],
            )


init = Group(
    tables=(
        Table(
            name='user_memberships',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='joined_at', type='timestamp'),
                Column(name='community_id', type='uuid'),
                Column(name='role', type='int'),
                Column(name='community_name', type='text'),
                Column(name='community_icon', type='text'),
                Column(name='community_description', type='text'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(
                    ('joined_at', 'desc'),
                    ('community_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_mu
        ),
    ),
)


def gen_cf1(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    m = faker.Membership(seed=config.seed)

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            membership = m.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                user['id'],
                membership['role'],
                membership['joined_at'].isoformat(),
                community['id'],
                community['name'],
                community['icon'],
                community['description'],
            )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='role', type='int'),
                Column(name='joined_at', type='timestamp'),
                Column(name='community_id', type='uuid'),
                Column(name='community_name', type='text'),
                Column(name='community_icon', type='text'),
                Column(name='community_description', type='text'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(
                    ('role', 'desc'),
                    ('joined_at', 'desc'),
                    ('community_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf1
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