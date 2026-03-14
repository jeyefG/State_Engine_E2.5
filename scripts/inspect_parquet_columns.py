#scripts/inspect_parquet_columns.py
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True, type=str)
    ap.add_argument("--head", type=int, default=3)
    args = ap.parse_args()

    p = Path(args.parquet)
    if not p.exists():
        raise FileNotFoundError(p)

    df = pd.read_parquet(p)

    print(f"[OK] loaded: {p}")
    print(f"rows={len(df):,} cols={df.shape[1]:,}\n")

    # Column list
    cols = list(df.columns)
    print("COLUMNS:")
    for c in cols:
        print(" -", c)

    # Quick checks for VWAP-ish fields
    keywords = ["vwap", "sigma", "std", "band", "atr", "dist", "ctx_dist_vwap_atr"]
    hits = [c for c in cols if any(k.lower() in c.lower() for k in keywords)]
    print("\nPOTENTIAL VWAP/SIGMA/ATR COLUMNS:")
    for c in hits:
        print(" *", c)

    # NaN rates for those hits
    if hits:
        print("\nNaN rates (only for hits):")
        nan_rates = (df[hits].isna().mean() * 100).sort_values(ascending=False)
        for c, r in nan_rates.items():
            print(f" - {c}: {r:.2f}%")

    # Show head
    print("\nHEAD:")
    print(df.head(args.head).to_string(index=False))


if __name__ == "__main__":
    main()