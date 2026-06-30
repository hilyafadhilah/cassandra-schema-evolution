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

    posts: int = 100_000
    tags_per_post: int = 5
    embeds_per_post: int = 3

    topics: int = 10
    topics_per_post: int = 3

    posts_per_topic: int = field(init=False)

    def __post_init__(self):
        posts_per_topic = self.posts * self.topics_per_post // self.topics
        object.__setattr__(self, 'posts_per_topic', posts_per_topic)


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


def gen_topics(config: Config) -> Iterator[tuple[str, ...]]:
    topics = faker.topics(config.topics, seed=config.seed)
    description = faker.description(5, seed=config.seed)

    for topic in topics:
        yield (
            topic['id'],
            topic['name'],
            description(),
        )


init = Group(
    tables=(
        Table(
            name='posts',
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
        Table(
            name='topics',
            columns=(
                Column(name='topic_id', type='uuid'),
                Column(name='name', type='text'),
                Column(name='description', type='text'),
            ),
            keys=TableKeys(
                partition=('topic_id',),
                clustering=()
            ),
            type='create',
            factory=gen_topics
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
    topics = faker.topics(config.topics, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_topic,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for topic in topics:
        for post in posts:
            yield (
                topic['id'],
                post['posted_at'].date().isoformat(),
                str(faker.relevancy_score(
                    seed=config.seed,
                    topic_id=topic['id'],
                    post_id=post['id']
                )),
                post['id'],
                post['title'],
                post['contents'],
                post['language'],
                post['posted_at'].isoformat(),
                utils.serialize(post['tags']),
                post['author']['id'],
                post['author']['handle'],
                post['author']['icon'],
                post['community']['id'],
                post['community']['name'],
            )


def gen_cf10(config: Config) -> Iterator[tuple[str, ...]]:
    posts = faker.posts(
        posts=config.posts,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )
    topics = faker.topics(config.topics_per_post, seed=config.seed)

    for post in posts:
        yield (
            post['id'],
            utils.serialize({
                topic['id']: {
                    'topic_name': topic['name'],
                    'relevancy_score': faker.relevancy_score(
                        seed=config.seed,
                        topic_id=topic['id'],
                        post_id=post['id']
                    )
                } for topic in topics
            }),
        )


qbal = Group(
    name='qbal',
    tables=(
        Table(
            name='cf1',
            columns=(
                Column(name='topic_id', type='uuid'),
                Column(name='post_date', type='date'),
                Column(name='relevancy_score', type='int'),
                Column(name='post_id', type='uuid'),
                Column(name='title', type='text'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='posted_at', type='timestamp'),
                Column(name='tags', type='set<text>'),
                Column(name='author_id', type='uuid'),
                Column(name='author_handle', type='text'),
                Column(name='author_icon', type='text'),
                Column(name='community_id', type='uuid'),
                Column(name='community_name', type='text'),
            ),
            keys=TableKeys(
                partition=('topic_id',),
                clustering=(
                    ('post_date', 'desc'),
                    ('relevancy_score', 'desc'),
                    ('post_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf1
        ),
        Table(
            name='posts',
            columns=(
                Column(name='topics_map', type='map<uuid, frozen<post_topic>>'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf10
        ),
    ),
    udts=(
        Udt(
            name='post_topic',
            fields=(
                Column(name='topic_name', type='text'),
                Column(name='relevancy_score', type='int'),
            )
        ),
    ),
)


def gen_cf2(config: Config) -> Iterator[tuple[str, ...]]:
    topics = faker.topics(config.topics, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_topic,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for topic in topics:
        for post in posts:
            yield (
                topic['id'],
                post['posted_at'].date().isoformat(),
                str(faker.relevancy_score(
                    seed=config.seed,
                    topic_id=topic['id'],
                    post_id=post['id']
                )),
                post['id'],
            )


def gen_cf11(config: Config) -> Iterator[tuple[str, ...]]:
    posts = faker.posts(
        posts=config.posts,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )
    topics = faker.topics(config.topics_per_post, seed=config.seed)

    for post in posts:
        yield (
            post['id'],
            utils.serialize([
                topic['id'] for topic in topics
            ]),
        )


qmin = Group(
    name='qmin',
    tables=(
        Table(
            name='cf2',
            columns=(
                Column(name='topic_id', type='uuid'),
                Column(name='post_date', type='date'),
                Column(name='relevancy_score', type='int'),
                Column(name='post_id', type='uuid'),
            ),
            keys=TableKeys(
                partition=('topic_id',),
                clustering=(
                    ('post_date', 'desc'),
                    ('relevancy_score', 'desc'),
                    ('post_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf2
        ),
        Table(
            name='posts',
            columns=(
                Column(name='topics_set', type='set<uuid>'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=()
            ),
            type='alter',
            factory=gen_cf11
        ),
    ),
)


def gen_cf13(config: Config) -> Iterator[tuple[str, ...]]:
    topics = faker.topics(config.topics, seed=config.seed)
    posts = faker.posts(
        posts=config.posts_per_topic,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )

    for topic in topics:
        for post in posts:
            yield (
                topic['id'],
                post['posted_at'].date().isoformat(),
                post['id'],
                post['title'],
                post['contents'],
                post['language'],
                post['posted_at'].isoformat(),
                str(faker.relevancy_score(
                    seed=config.seed,
                    topic_id=topic['id'],
                    post_id=post['id']
                )),
            )


def gen_cf9(config: Config) -> Iterator[tuple[str, ...]]:
    posts = faker.posts(
        posts=config.posts,
        tags_per_post=config.tags_per_post,
        embeds_per_post=config.embeds_per_post,
        seed=config.seed
    )
    topics = faker.topics(config.topics_per_post, seed=config.seed)

    for post in posts:
        for topic in topics:
            yield (
                post['id'],
                topic['id'],
                topic['name'],
                str(faker.relevancy_score(
                    seed=config.seed,
                    topic_id=topic['id'],
                    post_id=post['id']
                )),
            )


codevo = Group(
    name='codevo',
    tables=(
        Table(
            name='cf13',
            columns=(
                Column(name='topic_id', type='uuid'),
                Column(name='post_date', type='date'),
                Column(name='post_id', type='uuid'),
                Column(name='title', type='text'),
                Column(name='contents', type='text'),
                Column(name='language', type='text'),
                Column(name='posted_at', type='timestamp'),
                Column(name='relevancy_score', type='int'),
            ),
            keys=TableKeys(
                partition=('topic_id',),
                clustering=(
                    ('post_date', 'desc'),
                    ('post_id', 'asc'),
                )
            ),
            type='create',
            factory=gen_cf13
        ),
        Table(
            name='cf9',
            columns=(
                Column(name='post_id', type='uuid'),
                Column(name='topic_id', type='uuid'),
                Column(name='topic_name', type='text'),
                Column(name='relevancy_score', type='int'),
            ),
            keys=TableKeys(
                partition=('post_id',),
                clustering=(('topic_id', 'asc'),)
            ),
            type='create',
            factory=gen_cf9
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
