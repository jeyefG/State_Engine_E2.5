# scripts/analyze_intrabar_dynamics.py
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import numpy as np

from state_engine.mt5_connector import MT5Connector


def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def build_allow_episodes(dec: pd.DataFrame, symbol: str) -> pd.DataFrame:
    dec = dec.copy()
    dec = dec[dec["symbol"] == symbol].copy()
    dec = dec.sort_values(["symbol", "ts"]).reset_index(drop=True)

    is_allow = dec["decision"].astype(str).str.upper().eq("ALLOW")
    prev_allow = is_allow.shift(1, fill_value=False)
    start = is_allow & (~prev_allow)
    episode_id = start.cumsum()

    dec["episode_id"] = np.where(is_allow, episode_id, np.nan)
    dec = dec[is_allow].copy()

    ep = dec.groupby(["symbol", "episode_id"], as_index=False).agg(
        t0=("ts", "min"),
    )
    ep["episode_id"] = ep["episode_id"].astype(int)
    return ep



def analyze_tf(mt5, symbol, t_start, t_end, tf, entry_price):
    df = mt5.obtener_ohlcv(symbol, tf, t_start, t_end)

    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index().rename(columns={df.index.name or "index": "time"})
    df["time"] = to_server_naive_datetime(df["time"])
    df = df.sort_values("time")

    if df.empty:
        return None

    prices = df["close"].values
    rel_moves = (prices - entry_price) / entry_price

    abs_moves = np.abs(rel_moves)
    max_idx = np.argmax(abs_moves)
    max_abs_move = abs_moves[max_idx]
    time_to_max = max_idx + 1

    mfe = np.max(rel_moves)
    mae = np.min(rel_moves)
    mae_ratio = abs(mae) / abs(mfe) if mfe != 0 else np.nan

    return {
        "max_abs_move": max_abs_move,
        "time_to_max": time_to_max,
        "mae_ratio": mae_ratio,
        "n_bars": len(df)
    }


def main(symbol, enriched_parquet, decisions_csv, out_csv):
    df_h2 = pd.read_parquet(enriched_parquet)
    df_h2["time"] = to_server_naive_datetime(df_h2["time"])
    df_h2 = df_h2.sort_values("time")

    dec = pd.read_csv(decisions_csv)
    # if symbol column missing, assume single-symbol file
    if "symbol" not in dec.columns:
        dec["symbol"] = symbol
        dec["ts"] = to_server_naive_datetime(dec["ts"])
    dec = dec.sort_values("ts")

    ep = build_allow_episodes(dec, symbol)

    mt5 = MT5Connector()

    results = []

    for _, row in ep.iterrows():
        t0 = row["t0"]

        # Find execution H2 bar (next bar)
        idx = df_h2.index[df_h2["time"] == t0]
        if len(idx) == 0:
            continue
        i = idx[0]
        if i + 1 >= len(df_h2):
            continue

        h2_exec = df_h2.iloc[i + 1]
        t_start = h2_exec["time"]
        t_end = t_start + pd.Timedelta(hours=2)
        entry_price = h2_exec["open"]

        for tf in ["M30", "M15", "M5"]:
            res = analyze_tf(mt5, symbol, t_start, t_end, tf, entry_price)
            if res is None:
                continue
            res.update({
                "episode_id": row["episode_id"],
                "tf": tf
            })
            results.append(res)

    df_res = pd.DataFrame(results)

    summary = df_res.groupby("tf").agg(
        avg_max_move=("max_abs_move", "mean"),
        median_max_move=("max_abs_move", "median"),
        avg_time_to_max=("time_to_max", "mean"),
        avg_mae_ratio=("mae_ratio", "mean"),
        episodes=("episode_id", "nunique")
    ).reset_index()

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_csv, index=False)

    print(summary)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--enriched_parquet", required=True)
    ap.add_argument("--decisions_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    args = ap.parse_args()

    main(
        args.symbol,
        args.enriched_parquet,
        args.decisions_csv,
        args.out_csv
    )
