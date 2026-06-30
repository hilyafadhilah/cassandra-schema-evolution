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

    roles_per_community: int = 5
    roles_per_member: int = 2

    memberships_per_user: int = field(init=False)
    total_roles_per_user: int = field(init=False)
    total_community_member_roles: int = field(init=False)

    total_memberships: int = field(init=False)

    def __post_init__(self):
        memberships_per_user = (
            self.members_per_community * self.communities
        ) // self.users
        object.__setattr__(self, 'memberships_per_user', memberships_per_user)

        total_roles_per_user = self.memberships_per_user * self.roles_per_member
        object.__setattr__(self, 'total_roles_per_user', total_roles_per_user)

        total_community_member_roles = (
            self.members_per_community * self.roles_per_community
        )
        object.__setattr__(self, 'total_community_member_roles', total_community_member_roles)

        total_memberships = self.members_per_community * self.communities
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


def gen_communities(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)

    for community in communities:
        yield (
            community['id'],
            community['name'],
            community['icon'],
            community['description'],
            utils.serialize({
                owner['id']: {
                    'handle': owner['handle'],
                    'icon': owner['icon'],
                } for owner in community['owners']
            }),
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
            name='communities',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='name', type='text'),
                Column(name='icon', type='text'),
                Column(name='description', type='text'),
                Column(name='owners', type='map<uuid, frozen<user_info>>'),
            ),
            keys=TableKeys(partition=('community_id',), clustering=()),
            type='create',
            factory=gen_communities
        )
    ),
    udts=(
        Udt(
            name='user_info',
            fields=(
                Column(name='handle', type='text'),
                Column(name='icon', type='text'),
            )
        ),
    ),
)


def gen_cf2(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    membership = faker.MemberRoles(faker.Membership(seed=config.seed))

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
                num_roles=config.roles_per_member,
            )

            yield (
                user['id'],
                m['joined_at'].isoformat(),
                community['id'],
                utils.serialize({
                    role['rank']: {
                        'name': role['name'],
                        'privileges': role['privileges'],
                    } for role in m['roles']
                }),
            )


def gen_cf7(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    membership = faker.MemberRoles(faker.Membership(seed=config.seed))

    for community in communities:
        for user in users:
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
                num_roles=config.roles_per_member,
            )

            yield (
                community['id'],
                m['roles'][0]['rank'],
                m['joined_at'].isoformat(),
                user['id'],
                utils.serialize({
                    role['rank']: {
                        'name': role['name'],
                    } for role in m['roles']
                }),
            )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='user_memberships',
            columns=(
                Column(name='roles_map', type='map<int, frozen<member_role_2>>'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(
                    ('joined_at', 'desc'),
                    ('community_id', 'asc'),
                )
            ),
            type='alter',
            factory=gen_cf2
        ),
        Table(
            name='community_members',
            columns=(
                Column(name='roles_map', type='map<int, frozen<member_role_1>>'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('member_role', 'asc'),
                    ('joined_at', 'asc'),
                    ('member_id', 'asc'),
                )
            ),
            type='alter',
            factory=gen_cf7
        ),
    ),
    udts=(
        Udt(
            name='member_role_1',
            fields=(
                Column(name='name', type='text'),
            )
        ),
        Udt(
            name='member_role_2',
            fields=(
                Column(name='name', type='text'),
                Column(name='privileges', type='set<text>'),
            )
        ),
    ),
)


def gen_cf3(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    membership = faker.MemberRoles(faker.Membership(seed=config.seed))

    communities = faker.communities(config.communities, seed=config.seed).create()
    rand = faker.Random(config.seed)

    for user in users:
        for community in rand.sample(communities, config.memberships_per_user):
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
                num_roles=config.roles_per_member,
            )

            yield (
                user['id'],
                m['joined_at'].isoformat(),
                community['id'],
                utils.serialize([
                    role['rank'] for role in m['roles']
                ]),
            )


def gen_cf8(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    membership = faker.MemberRoles(faker.Membership(seed=config.seed))

    for community in communities:
        for user in users:
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
                num_roles=config.roles_per_member,
            )

            yield (
                community['id'],
                m['roles'][0]['rank'],
                m['joined_at'].isoformat(),
                user['id'],
                utils.serialize([
                    role['rank'] for role in m['roles']
                ]),
            )


def gen_cf4(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    roles = faker.community_roles(config.roles_per_community, seed=config.seed)

    for community in communities:
        r = (
            list(faker.MemberRoles.MEMBER_ROLE_DEFINITIONS.values()) +
            roles.create()
        )

        for role in r:
            yield (
                community['id'],
                role['rank'],
                role['name'],
                utils.serialize(role['privileges']),
            )


qmin = Group(
    name='qmin',
    tables=(
        Table(
            name='user_memberships',
            columns=(
                Column(name='roles_set', type='set<int>'),
            ),
            keys=TableKeys(
                partition=('user_id',),
                clustering=(
                    ('joined_at', 'desc'),
                    ('community_id', 'asc'),
                )
            ),
            type='alter',
            factory=gen_cf3
        ),
        Table(
            name='community_members',
            columns=(
                Column(name='roles_set', type='set<int>'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('member_role', 'asc'),
                    ('joined_at', 'asc'),
                    ('member_id', 'asc'),
                )
            ),
            type='alter',
            factory=gen_cf8
        ),
        Table(
            name='cf4',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='role_rank', type='int'),
                Column(name='name', type='text'),
                Column(name='privileges', type='set<text>'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('role_rank', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf4
        ),
    ),
)


def gen_cf5(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    roles = faker.community_roles(config.roles_per_community, seed=config.seed)

    for community in communities:
        r = (
            list(faker.MemberRoles.MEMBER_ROLE_DEFINITIONS.values()) +
            roles.create()
        )

        yield (
            community['id'],
            utils.serialize({
                role['rank']: {
                    'name': role['name'],
                    'privileges': role['privileges'],
                } for role in r
            }),
        )


def gen_cf9(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    users = faker.users(config.members_per_community, seed=config.seed)
    membership = faker.MemberRoles(faker.Membership(seed=config.seed))

    for community in communities:
        for user in users:
            m = membership.create(
                member_id=user['id'],
                community_id=community['id'],
                num_roles=config.roles_per_member,
            )

            for role in m['roles']:
                yield (
                    community['id'],
                    user['id'],
                    role['rank'],
                    user['handle'],
                    user['icon'],
                    m['joined_at'].isoformat(),
                )


codevo = Group(
    name='codevo',
    tables=(
        Table(
            name='communities',
            columns=(
                Column(name='roles_map', type='map<int, frozen<role_info>>'),
            ),
            keys=TableKeys(partition=('community_id',), clustering=()),
            type='alter',
            factory=gen_cf5
        ),
        Table(
            name='cf9',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='member_id', type='uuid'),
                Column(name='role_rank', type='int'),
                Column(name='member_handle', type='text'),
                Column(name='member_icon', type='text'),
                Column(name='joined_at', type='timestamp'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('member_id', 'asc'),
                    ('role_rank', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf9
        ),
    ),
    udts=(
        Udt(
            name='role_info',
            fields=(
                Column(name='name', type='text'),
                Column(name='privileges', type='set<text>'),
            )
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
