"""
Cost gap vs. runtime gap per (evol, subcase), EB families only.

Reads the raw long-format diff.csv, reshapes it to one row per
(evol, subcase), computes the <method>-minus-qmin gaps for both cost and
runtime, and draws a scatter with an OLS trend line.

The method compared against qmin is selected on the command line:

    python diff.py            # defaults to qbal
    python diff.py qbal       # qbal  - qmin
    python diff.py codevo     # codevo - qmin

The output filename follows the chosen method, e.g.
    qbal_vs_qmin_EBonly.png  /  codevo_vs_qmin_EBonly.png

Input columns (long format, 2 rows per group):
    evol, subcase, value_type ('cost' | 'res'), qmin, qbal, codevo
Numeric values use a comma decimal separator; 'res' values carry a
trailing 's' (seconds).
"""

import argparse
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import font_manager

# --- CLI: which method column to compare against qmin ----------------
METHOD_LABEL = {
    'qbal': 'Penyeimbangan Cost',
    'codevo': 'CoDEvo',
}

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('method', nargs='?', choices=['qbal', 'codevo'], default='qbal',
                    help="Method column to compare against qmin (default: qbal)")
args = parser.parse_args()
METHOD = args.method

# --- Use Arial (falls back to metric-compatible fonts if unavailable) ---
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'Liberation Sans', 'DejaVu Sans']
plt.rcParams['font.serif'] = ['Cambria Math', 'Times New Roman', 'DejaVu Serif']

CSV_PATH = Path(__file__).parent / 'diff.csv'
OUT_PATH = Path(__file__).parent / f'{METHOD}_vs_qmin_EBonly.png'


def parse_num(v):
    """'17,8s' -> 17.8 ; '11,22' -> 11.22 ; '-2,43' -> -2.43"""
    s = str(v).strip()
    if s.endswith('s'):
        s = s[:-1]
    return float(s.replace(',', '.'))


# --- Load & reshape long -> wide -------------------------------------
df = pd.read_csv(CSV_PATH)
df['qmin'] = df['qmin'].map(parse_num)
df[METHOD] = df[METHOD].map(parse_num)

wide = df.pivot_table(index=['evol', 'subcase'],
                      columns='value_type',
                      values=['qmin', METHOD])
wide.columns = [f'{a}.{b}' for a, b in wide.columns]
wide = wide.reset_index()

wide['cost_diff'] = wide[f'{METHOD}.cost'] - wide['qmin.cost']
wide['res_diff']  = wide[f'{METHOD}.res']  - wide['qmin.res']

# --- Exclude EQ families ---------------------------------------------
wide = wide[~wide['evol'].str.startswith('EQ')]
wide = wide.sort_values(['evol', 'subcase']).reset_index(drop=True)

# --- Plot ------------------------------------------------------------
x, y = wide['cost_diff'].values, wide['res_diff'].values
evols = sorted(wide['evol'].unique())
cmap = plt.colormaps['tab10']
color_map = {e: cmap(i % 10) for i, e in enumerate(evols)}

fig, ax = plt.subplots(figsize=(10, 7.5), dpi=150)

# OLS trend line
m, b = np.polyfit(x, y, 1)
r = np.corrcoef(x, y)[0, 1]
xs = np.linspace(x.min(), x.max(), 100)
ax.plot(xs, m * xs + b, color='#444', lw=1.4, ls='--', zorder=1)

# Correlation label, horizontal, just above the right end of the line.
x_lab = x.max() - (0.05 * (x.max() - x.min())) # small horizontal offset
y_lab = m * x_lab + b + (0.02 * (y.max() - y.min())) # small vertical offset
ax.text(x_lab, y_lab, f'r = {r:.2f}   R\u00b2 = {r**2:.2f}',
        ha='right', va='bottom', fontsize=16, color='#333',
        fontweight='bold', fontfamily='serif', zorder=2)

# points colored by evol
for e in evols:
    sub = wide[wide['evol'] == e]
    ax.scatter(sub['cost_diff'], sub['res_diff'], s=80,
               color=color_map[e], edgecolor='white', linewidth=0.6,
               label=e, zorder=3)

ax.set_xlabel('Selisih Cost', fontsize=12)
ax.set_ylabel('Selisih Runtime', fontsize=12)
ax.set_title(f'Perbandingan Selisih Cost dan Runtime\nMetode {METHOD_LABEL[METHOD]} vs. Minimalisasi Cost',
             fontsize=13, fontweight='bold', pad=12)
ax.grid(True, alpha=0.25, lw=0.6)
ax.axhline(0, color='#bbb', lw=0.8)
ax.axvline(0, color='#bbb', lw=0.8)
ax.legend(title='Evolusi', fontsize=9.5, title_fontsize=10,
          loc='upper left', framealpha=0.9)

fig.tight_layout()
fig.savefig(OUT_PATH, bbox_inches='tight')
print(f'Saved {OUT_PATH}  ({len(wide)} points, r = {r:.3f})')