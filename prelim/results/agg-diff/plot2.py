"""
Plot the ratio (ac_2 - 3.2) / (ac_1 - 3.2) for each agg_type,
with a horizontal reference line at y=2 to show convergence to a 2:1 ratio.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

REFERENCE = 3.2

# ---- Load data ----
df = pd.read_csv(Path(__file__).parent / "data.csv")

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
        group["ac_1"],
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
ax.set_xlabel("Jumlah Value", fontsize=12)
ax.set_ylabel("Waktu Load (s)", fontsize=12)
# ax.set_title(
#     "Waktu Load vs. Jumlah Field\n"
#     "Jumlah partition = 100, jumlah row/partition = 1000\n",
#     fontsize=12,
# )

# ---- Grid & legend ----
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="lower right", frameon=True)

plt.tight_layout()
plt.savefig(Path(__file__).parent / "diff_plot.png", dpi=150)
plt.show()
print("Saved to diff_plot.png")