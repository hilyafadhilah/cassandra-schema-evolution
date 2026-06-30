# Supplementary materials for my computer science bachelor's degree final project @ITB

![WIP](https://img.shields.io/badge/version-v0.0.1--alpha-blue) ![WIP](https://img.shields.io/badge/⚠️_WORK_IN_PROGRESS-red)

## My final project

I created a data modeling methodology for Cassandra-based model evolution that incorporates conceptual data model + workload (in the form of queries).

Basically:

```
Evolved <ER Model + Workload Queries> ⇒ Cassandra Model + Query Execution Plans
```

It can only accept read queries as workload.

## What's in this repository

1. `/prelim`: preliminary testing materials (code and results)
2. `/test`: evaluation/testing materials (code, and results)
3. `/docs`: documentation

## TODO

1. Refactor code (abstractions, comments)
2. Separate docs on `/docs` into each test case directory, use markdown
3. Create docs for each prelim category
4. Refactor preliminary results (csv names, directories)