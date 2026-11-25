#!/usr/bin/env python3
"""
M2 regression for T_load(num_columns, num_partitions, num_partition_rows).

Model M2:
    load ~ num_columns
         + num_partitions
         + num_partition_rows
         + (num_partitions * num_partition_rows)

The standalone `num_partitions` term lets the model account for
partition-management overhead independently of total row count -- i.e. two
configurations with the same total rows but different partition layouts can
still get different predicted load times.

Usage:
    python m2_regression.py [path/to/data.csv]

Requires: pandas, statsmodels
    pip install pandas statsmodels
"""

import sys
import pandas as pd
import statsmodels.formula.api as smf
from pathlib import Path

# ----------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------
csv_path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "data.csv"
df = pd.read_csv(csv_path)

required = {"num_columns", "num_partitions", "num_partition_rows", "load"}
missing = required - set(df.columns)
if missing:
    raise SystemExit(f"CSV is missing required columns: {sorted(missing)}")

# ----------------------------------------------------------------------
# Feature: the partitions x rows interaction (== total rows)
# ----------------------------------------------------------------------
df["part_x_rows"] = df["num_partitions"] * df["num_partition_rows"]

# ----------------------------------------------------------------------
# Fit M2
# ----------------------------------------------------------------------
formula = (
    "load ~ num_columns + num_partitions + num_partition_rows + part_x_rows"
)
model = smf.ols(formula, data=df).fit()

# ----------------------------------------------------------------------
# Full statistical report
# ----------------------------------------------------------------------
print(model.summary())

# ----------------------------------------------------------------------
# Fit quality summary
# ----------------------------------------------------------------------
pred = model.predict(df)
resid = (df["load"] - pred).abs()
print("\n" + "=" * 60)
print("FIT QUALITY")
print("=" * 60)
print(f"R-squared           : {model.rsquared:.4f}")
print(f"Adjusted R-squared  : {model.rsquared_adj:.4f}")
print(f"AIC / BIC           : {model.aic:.1f} / {model.bic:.1f}")
print(f"Mean abs residual   : {resid.mean():.3f}")
print(f"Max  abs residual   : {resid.max():.3f}")

# ----------------------------------------------------------------------
# Human-readable fitted equation
# ----------------------------------------------------------------------
c = model.params
print("\n" + "=" * 60)
print("FITTED EQUATION")
print("=" * 60)
print(
    "T_load = "
    f"{c['Intercept']:.6g}\n"
    f"       + {c['num_columns']:.6g} * num_columns\n"
    f"       + {c['num_partitions']:.6g} * num_partitions\n"
    f"       + {c['num_partition_rows']:.6g} * num_partition_rows\n"
    f"       + {c['part_x_rows']:.6g} * (num_partitions * num_partition_rows)"
)


# ----------------------------------------------------------------------
# Reusable predictor
# ----------------------------------------------------------------------
def predict_load(num_columns, num_partitions, num_partition_rows):
    """Return predicted T_load for a single configuration."""
    return (
        c["Intercept"]
        + c["num_columns"] * num_columns
        + c["num_partitions"] * num_partitions
        + c["num_partition_rows"] * num_partition_rows
        + c["part_x_rows"] * num_partitions * num_partition_rows
    )


if __name__ == "__main__":
    # Example: 10 columns, 1000 partitions of 100 rows each
    example = predict_load(num_columns=10, num_partitions=1000, num_partition_rows=100)
    print("\nExample prediction (10 cols, 1000 partitions x 100 rows): "
          f"{example:.2f} s")