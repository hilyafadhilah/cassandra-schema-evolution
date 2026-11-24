from dataclasses import field
from pathlib import Path
from typing import Iterator

from pydantic.dataclasses import dataclass

from eval.lib.evol import Column, GeneratorConfig, Group, Table, TableKeys, TestCaseDataGenerator, Udt
from eval.lib import faker
from eval.lib import utils
from eval.lib import run


@dataclass(frozen=True)
class Config(GeneratorConfig):
    seed: int = 0xFF

    tags_per_post: int = 5
    embeds_per_post: int = 3

    users: int = 100_000
    posts_per_user: int = 10

    communities: int = 100
    posts_per_community: int = 1000

    tags: int = 100

    followers_per_user: int = 10
    memberships_per_user: int = 10

    posts: int = field(init=False)
    posts_per_tag: int = field(init=False)

    def __post_init__(self):
        posts = self.users * self.posts_per_user
        posts_per_tag = posts * self.tags_per_post // self.tags
        object.__setattr__(self, 'posts', posts)
        object.__setattr__(self, 'posts_per_tag', posts_per_tag)


def gen_posts_by_author(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_user,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for user in users:
        for post in posts:
            yield (
                user['id'],
                post['posted_at'].isoformat(),
                post['id'],
                post['title'],
                post['contents'],
                post['language'],
                utils.serialize(post['tags']),
                user['handle'],
                user['icon'],
                post['community']['id'],
                post['community']['name'],
            )


def gen_posts_by_community(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_community,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for comm in communities:
        for post in posts:
            yield (
                comm['id'],
                post['posted_at'].isoformat(),
                post['id'],
                post['title'],
                post['contents'],
                post['language'],
                utils.serialize(post['tags']),
                post['author']['id'],
                post['author']['handle'],
                post['author']['icon'],
                comm['name'],
            )


def gen_posts_by_tag(config: Config) -> Iterator[tuple[str, ...]]:
    tags = faker.tags(config.tags, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_tag,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for tag in tags:
        for post in posts:
            yield (
                tag['tagname'],
                post['posted_at'].isoformat(),
                post['id'],
                post['title'],
                post['contents'],
                post['language'],
                utils.serialize(post['tags']),
                post['author']['id'],
                post['author']['handle'],
                post['author']['icon'],
                post['community']['id'],
                post['community']['name'],
            )


def gen_posts(config: Config) -> Iterator[tuple[str, ...]]:
    posts = faker.posts(
        posts=config.posts,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for post in posts:
        yield (
            post['id'],
            post['title'],
            post['contents'],
            post['language'],
            post['posted_at'].isoformat(),
            utils.serialize({
                embed['id']: {
                    'type': embed['type'],
                    'media': embed['media'],
                } for embed in post['embeds']
            }),
            utils.serialize(post['tags']),
            post['author']['id'],
            post['author']['handle'],
            post['author']['icon'],
            post['community']['id'],
            post['community']['name'],
        )


init = Group(
    tables=(
        Table(
            name='pa',
            columns=(
                Column(name='author_id', type='uuid'),
                Column(name='posted_at', type='timestamp'),
                Column(name='post_id', type='uuid'),
                Column(name='title', type='text'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='tags', type='set<text>'),
                Column(name='author_handle', type='text'),
                Column(name='author_icon', type='text'),
                Column(name='community_id', type='uuid'),
                Column(name='community_name', type='text'),
            ),
            keys=TableKeys(
                partition=('author_id',),
                clustering=(
                    ('posted_at', 'desc'),
                    ('post_id', 'asc')
                )
            ),
            type='create',
            factory=gen_posts_by_author
        ),
        Table(
            name='pc',
            columns=(
                Column(name='community_id', type='uuid'),
                Column(name='posted_at', type='timestamp'),
                Column(name='post_id', type='uuid'),
                Column(name='title', type='text'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='tags', type='set<text>'),
                Column(name='author_id', type='uuid'),
                Column(name='author_handle', type='text'),
                Column(name='author_icon', type='text'),
                Column(name='community_name', type='text'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('posted_at', 'desc'),
                    ('post_id', 'asc')
                )
            ),
            type='create',
            factory=gen_posts_by_community
        ),
        Table(
            name='pt',
            columns=(
                Column(name='tagname', type='text'),
                Column(name='posted_at', type='timestamp'),
                Column(name='post_id', type='uuid'),
                Column(name='title', type='text'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='tags', type='set<text>'),
                Column(name='author_id', type='uuid'),
                Column(name='author_handle', type='text'),
                Column(name='author_icon', type='text'),
                Column(name='community_id', type='uuid'),
                Column(name='community_name', type='text'),
            ),
            keys=TableKeys(
                partition=('tagname',),
                clustering=(
                    ('posted_at', 'desc'),
                    ('post_id', 'asc')
                )
            ),
            type='create',
            factory=gen_posts_by_tag
        ),
        Table(
            name='p',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='title', type='text'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='posted_at', type='timestamp'),
                Column(name='embeds', type='map<uuid, frozen<embed>>'),
                Column(name='tags', type='set<text>'),
                Column(name='author_id', type='uuid'),
                Column(name='author_handle', type='text'),
                Column(name='author_icon', type='text'),
                Column(name='community_id', type='uuid'),
                Column(name='community_name', type='text'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=()
            ),
            type='create',
            factory=gen_posts
        ),
    ),
    udts=(
        Udt(
            name='embed',
            fields=(
                Column(name='type', type='text'),
                Column(name='media', type='text'),
            )
        ),
    ),
)


def gen_cf1(config: Config) -> Iterator[tuple[str, ...]]:
    users = faker.users(config.users, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_user,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    icon = faker.uris(seed=f'{config.seed}_icon')

    for user in users:
        for post in posts:
            yield (
                user['id'],
                post['posted_at'].isoformat(),
                post['id'],
                icon(),
            )


def gen_cf4(config: Config) -> Iterator[tuple[str, ...]]:
    communities = faker.communities(config.communities, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_community,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    icon = faker.uris(seed=f'{config.seed}_icon')

    for comm in communities:
        for post in posts:
            yield (
                comm['id'],
                post['posted_at'].isoformat(),
                post['id'],
                icon(),
            )


def gen_cf6(config: Config) -> Iterator[tuple[str, ...]]:
    tags = faker.tags(config.tags, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_tag,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    icon = faker.uris(seed=f'{config.seed}_icon')

    for tag in tags:
        for post in posts:
            yield (
                tag['tagname'],
                post['posted_at'].isoformat(),
                post['id'],
                icon(),
            )


def gen_cf8(config: Config) -> Iterator[tuple[str, ...]]:
    posts = faker.posts(
        posts=config.posts,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    icon = faker.uris(seed=f'{config.seed}_icon')

    for post in posts:
        yield (
            post['id'],
            icon(),
        )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='pa',
            columns=(
                Column(name='community_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('author_id',),
                clustering=(
                    ('posted_at', 'desc'),
                    ('post_id', 'asc')
                )
            ),
            type='alter',
            factory=gen_cf1
        ),
        Table(
            name='pc',
            columns=(
                Column(name='community_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('community_id',),
                clustering=(
                    ('posted_at', 'desc'),
                    ('post_id', 'asc')
                )
            ),
            type='alter',
            factory=gen_cf4
        ),
        Table(
            name='pt',
            columns=(
                Column(name='community_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('tagname',),
                clustering=(
                    ('posted_at', 'desc'),
                    ('post_id', 'asc')
                )
            ),
            type='alter',
            factory=gen_cf6
        ),
        Table(
            name='p',
            columns=(
                Column(name='community_icon', type='text'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf8
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