#!/usr/bin/env python3
"""
Fit and evaluate linear models for `unload`.

The key structural finding for this dataset is that `unload` scales with the
*product* of the three design parameters (total data volume = partitions x
rows x columns), not with their additive sum. The recommended model therefore
includes the triple-product interaction term.

Usage:
    python unload_regression.py [path/to/data.csv]

Dependencies:
    pip install pandas numpy statsmodels scikit-learn
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.model_selection import KFold

# Short aliases keep the Patsy formulas readable.
COLUMN_ALIASES = {
    "num_partitions": "P",
    "num_partition_rows": "R",
    "num_columns": "C",
}

# Candidate models, keyed by a human label -> Patsy formula.
CANDIDATE_MODELS = {
    "volume + main (recommended)": "unload ~ P + R + C + P:R:C",
    "volume only (PRC)":           "unload ~ P:R:C",
}

RECOMMENDED = "volume + main (recommended)"


def load_data(path: str) -> pd.DataFrame:
    """Load the CSV, rename design columns to short aliases, drop blank rows."""
    df = pd.read_csv(path)
    df = df.rename(columns=COLUMN_ALIASES)
    df = df.dropna().reset_index(drop=True)
    return df


def cross_validate(formula: str, df: pd.DataFrame, n_splits: int = 10,
                   seed: int = 0) -> tuple[float, float]:
    """Return (mean out-of-sample R^2, mean RMSE) over K folds."""
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    r2s, rmses = [], []
    for train_idx, test_idx in kf.split(df):
        model = smf.ols(formula, df.iloc[train_idx]).fit()
        pred = model.predict(df.iloc[test_idx])
        y = df.iloc[test_idx]["unload"]
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2s.append(1.0 - ss_res / ss_tot)
        rmses.append(np.sqrt(np.mean((y - pred) ** 2)))
    return float(np.mean(r2s)), float(np.mean(rmses))


def compare_models(df: pd.DataFrame) -> pd.DataFrame:
    """Fit every candidate, returning in-sample and cross-validated metrics."""
    rows = []
    for label, formula in CANDIDATE_MODELS.items():
        fit = smf.ols(formula, df).fit()
        cv_r2, cv_rmse = cross_validate(formula, df)
        rows.append({
            "model": label,
            "formula": formula,
            "R2_in_sample": fit.rsquared,
            "CV_R2": cv_r2,
            "CV_RMSE": cv_rmse,
            "n_params": len(fit.params),
            "AIC": fit.aic,
        })
    return pd.DataFrame(rows).sort_values("CV_R2", ascending=False)


def report_final_model(df: pd.DataFrame, formula: str) -> None:
    """Print the full statsmodels summary plus a plain-text equation."""
    fit = smf.ols(formula, df).fit()
    print("\n" + "=" * 70)
    print(f"FINAL MODEL:  {formula}")
    print("=" * 70)
    print(fit.summary())

    print("\nFitted equation:")
    terms = []
    for name, coef in fit.params.items():
        if name == "Intercept":
            terms.append(f"{coef:.4g}")
        else:
            terms.append(f"({coef:.4g} * {name})")
    print("  unload = " + " + ".join(terms))

    if "P:R:C" in fit.params.index:
        per_unit = fit.params["P:R:C"]
        if per_unit > 0:
            print(f"\n  => roughly 1 unit of unload per "
                  f"{1 / per_unit / 1e6:.2f} million cells (P*R*C).")


def main() -> None:
    path = Path(__file__).parent / "data.csv"
    df = load_data(path)
    print(f"Loaded {len(df)} rows from {path}")
    print(f"Columns (aliased): {list(df.columns)}\n")

    comparison = compare_models(df)
    with pd.option_context("display.float_format", lambda v: f"{v:.4f}",
                           "display.max_colwidth", 40, "display.width", 120):
        print("Model comparison (ranked by cross-validated R^2):")
        print(comparison.to_string(index=False))

    report_final_model(df, CANDIDATE_MODELS[RECOMMENDED])


if __name__ == "__main__":
    main()