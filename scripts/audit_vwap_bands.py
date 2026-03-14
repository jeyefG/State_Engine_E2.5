#scripts/audit_vwap_bands.py
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()

    df = pd.read_parquet(Path(args.parquet))
    df["time"] = pd.to_datetime(df["time"], utc=False)

    if args.symbol:
        df = df[df["symbol"] == args.symbol].copy()

    req = ["close","ctx_vwap","ctx_vwap_sigma","ctx_vwap_hi","ctx_vwap_lo"]
    missing = [c for c in req if c not in df.columns]
    if missing:
        raise ValueError(f"Missing cols: {missing}")

    sigma = df["ctx_vwap_sigma"].replace(0, np.nan)
    z = (df["close"] - df["ctx_vwap"]) / sigma
    df["z"] = z

    df["outside"] = (df["close"] > df["ctx_vwap_hi"]) | (df["close"] < df["ctx_vwap_lo"])

    print(f"[OK] rows={len(df):,} cols={df.shape[1]:,}")
    print("[AUDIT] NaN% bands:", (df[req].isna().mean()*100).to_dict())
    print("[AUDIT] outside_rate_all:", float(df["outside"].mean()))

    # z distribution
    z_clean = df["z"].dropna()
    if len(z_clean) > 0:
        qs = z_clean.quantile([0.01,0.05,0.1,0.25,0.5,0.75,0.9,0.95,0.99]).to_dict()
        print("[AUDIT] z_quantiles:", {k: float(v) for k,v in qs.items()})
        print("[AUDIT] pct(|z|>2):", float((z_clean.abs() > 2).mean()))
        print("[AUDIT] pct(|z|>1.5):", float((z_clean.abs() > 1.5).mean()))
        print("[AUDIT] pct(|z|>1):", float((z_clean.abs() > 1).mean()))

    # If you have baseline markers in df (you don't), we can still approximate via LOOK_FOR_balance_* flags:
    lf_cols = [c for c in df.columns if c.startswith("LOOK_FOR_balance_")]
    if lf_cols:
        df["any_balance_lf"] = df[lf_cols].fillna(0).sum(axis=1) > 0
        sub = df[df["any_balance_lf"]].copy()
        if len(sub) > 0:
            print("[AUDIT] outside_rate_any_balance_lf:", float(sub["outside"].mean()))
            z2 = sub["z"].dropna()
            if len(z2) > 0:
                print("[AUDIT] pct(|z|>2) within balance_lf:", float((z2.abs() > 2).mean()))

if __name__ == "__main__":
    main()