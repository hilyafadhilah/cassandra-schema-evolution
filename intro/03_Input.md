# Conceptual Model Represented in GDM

The methodology I developed uses the Generic Data Metamodel (GDM), a conceptual data model format
developed by [de la Vega, et al. (2020)](https://doi.org/10.1016/j.future.2019.11.032) for the very
purpose of NoSQL data modeling.

The following text is the GDM representation of the conceptual model defined in [part 01](./01_ConceptualModel.md).

```
entity User {
  id id
  text handle
  text email
  text icon
  text bio
  text region
  list<text> languages
  ref Follow[*] followings
  ref Follow[*] followers
  ref Membership[*] memberships
  ref Post[*] posts
  ref Interaction[*] interactions
  ref Badge[1] badge
}

entity Post {
  id id
  text title
  text contents
  date postedAt
  text language
  ref Tag[*] tags
  ref Embed[*] embeds
  ref User[1] author
  ref Community[1] community
  ref Interaction[*] interactions
}

entity Tag {
  text tagname
}

entity Embed {
  id id
  text type
  text media
  ref Post[1] post
}

entity Comment {
  ref Post[1] post
  text id
  text contents
  text language
  date postedAt
  int likesCount
  ref Comment[1] parent
  ref Comment[*] replies
  ref User[*] likers
}

entity Community {
  id id
  text name
  text icon
  text description 
  ref Membership[*] memberships
  ref Post[*] posts
  ref User[*] owners
}

entity Badge {
  id id
  text type
  text display
}

entity Interaction {
  ref User[1] user
  ref Post[1] post
  text type
  date timestamp
}

entity Follow {
  ref User[1] follower
  ref User[1] followee
  date followedAt
}

entity Membership {
  ref User[1] member
  ref Community[1] community
  date joinedAt
  text role
}


query Q01_RecentPostsByFollowedUsers:
  SELECT
    post.id, post.title, post.contents,
    post.postedAt, post.language, tag.tagname,
    author.id, author.handle, author.icon,
    community.id, community.name
  FROM User as user
  INCLUDING
    user.followings as follow,
    follow.followee as followee,
    followee.posts as post,
    post.tags as tag,
    post.author as author,
    post.community as community
  WHERE user.id = ?
  ORDER BY post.postedAt DESC

query Q02_RecentPostsInJoinedCommunities:
  SELECT
    post.id, post.title, post.contents,
    post.postedAt, post.language, tag.tagname,
    author.id, author.handle, author.icon,
    community.id, community.name
  FROM User as user
  INCLUDING
    user.memberships as membership,
    membership.community as community,
    community.posts as post,
    post.tags as tag, 
    post.author as author 
  WHERE user.id = ?
  ORDER BY post.postedAt DESC

query Q03_RecentPostsByTag:
  SELECT
    post.id, post.title, post.contents,
    post.postedAt, post.language, tag.tagname,
    author.id, author.handle, author.icon,
    community.id, community.name
  FROM Post as post
  INCLUDING
    post.tags as t,
    post.tags as tag, 
    post.author as author
  WHERE t.tagname = ?
  ORDER BY post.postedAt DESC

query Q04_TopRootComments:
  SELECT
    comment.id, comment.contents,
    comment.language, comment.postedAt, comment.likesCount,
    commenter.id, commenter.handle, commenter.icon
  FROM Post as post
  INCLUDING
    post.comments as comment,
    comment.commenter as commenter,
    comment.parent as parent
  WHERE post.id = ? AND parent = NIL
  ORDER BY comment.likesCount DESC

query Q05_ChronologicalReplyComments:
  SELECT
    comment.id, comment.contents,
    comment.language, comment.postedAt, comment.likesCount,
    commenter.id, commenter.handle, commenter.icon
  FROM Post as post
  INCLUDING
    post.comments as comment,
    comment.commenter as commenter,
    comment.parent as parent
  WHERE post.id = ? AND parent.id = ?
  ORDER BY comment.commentedAt ASC

query Q06_RecentPostInteractions:
  SELECT
    interaction.type, interaction.timestamp,
    user.id, user.handle, user.icon,
    user.region, user.languages
  FROM Post as post
  INCLUDING
    post.interactions as interaction,
    interaction.user as user 
  WHERE post.id = ?
  ORDER BY interaction.timestamp DESC

query Q07_RecentUserInteractions:
  SELECT
    interaction.type, interaction.timestamp,
    post.id, post.title, post.contents,
    post.postedAt, post.language, tag.tagname,
    author.id, author.handle, author.icon,
    community.id, community.name
  FROM User as user
  INCLUDING
    user.interactions as interaction,
    interaction.post as post,
    post.tags as tag,
    post.author as author,
    post.community as community 
  WHERE user.id = ? AND interaction.type = ?
  ORDER BY interaction.timestamp DESC

query Q08_FollowedUsers:
  SELECT
    followee.id, followee.handle, followee.icon,
    followee.email, followee.bio,
    follow.followedAt
  FROM User as user
  INCLUDING
    user.followings as follow,
    follow.followee as followee 
  WHERE user.id = ?
  ORDER BY follow.followedAt DESC

query Q09_JoinedCommunities:
  SELECT
    community.id, community.name,
    community.icon, community.description,
    membership.joinedAt, membership.role
  FROM User as user
  INCLUDING
    user.memberships as membership,
    membership.community as community
  WHERE user.id = ?
  ORDER BY membership.joinedAt DESC

query Q10_CommunityMembers:
  SELECT
    member.id, member.handle, member.icon,
    membership.joinedAt, membership.role
  FROM Community as community
  INCLUDING
    community.memberships as membership,
    membership.member as member
  WHERE community.id = ?
  ORDER BY membership.role ASC, membership.joinedAt ASC

query Q11_CommunityMembersByRole:
  SELECT
    member.id, member.handle, member.icon,
    membership.joinedAt, membership.role
  FROM Community as community
  INCLUDING
    community.memberships as membership,
    membership.member as member 
  WHERE community.id = ? AND membership.role = ?
  ORDER BY membership.joinedAt ASC

query Q12_UserInfo:
  SELECT
    user.id, user.handle, user.icon,
    user.email, user.bio, user.region, user.languages,
    badge.id, badge.contents
  FROM User as user
  INCLUDING user.badge as badge
  WHERE user.id = ?

query Q13_PostInfo:
  SELECT
    post.id, post.title, post.contents,
    post.postedAt, post.language, tag.tagname,
    embed.id, embed.type, embed.media,
    author.id, author.handle, author.icon,
    community.id, community.handle
  FROM Post as post
  INCLUDING
    post.tags as tag,
    post.embeds as embed,
    post.author as author,
    post.community as community
  WHERE post.id = ?

query Q14_CommunityInfo:
  SELECT
    community.id, community.name,
    community.icon, community.description,
    owner.id, owner.handle, owner.icon
  FROM Community as community
  INCLUDING community.owners as owner
  WHERE community.id = ?

query Q15_CommentLikes:
  SELECT
    liker.id, liker.handle, liker.icon
  FROM Post as post
  INCLUDING
    post.comments as comment,
    comment.likers as liker
  WHERE post.id = ? AND comment.id = ?
```


## Read more

- [00: Intro](./README.md)
- [01: Conceptual Model](./01_ConceptualModel.md)
- [02: Logical Model](./01_ConceptualModel.md)