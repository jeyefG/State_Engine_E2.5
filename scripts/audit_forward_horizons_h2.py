# scripts/audit_forward_horizons_h2.py
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def parse_int_list(s: str) -> list[int]:
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def main(
    symbol: str,
    enriched_h2_parquet: str,
    decisions_with_side_csv: str,
    out_dir: str,
    horizons: list[int],
    filter_setup_family: str | None = None,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    h2 = pd.read_parquet(enriched_h2_parquet)
    h2 = h2[h2["symbol"] == symbol].copy()
    h2["time"] = to_server_naive_datetime(h2["time"])
    h2 = h2.sort_values("time").reset_index(drop=True)

    # index map for exact ts -> row index
    idx_map = pd.Series(h2.index.values, index=h2["time"].values)

    dec = pd.read_csv(decisions_with_side_csv)
    if "symbol" not in dec.columns:
        dec["symbol"] = symbol
    dec = dec[dec["symbol"] == symbol].copy()
    dec["ts"] = to_server_naive_datetime(dec["ts"])
    dec = dec.sort_values("ts").reset_index(drop=True)

    # only ALLOW
    dec = dec[dec["decision"].astype(str).str.upper().eq("ALLOW")].copy()
    if dec.empty:
        raise RuntimeError("No ALLOW rows in decisions_with_side_csv.")

    if filter_setup_family:
        dec = dec[dec["setup_family"].astype(str) == filter_setup_family].copy()
        if dec.empty:
            raise RuntimeError(f"No ALLOW rows after filter_setup_family={filter_setup_family}")

    max_h = max(horizons)

    rows = []
    for _, r in dec.iterrows():
        ts = r["ts"]
        if ts not in idx_map.index:
            continue
        i = int(idx_map.loc[ts])
        # execution bar = next H2
        if i + 1 >= len(h2):
            continue
        j0 = i + 1
        if j0 + (max_h - 1) >= len(h2):
            continue

        open_exec = float(h2.loc[j0, "open"])
        if not np.isfinite(open_exec) or open_exec <= 0:
            continue

        base = dict(
            symbol=symbol,
            ts=ts,
            exec_time=h2.loc[j0, "time"],
            setup_family=str(r.get("setup_family", "unknown")),
            side_intent=str(r.get("side_intent", "NONE")),
            state_hat=int(r.get("state_hat", -1)) if pd.notna(r.get("state_hat", np.nan)) else -1,
            quality_label=str(r.get("quality_label", "")),
            quality_label_full=str(r.get("quality_label_full", "")),
            open_exec=open_exec,
            year=int(pd.to_datetime(h2.loc[j0, "time"]).year),
        )

        # window for MFE/MAE up to max_h bars
        w = h2.iloc[j0 : j0 + max_h].copy()
        highs = w["high"].astype(float).values
        lows = w["low"].astype(float).values

        # Precompute cumulative max/min excursions for each horizon
        # MFE: max(high - open_exec)/open_exec
        # MAE: min(low  - open_exec)/open_exec (negative)
        cum_max_high = np.maximum.accumulate(highs)
        cum_min_low = np.minimum.accumulate(lows)

        for h in horizons:
            j_end = j0 + (h - 1)
            close_h = float(h2.loc[j_end, "close"])
            ret_h = (close_h - open_exec) / open_exec
            abs_ret_h = abs(ret_h)

            mfe_h = (cum_max_high[h - 1] - open_exec) / open_exec
            mae_h = (cum_min_low[h - 1] - open_exec) / open_exec

            row = base.copy()
            row.update({
                "h": h,
                "ret": ret_h,
                "abs_ret": abs_ret_h,
                "mfe": mfe_h,
                "mae": mae_h,
            })
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No rows produced (check ts/time alignment or data coverage).")

    # summaries
    def agg_block(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n": len(g),
            "ret_mean": g["ret"].mean(),
            "ret_median": g["ret"].median(),
            "ret_p10": g["ret"].quantile(0.10),
            "ret_p90": g["ret"].quantile(0.90),
            "abs_ret_mean": g["abs_ret"].mean(),
            "mfe_mean": g["mfe"].mean(),
            "mae_mean": g["mae"].mean(),
        })

    by_setup = df.groupby(["setup_family", "h"], as_index=False).apply(agg_block).reset_index(drop=True)
    by_setup_side = df.groupby(["setup_family", "side_intent", "h"], as_index=False).apply(agg_block).reset_index(drop=True)
    by_year_setup = df.groupby(["year", "setup_family", "h"], as_index=False).apply(agg_block).reset_index(drop=True)

    # write outputs
    (out_dir / "forward_rows.parquet").unlink(missing_ok=True) if hasattr(Path, "unlink") else None
    df.to_parquet(out_dir / "forward_rows.parquet", index=False)
    by_setup.to_csv(out_dir / "summary_by_setup.csv", index=False)
    by_setup_side.to_csv(out_dir / "summary_by_setup_side.csv", index=False)
    by_year_setup.to_csv(out_dir / "summary_by_year_setup.csv", index=False)

    # print top-level
    print("[OK] forward horizon audit finished")
    print("rows:", len(df), " unique ts:", df["ts"].nunique())
    print("\n[SUMMARY] by setup_family (h=1..):")
    print(by_setup.sort_values(["h", "n"], ascending=[True, False]).head(15).to_string(index=False))
    print("\noutputs:", str(out_dir))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--enriched_h2_parquet", required=True)
    ap.add_argument("--decisions_with_side_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--horizons", default="1,2,3")
    ap.add_argument("--filter_setup_family", default=None)
    args = ap.parse_args()

    main(
        symbol=args.symbol,
        enriched_h2_parquet=args.enriched_h2_parquet,
        decisions_with_side_csv=args.decisions_with_side_csv,
        out_dir=args.out_dir,
        horizons=parse_int_list(args.horizons),
        filter_setup_family=args.filter_setup_family,
    )
