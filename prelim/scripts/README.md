# Preliminary Test Scripts

This module contains the scripts needed to run preliminary tests on the database.
As has been described in my work, there are 4 evolution cost functions that we need to define:

- `T_load(c,p,r)`
- `T_unload(c,p,r)`
- `T_overhead_set(p,r,v)`
- `T_overhead_map(p,r,v)`

With the addition of NoSE's workload cost function:

- `T(n,w)`

##### Example Run

The following is a command sequence example to find the load & unload runtime for tables of type
P-1 with 50k, 75k, and 100k rows.

```
source ./cmd.sh

gen_prel p1 --row-counts 50_000 75_000 100_000
# => CSV generation info

run_prel p1
# => dsbulk PID

watch_prel
# => dsbulk logs

extract_prel p1 p1_50_75_100.csv
# => extraction info

# result:
#   ./results/p1_50_75_100.load.csv
#   ./results/p1_50_75_100.unload.csv

# NOTE: "prelim/scripts/results" is NOT THE SAME as "prelim/results"

clean_prel
# => rm -rf ./out/* ./data/*
```

For workload cost, the commands are different.

```
./read/gen.sh
# => CSV generation & dsbulk load into database
# note that this script in particular have hardcoded configs
# the generated data is a pn table with p=100, r=1000, c=[1,20]

./read/read.sh
# => database testing info

# result: ./read/results/result-YYYYMMDD-HHmmss.csv
```

### Table Types

- `p1`: single-row partition
  - CSV generation args  
    `--column-counts`, `--row-counts`
  - Result fields  
    `num_columns`, `num_rows`
- `pn`: multi-row partition
  - CSV generation args  
    `--column-counts`, `--num-partitions`, `--partition-row-counts`
  - Result fields  
    `num_columns`, `num_partitions`, `num_partition_rows`

The aggregated variants, `agg-p1` & `agg-pn`, have additional arguments and result fields:
- CSV generation args  
  `--agg-types`, `--value-counts`, `--field-counts`, `--num-agg-columns`
- Result fields  
  `agg_type`, `num_values`, `num_fields`

The commands in `cmd.sh` receives the table type name as argument, e.g.
`gen_prel p1`, `gen_prel pn`, `gen_prel agg-p1`, `gen_prel agg-pn`.

### Commands

- `gen_prel <type>`, `gpr <type>`  
  Run CSV generation script for `<type>`, available args are described above.
  This command can be run several times to produce as many table data as needed.
  The generated files can be found in `./data/<type>/` categorized by table.
- `run_prel <type>`, `rpr <type>`  
  Run nohup `dsbulk` load-unload for all tables found in `./data/<type>/`.
  The stdout logs can be found in `./out/logs` and PID in `./out/pid`.
  The `dsbulk` work logs can be found in `./out/<type>` categorized by table.
- `watch_prel`, `wpr`  
  See the running stdout logs using `tail`.
- `extract_prel <type> <csv_path>`, `epr <type> <csv_path>`  
  Extract results from `dsbulk` logs in `./out/<type>` into `./results/<csv_path>.load.csv` and
  `./results/<csv_path>.unload.csv`.
- `clean_prel`, `cpr`  
  Wipe out `./data/*` and `./out/*`. Be careful when calling this command.
- `kill_prel`, `kpr`  
  Stop the currently running test based on the contents of `./out/pid`.

### Modules & Scripts

```
prelim/scripts/
├── gen/                CSV generation module
│   ├── lib.py            Functions & classes used by other scripts
│   ├── p1.py             Generate P-1 (single-row partition) tables
│   ├── pn.py             Generate P-N (multi-row partition) tables
│   ├── agg-p1.py         Generate P-1 tables with aggregate columns
│   └── agg-pn.py         Generate P-N tables with aggregate columns
├── read/               Specialized module for workload test
│   ├── read.py           Test read queries with background load
│   ├── gen.sh            Generate CSV, load into db (uses gen/ module)
│   └── read.sh           Run read.py after gen.sh
├── gen.sh              Generate CSV using gen/ module
├── run.sh              Run dsbulk for all generated CSV
├── extract.py          Extract results from multiple dsbulk logs into one CSV [🤖]
├── group.py            Aggregate CSV fields [🤖]
├── merge.py            Merge CSV files [🤖]
└── cmd.sh              Shortcuts for running the scripts
```
> 🤖: AI-generated script

### Generated Structures

```
prelim/scripts/
├── data/                                           # gen_prel output 
│   └── <type>/
│       ├── <table1>/
│       │   ├── 001.csv
│       │   ├── tblname.txt
│       │   ├── init.cql
│       │   └── cleanup.cql
│       ├── <table2>/
│       │   └── ...
│       └── <table...>/
├── out/                                            # run_prel output
│   ├── logs
│   ├── pid
│   └── <type>/
│       ├── <table1>/
│       │   ├── unload/                             # dsbulk unload output, only the latest is saved
│       │   │   └── <...>.csv
│       │   └── logs/                               # dsbulk logs, 5 load 5 unload
│       │       ├── LOAD_YYYYMMDD-HHmmss-ffffff/
│       │       │   ├── checkpoint.csv
│       │       │   └── operation.log
│       │       ├── LOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── LOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── LOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── LOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── UNLOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── UNLOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── UNLOAD_YYYYMMDD-HHmmss-ffffff/
│       │       ├── UNLOAD_YYYYMMDD-HHmmss-ffffff/
│       │       └── UNLOAD_YYYYMMDD-HHmmss-ffffff/
│       ├── <table2>/
│       │   ├── unload/
│       │   │   └── ...
│       │   └── logs/
│       │       └── ...
│       └── <table...>/
├── results/                                        # extract_prel output
│   ├── <result1>.csv
│   ├── <result2>.csv
│   └── <result...>.csv
├── gen/                                            # gen module
│   └── ...
├── read/                                           # read module
│   ├── data/                                       # same as ./data above
│   │   └── <type>/
│   │       └── ...
│   ├── out/                                        # dsbulk load logs
│   │   ├── <table1>/
│   │   │   └── LOAD_YYYYMMDD-HHmmss-ffffff/
│   │   │       └── ...
│   │   ├── <table2>/
│   │   │   └── ...
│   │   └── <table...>
│   ├── results/                                    # workload test results
│   │   ├── result-YYYYMMDD-HHmmss.csv
│   │   └── <result...>.csv
│   └── ...
└── ...
```