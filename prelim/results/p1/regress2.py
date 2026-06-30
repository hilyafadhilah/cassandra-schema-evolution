#!/usr/bin/env python3
"""
Fit the leaner QUADRATIC model for `unload` (five terms; the marginal
num_columns^2 term is dropped):

    unload = a*num_rows + b*num_columns + c*num_rows*num_columns
             + e*num_rows^2 + g

This model was selected over a log-transform of the target: on leave-one-out
cross-validation (original unload scale) the quadratic gave RMSE ~0.73 / R^2 ~0.98,
versus the log model's RMSE ~3.0 / R^2 ~0.67. Dropping the num_columns^2 term
leaves out-of-sample accuracy essentially unchanged (LOOCV RMSE ~0.73) while
keeping the model leaner.

Uses statsmodels OLS for full statistical output: coefficients, standard
errors, p-values, confidence intervals, R^2, AIC/BIC.

Usage:
    python fit_unload_quadratic.py [path/to/data.csv]

If no path is given, it defaults to ./data.csv
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

TARGET = "unload"


def build_design(r: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Design matrix: [intercept, r, c, r*c, r^2]."""
    return sm.add_constant(np.column_stack([r, c, r * c, r ** 2]))


def fit_quadratic(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Fit the leaner quadratic: unload ~ r + c + r*c + r^2 (with intercept)."""
    required = {"num_rows", "num_columns", TARGET}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {sorted(missing)}")

    r = df["num_rows"].to_numpy(dtype=float)
    c = df["num_columns"].to_numpy(dtype=float)
    y = df[TARGET].to_numpy(dtype=float)

    return sm.OLS(y, build_design(r, c)).fit()


def predict(result, num_rows: float, num_columns: float) -> float:
    """Predict unload for a single (num_rows, num_columns) pair."""
    g, a, b, c, e = result.params  # const, r, c, r*c, r^2
    return (
        g
        + a * num_rows
        + b * num_columns
        + c * num_rows * num_columns
        + e * num_rows ** 2
    )


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "data.csv"
    df = pd.read_csv(path)

    result = fit_quadratic(df)

    # --- Full statistical summary ---
    labels = [
        "const (g)",
        "num_rows (a)",
        "num_columns (b)",
        "rows*cols (c)",
        "num_rows^2 (e)",
    ]
    print(result.summary(xname=labels, yname=TARGET))

    # --- Compact equation + key fit metrics ---
    g, a, b, c, e = result.params
    n = len(df)
    rmse = float(np.sqrt(np.mean(result.resid ** 2)))

    print("\nFitted equation:")
    print(
        f"  {TARGET} = {a:.4f}*num_rows + {b:.4f}*num_columns "
        f"+ {c:.4f}*num_rows*num_columns\n"
        f"           + {e:.4f}*num_rows^2 + {g:.4f}"
    )
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