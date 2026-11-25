# Cassandra Schema Evolution: A Workload-Driven Methodology (Supplementary Materials)

![WIP](https://img.shields.io/badge/version-v0.0.2--alpha-blue) ![WIP](https://img.shields.io/badge/⚠️_WORK_IN_PROGRESS-red)

Computer science bachelor's degree final project @ Institut Teknologi Bandung (ITB)
by Hilya Fadhilah Imania.

Officially registered in [ITB's digital library (digilib.itb.ac.id)🔗](https://digilib.itb.ac.id/gdl/view_data/metode-evolusi-model-data-berbasis-query-untuk-model-data-column-family-cassandra-13520024).


## Summary

I created a data modeling methodology for Cassandra-based schema evolution that
incorporates conceptual data model + workload (in the form of queries).

Previous research:

```
Evolved <Conceptual Model> ⇒ Cassandra Schema + ... (depends on the tool)
```

My research:

```
Evolved <Conceptual Model + Workload Queries> ⇒ Cassandra Schema + Query Execution Plans
```

It can only accept read queries as workload (write queries are not supported).
And yes, the workload queries are for the conceptual model! Not SQL tables.

The methodology is based on NoSE, a Cassandra data modeling tool developed by
[Mior et al. (2017)](https://doi.org/10.1109/TKDE.2017.2722412)
which is then modified for the purpose of **schema evolution**.
The methodology adopts various mechanisms from the following works:

- [Mortadelo by de la Vega et al. (2020)](https://doi.org/10.1016/j.future.2019.11.032)
  - The Generic Data Metamodel (GDM), for input
  - The query-to-table algorithm
  - The optimization mechanisms; *query merging* and *partition key softening*
- [CoDEvo by Suárez-Otero et al. (2023)](https://doi.org/10.1016/j.jss.2023.111743)
  - The *aggregation* mechanism (using CQL's `map`, `set`, and `list` column types)
- [NoSE by Mior et al. (2017)](https://doi.org/10.1109/TKDE.2017.2722412) itself
  - *Support query* mechanism, for `WHERE` condition removal

### Major contribution: The evolution cost model

My major contribution is defining the **schema evolution cost model** for Cassandra as the total
migration runtime, which is formally defined in the following image.

![Our evolution cost model](./intro/img/equations/evolution-cost-model.svg)


## What's in this repository

1. `/prelim`: [Preliminary tests🔗](./prelim/)  
   Preliminary testing is done for (a) **formulating the cost model** during the development stage 
   of our methodology and (b) **fitting/calibrating** the model itself during the evaluation stage
   of our methodology.
2. `/intro`: [Case study introduction for the evaluation stage🔗](./intro)  
   Documentation for the initial state (before evolution) of the case study for the evaluation stage
   of our methodology. The docs describes in detail relevant informations, such as: the data model
   & access patterns, conceptual & logical schema, and GDM input.
3. `/eval`: [Scripts, results, & docs for the evaluation stage🔗](./eval)  
   Scripts, results, & docs for the evolutions done on the case study for the evaluation stage.
   Each test case is separate from one another unless stated otherwise.
4. `/containers`  
   Python & DSBulk dockerfiles


## TODO!!

1. Refactor code for `/eval`
2. Write docs for `/eval`