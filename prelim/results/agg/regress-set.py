"""
Linear regression for set.csv, with the target defined relative to a
per-(P,R) reference load from ref.csv.

Target:
    ref.csv holds one baseline `load` per (num_partitions,
    num_partition_rows) pair (independent of num_values). For each set.csv
    row, subtract the reference load for that row's (P, R); the same
    reference is reused across all V variations of a given (P, R).

        Y = load_set(P,R,V) - load_ref(P,R)

Model (linear in parameters):
    Y = b0 + b1 * (num_partitions * num_partition_rows * num_values)

Unlike the log fit used for map.csv, this is linear in Y, so rows where
Y <= 0 are perfectly valid and are KEPT.

Requires: pandas, numpy, statsmodels
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

DATA_DIR = Path(__file__).parent / "data"
SET_PATH = DATA_DIR / "set.csv"   # set.csv with per-row load measurements
REF_PATH = DATA_DIR / "base.csv"   # reference loads per (P,R) pair
KEYS = ["num_partitions", "num_partition_rows"]   # (P, R) reference key


def main():
    st = pd.read_csv(SET_PATH)
    rf = pd.read_csv(REF_PATH)[KEYS + ["load"]].rename(columns={"load": "load_ref"})

    # Attach the per-(P,R) reference load to every set row, then subtract.
    df = st.merge(rf, on=KEYS, how="left")

    missing = int(df["load_ref"].isna().sum())
    if missing:
        pairs = df.loc[df["load_ref"].isna(), KEYS].drop_duplicates()
        print(f"WARNING: {missing} set rows have no matching (P,R) in ref.csv "
              f"and are dropped:\n{pairs.to_string(index=False)}\n")
        df = df.dropna(subset=["load_ref"])

    # Y = load_set - load_ref, but never below 0: a load that comes in under
    # its reference is treated as "no excess load" (Y = 0) rather than negative.
    raw_diff = df["load"] - df["load_ref"]
    df["Y"] = raw_diff.clip(lower=0)
    n_clamped = int((raw_diff < 0).sum())
    if n_clamped:
        print(f"Note: {n_clamped} rows had load_set < load_ref and were "
              f"clamped to Y = 0.\n")

    P = df["num_partitions"]
    R = df["num_partition_rows"]
    V = df["num_values"]
    df["PRV"] = P * R * V

    # Fit: Y ~ const + PRV
    X = sm.add_constant(df[["PRV"]])
    model = sm.OLS(df["Y"], X).fit()
    b0 = model.params["const"]
    b1 = model.params["PRV"]

    # --- Report -------------------------------------------------------------
    print("=" * 64)
    print("Target: Y = load_set(P,R,V) - load_ref(P,R)")
    print(f"    Y = {b0:.4f} + {b1:.3e} * (P * R * V)")
    print("=" * 64)
    print(f"rows used        : {len(df)}  "
          f"({int((df['Y'] == 0).sum())} rows at Y = 0 after clamping)")
    print(f"R^2              : {model.rsquared:.4f}")
    print(f"Adjusted R^2     : {model.rsquared_adj:.4f}")
    print(f"Residual std     : {np.sqrt(model.scale):.3f}  "
          f"(noise floor; smaller differences are not meaningful)")
    print()
    print("Coefficients (dependent variable = Y):")
    print(model.summary2().tables[1].to_string())

    # Per-row predictions on the Y scale.
    # df["Y_actual"] = df["Y"]
    # df["Y_pred"] = model.fittedvalues
    # df["residual"] = df["Y_actual"] - df["Y_pred"]
    # df.to_csv("set_ref_predictions.csv", index=False)
    # print("\nWrote per-row predictions to set_ref_predictions.csv")


if __name__ == "__main__":
    main()