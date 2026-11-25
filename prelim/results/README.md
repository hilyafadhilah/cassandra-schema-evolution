# Preliminary Test Results

This module contains the data obtained from running the preliminary tests (using the `scripts`
module) and the scripts to process those results. This module is divided based on the type of tests
done. It is used in two different stages of the research:

1. To formulate the evolution cost model, during the development of the methodology
2. To get the fitted/calibrated function, during the evaluation of the methodology

### Formulation of The Cost Model

We decided the cost model is defined by the total migration runtime. To define it, we base our
initial formula on the heuristic that, for the same throughput, the runtime is determined by the
volume of data. Of course, the volume is dependent on the shape of the data. Inspired by NoSE's
workload cost model `T(n,w)`, we use the parameters:
- 𝑝 : Number of partitions
- 𝑟 : Number of rows/partition
- 𝑐 : Number of columns (that need migration)

At first, it was just the total number of rows and columns. However testing shows that different
𝑝 and 𝑟 pairs with the same product produce slightly different results, as shown below.

|   𝑝   |   𝑟   |  𝑝×𝑟  |  𝑐  | `T_load` | `T_unload` |
|------:|------:|------:|----:|---------:|-----------:|
|   100 |  1000 |  100k |  12 |     3.2s |       1.0s |
|   200 |   500 |  100k |  12 |     3.0s |       1.0s |
|   250 |   400 |  100k |  12 |     3.0s |       1.0s |
|   400 |   250 |  100k |  12 |     3.2s |       1.0s |
|   500 |   200 |  100k |  12 |     3.2s |       1.0s |
|  1000 |   100 |  100k |  12 |     3.0s |       1.0s |
|       |       |       |     |          |            |
|   200 |  1000 |  200k |  12 |     5.8s |       2.0s |
|   250 |   800 |  200k |  12 |     5.4s |       2.0s |
|   400 |   500 |  200k |  12 |     5.6s |       2.0s |
|   500 |   400 |  200k |  12 |     6.0s |       2.2s |
|   800 |   250 |  200k |  12 |     6.0s |       2.0s |
|  1000 |   200 |  200k |  12 |     6.0s |       2.4s |
|       |       |       |     |          |            |
|   300 |  1000 |  300k |  12 |     9.0s |       2.6s |
|   400 |   750 |  300k |  12 |     8.4s |       2.4s |
|   500 |   600 |  300k |  12 |     9.6s |       2.4s |
|   600 |   500 |  300k |  12 |     9.2s |       2.8s |
|   750 |   400 |  300k |  12 |     9.2s |       2.4s |
|  1000 |   300 |  300k |  12 |     9.2s |       2.8s |

Of course we note that, for unload runtime, the difference is not significant and statistically
meaningless. As for load time, the difference is small. However, the sample data we collected here
is for 𝑝 and 𝑟 with the same range, which is 100–1000. We extrapolate that the difference will get
more pronounced for a more varied 𝑝 and 𝑟, which is more likely to happen in the real world. Hence,
we define the load/unload time cost model for a single table as `T_load(𝑝,𝑟,𝑐)` and
`T_unload(𝑝,𝑟,𝑐)`.

In line with that, we need to also consider our use of aggregate columns (set, list, map types) as
it obviously affects the cost model. How we get the cost model for aggregations is explained in the
[`agg` module](./agg/).

The final formulation results in 4 cost functions that need to be fitted:
1. `T_unload(𝑝,𝑟,𝑐)`
   Unload time of a table with 𝑝 partitions, 𝑟 rows/partition, and 𝑐 columns.
2. `T_load(𝑝,𝑟,𝑐)`
   Load time of a table with 𝑝 partitions, 𝑟 rows/partition, and 𝑐 non-aggregate columns.
3. `T_overhead_set(𝑝,𝑟,𝑣)`
   Load overhead time of an aggregate column of type set & list for a table with 𝑝 partitions,
   𝑟 rows/partition, and 𝑣 aggregate values/row.
4. `T_overhead_map(𝑝,𝑟,𝑣)`
   Load overhead time of an aggregate column of type map for a table with 𝑝 partitions,
   𝑟 rows/partition, and 𝑣 aggregate values/row.

### Fitting The Model for Evaluation of The Methodology

For `T_unload` and `T_load`, we divide each into two categories:
- **P-N High** : 𝑝 and 𝑟 in the range of 100–1000
  Data & post-processing scripts in [the `pn` module](./pn/).
- **P-N Low**  : 𝑝 in the range of 10k–1000k, 𝑟 in the range of 5–50
  Data & post-processing scripts in [the `pn-low` module](./pn-low/).
This is due to the nature of the data of the case study which makes the tables usually
falls in these two categories.

For `T_overhead_set` and `T_overhead_map`, it is not categorized as such. Details of fitting these
aggregate models is detailed in the [`agg` module](./agg/).

###### Notes

The models (whether linear, logarithmic, etc.) and parameters (esp. product parameters)
were chosen based on AI-assisted analysis of the data which includes comparison between models.
This is the recommended approach. For future research, a **one-size-fits-all ML model** might even
be more effective at suggesting the most optimized schema candidate for the purpose of
data modeling.

###### Results

```
# P-N High
T_unload(𝑝, 𝑟, 𝑐) =  0.32𝑐  + 0.00086𝑝 + 0.00045𝑟 + 0.00002508𝑝𝑟   - 3.24
T_load(𝑝, 𝑟, 𝑐)   = -0.043𝑐 + 0.00072𝑝 + 0.00069𝑟 + 0.000000573𝑝𝑟𝑐 + 0.27

# P-N Low
T_unload(𝑝, 𝑟, 𝑐) = 0.02𝑐 + 0.0000014𝑝                       - 0.17
T_load(𝑝, 𝑟, 𝑐)   = 0.47𝑐 + 0.0001147𝑝 + 0.07𝑟 + 0.0000102𝑝𝑟 - 3.26

# Aggregate
T_overhead_set(𝑝, 𝑟, 𝑣) = (1.52 * 𝑝𝑟𝑣 * 10^-6) - 0.4
T_overhead_map(𝑝, 𝑟, 𝑣) = 82.95 * (𝑝 ^ 0.87) * (𝑟 ^ 0.80) * (𝑣 ^ 0.81) * 10^-6 
```

### Files

```
prelim/results/
│
├── p1/                          P-1 Module: Single row/partition
│   ├── data.csv                 Results data (𝑟 is multiplied by 10^-5)
│   ├── plot.py                  Generate scatter plot of 'T' vs '𝑝×𝑟' [🤖]
│   ├── regress-load.py          Fit T_load [🤖]
│   ├── regress-unload.py        Fit T_unload [🤖]
│   └── out/                     Scatter plot results (SVG)
│
├── pn/                          P-N High Module
│   ├── data.csv                 Results data
│   ├── plot.py                  Generate scatter plot of T vs 𝑝 grouped by 𝑟 for a given 𝑐 [🤖]
│   ├── regress-load.py          Fit T_load [🤖]
│   ├── regress-unload.py        Fit T_unload [🤖]
│   └── out/                     Scatter plot results (SVG)
│
├── pn-low/                      P-N Low Module
│   ├── data.csv                 Results data
│   ├── regress-load.py          Fit T_load [🤖]
│   └── regress-unload.py        Fit T_unload [🤖]
│
└── agg/                         Agg Module: Aggregate columns
    ├── README.md                Read more about this module here
    └── ...
```