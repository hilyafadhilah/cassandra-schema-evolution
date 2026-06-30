"""
Scatter plot of load vs num_values for a chosen agg_type.
Points are colored by num_partitions (discrete); lines connect each partition group.

Usage:
    python plot_agg.py                # defaults to agg_type=list
    python plot_agg.py --agg-type set
    python plot_agg.py -a map
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ---- CLI ----
parser = argparse.ArgumentParser(description="Plot load vs num_values for a chosen agg_type")
parser.add_argument(
    "-a", "--agg-type",
    type=str,
    default="list",
    help="Filter the data to this agg_type (default: list)",
)
args = parser.parse_args()

# ---- Load & filter ----
df_all = pd.read_csv(Path(__file__).parent / "data.csv")
df = df_all[df_all["agg_type"] == args.agg_type]

if df.empty:
    available = sorted(df_all["agg_type"].unique())
    raise SystemExit(f"No rows with agg_type={args.agg_type!r}. Available: {available}")

# ---- Discrete color map for num_partitions ----
partition_values = sorted(df["num_partitions"].unique())
cmap = plt.get_cmap("viridis", len(partition_values))
color_map = {val: cmap(i) for i, val in enumerate(partition_values)}

# ---- Build the figure ----
fig, ax = plt.subplots(figsize=(9, 5.5))

plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 11

# One line+scatter per num_partitions value
for val in partition_values:
    sub = df[df["num_partitions"] == val].sort_values("num_values")
    ax.plot(
        sub["num_values"],
        sub["load"],
        color=color_map[val],
        linewidth=1.8,
        zorder=2,
    )
    ax.scatter(
        sub["num_values"],
        sub["load"],
        color=color_map[val],
        label=f"{val} partition",
        s=70,
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )

# ---- Labels, title, grid, legend ----
ax.set_xlabel("Jumlah Value", fontsize=12)
ax.set_ylabel("Waktu Load (s)", fontsize=12)
# ax.set_title(
#     f"Load time vs. num_values  (agg_type = {args.agg_type})",
#     fontsize=14,
#     fontweight="bold",
# )
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(
    # title="Jumlah Partition",
    loc="upper left",
    frameon=True,
    fontsize=9,
)

plt.tight_layout()
out_path = Path(__file__).parent / f"plot_{args.agg_type}.png"
plt.savefig(out_path, dpi=150)
plt.show()
print(f"Saved to {out_path}")