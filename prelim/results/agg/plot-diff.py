"""
Plot the difference (T<num_agg_2> - T<num_agg_1>) for each agg_type,
with a horizontal reference line at y=0 to show no difference.
"""

import argparse

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

REFERENCE = 3.2

DATA_FILE = Path(__file__).parent / "data" / "agg1-agg2.csv"
OUTPUT_DIR = Path(__file__).parent / "out"

# ---- CLI ----
parser = argparse.ArgumentParser(description="Plot the difference of load times for all agg_types")
parser.add_argument(
    "-l", "--laporan",
    action="store_true",
    help="Print in laporan (report) format: Indonesian, no title",
)
args = parser.parse_args()

# ---- Load data ----
df = pd.read_csv(DATA_FILE)

# ---- Style configuration (tweak these) ----
COLORS = {
    "list": "#1f77b4",  # blue
    "set":  "#2ca02c",  # green
    "map":  "#d62728",  # red
}
MARKERS = {"list": "o", "set": "s", "map": "^"}  # circle, square, triangle

# ---- Build the figure ----
fig, ax = plt.subplots(figsize=(9, 5.5))

plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 11

for agg_type, group in df.groupby("agg_type"):
    group = group.sort_values("num_values")
    ax.plot(
        group["num_values"],
        group["num_agg_1"],
        label=agg_type.title(),
        color=COLORS[agg_type],
        marker=MARKERS[agg_type],
        markersize=7,
        linewidth=2,
    )

# ---- Reference line at y = REFERENCE ----
ax.axhline(
    y=REFERENCE,
    color="gray",
    linestyle="--",
    linewidth=1.5,
    label=f"Baseline: {REFERENCE:.1f}s",
    zorder=0,
)

# ---- Axis labels & title ----
if args.laporan:
    ax.set_xlabel("Jumlah Value", fontsize=12)
    ax.set_ylabel("Waktu Load (s)", fontsize=12)
else:
    ax.set_xlabel("Number of Values", fontsize=12)
    ax.set_ylabel("Load Time (s)", fontsize=12)
    ax.set_title(
        "Load Time Growth:\nAggregation vs. Baseline",
        fontsize=12,
        fontweight="bold",
        y=1.025
    )

# ---- Grid & legend ----
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="lower right", frameon=True)

if args.laporan:
    out_path = OUTPUT_DIR / "plot-agg-diff.laporan.svg"
else:
    out_path = OUTPUT_DIR / "plot-agg-diff.svg"

plt.rcParams["svg.fonttype"] = "none"  # keep text as text in SVG
plt.tight_layout()
plt.savefig(out_path, bbox_inches="tight", dpi=300)
plt.show()
print(f"Saved to {out_path.name}")