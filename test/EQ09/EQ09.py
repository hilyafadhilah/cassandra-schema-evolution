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


def gen_mc(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    m = faker.Membership(seed=config.seed)

    for community in communities:
        for user in users:
            membership = m.create(
                member_id=user['id'],
                community_id=community['id']
            )

            yield (
                community['id'],
                membership['role'],
                membership['joined_at'].isoformat(),
                user['id'],
                user['handle'],
                user['icon'],
            )


init = Group(
    tables=(
        Table(
            name='community_members',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='member_role', type='int'),
                Column(name='joined_at', type='timestamp'),
                Column(name='member_id', type='uuid'),
                Column(name='member_handle', type='text'),
                Column(name='member_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('member_role', 'asc'),
                    ('joined_at', 'asc'),
                    ('member_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_mc
        ),
    ),
)


def gen_cf1(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    m = faker.Membership(seed=config.seed)

    for community in communities:
        for user in users:
            membership = m.create(
                member_id=user['id'],
                community_id=community['id']
            )

            yield (
                community['id'],
                membership['joined_at'].isoformat(),
                user['id'],
                user['handle'],
                user['icon'],
                membership['role'],
            )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='joined_at', type='timestamp'),
                Column(name='member_id', type='uuid'),
                Column(name='member_handle', type='text'),
                Column(name='member_icon', type='text'),
                Column(name='member_role', type='int'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('joined_at', 'asc'),
                    ('member_id', 'asc'),
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