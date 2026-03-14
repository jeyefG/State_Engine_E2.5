# scripts/build_phase_f_enriched_ohlc.py
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def _to_naive_dt(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def main(prices_parquet: str, context_parquet: str, out_parquet: str, symbol: str | None = None) -> int:
    prices_path = Path(prices_parquet)
    ctx_path = Path(context_parquet)
    out_path = Path(out_parquet)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    px = pd.read_parquet(prices_path)
    ctx = pd.read_parquet(ctx_path)

    # Normalize time columns
    if "time" not in px.columns:
        raise SystemExit("prices_parquet missing required column: time")
    if "time" not in ctx.columns:
        raise SystemExit("context_parquet missing required column: time")

    px["time"] = _to_naive_dt(px["time"])
    ctx["time"] = _to_naive_dt(ctx["time"])

    # Basic required columns
    for c in ["symbol", "open", "high", "low", "close"]:
        if c not in px.columns:
            raise SystemExit(f"prices_parquet missing required column: {c}")
    for c in ["symbol", "state_hat"]:
        if c not in ctx.columns:
            raise SystemExit(f"context_parquet missing required column: {c}")

    # Optional symbol filter
    if symbol:
        px = px[px["symbol"] == symbol].copy()
        ctx = ctx[ctx["symbol"] == symbol].copy()

    # Deduplicate in case of duplicates
    px = px.sort_values(["symbol", "time"]).drop_duplicates(["symbol", "time"], keep="last")
    ctx = ctx.sort_values(["symbol", "time"]).drop_duplicates(["symbol", "time"], keep="last")

    merged = px.merge(ctx, on=["symbol", "time"], how="left", validate="one_to_one")

    # Report coverage
    miss = merged["state_hat"].isna().mean()
    print(f"[INFO] context join missing rate: {miss:.2%}")

    merged.to_parquet(out_path, index=False)
    print(f"[OK] wrote: {out_path}")
    print(f"[INFO] columns: {len(merged.columns)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices_parquet", required=True)
    ap.add_argument("--context_parquet", required=True)
    ap.add_argument("--out_parquet", required=True)
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()

    raise SystemExit(main(
        prices_parquet=args.prices_parquet,
        context_parquet=args.context_parquet,
        out_parquet=args.out_parquet,
        symbol=args.symbol,
    ))