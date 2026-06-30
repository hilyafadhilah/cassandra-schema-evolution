#!/usr/bin/env python3
"""
Fit the interaction regression model for query/column timing data.

    time_ms = a * n_queries
            + b * n_columns
            + c * n_queries * n_columns
            + d

Usage:
    python fit_interaction_model.py [data.csv]

If no path is given, it looks for "data.csv" in the current directory.

Requires: pandas, numpy, statsmodels
    pip install pandas numpy statsmodels
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def load_data(path: Path) -> pd.DataFrame:
    """Read the CSV and validate the expected columns are present."""
    df = pd.read_csv(path)
    required = {"n_queries", "n_columns", "time_ms"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {sorted(missing)}")
    return df


def fit_model(df: pd.DataFrame):
    """
    Fit the bilinear interaction model with OLS.

    Standard errors use the HC3 heteroscedasticity-consistent estimator,
    since latency variance tends to grow with the mean. This does not change
    the fitted coefficients, only the standard errors / p-values used for
    inference, making them robust to non-constant residual variance.
    """
    # The ':' term is the interaction (n_queries * n_columns); the intercept
    # is included automatically and plays the role of d.
    model = smf.ols("time_ms ~ n_queries + n_columns + n_queries:n_columns", data=df)
    return model.fit(cov_type="HC3")


def report(result) -> None:
    """Print the coefficients in the a/b/c/d naming plus fit diagnostics."""
    params = result.params
    a = params["n_queries"]
    b = params["n_columns"]
    c = params["n_queries:n_columns"]
    d = params["Intercept"]

    print("=" * 64)
    print("Fitted model:  time_ms = a*n_queries + b*n_columns")
    print("                       + c*n_queries*n_columns + d")
    print("=" * 64)
    print(f"  a (n_queries)            = {a:12.6f}  ms / query")
    print(f"  b (n_columns)            = {b:12.6f}  ms / column")
    print(f"  c (n_queries*n_columns)  = {c:12.6f}  ms / (query*column)")
    print(f"  d (intercept)            = {d:12.6f}  ms")
    print()
    print("  Per-coefficient inference (HC3 robust standard errors):")
    summary = pd.DataFrame(
        {
            "coef": result.params,
            "std_err": result.bse,
            "t": result.tvalues,
            "p_value": result.pvalues,
            "ci_low": result.conf_int()[0],
            "ci_high": result.conf_int()[1],
        }
    )
    with pd.option_context("display.float_format", lambda v: f"{v:.6g}"):
        print(summary.to_string())
    print()
    print("  Goodness of fit:")
    print(f"    R-squared          = {result.rsquared:.4f}")
    print(f"    Adjusted R-squared = {result.rsquared_adj:.4f}")
    print(f"    AIC                = {result.aic:.1f}")
    print(f"    BIC                = {result.bic:.1f}")
    print(f"    Residual std dev   = {np.sqrt(result.scale):.4f} ms")
    print(f"    Observations       = {int(result.nobs)}")
    print("=" * 64)


def predict(result, n_queries: float, n_columns: float) -> float:
    """Predict time_ms for a single (n_queries, n_columns) point."""
    point = pd.DataFrame({"n_queries": [n_queries], "n_columns": [n_columns]})
    return float(result.predict(point).iloc[0])


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "data.csv"
    df = load_data(path)
    result = fit_model(df)
    report(result)

    # A couple of example predictions at the corners of the design space.
    print("\nExample predictions:")
    for q, c in [(1, 1), (50, 10), (100, 20)]:
        print(f"  n_queries={q:>4}, n_columns={c:>3}  ->  {predict(result, q, c):8.2f} ms")


if __name__ == "__main__":
    main()