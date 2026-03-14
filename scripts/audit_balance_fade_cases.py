#scripts/audit_balance_fade_cases.py
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions_with_side_csv", required=True)
    ap.add_argument("--enriched_parquet", required=True)
    ap.add_argument("--out_csv", default=None)
    args = ap.parse_args()

    df_dec = pd.read_csv(Path(args.decisions_with_side_csv))
    # handle ts/time naming
    time_col = "time" if "time" in df_dec.columns else ("ts" if "ts" in df_dec.columns else None)
    if time_col is None:
        raise ValueError("No time/ts column found in decisions_with_side")

    df_dec[time_col] = pd.to_datetime(df_dec[time_col], utc=False)

    # keep only balance fades
    fades = df_dec[
        (df_dec["setup_family"] == "balance_stability_fade")
        & (df_dec["side_intent"].isin(["LONG", "SHORT"]))
    ].copy()

    print(f"[AUDIT] balance_stability_fade rows: {len(fades)}")
    if fades.empty:
        print("[NO DATA] nothing to audit.")
        return

    df_en = pd.read_parquet(Path(args.enriched_parquet))
    df_en["time"] = pd.to_datetime(df_en["time"], utc=False)

    # merge to get context + vwap bands columns
    cols_need = [
        "symbol","time","close","ctx_vwap","ctx_vwap_sigma","ctx_vwap_hi","ctx_vwap_lo",
        "ctx_dist_vwap_atr","ctx_session_bucket","ctx_state_age","quality_label_full",
        "LOOK_FOR_balance_compression","LOOK_FOR_balance_vwap_proximity","LOOK_FOR_balance_extreme_to_center",
        "margin","state_hat"
    ]
    cols_need = [c for c in cols_need if c in df_en.columns]
    df_m = fades.merge(df_en[cols_need], left_on=["symbol", time_col], right_on=["symbol","time"], how="left")

    # compute z
    df_m["z"] = (df_m["close"] - df_m["ctx_vwap"]) / df_m["ctx_vwap_sigma"].replace(0, np.nan)

    show_cols = [
        "symbol", time_col, "side_intent", "setup_family",
        "close","ctx_vwap","ctx_vwap_sigma","z",
        "ctx_vwap_hi","ctx_vwap_lo","ctx_dist_vwap_atr",
        "ctx_session_bucket","ctx_state_age","quality_label_full",
        "LOOK_FOR_balance_compression","LOOK_FOR_balance_vwap_proximity","LOOK_FOR_balance_extreme_to_center",
        "margin","state_hat"
    ]
    show_cols = [c for c in show_cols if c in df_m.columns]
    df_out = df_m[show_cols].sort_values(time_col)

    print(df_out.to_string(index=False))

    if args.out_csv:
        p = Path(args.out_csv)
        p.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(p, index=False)
        print("[OK] wrote:", p)

if __name__ == "__main__":
    main()