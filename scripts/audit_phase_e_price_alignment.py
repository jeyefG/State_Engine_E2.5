# scripts/audit_phase_e_price_alignment.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import numpy as np
import pandas as pd


# ------------------ CONTRACT ------------------
OUTCOME_TP = "TP"
OUTCOME_SL = "SL"
OUTCOME_NONE = "NONE"
# ---------------------------------------------


def _pick_first_present(cols, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    return None


def _ensure_datetime(series: pd.Series) -> pd.Series:
    if np.issubdtype(series.dtype, np.datetime64):
        return series
    return pd.to_datetime(series, errors="coerce", utc=False)


def _read_bars_prices(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"bars file not found: {p}")

    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    elif p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    else:
        raise ValueError(f"Unsupported bars file type: {p.suffix} (use .parquet or .csv)")

    if df.empty:
        raise ValueError("bars dataframe is empty")

    time_col = _pick_first_present(df.columns, ["time", "bar_ts", "ts", "timestamp", "datetime"])
    if time_col is None:
        raise ValueError("bars missing time column. Expected one of: time, bar_ts, ts, timestamp, datetime")

    df = df.copy()
    df[time_col] = _ensure_datetime(df[time_col])
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    df = df.rename(columns={time_col: "bar_ts"})

    # required OHLC
    for c in ["open", "high", "low", "close"]:
        if c not in df.columns:
            raise ValueError(f"bars missing required column: {c}")

    return df


def _read_events(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"events file not found: {p}")

    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    elif p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        raise ValueError(f"Unsupported events file type: {p.suffix} (use .csv or .parquet)")

    if df.empty:
        raise ValueError("events dataframe is empty")

    ts_col = _pick_first_present(df.columns, ["ts", "time", "bar_ts", "timestamp", "datetime"])
    if ts_col is None:
        raise ValueError("events missing ts/time column (expected ts/time/bar_ts/...)")

    df = df.copy()
    df[ts_col] = _ensure_datetime(df[ts_col])
    df = df.dropna(subset=[ts_col]).sort_values(ts_col).reset_index(drop=True)
    df = df.rename(columns={ts_col: "ts"})

    # keep only ALLOW if column exists
    if "decision" in df.columns:
        df = df.loc[df["decision"].astype(str).str.upper() == "ALLOW"].copy()

    return df


def _asof_align_events_to_bars(events: pd.DataFrame, bars: pd.DataFrame, tolerance: pd.Timedelta) -> pd.DataFrame:
    # align event.ts -> nearest bar_ts within tolerance
    e = events.sort_values("ts").copy()
    b = bars[["bar_ts"]].sort_values("bar_ts").copy()

    aligned = pd.merge_asof(
        e,
        b,
        left_on="ts",
        right_on="bar_ts",
        direction="nearest",
        tolerance=tolerance,
    )

    aligned = aligned.dropna(subset=["bar_ts"]).reset_index(drop=True)
    return aligned


def _compute_tp_sl_outcome(
    bars: pd.DataFrame,
    idx: int,
    tp_dist: float,
    sl_dist: float,
    horizon: int,
) -> Tuple[str, Optional[int]]:
    """
    Symmetric-ish TP/SL:
    - entry at close(idx)
    - TP hit if high >= entry + tp_dist OR low <= entry - tp_dist  (touch either side => TP for straddle-like)
    - SL hit if first touch is beyond opposite? (For clean contract we define:
        - if within horizon touches either side -> TP
        - else NONE
      (SL only meaningful if you model single-direction entry; for straddle expansion it’s TP/NONE.)
    """
    entry = float(bars.at[idx, "close"])
    up = entry + tp_dist
    dn = entry - tp_dist

    n = len(bars)
    max_fwd = min(idx + horizon, n - 1)
    if idx >= n - 1 or max_fwd <= idx:
        return OUTCOME_NONE, None

    for j in range(idx + 1, max_fwd + 1):
        hi = float(bars.at[j, "high"])
        lo = float(bars.at[j, "low"])
        if hi >= up or lo <= dn:
            return OUTCOME_TP, j - idx

    return OUTCOME_NONE, None


def _build_ts_to_idx(bars: pd.DataFrame) -> Dict[pd.Timestamp, int]:
    # NOTE: bars["bar_ts"] is Timestamp; keep as Timestamp for dict keys
    return {pd.Timestamp(ts): i for i, ts in enumerate(bars["bar_ts"].values)}


def _summarize(df: pd.DataFrame, group_cols: Optional[List[str]] = None) -> pd.DataFrame:
    if group_cols is None:
        group_cols = []

    d = df.copy()
    d["is_tp"] = d["outcome"].eq(OUTCOME_TP)
    d["is_none"] = d["outcome"].eq(OUTCOME_NONE)

    def agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        n_tp = int(g["is_tp"].sum())
        n_none = int(g["is_none"].sum())
        tp_rate = n_tp / n if n else np.nan
        mean_bars_to_tp = g.loc[g["is_tp"], "bars_to_hit"].astype(float).mean() if n_tp else np.nan
        return pd.Series(
            {
                "n_events": n,
                "n_tp": n_tp,
                "n_none": n_none,
                "tp_rate": tp_rate,
                "mean_bars_to_tp": mean_bars_to_tp,
            }
        )

    if group_cols:
        return d.groupby(group_cols, dropna=False).apply(agg).reset_index()
    return agg(d).to_frame().T


def _sample_unconditional(bars_eval: pd.DataFrame, n: int, rng: np.random.Generator) -> np.ndarray:
    ts = bars_eval["bar_ts"].values
    if len(ts) == 0:
        raise ValueError("No eligible bars to sample from (check horizon cutoff).")
    replace = n > len(ts)
    idx = rng.choice(len(ts), size=n, replace=replace)
    return ts[idx]


def _sample_state_matched(bars_eval: pd.DataFrame, allow_df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    if "state_hat" not in bars_eval.columns or "state_hat" not in allow_df.columns:
        raise ValueError("bars or allow_df missing state_hat (needed for state-matched baseline).")

    pools: Dict[str, np.ndarray] = {}
    for key, g in bars_eval.groupby(["state_hat"], dropna=False):
        pools[str(key)] = g["bar_ts"].values

    out = []
    for _, row in allow_df.iterrows():
        key = str(row.get("state_hat"))
        pool = pools.get(key)
        if pool is None or len(pool) == 0:
            pool = bars_eval["bar_ts"].values
        j = rng.integers(0, len(pool))
        out.append(pool[j])
    return np.array(out)


def _evaluate_ts_list(
    bars: pd.DataFrame,
    ts_list: np.ndarray,
    horizon: int,
    tp_dist: float,
    label: str,
    setup_families: Optional[np.ndarray] = None,
) -> pd.DataFrame:
    ts_to_idx = _build_ts_to_idx(bars)

    rows = []
    missing = 0
    for i, ts in enumerate(ts_list):
        ts = pd.Timestamp(ts)
        if ts not in ts_to_idx:
            missing += 1
            continue
        idx = ts_to_idx[ts]

        outcome, bars_to_hit = _compute_tp_sl_outcome(bars, idx, tp_dist=tp_dist, sl_dist=tp_dist, horizon=horizon)
        row = {
            "baseline": label,
            "bar_ts": ts,
            "year": ts.year,
            "tp_dist": tp_dist,
            "horizon_bars": horizon,
            "outcome": outcome,
            "bars_to_hit": bars_to_hit,
        }
        if setup_families is not None:
            row["setup_family"] = str(setup_families[i])

        if "state_hat" in bars.columns:
            row["state_hat"] = bars.at[idx, "state_hat"]

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"No events evaluated for {label}. missing_ts={missing}")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--events", required=True, help="decisions_with_side.csv (or similar)")
    ap.add_argument("--bars", required=True, help="prices parquet/csv with time+OHLC (state_hat optional)")
    ap.add_argument("--tolerance", required=False, default="30min")
    ap.add_argument("--seed", required=False, type=int, default=42)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tf", required=False, default="M30", choices=["M30", "H2"])
    ap.add_argument("--horizon_bars", required=False, type=int, default=None, help="Override horizon bars")
    ap.add_argument("--tp_k", required=False, type=float, default=0.5, help="TP distance multiplier of X")
    ap.add_argument("--x_window", required=False, type=int, default=20, help="Rolling window for X = mean(high-low)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    tol = pd.Timedelta(args.tolerance)

    bars = _read_bars_prices(args.bars)

    # Create canonical X from OHLC (fixed, no tuning)
    # X = rolling mean of (high-low)
    bars = bars.copy()
    bars["X"] = (bars["high"] - bars["low"]).rolling(window=args.x_window, min_periods=args.x_window).mean()

    # Horizon default by TF
    if args.horizon_bars is None:
        horizon = 3 if args.tf == "M30" else 1
    else:
        horizon = int(args.horizon_bars)

    # Only sample from bars where forward horizon exists and X exists
    last_valid_idx = len(bars) - 1 - horizon
    if last_valid_idx < 1:
        raise ValueError("bars too short for requested horizon")
    bars_eval = bars.loc[:last_valid_idx].copy().reset_index(drop=True)
    bars_eval = bars_eval.dropna(subset=["X"]).reset_index(drop=True)

    events = _read_events(args.events)
    if events.empty:
        raise ValueError("No ALLOW events in events file (or events file empty).")

    # Align events to bars
    allow_aligned = _asof_align_events_to_bars(events, bars_eval, tolerance=tol)
    if allow_aligned.empty:
        raise ValueError("No events aligned within tolerance. Increase --tolerance or check timezones/ts.")

    # Derive TP dist per event using event's bar X at aligned bar_ts
    # For bridge audit we use TP = tp_k * X(bar)
    ts_to_idx = _build_ts_to_idx(bars)
    tp_dists = []
    for ts in allow_aligned["bar_ts"].values:
        ts = pd.Timestamp(ts)
        idx = ts_to_idx.get(ts)
        if idx is None:
            tp_dists.append(np.nan)
            continue
        x = float(bars.at[idx, "X"])
        tp_dists.append(args.tp_k * x if np.isfinite(x) and x > 0 else np.nan)
    allow_aligned = allow_aligned.copy()
    allow_aligned["tp_dist"] = tp_dists
    allow_aligned = allow_aligned.dropna(subset=["tp_dist"]).reset_index(drop=True)

    # Evaluate ALLOW as "baseline=ALLOW"
    allow_rows = []
    missing = 0
    for _, r in allow_aligned.iterrows():
        ts = pd.Timestamp(r["bar_ts"])
        idx = ts_to_idx.get(ts)
        if idx is None:
            missing += 1
            continue
        outcome, bars_to_hit = _compute_tp_sl_outcome(
            bars=bars,
            idx=idx,
            tp_dist=float(r["tp_dist"]),
            sl_dist=float(r["tp_dist"]),
            horizon=horizon,
        )
        row = {
            "baseline": "ALLOW",
            "bar_ts": ts,
            "year": ts.year,
            "tp_dist": float(r["tp_dist"]),
            "horizon_bars": horizon,
            "outcome": outcome,
            "bars_to_hit": bars_to_hit,
        }
        # carry optional labels if present
        if "setup_family" in r:
            row["setup_family"] = r.get("setup_family")
        if "state_hat" in r:
            row["state_hat"] = r.get("state_hat")
        allow_rows.append(row)

    df_allow = pd.DataFrame(allow_rows)
    if df_allow.empty:
        raise ValueError(f"No events evaluated for ALLOW. missing_ts={missing}")

    # Save ALLOW evaluated events
    df_allow.to_csv(out_dir / "allow_price_events.csv", index=False)

    rng = np.random.default_rng(args.seed)
    n = len(df_allow)

    # Baseline B0 unconditional
    ts_b0 = _sample_unconditional(bars_eval=bars_eval, n=n, rng=rng)

    # For baseline, use a single TP distance proxy: match each sampled bar's own X
    # (so each baseline event has tp_dist = tp_k * X(sampled_bar))
    # We'll implement this by evaluating with tp_dist computed inside ts loop:
    b0_rows = []
    for ts in ts_b0:
        ts = pd.Timestamp(ts)
        idx = ts_to_idx.get(ts)
        if idx is None:
            continue
        x = float(bars.at[idx, "X"])
        if not np.isfinite(x) or x <= 0:
            continue
        tp_dist = args.tp_k * x
        outcome, bars_to_hit = _compute_tp_sl_outcome(bars, idx, tp_dist, tp_dist, horizon)
        b0_rows.append(
            {
                "baseline": "B0_unconditional",
                "bar_ts": ts,
                "year": ts.year,
                "tp_dist": tp_dist,
                "horizon_bars": horizon,
                "outcome": outcome,
                "bars_to_hit": bars_to_hit,
                "state_hat": bars.at[idx, "state_hat"] if "state_hat" in bars.columns else None,
            }
        )
    df_b0 = pd.DataFrame(b0_rows)
    if df_b0.empty:
        raise ValueError("Baseline B0 produced no events (check X window / data).")
    df_b0.to_csv(out_dir / "baseline_B0_price_events.csv", index=False)

    # Baseline B1 state-matched (AUTO-DEGRADE if bars lacks state_hat)
    df_b1 = None
    if "state_hat" in bars_eval.columns and "state_hat" in df_allow.columns:
        ts_b1 = _sample_state_matched(bars_eval=bars_eval, allow_df=df_allow, rng=rng)
        b1_rows = []
        for ts in ts_b1:
            ts = pd.Timestamp(ts)
            idx = ts_to_idx.get(ts)
            if idx is None:
                continue
            x = float(bars.at[idx, "X"])
            if not np.isfinite(x) or x <= 0:
                continue
            tp_dist = args.tp_k * x
            outcome, bars_to_hit = _compute_tp_sl_outcome(bars, idx, tp_dist, tp_dist, horizon)
            b1_rows.append(
                {
                    "baseline": "B1_state_matched",
                    "bar_ts": ts,
                    "year": ts.year,
                    "tp_dist": tp_dist,
                    "horizon_bars": horizon,
                    "outcome": outcome,
                    "bars_to_hit": bars_to_hit,
                    "state_hat": bars.at[idx, "state_hat"],
                }
            )
        df_b1 = pd.DataFrame(b1_rows)
        if not df_b1.empty:
            df_b1.to_csv(out_dir / "baseline_B1_price_events.csv", index=False)
    else:
        print("WARN: bars missing state_hat (or ALLOW missing state_hat). Skipping B1_state_matched baseline.")

    # Summaries
    allow_global = _summarize(df_allow)
    b0_global = _summarize(df_b0)
    allow_by_year = _summarize(df_allow, group_cols=["year"])
    b0_by_year = _summarize(df_b0, group_cols=["year"])

    allow_global.to_csv(out_dir / "allow_price_summary_global.csv", index=False)
    b0_global.to_csv(out_dir / "baseline_B0_price_summary_global.csv", index=False)
    allow_by_year.to_csv(out_dir / "allow_price_summary_by_year.csv", index=False)
    b0_by_year.to_csv(out_dir / "baseline_B0_price_summary_by_year.csv", index=False)

    # Compare (ALLOW vs B0, and vs B1 if available)
    def _compare(a: pd.DataFrame, b: pd.DataFrame, key_cols: List[str], baseline_name: str) -> pd.DataFrame:
        aa = a.copy()
        bb = b.copy()
        if not key_cols:
            aa["key"] = 1
            bb["key"] = 1
            key_cols = ["key"]
        m = aa.merge(bb, on=key_cols, how="left", suffixes=("_allow", "_base"))
        m["uplift_tp_rate"] = m["tp_rate_allow"] - m["tp_rate_base"]
        m["uplift_mean_bars_to_tp"] = m["mean_bars_to_tp_allow"] - m["mean_bars_to_tp_base"]
        m["baseline"] = baseline_name
        if "key" in m.columns:
            m = m.drop(columns=["key"])
        return m

    comp_global = []
    comp_global.append(_compare(allow_global, b0_global, key_cols=[], baseline_name="B0_unconditional"))

    comp_by_year = []
    comp_by_year.append(_compare(allow_by_year, b0_by_year, key_cols=["year"], baseline_name="B0_unconditional"))

    if df_b1 is not None and not df_b1.empty:
        b1_global = _summarize(df_b1)
        b1_by_year = _summarize(df_b1, group_cols=["year"])
        b1_global.to_csv(out_dir / "baseline_B1_price_summary_global.csv", index=False)
        b1_by_year.to_csv(out_dir / "baseline_B1_price_summary_by_year.csv", index=False)

        comp_global.append(_compare(allow_global, b1_global, key_cols=[], baseline_name="B1_state_matched"))
        comp_by_year.append(_compare(allow_by_year, b1_by_year, key_cols=["year"], baseline_name="B1_state_matched"))

    comp_global_df = pd.concat(comp_global, ignore_index=True)
    comp_by_year_df = pd.concat(comp_by_year, ignore_index=True)

    comp_global_df.to_csv(out_dir / "price_bridge_compare_global.csv", index=False)
    comp_by_year_df.to_csv(out_dir / "price_bridge_compare_by_year.csv", index=False)

    # Console
    print("=== Phase E Price Bridge Audit (AUTO-DEGRADE) ===")
    print(f"symbol={args.symbol} tf={args.tf} horizon_bars={horizon} tp_k={args.tp_k} x_window={args.x_window}")
    print(f"events={args.events}")
    print(f"bars={args.bars}")
    print(f"aligned_allow={len(df_allow)}")
    print(f"out={out_dir.resolve()}")
    print("\nGLOBAL COMPARE:")
    cols = ["baseline", "n_events_allow", "tp_rate_allow", "tp_rate_base", "uplift_tp_rate", "mean_bars_to_tp_allow", "mean_bars_to_tp_base", "uplift_mean_bars_to_tp"]
    # Ensure columns exist (they will)
    print(comp_global_df[cols].to_string(index=False))


if __name__ == "__main__":
    main()