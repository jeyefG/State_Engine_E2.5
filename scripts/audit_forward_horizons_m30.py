# scripts/audit_forward_horizons_m30.py
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from state_engine.mt5_connector import MT5Connector


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


def _ensure_time_col(df: pd.DataFrame) -> pd.DataFrame:
    if "time" in df.columns:
        return df
    # If mt5 returns DateTimeIndex
    if isinstance(df.index, pd.DatetimeIndex):
        out = df.reset_index()
        out = out.rename(columns={out.columns[0]: "time"})
        return out
    raise ValueError("No 'time' column and index is not DateTimeIndex.")


def main(
    symbol: str,
    enriched_h2_parquet: str,
    decisions_with_side_csv: str,
    out_dir: str,
    horizons: list[int],
    pad_hours: int = 6,
    m30_timeframe: str = "M30",
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    max_h = max(horizons)

    # Load H2 enriched
    h2 = pd.read_parquet(enriched_h2_parquet)
    h2 = h2[h2["symbol"] == symbol].copy()
    h2["time"] = to_server_naive_datetime(h2["time"])
    h2 = h2.sort_values("time").reset_index(drop=True)

    # Map exact ts -> H2 row
    idx_map = pd.Series(h2.index.values, index=h2["time"].values)

    # Decisions (ALLOW only)
    dec = pd.read_csv(decisions_with_side_csv)
    if "symbol" not in dec.columns:
        dec["symbol"] = symbol
    dec = dec[dec["symbol"] == symbol].copy()
    dec["ts"] = to_server_naive_datetime(dec["ts"])
    dec = dec.sort_values("ts").reset_index(drop=True)
    dec = dec[dec["decision"].astype(str).str.upper().eq("ALLOW")].copy()
    if dec.empty:
        raise RuntimeError("No ALLOW rows in decisions_with_side_csv.")

    # Build execution windows (H2 next)
    exec_rows = []
    for _, r in dec.iterrows():
        ts = r["ts"]
        if ts not in idx_map.index:
            continue
        i = int(idx_map.loc[ts])
        if i + 1 >= len(h2):
            continue
        exec_start = h2.loc[i + 1, "time"]
        exec_end = exec_start + pd.Timedelta(hours=2)
        open_exec = float(h2.loc[i + 1, "open"])
        if not np.isfinite(open_exec) or open_exec <= 0:
            continue

        exec_rows.append(
            dict(
                ts=ts,
                exec_start=exec_start,
                exec_end=exec_end,
                open_exec=open_exec,
                setup_family=str(r.get("setup_family", "unknown")),
                side_intent=str(r.get("side_intent", "NONE")),
                state_hat=int(r.get("state_hat", -1)) if pd.notna(r.get("state_hat", np.nan)) else -1,
                quality_label=str(r.get("quality_label", "")),
                quality_label_full=str(r.get("quality_label_full", "")),
                year=int(pd.to_datetime(exec_start).year),
            )
        )

    exec_df = pd.DataFrame(exec_rows)
    if exec_df.empty:
        raise RuntimeError("No execution windows produced (ts/time alignment issue).")

    # Download M30 once for the whole span (+pad)
    t0 = exec_df["exec_start"].min() - pd.Timedelta(hours=pad_hours)
    t1 = exec_df["exec_end"].max() + pd.Timedelta(hours=pad_hours)

    mt5 = MT5Connector()
    m30 = mt5.obtener_ohlcv(symbol, m30_timeframe, t0, t1)  # IMPORTANT: positional args (repo signature)
    m30 = _ensure_time_col(m30)
    m30["time"] = to_server_naive_datetime(m30["time"])
    m30 = m30.sort_values("time").reset_index(drop=True)

    if m30.empty:
        raise RuntimeError("M30 download returned empty dataframe.")

    # Fast lookup by time range using boolean masks (small data; OK)
    rows = []
    missing_windows = 0
    short_windows = 0

    for _, w in exec_df.iterrows():
        exec_start = w["exec_start"]
        exec_end = w["exec_end"]
        open_exec = float(w["open_exec"])

        win = m30[(m30["time"] >= exec_start) & (m30["time"] < exec_end)].copy()
        win = win.reset_index(drop=True)

        if win.empty:
            missing_windows += 1
            continue

        # Need enough bars to compute max horizon (inside 1 H2 => ideally 4 bars)
        if len(win) < max_h:
            short_windows += 1
            continue

        highs = win["high"].astype(float).values
        lows = win["low"].astype(float).values
        closes = win["close"].astype(float).values
        times = win["time"].values

        # cumulative max/min within window for MFE/MAE
        cum_max_high = np.maximum.accumulate(highs)
        cum_min_low = np.minimum.accumulate(lows)

        for h in horizons:
            j = h - 1
            close_h = float(closes[j])
            ret_h = (close_h - open_exec) / open_exec
            abs_ret_h = abs(ret_h)

            mfe_h = (cum_max_high[j] - open_exec) / open_exec
            mae_h = (cum_min_low[j] - open_exec) / open_exec

            # time-to-MFE/MAE within first h bars
            ttmfe = int(np.argmax(highs[:h]))
            ttmae = int(np.argmin(lows[:h]))

            rows.append(
                dict(
                    symbol=symbol,
                    ts=w["ts"],
                    exec_start=exec_start,
                    setup_family=w["setup_family"],
                    side_intent=w["side_intent"],
                    year=w["year"],
                    h=h,
                    open_exec=open_exec,
                    close_h=close_h,
                    ret=ret_h,
                    abs_ret=abs_ret_h,
                    mfe=mfe_h,
                    mae=mae_h,
                    ttmfe_bars=ttmfe,
                    ttmae_bars=ttmae,
                    end_time=pd.to_datetime(times[j]),
                )
            )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No rows produced (check M30 coverage, exec windows, horizons).")

    def agg_block(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "n": len(g),
                "ret_mean": g["ret"].mean(),
                "ret_median": g["ret"].median(),
                "ret_p10": g["ret"].quantile(0.10),
                "ret_p90": g["ret"].quantile(0.90),
                "abs_ret_mean": g["abs_ret"].mean(),
                "mfe_mean": g["mfe"].mean(),
                "mae_mean": g["mae"].mean(),
                "ttmfe_mean": g["ttmfe_bars"].mean(),
                "ttmae_mean": g["ttmae_bars"].mean(),
            }
        )

    by_setup = df.groupby(["setup_family", "h"], as_index=False).apply(agg_block).reset_index(drop=True)
    by_setup_side = df.groupby(["setup_family", "side_intent", "h"], as_index=False).apply(agg_block).reset_index(drop=True)
    by_year_setup = df.groupby(["year", "setup_family", "h"], as_index=False).apply(agg_block).reset_index(drop=True)

    # Save
    df.to_parquet(out_dir / "forward_rows_m30.parquet", index=False)
    by_setup.to_csv(out_dir / "summary_by_setup_m30.csv", index=False)
    by_setup_side.to_csv(out_dir / "summary_by_setup_side_m30.csv", index=False)
    by_year_setup.to_csv(out_dir / "summary_by_year_setup_m30.csv", index=False)

    print("[OK] forward horizon audit (M30 within next H2) finished")
    print("rows:", len(df), " unique ts:", df["ts"].nunique())
    print("missing_windows:", missing_windows, " short_windows(<max_h):", short_windows)
    print("\n[SUMMARY] by setup_family (M30 horizons):")
    print(by_setup.sort_values(["h", "n"], ascending=[True, False]).head(15).to_string(index=False))
    print("\noutputs:", str(out_dir))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--enriched_h2_parquet", required=True)
    ap.add_argument("--decisions_with_side_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--horizons", default="1,2,3,4")
    ap.add_argument("--pad_hours", type=int, default=6)
    args = ap.parse_args()

    main(
        symbol=args.symbol,
        enriched_h2_parquet=args.enriched_h2_parquet,
        decisions_with_side_csv=args.decisions_with_side_csv,
        out_dir=args.out_dir,
        horizons=parse_int_list(args.horizons),
        pad_hours=args.pad_hours,
    )
