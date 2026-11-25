# Evaluating The Methodology: Case Study

We chose a **synthetic** case study for the evaluation of our methodology. Of course, despite the
official arguments written in our paper, the reason we did not use real-world data is because this
is a bachelor's degree project. In the future, I hope to continue my study and complete this
research in my thesis and/or dissertation.

After browsing the "use case" section in the official Cassandra and ScyllaDB website, we (I) ended
up deciding with a social media application for the case study. It is inspired by (a) X/Twitter
using Cassandra and (b) ShareChat (India's TikTok) using ScyllaDB. X/Twitter later ditched Cassandra
for their own in-house database ManhattanDB. However, looking deeper into it, I found that their
ManhattanDB's architecture and data model is still very similar to Cassandra.

[Read about ManhattanDB's data model here.](https://blog.x.com/en/engineering/native-secondary-indexing-in-manhattan)


### What's in this docs

- **Intro (this page)**  
  Describes the general overview of the social media app used in the case study.
- [01: Conceptual Model](./01_ConceptualModel.md)  
  Details the initial ER model of the social media app and its queries (access pattern).
  The queries are defined in the conceptual sense, not in any query language such as SQL or CQL.
- [02: Logical Model](./02_LogicalModel.md)  
  Details the initial Cassandra tables and how it relates to the conceptual model and its queries.
  Additionally, the costs of the queries are calculated.
- [03: Input](./03_Input.md)  
  Translates the conceptual model and its queries from chapter 01 into the Generic Data Metamodel
  (GDM), the conceptual model we use as input for our schema evolution methodology.


### The Social Media App

Another reason the social media app was chosen is I can imagine more feature updates because,
of course, I use social media apps in the daily. So for this case study, the initial state and
the evolutions are taken from my experience.

Initial features:

1. Users can browse posts in their personalized FYP (for you page)
2. Users can write posts; posts can have media in it (links, images, etc.)
3. Users can write *community posts*
4. Users can join communities
5. Users can follow other users
6. Users can create communities
7. Users can have *roles* in communities
8. Users can interact with posts (like, bookmark, etc.) 
9. Users can write comments on posts
10. Users can reply to comments on posts
11. Users can like comments

The FYP feature of course is the most significant part of the app, which makes it read-heavy for
posts. As such, in the data access pattern we synthesize later, the frequency of post-related read
queries would be high.

I would say most writes would be on the 8th feature which is post interaction. The amount of writes
per second would be very high if the app decides to also log "engagement" interactions such as post
views, clicks, profile visits, etc. However, remember that our methodology **does not yet consider**
**write queries**. Hence this is not added in the access pattern documentations.

Some further notes to help visualize the app features:
- The community & community post feature is similar to X/Twitter.
- The comments feature is more similar to TikTok.


### Future Research: Secondary Indexing & Materialized Views

If you read the ManhattanDB article I linked above, you will notice that *some* of the problems that
is meant to be addressed by our schema evolution methodology is solved by the *secondary indexing*
feature. This is interesting because this feature also does exist in Cassandra & ScyllaDB, alongside
the *materialized view* feature.

> I initially wanted to mention these two features both in my paper and my printed final project
> report document. However, there was just not enough space (😅). And, I suppose it was not
> significant enough to mention, as it relates more with future research.

The main arguments of the importance of our schema evolution methodology is that:

1. Tables can only be queried a certain way based on its keys.
2. Table keys cannot be changed once defined.

However, using *secondary indexing* or *materialized views*, the tables **can** actually be queried
in several different ways without changing the keys. The downside is the additional latency for
write queries involving the original table.

Compare that to our methodology which uses only *table modifications* (adding non-key columns,
adding/deleting tables). Many cases allow the bottleneck to be only in the data migration stage
with little to no effects on write queries afterwards.

As such, this naturally brings us to the question of

> **When should we use *secondary indexing*, *materialized views*, and *table modifications*?**

which is very appropriate for future research! I really hope I could also research this :D

I genuinely believe that the use cases of these features are not exclusive to our methodology.
Instead, what will happen is the methodology could suggest to use *secondary indexing* or
*materialized views* in place of a table candidate, where it thinks the performance would be
better.

