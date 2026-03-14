# scripts/build_barstream_enriched.py
from __future__ import annotations

from pathlib import Path
import pandas as pd


def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_localize(None)
    return dt


def diagnose_nearest_delta(ctx: pd.DataFrame, prices: pd.DataFrame) -> pd.Timedelta:
    """
    Diagnostic only (NOT used for final merge): estimates systematic time shift.
    Uses merge_asof nearest within tolerance to infer modal delta.
    """
    l = ctx[["symbol", "time"]].sort_values(["symbol", "time"])
    r = prices[["symbol", "time"]].sort_values(["symbol", "time"])

    out = pd.merge_asof(
        l, r,
        on="time", by="symbol",
        direction="nearest",
        tolerance=pd.Timedelta(hours=6),
        suffixes=("", "_r"),
    )
    delta = (out["time"] - out["time_r"]).dropna()
    if delta.empty:
        return pd.Timedelta(0)
    return delta.mode().iloc[0]


def main(
    context_parquet: str,
    prices_parquet: str,
    out_parquet: str,
    min_coverage: float = 0.995,
) -> None:
    ctx = pd.read_parquet(context_parquet)
    prices = pd.read_parquet(prices_parquet)

    if "time" not in ctx.columns or "symbol" not in ctx.columns:
        raise RuntimeError("Context parquet debe contener columnas 'symbol' y 'time'.")
    if "time" not in prices.columns or "symbol" not in prices.columns:
        raise RuntimeError("Prices parquet debe contener columnas 'symbol' y 'time'.")

    ctx["time"] = to_server_naive_datetime(ctx["time"])
    prices["time"] = to_server_naive_datetime(prices["time"])

    ctx = ctx.sort_values(["symbol", "time"])
    prices = prices.sort_values(["symbol", "time"])

    # Exact merge (production)
    enriched = ctx.merge(
        prices,
        on=["symbol", "time"],
        how="left",
        validate="many_to_one",
    )

    coverage = 1.0 - enriched["open"].isna().mean()
    print(f"[INFO] OHLC coverage: {coverage:.4%} (min required {min_coverage:.2%})")

    if coverage < min_coverage:
        # Diagnostic to help fix contract (timezone vs open/close time shift)
        delta_mode = diagnose_nearest_delta(ctx, prices)
        missing_sample = enriched.loc[enriched["open"].isna(), ["symbol", "time"]].head(12)

        # Also check if ctx time grid looks H2-like
        grid_minute = ctx["time"].dt.minute.value_counts().head(5).to_dict()
        grid_second = ctx["time"].dt.second.value_counts().head(5).to_dict()
        grid_hour_mod2 = (ctx["time"].dt.hour % 2).value_counts().to_dict()

        raise RuntimeError(
            "OHLC coverage bajo: merge exacto no calza.\n"
            f"coverage={coverage:.4%} (< {min_coverage:.2%})\n"
            f"delta_mode(nearest, tol=6h)={delta_mode}\n"
            f"ctx grid minute(top)={grid_minute}, second(top)={grid_second}, hour%2={grid_hour_mod2}\n"
            f"sample_missing:\n{missing_sample.to_string(index=False)}\n"
            "Causas probables: (1) time en ctx es close-time y prices es open-time (shift ~2h),\n"
            "o (2) timezone mismatch (menos probable dado convenio server-naive),\n"
            "o (3) MT5 no entregó historia completa.\n"
            "Fix permitido: ajuste determinístico del contrato temporal (shift fijo), NO asof como solución final."
        )

    outp = Path(out_parquet)
    outp.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_parquet(outp, index=False)

    print(f"[OK] enriched saved: {outp} | rows={len(enriched)}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--context_parquet", required=True)
    ap.add_argument("--prices_parquet", required=True)
    ap.add_argument("--out_parquet", required=True)
    ap.add_argument("--min_coverage", type=float, default=0.995)
    args = ap.parse_args()

    main(
        context_parquet=args.context_parquet,
        prices_parquet=args.prices_parquet,
        out_parquet=args.out_parquet,
        min_coverage=args.min_coverage,
    )
