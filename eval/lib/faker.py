from enum import Enum
from typing import Any
from uuid import UUID

from mimesis import Field, Fieldset, keys
from mimesis.schema import Schema
from mimesis.random import Random


def _rand_int(field: Field, start: int, end: int) -> int:
    return field('integer_number', start=start, end=end)


def users(num_users: int, seed: int | None = None):
    field = Field(seed=seed)
    fieldset = Fieldset(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'handle': field('username'),
        'email': field('email'),
        'icon': field('uri'),
        'bio': field('quote'),
        'region': field('country_code'),
        'languages': fieldset('locale_code', i=_rand_int(field, 1, 3)),
        'badge': {
            'id': field('uuid'),
            'contents': field('text', quantity=_rand_int(field, 1, 5))
        }
    }, iterations=num_users)


def user_infos(num_users: int, seed: int | None = None):
    field = Field(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'handle': field('username'),
        'icon': field('uri'),
    }, iterations=num_users)


def badges(num_badges: int, seed: int | None = None):
    field = Field(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'contents': field('text', quantity=_rand_int(field, 1, 5))
    }, iterations=num_badges)


EMBED_TYPES = ('image', 'video', 'link', 'post')


def posts(
    posts: int,
    tags_per_post: int = 5,
    embeds_per_post: int = 3,
    seed: int | None = None,
):
    field = Field(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'title': field('text', quantity=1),
        'contents': field('text', quantity=_rand_int(field, 1, 5)),
        'language': field('locale_code'),
        'posted_at': field('datetime'),
        'tags': field('words', quantity=tags_per_post),
        'author': {
            'id': field('uuid'),
            'handle': field('username'),
            'icon': field('uri'),
        },
        'community': {
            'id': field('uuid'),
            'name': field('company'),
        },
        'embeds': [
            {
                'id': field('uuid'),
                'type': field('choice', items=EMBED_TYPES),
                'media': field('uri'),
            }
            for _ in range(embeds_per_post)
        ]
    }, iterations=posts)


def communities(
    num_communities: int,
    num_community_owners: int = 3,
    seed: int | None = None
):
    field = Field(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'name': field('company'),
        'icon': field('uri'),
        'description': field('text', quantity=_rand_int(field, 1, 5)),
        'owners': [
            {
                'id': field('uuid'),
                'handle': field('username'),
                'icon': field('uri'),
            }
            for _ in range(num_community_owners)
        ]
    }, iterations=num_communities)


def tags(num_tags: int, seed: int | None = None):
    field = Field(seed=seed)

    return Schema(lambda: {
        'tagname': field('word'),
    }, iterations=num_tags)


class Membership:
    class MemberRole(Enum):
        OWNER = 0
        ADMIN = 1
        MODERATOR = 2
        VIP = 3
        MEMBER = 99


    MEMBER_ROLE_CHOICES = {
        MemberRole.OWNER.value: .01,
        MemberRole.ADMIN.value: .15,
        MemberRole.MODERATOR.value: .1,
        MemberRole.VIP.value: .04,
        MemberRole.MEMBER.value: .7,
    }

    def __init__(
        self,
        seed: int | None = None,
    ):
        self.seed = seed
        self.field = Field()
        self.random = Random()

    def create(self, member_id: str | None = None, community_id: str | None = None):
        self.field.reseed(f'{self.seed}_{member_id}_{community_id}')
        self.random.seed(f'{self.seed}_{member_id}_{community_id}')

        return {
            'joined_at': self.field('datetime'),
            'role': self.random.weighted_choice(self.MEMBER_ROLE_CHOICES),
        }
    

def uuids(seed: Any = None,):
    field = Field(seed=seed)
    return lambda: field('uuid')


def likes(
    users: list[dict],
    num_posts: int,
    num_post_comments: int,
    num_comment_likes: int,
    seed: int | None = None
):
    rand = Random(seed)

    post_field = Field(seed=f'{seed}_posts')
    comment_field = Field(seed=f'{seed}_comments')

    for _ in range(num_posts):
        for _ in range(num_post_comments):
            for user in rand.sample(users, num_comment_likes):
                yield {
                    'post_id': post_field('uuid'),
                    'comment_id': comment_field('uuid'),
                    'user': {
                        'id': user['id'],
                        'handle': user['handle'],
                        'icon': user['icon'],
                    }
                }


def comments(
    users: list[dict],
    posts: int,
    root_comments_per_post: int,
    replies_per_comment: int,
    reply_levels: int,
    seed: int | None = None
):
    rand = Random(seed)

    post_field = Field(seed=rand.random())
    comment_field = Field(seed=rand.random())

    for _ in range(posts):
        post_id = post_field('uuid')

        # Generate root comments
        root_comments = []
        for _ in range(root_comments_per_post):
            user = rand.choice(users)
            comment_id = comment_field('uuid')
            root_comments.append(comment_id)

            yield {
                'post_id': post_id,
                'comment_id': comment_id,
                'parent_comment_id': UUID(int=0),  # Root comments have no parent
                'commented_at': comment_field('datetime'),
                'contents': comment_field('text', quantity=_rand_int(comment_field, 1, 5)),
                'language': comment_field('locale_code'),
                'likes': rand.randint(0, 100),
                'user': {
                    'id': user['id'],
                    'handle': user['handle'],
                    'icon': user['icon'],
                }
            }

            # Generate replies with BFS traversal
            queue = [(comment_id, 1)]  # (parent_comment_id, current_level)
            while queue:
                parent_comment_id, current_level = queue.pop(0)

                if current_level > reply_levels:
                    continue

                for _ in range(replies_per_comment):
                    user = rand.choice(users)
                    reply_comment_id = comment_field('uuid')

                    yield {
                        'post_id': post_id,
                        'comment_id': reply_comment_id,
                        'parent_comment_id': parent_comment_id,
                        'commented_at': comment_field('datetime'),
                        'contents': comment_field('text', quantity=_rand_int(comment_field, 1, 5)),
                        'language': comment_field('locale_code'),
                        'likes': rand.randint(0, 100),
                        'user': {
                            'id': user['id'],
                            'handle': user['handle'],
                            'icon': user['icon'],
                        }
                    }

                    queue.append((reply_comment_id, current_level + 1))


# evol


class PostStatus(Enum):
    DRAFT = 0
    PUBLISHED = 1
    ARCHIVED = -1


POST_STATUS_VALUES = [
    status.value for status in PostStatus
]


status_field = Field()
def post_status(seed: int | None = None, post_id: str | None = None):
    status_field.reseed(f'{seed}_{post_id}')
    return status_field('choice', items=POST_STATUS_VALUES)


def bookmarks(num_bookmarks: int, seed: int | None = None):
    field = Field(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'name': field('text.title'),
        'cover': field('uri'),
        'updated_at': field('datetime'),
    }, iterations=num_bookmarks)


def topics(num_topics: int, seed: int | None = None):
    field = Field(seed=seed)

    return Schema(lambda: {
        'id': field('uuid'),
        'name': field('text.title'),
    }, iterations=num_topics)

def description(n: int, seed: int | None = None):
    field = Field(seed=seed)

    return lambda: field('text', quantity=_rand_int(field, 1, n))

relevancy_field = Field()
def relevancy_score(
    seed: int | None = None,
    topic_id: str | None = None,
    post_id: str | None = None,
):
    relevancy_field.reseed(f'{seed}_{topic_id}_{post_id}')
    return relevancy_field('integer_number', start=-1000, end=1000)


def community_roles(
    num_roles: int,
    num_privileges: int = 5,
    seed: int | None = None,
):
    field = Field(seed=seed)

    return Schema(lambda: {
        'rank': field('integer_number', start=10, end=90),
        'name': field('words', quantity=_rand_int(field, 1, 3), key=keys.join(' ')),
        'privileges': field('words', quantity=_rand_int(field, 1, num_privileges)),
    }, iterations=num_roles)


class MemberRoles:
    MEMBER_ROLE_DEFINITIONS = {
        Membership.MemberRole.OWNER.value: {
            'rank': Membership.MemberRole.OWNER.value,
            'name': 'Owner',
            'privileges': [
                'manage_community',
                'manage_members',
                'manage_posts',
                'manage_settings',
            ]
        },
        Membership.MemberRole.ADMIN.value: {
            'rank': Membership.MemberRole.ADMIN.value,
            'name': 'Admin',
            'privileges': [
                'manage_members',
                'manage_posts',
            ]
        },
        Membership.MemberRole.MODERATOR.value: {
            'rank': Membership.MemberRole.MODERATOR.value,
            'name': 'Moderator',
            'privileges': [
                'manage_posts',
            ]
        },
        Membership.MemberRole.VIP.value: {
            'rank': Membership.MemberRole.VIP.value,
            'name': 'VIP',
            'privileges': [
                'access_vip_content',
            ]
        },
        Membership.MemberRole.MEMBER.value: {
            'rank': Membership.MemberRole.MEMBER.value,
            'name': 'Member',
            'privileges': []
        },
    }
    
    def __init__(self, membership: Membership):
        self.membership = membership
        self.seed = membership.seed
        self.field = Field()

    def schema(
        self,
        num_roles: int,
        num_privileges: int = 5,
        community_id: str | None = None,
        member_id: str | None = None,
    ):
        field = self.field
        field.reseed(f'{self.seed}_{community_id}_{member_id}')

        return Schema(lambda: {
            'rank': field('integer_number', start=10, end=90),
            'name': field('words', quantity=_rand_int(field, 1, 3), key=keys.join(' ')),
            'privileges': field('words', quantity=_rand_int(field, 1, num_privileges)),
        }, iterations=num_roles)

    def create(
        self,
        num_roles: int,
        num_privileges: int = 5,
        community_id: str | None = None,
        member_id: str | None = None,
    ):
        field = self.field
        field.reseed(f'{self.seed}_{community_id}_{member_id}')

        m = self.membership.create(member_id=member_id, community_id=community_id)

        return {
            'joined_at': m['joined_at'],
            'roles': [
                self.MEMBER_ROLE_DEFINITIONS[m['role']]
            ] + self.schema(
                num_roles=num_roles - 1,
                num_privileges=num_privileges,
                community_id=community_id,
                member_id=member_id,
            ).create(),
        }
    

def uris(seed: Any | None = None):
    field = Field(seed=seed)
    return lambda: field('uri')