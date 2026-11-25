"""
Scatter plot of load vs num_partitions, filtered to a single num_columns value.
Points are colored by num_partition_rows; trend lines are drawn for 200, 500, 1000.

Usage:
    python plot_load.py                # defaults to num_columns=10
    python plot_load.py --num-columns 5
    python plot_load.py -n 20
"""

import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_FILE = Path(__file__).parent / "data.csv"
OUTPUT_DIR = Path(__file__).parent / "out"

# ---- CLI ----
parser = argparse.ArgumentParser(description="Plot load vs num_partitions for a given num_columns")
parser.add_argument(
    "-f", "--file",
    type=str,
    default=DATA_FILE,
    help="Path to the CSV file containing the data (default: data.csv)",
)
parser.add_argument(
    "-n", "--num-columns",
    type=int,
    default=10,
    help="Filter the data to this num_columns value (default: 10)",
)
parser.add_argument(
    "-y", "--y-col",
    type=str,
    default="load",
    help="Which column to plot on the Y-axis (default: load)",
)
parser.add_argument(
    "--save",
    action="store_true",
    help="Whether to save the plot as a SVG file (default: False, just show)",
)
parser.add_argument(
    "-l", "--laporan",
    action="store_true",
    help="Print in laporan (report) format: Indonesian, no title",
)
args = parser.parse_args()

y_col = args.y_col

# ---- Load & filter ----
df_all = pd.read_csv(args.file)
df = df_all[df_all["num_columns"] == args.num_columns]

if df.empty:
    available = sorted(df_all["num_columns"].unique())
    raise SystemExit(f"No rows with num_columns={args.num_columns}. Available: {available}")

# filter to num_partitions = {100,200,300,500,750,1000} & num_partition_rows = {100,250,500,750,1000}
df = df[
    df["num_partitions"].isin([100, 200, 300, 500, 750, 1000]) & 
    df["num_partition_rows"].isin([100, 250, 500, 750, 1000])
]

# ---- Discrete color map for num_partition_rows ----
row_values = sorted(df["num_partition_rows"].unique())
cmap = plt.get_cmap("viridis", len(row_values))
color_map = {val: cmap(i) for i, val in enumerate(row_values)}

# ---- Build the figure ----
fig, ax = plt.subplots(figsize=(9, 5.5))

plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 11

# Scatter: one call per num_partition_rows value so the legend is discrete
for val in row_values:
    label = f"{val} row/partition" if args.laporan else f"{val} rows/partition"
    sub = df[df["num_partition_rows"] == val]
    ax.scatter(
        sub["num_partitions"],
        sub[y_col],
        color=color_map[val],
        label=label,
        s=70,
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )

# ---- Dashed trend lines for selected num_partition_rows values ----
for val in row_values:
    if val not in color_map:
        continue  # safety net in case the dataset changes
    ref = df[df["num_partition_rows"] == val].sort_values("num_partitions")
    ax.plot(
        ref["num_partitions"],
        ref[y_col],
        linestyle="--",
        color=color_map[val],
        linewidth=1.8,
        # label=f"Tren {val} row/partition",
        zorder=2,
    )

# ---- Labels, title, grid, legend ----
if args.laporan:
    ax.set_xlabel("Jumlah Partition", fontsize=12)
    ax.set_ylabel(f"Waktu {y_col.title()} (s)", fontsize=12)
else:
    ax.set_xlabel("Number of Partitions", fontsize=12)
    ax.set_ylabel(f"{y_col.title()} Time (s)", fontsize=12)
    ax.set_title(
        f"{y_col.title()} Time vs. Number of Partitions\n"
        f"P-N Table Type, {args.num_columns} columns",
        fontsize=12,
        fontweight="bold",
        y=1.025
    )

ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(
    # title="num_partition_rows",
    loc="upper left",
    frameon=True,
    ncol=2,
    fontsize=9,
)

plt.rcParams["svg.fonttype"] = "none"  # keep text as text in SVG
plt.tight_layout()

if args.save:
    if args.laporan:
        out_path = OUTPUT_DIR / f"plot-pn-{y_col}-{args.num_columns}c.laporan.svg"
    else:
        out_path = OUTPUT_DIR / f"plot-pn-{y_col}-{args.num_columns}c.svg"
    plt.savefig(out_path, bbox_inches="tight", dpi=300)
    print(f"Saved to {out_path}")

plt.show()