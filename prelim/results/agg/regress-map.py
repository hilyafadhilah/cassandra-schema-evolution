"""
Power-law (log-log) regression where the target is the load measured in
map.csv MINUS a per-(P,R) reference load defined in ref.csv.

Reference:
    ref.csv holds one baseline `load` for each (num_partitions,
    num_partition_rows) pair -- it does NOT depend on num_values. For every
    map.csv row, Y is computed by subtracting the reference load for that
    row's (P, R); the same reference is reused across all V variations of a
    given (P, R).

        Y = load_map(P,R,V) - load_ref(P,R)

Model (ordinary linear regression on logs):
    log(Y) = b0 + b1*log(P) + b2*log(R) + b3*log(V)
    => Y = exp(b0) * P^b1 * R^b2 * V^b3

NOTE: log requires Y > 0. Rows where load_map <= load_ref give Y <= 0 and
cannot enter a log fit; they are reported and excluded.

Requires: pandas, numpy, statsmodels
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

DATA_DIR = Path(__file__).parent / "data"
MAP_PATH = DATA_DIR / "map.csv"   # map.csv with per-row load measurements
REF_PATH = DATA_DIR / "base.csv"   # reference loads per (P,R) pair
KEYS = ["num_partitions", "num_partition_rows"]   # (P, R) reference key


def main():
    mp = pd.read_csv(MAP_PATH)
    rf = pd.read_csv(REF_PATH)[KEYS + ["load"]].rename(columns={"load": "load_ref"})

    # Attach the per-(P,R) reference load to every map row, then subtract.
    df = mp.merge(rf, on=KEYS, how="left")

    missing = int(df["load_ref"].isna().sum())
    if missing:
        pairs = df.loc[df["load_ref"].isna(), KEYS].drop_duplicates()
        print(f"WARNING: {missing} map rows have no matching (P,R) in ref.csv "
              f"and are dropped:\n{pairs.to_string(index=False)}\n")
        df = df.dropna(subset=["load_ref"])

    df["Y"] = df["load"] - df["load_ref"]

    # log domain: Y must be > 0
    usable = df["Y"] > 0
    n_drop = int((~usable).sum())
    if n_drop:
        print(f"WARNING: {n_drop} of {len(df)} rows have load_map <= load_ref "
              f"(Y <= 0) and are excluded from the log fit.\n")
    fit_df = df[usable].copy()

    P = fit_df["num_partitions"]
    R = fit_df["num_partition_rows"]
    V = fit_df["num_values"]

    # Fit: log(Y) ~ log P + log R + log V
    X = sm.add_constant(pd.DataFrame({
        "logP": np.log(P), "logR": np.log(R), "logV": np.log(V),
    }))
    model = sm.OLS(np.log(fit_df["Y"]), X).fit()
    b0 = model.params["const"]
    bP, bR, bV = model.params["logP"], model.params["logR"], model.params["logV"]

    # --- Report -------------------------------------------------------------
    print("=" * 66)
    print("Target: Y = load_map(P,R,V) - load_ref(P,R)   (fit on log scale)")
    print(f"  log(Y) = {b0:.4f} + {bP:.3f}*logP + {bR:.3f}*logR + {bV:.3f}*logV")
    print(f"  i.e.  Y = {np.exp(b0):.3e} * P^{bP:.3f} * R^{bR:.3f} * V^{bV:.3f}")
    print("=" * 66)
    print(f"rows used        : {len(fit_df)}  (of {len(df)})")
    print(f"R^2 (log scale)  : {model.rsquared:.4f}")
    print(f"Adjusted R^2     : {model.rsquared_adj:.4f}")
    print()
    print("Coefficients (dependent variable = log(Y)):")
    print(model.summary2().tables[1].to_string())

    # Back-transformed predictions on the Y scale.
    # fit_df["Y_actual"] = fit_df["Y"]
    # fit_df["Y_pred"] = np.exp(model.fittedvalues)
    # fit_df["residual"] = fit_df["Y_actual"] - fit_df["Y_pred"]
    # ss_res = (fit_df["residual"] ** 2).sum()
    # ss_tot = ((fit_df["Y_actual"] - fit_df["Y_actual"].mean()) ** 2).sum()
    # print(f"\nR^2 on the Y scale after back-transform: {1 - ss_res / ss_tot:.4f}")

    # fit_df.to_csv("load_ref_log_predictions.csv", index=False)
    # print("Wrote per-row predictions to load_ref_log_predictions.csv")


if __name__ == "__main__":
    main()