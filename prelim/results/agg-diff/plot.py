"""
Plot the ratio (ac_2 - 3.2) / (ac_1 - 3.2) for each agg_type,
with a horizontal reference line at y=2 to show convergence to a 2:1 ratio.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ---- Load data ----
df = pd.read_csv(Path(__file__).parent / "ratio.csv")

# ---- Compute the ratio ----
REFERENCE = 3.2
df["ratio"] = (df["ac_2"] - REFERENCE) / (df["ac_1"] - REFERENCE)

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
ax.set_xlabel("Jumlah Value", fontsize=12)
ax.set_ylabel("Rasio Overhead", fontsize=12)
# ax.set_title("Convergence toward a 2:1 ratio", fontsize=14, fontweight="medium")

# ---- Zoom the Y-axis so convergence is visible ----
ax.set_ylim(1.0, 2.5)

# ---- Grid & legend ----
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="lower right", frameon=True)

plt.tight_layout()
plt.savefig(Path(__file__).parent / "ratio_plot.png", dpi=150)
plt.show()
print("Saved to ratio_plot.png")