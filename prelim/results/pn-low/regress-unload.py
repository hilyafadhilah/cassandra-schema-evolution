#!/usr/bin/env python3
"""
Linear regression on partition-data for the target Y = unload.

Fits and compares three models:

    Model 1:  unload ~ c + p + r + intercept
    Model 2:  unload ~ c + p + r + p*r + intercept
    Reduced:  unload ~ c + p + intercept

where
    p = num_partitions
    r = num_partition_rows
    c = num_columns

Background:
    Unlike `load`, the `unload` target is driven almost entirely by the
    number of partitions (p) and columns (c). The per-partition row count
    (r) carries essentially no signal (corr(unload, r) ~ 0.01), so neither
    r nor the interaction p*r helps. The Reduced model (c + p) therefore
    has the best adjusted R^2 and is the recommended fit. Note also that
    `unload` is nearly discrete (most values are exactly 0.0 or 1.0), so a
    logistic/threshold model may fit better than OLS if you need to predict
    that step behavior precisely.

Usage:
    python unload_regression.py [path/to/data.csv]

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
    """Read the CSV and return the dataframe, dropping blank/NaN rows."""
    df = pd.read_csv(path).dropna(how="all")  # drop fully empty trailing rows
    required = {"num_partitions", "num_partition_rows", "num_columns", "unload"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
    df = df.dropna(subset=list(required))
    return df


def fit_model(Y, X, name):
    """Fit an OLS model, print a summary, and return (model, rmse)."""
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
    path = Path(__file__).parent / "data.csv"
    df = load_data(path)

    Y = df["unload"]
    p = df["num_partitions"]
    r = df["num_partition_rows"]
    c = df["num_columns"]

    # Quick look at how unload relates to each predictor
    print("Correlations with unload:")
    corr = df[["num_columns", "num_partitions", "num_partition_rows", "unload"]] \
        .corr()["unload"].drop("unload")
    print(corr.to_string(float_format=lambda v: f"{v:.4f}"))
    print()

    # Model 1: c, p, r + intercept
    X1 = pd.DataFrame({"c": c, "p": p, "r": r})
    m1, rmse1 = fit_model(Y, X1, "MODEL 1: unload ~ c + p + r + intercept")

    # Model 2: c, p, r, p*r + intercept
    X2 = pd.DataFrame({"c": c, "p": p, "r": r, "p_r": p * r})
    m2, rmse2 = fit_model(Y, X2, "MODEL 2: unload ~ c + p + r + p*r + intercept")

    # Reduced model: c, p + intercept (recommended)
    X3 = pd.DataFrame({"c": c, "p": p})
    m3, rmse3 = fit_model(Y, X3, "REDUCED: unload ~ c + p + intercept  (recommended)")

    # Side-by-side comparison
    print("=" * 64)
    print("COMPARISON")
    print("-" * 64)
    print(f"{'metric':<14}{'Model 1':>13}{'Model 2':>13}{'Reduced':>13}")
    print(f"{'R^2':<14}{m1.rsquared:>13.4f}{m2.rsquared:>13.4f}{m3.rsquared:>13.4f}")
    print(f"{'adj. R^2':<14}{m1.rsquared_adj:>13.4f}{m2.rsquared_adj:>13.4f}{m3.rsquared_adj:>13.4f}")
    print(f"{'RMSE':<14}{rmse1:>13.4f}{rmse2:>13.4f}{rmse3:>13.4f}")
    print("=" * 64)

    # Predict helper for the Reduced model (const, c, p order)
    def predict_unload(c_val, p_val):
        x = [1.0, c_val, p_val]
        return float(np.dot(m3.params.values, x))

    print("\nExample (Reduced model): predicted unload for c=10, p=50000:")
    print(f"  {predict_unload(10, 50000):.3f}")


if __name__ == "__main__":
    main()