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
    communities: int = 100
    owners_per_community: int = 10

    total_owners: int = field(init=False)

    def __post_init__(self):
        total_owners = self.communities * self.owners_per_community
        object.__setattr__(self, 'total_owners', total_owners)


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
        ),
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


def gen_cf6(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    badges = faker.badges(config.owners_per_community, seed=config.seed + 1)

    for community in communities:
        yield (
            community['id'],
            utils.serialize({
                badge['id']: {
                    'contents': badge['contents']
                } for badge in badges
            })
        )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='communities',
            columns=(
                Column(name='badges', type='map<uuid, frozen<badge_info>>'),
            ),
            keys=TableKeys(partition=('community_id',), clustering=()),
            type='alter',
            factory=gen_cf6
        ),
    ),
    udts=(
        Udt(
            name='badge_info',
            fields=(
                Column(name='contents', type='text'),
            )
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