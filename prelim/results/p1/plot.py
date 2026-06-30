"""
Scatter plot of load_s vs num_rows, with discrete colors per num_columns value.
A dashed line connects the num_columns=10 points to show the growth trend.
"""

import sys

import pandas as pd
import matplotlib.pyplot as plt

# ---- Load data ----
y_col = sys.argv[1] if len(sys.argv) > 1 else "load"
df = pd.read_csv("data.csv")

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
    sub = df[df["num_columns"] == val]
    ax.scatter(
        sub["num_rows"],
        sub[y_col],
        color=color_map[val],
        label=f"{val} column",
        s=70,
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )

# ---- Dashed trend lines for selected num_columns values ----
TREND_VALUES = [5, 10, 20]
for val in TREND_VALUES:
    ref = df[df["num_columns"] == val].sort_values("num_rows")
    ax.plot(
        ref["num_rows"],
        ref[y_col],
        linestyle="--",
        color=color_map[val],   # match the scatter color for this value
        linewidth=1.5,
        label=f"Tren {val} column",
        zorder=2,
    )

# ---- Labels, title, grid, legend ----
ax.set_xlabel("Jumlah Row (× 100.000)", fontsize=12)
ax.set_ylabel(f"Waktu {y_col.capitalize()} (s)", fontsize=12)
# ax.set_title("Load time vs. number of rows", fontsize=14, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(
    # title="num_columns",
    loc="upper left",
    frameon=True,
    ncol=2,            # two columns so the legend stays compact
    fontsize=9,
)

dst = f"{y_col}_plot.png"

plt.tight_layout()
plt.savefig(dst, dpi=150)
plt.show()
print(f"Saved to {dst}")