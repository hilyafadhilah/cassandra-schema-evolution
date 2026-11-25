"""
Scatter plot of load_s vs num_rows, with discrete colors per num_columns value.
A dashed line connects the num_columns=10 points to show the growth trend.
"""

import argparse
from pathlib import Path
import sys

import pandas as pd
import matplotlib.pyplot as plt

DATA_FILE = Path(__file__).parent / "data.csv"
OUTPUT_DIR = Path(__file__).parent / "out"

# ---- CLI ----
parser = argparse.ArgumentParser(description="Scatter plot of load_s/unload_s vs num_rows, colored by num_columns")
parser.add_argument(
    "y_col",
    type=str,
    choices=["load", "unload"],
    help="Which column to plot on the y-axis (default: load)",
)
parser.add_argument(
    "-l", "--laporan",
    action="store_true",
    help="Print in laporan (report) format: Indonesian, no title",
)
args = parser.parse_args()

# ---- Load data ----
y_col = args.y_col
df = pd.read_csv(DATA_FILE)

# ---- Build the figure ----
fig, ax = plt.subplots(figsize=(9, 5.5))

plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 11

# Assign a discrete color to each unique num_columns value
column_values = sorted(df["num_columns"].unique())
cmap = plt.get_cmap("viridis", len(column_values))
color_map = {val: cmap(i) for i, val in enumerate(column_values)}

# One scatter call per num_columns value so the legend has discrete entries
for val in column_values:
    label = f"{val} column" if args.laporan else f"{str(val).capitalize()} columns"
    sub = df[df["num_columns"] == val]
    ax.scatter(
        sub["num_rows"],
        sub[y_col],
        color=color_map[val],
        label=label,
        s=70,
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )

# ---- Dashed trend lines for selected num_columns values ----
TREND_VALUES = [5, 10, 20]
for val in TREND_VALUES:
    label = f"Tren {val} column" if args.laporan else f"{str(val).capitalize()} columns trend"
    ref = df[df["num_columns"] == val].sort_values("num_rows")
    ax.plot(
        ref["num_rows"],
        ref[y_col],
        linestyle="--",
        color=color_map[val],   # match the scatter color for this value
        linewidth=1.5,
        label=label,
        zorder=2,
    )

# ---- Labels, title, grid, legend ----

if args.laporan:
    ax.set_xlabel("Jumlah Row (× 100.000)", fontsize=12)
    ax.set_ylabel(f"Waktu {y_col.capitalize()} (s)", fontsize=12)
else:
    ax.set_xlabel("Number of Rows (× 100,000)", fontsize=12)
    ax.set_ylabel(f"{y_col.capitalize()} Time (s)", fontsize=12)
    ax.set_title(
        f"{y_col.capitalize()} Time vs. Number of Rows, P-1 Table Type",
        fontsize=12,
        fontweight="bold",
        y=1.025
    )

ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(
    # title="num_columns",
    loc="upper left",
    frameon=True,
    ncol=2,            # two columns so the legend stays compact
    fontsize=9,
)

if args.laporan:
    out_path = OUTPUT_DIR / f"plot-p1-{y_col}.laporan.svg"
else:
    out_path = OUTPUT_DIR / f"plot-p1-{y_col}.svg"

plt.rcParams["svg.fonttype"] = "none"  # keep text as text in SVG

plt.tight_layout()
plt.savefig(out_path, bbox_inches="tight", dpi=300)
plt.show()
print(f"Saved to {out_path.name}")