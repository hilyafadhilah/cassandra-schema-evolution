#!/usr/bin/env python3
"""
Linear regression on partition-load data.

Fits and compares two models for the target Y = load:

    Model 1:  load ~ c + p + r + intercept
    Model 2:  load ~ c + p + r + p*r + intercept

where
    p = num_partitions
    r = num_partition_rows
    c = num_columns

Usage:
    python load_regression.py [path/to/data.csv]

If no path is given, it defaults to "data.csv" in the current directory.

Dependencies:
    pandas, numpy, statsmodels
        pip install pandas numpy statsmodels
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm


def load_data(path):
    """Read the CSV and return the predictor/target columns, dropping blank rows."""
    df = pd.read_csv(path).dropna(how="all")  # drop fully empty trailing rows
    required = {"num_partitions", "num_partition_rows", "num_columns", "load"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
    # Drop any remaining rows with NaNs in the columns we use
    df = df.dropna(subset=list(required))
    return df


def fit_model(Y, X, name):
    """Fit an OLS model, print a summary, and return the fitted result."""
    X = sm.add_constant(X)            # adds the intercept term
    model = sm.OLS(Y, X).fit()

    rmse = np.sqrt(model.mse_resid)   # residual standard error

    print("=" * 64)
    print(name)
    print("-" * 64)
    print(f"n            = {int(model.nobs)}")
    print(f"R^2          = {model.rsquared:.4f}")
    print(f"adj. R^2     = {model.rsquared_adj:.4f}")
    print(f"RMSE         = {rmse:.4f}")
    print(f"F p-value    = {model.f_pvalue:.3e}")
    print("\nCoefficients:")
    coefs = pd.DataFrame({
        "coef": model.params,
        "p_value": model.pvalues,
    })
    print(coefs.to_string(float_format=lambda v: f"{v:.6g}"))
    print()
    return model, rmse


def main():
    path = Path(__file__).parent / "data.csv"  # default path
    df = load_data(path)

    Y = df["load"]
    p = df["num_partitions"]
    r = df["num_partition_rows"]
    c = df["num_columns"]

    # Model 1: c, p, r + intercept
    X1 = pd.DataFrame({"c": c, "p": p, "r": r})
    m1, rmse1 = fit_model(Y, X1, "MODEL 1: load ~ c + p + r + intercept")

    # Model 2: c, p, r, p*r + intercept
    X2 = pd.DataFrame({"c": c, "p": p, "r": r, "p_r": p * r})
    m2, rmse2 = fit_model(Y, X2, "MODEL 2: load ~ c + p + r + p*r + intercept")

    # Side-by-side comparison
    print("=" * 64)
    print("COMPARISON")
    print("-" * 64)
    print(f"{'metric':<14}{'Model 1':>14}{'Model 2':>14}")
    print(f"{'R^2':<14}{m1.rsquared:>14.4f}{m2.rsquared:>14.4f}")
    print(f"{'adj. R^2':<14}{m1.rsquared_adj:>14.4f}{m2.rsquared_adj:>14.4f}")
    print(f"{'RMSE':<14}{rmse1:>14.4f}{rmse2:>14.4f}")
    print("=" * 64)

    # Predict helper for Model 2 (the better fit): build the row in the
    # same column order statsmodels used (const, c, p, r, p_r).
    def predict_load(c_val, p_val, r_val):
        x = [1.0, c_val, p_val, r_val, p_val * r_val]
        return float(np.dot(m2.params.values, x))

    # Example prediction
    print("\nExample (Model 2): predicted load for c=10, p=50000, r=20:")
    print(f"  {predict_load(10, 50000, 20):.3f}")


if __name__ == "__main__":
    main()