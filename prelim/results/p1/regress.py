#!/usr/bin/env python3
"""
Fit Model 1 for `load` (no interaction term):

    load = a*num_rows + b*num_columns + c

Uses statsmodels OLS for full statistical output: coefficients, standard
errors, p-values, confidence intervals, R^2, AIC/BIC.

Usage:
    python fit_load_model1.py [path/to/data.csv]

If no path is given, it defaults to ./data.csv
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

TARGET = "load"


def build_design(r: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Design matrix: [intercept, num_rows, num_columns]."""
    return sm.add_constant(np.column_stack([r, c]))


def fit_model1(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Fit load ~ num_rows + num_columns (with intercept)."""
    required = {"num_rows", "num_columns", TARGET}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {sorted(missing)}")

    r = df["num_rows"].to_numpy(dtype=float)
    c = df["num_columns"].to_numpy(dtype=float)
    y = df[TARGET].to_numpy(dtype=float)

    return sm.OLS(y, build_design(r, c)).fit()


def predict(result, num_rows: float, num_columns: float) -> float:
    """Predict load for a single (num_rows, num_columns) pair."""
    c, a, b = result.params  # const, num_rows, num_columns
    return c + a * num_rows + b * num_columns


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'data.csv'
    df = pd.read_csv(path)

    result = fit_model1(df)

    # --- Full statistical summary ---
    labels = ["const (c)", "num_rows (a)", "num_columns (b)"]
    print(result.summary(xname=labels, yname=TARGET))

    # --- Compact equation + key fit metrics ---
    c, a, b = result.params
    n = len(df)
    rmse = float(np.sqrt(np.mean(result.resid ** 2)))

    print("\nFitted equation:")
    print(f"  {TARGET} = {a:.4f}*num_rows + {b:.4f}*num_columns + {c:.4f}")
    print("\nFit quality:")
    print(f"  R^2      = {result.rsquared:.5f}")
    print(f"  Adj R^2  = {result.rsquared_adj:.5f}")
    print(f"  RMSE     = {rmse:.4f}  (n = {n})")
    print(f"  AIC/BIC  = {result.aic:.2f} / {result.bic:.2f}")

    # --- Example prediction ---
    example = predict(result, num_rows=5, num_columns=12)
    print(f"\nExample: predicted {TARGET} at (num_rows=5, num_columns=12) = {example:.2f}")


if __name__ == "__main__":
    main()