"""
Plot the ratio (T<num_agg_2> - 3.2) / (T<num_agg_1> - 3.2) for each agg_type,
with a horizontal reference line at y=2 to show convergence to a 2:1 ratio.
"""

import argparse

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "agg1-agg2.csv"
OUTPUT_DIR = Path(__file__).parent / "out"

# ---- CLI ----
parser = argparse.ArgumentParser(description="Plot the ratio of load times difference for all agg_types")
parser.add_argument(
    "-l", "--laporan",
    action="store_true",
    help="Print in laporan (report) format: Indonesian, no title",
)
args = parser.parse_args()

# ---- Load data ----
df = pd.read_csv(DATA_FILE)

# ---- Compute the ratio ----
REFERENCE = 3.2
df["ratio"] = (df["num_agg_2"] - REFERENCE) / (df["num_agg_1"] - REFERENCE)

# ---- Style configuration (tweak these) ----
COLORS = {
    "list": "#1f77b4",  # blue
    "set":  "#2ca02c",  # green
    "map":  "#d62728",  # red
}
MARKERS = {"list": "o", "set": "s", "map": "^"}  # circle, square, triangle
TARGET_RATIO = 2.0

# ---- Build the figure ----
fig, ax = plt.subplots(figsize=(9, 5.5))

plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 11

for agg_type, group in df.groupby("agg_type"):
    group = group.sort_values("num_values")
    ax.plot(
        group["num_values"],
        group["ratio"],
        label=agg_type.title(),
        color=COLORS[agg_type],
        marker=MARKERS[agg_type],
        markersize=7,
        linewidth=2,
    )

# ---- Reference line at y = 2 (the 2:1 target) ----
ax.axhline(
    y=TARGET_RATIO,
    color="gray",
    linestyle="--",
    linewidth=1.5,
    label=f"Rasio {TARGET_RATIO:.0f}:1",
    zorder=0,
)

# ---- Axis labels & title ----
if args.laporan:
    ax.set_xlabel("Jumlah Value", fontsize=12)
    ax.set_ylabel("Rasio Overhead", fontsize=12)
else:
    ax.set_xlabel("Number of Values", fontsize=12)
    ax.set_ylabel("Overhead Ratio", fontsize=12)
    ax.set_title(
        "Aggregate Column Load Time Overhead:\nConvergence Towards A 2:1 Ratio",
        fontsize=12,
        fontweight="bold",
        y=1.025
    )

# ---- Zoom the Y-axis so convergence is visible ----
ax.set_ylim(1.0, 2.5)

# ---- Grid & legend ----
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="lower right", frameon=True)

if args.laporan:
    out_path = OUTPUT_DIR / "plot-agg-diff-ratio.laporan.svg"
else:
    out_path = OUTPUT_DIR / "plot-agg-diff-ratio.svg"

plt.rcParams["svg.fonttype"] = "none"  # keep text as text in SVG
plt.tight_layout()
plt.savefig(out_path, bbox_inches="tight", dpi=300)
plt.show()
print(f"Saved to {out_path.name}")