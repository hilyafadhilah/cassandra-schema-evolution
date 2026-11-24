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
    membership = faker.Membership(seed=config.seed)

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    membership_id = faker.uuids(f'{config.seed}_membership')

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                user['id'],
                m['joined_at'].isoformat(),
                membership_id(),
                m['role'],
                community['id'],
                community['name'],
                community['icon'],
                community['description'],
            )


def gen_cf10(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    membership = faker.Membership(seed=config.seed)

    membership_id = faker.uuids(f'{config.seed}_membership')

    for community in communities:
        for user in users:
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                community['id'],
                m['role'],
                m['joined_at'].isoformat(),
                membership_id(),
                user['id'],
                user['handle'],
                user['icon'],
            )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='joined_at', type='timestamp'),
                Column(name='membership_id', type='uuid'),
                Column(name='role', type='int'),
                Column(name='community_id', type='uuid'),
                Column(name='community_name', type='text'),
                Column(name='community_icon', type='text'),
                Column(name='community_description', type='text'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(
                    ('joined_at', 'desc'),
                    ('membership_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf1
        ),
        Table(
            name='cf10',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='member_role', type='int'),
                Column(name='joined_at', type='timestamp'),
                Column(name='membership_id', type='uuid'),
                Column(name='member_id', type='uuid'),
                Column(name='member_handle', type='text'),
                Column(name='member_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('member_role', 'asc'),
                    ('joined_at', 'asc'),
                    ('membership_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf10
        ),
    ),
)


def gen_cf2(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    membership = faker.Membership(seed=config.seed)

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    membership_id = faker.uuids(f'{config.seed}_membership')

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                user['id'],
                m['joined_at'].isoformat(),
                membership_id(),
                m['role'],
                community['id'],
            )


def gen_cf11(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    membership = faker.Membership(seed=config.seed)

    membership_id = faker.uuids(f'{config.seed}_membership')

    for community in communities:
        for user in users:
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                community['id'],
                m['role'],
                m['joined_at'].isoformat(),
                membership_id(),
                user['id'],
            )


qmin = Group(
    name='qmin',
    tables=(
        Table(
            name='cf2',
            columns=(
                Column(name='user_id', type='uuid'),
                Column(name='joined_at', type='timestamp'),
                Column(name='membership_id', type='uuid'),
                Column(name='role', type='int'),
                Column(name='community_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(
                    ('joined_at', 'desc'),
                    ('membership_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf2
        ),
        Table(
            name='cf11',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='member_role', type='int'),
                Column(name='joined_at', type='timestamp'),
                Column(name='membership_id', type='uuid'),
                Column(name='member_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('member_role', 'asc'),
                    ('joined_at', 'asc'),
                    ('membership_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf11
        ),
    ),
)


def gen_cf8(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    membership_id = faker.uuids(f'{config.seed}_membership')

    for user in users:
        yield (
            user['id'],
            utils.serialize([
                membership_id() for _ in range(config.memberships_per_user)
            ]),
        )


def gen_cf21(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    membership_id = faker.uuids(f'{config.seed}_membership')

    for community in communities:
        for _ in range(config.members_per_community):
            yield (
                community['id'],
                membership_id(),
            )


def gen_memberships(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    membership = faker.Membership(seed=config.seed)

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    membership_id = faker.uuids(f'{config.seed}_membership')

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
            )

            yield (
                membership_id(),
                m['joined_at'].isoformat(),
                m['role'],
                user['id'],
                community['id'],
            )


alt = Group(
    name='alt',
    tables=(
        Table(
            name='users',
            columns=(
                Column(name='memberships_set', type='set<uuid>'),
            ),
            keys=TableKeys(partition=('user_id',), clustering=()),
            type='alter',
            factory=gen_cf8
        ),
        Table(
            name='cf21',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='membership_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('membership_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf21
        ),
        Table(
            name='memberships',
            columns=(
                Column(name='membership_id', type='uuid'),
                Column(name='joined_at', type='timestamp'),
                Column(name='role', type='int'),
                Column(name='member_id', type='uuid'),
                Column(name='community_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=()
            ),
            type='create',
            factory=gen_memberships
        ),
    ),
)


tcg = TestCaseDataGenerator(Config)
tcg.register_groups((init, qbal, qmin, alt))


if __name__ == '__main__':
    run.main(
        tcg,
        default_conf_file=Path(__file__).parent / 'in.yml',
        default_outdir=Path(__file__).parent / 'out' / 'data',
    )
