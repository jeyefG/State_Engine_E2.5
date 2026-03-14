# scripts/audit_expansion_scalp.py
# ------------------------------------------------------------
# Expansion Scalp audit (post-ALLOW) with a FIXED contract:
# - K = 0.5 (±0.5X)
# - Horizon bars: H2 -> 1, M30 -> 3
# - Outcome: UP / DOWN / NONE / DISCARD (if both touched same future bar)
# - No tuning knobs exposed for K/horizon.
# ------------------------------------------------------------

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


# -------- FIXED CONTRACT (DO NOT CHANGE) --------
K_FIXED = 0.5
HORIZON_BARS = {"H2": 1, "M30": 3}
OUTCOME_UP = "UP"
OUTCOME_DOWN = "DOWN"
OUTCOME_NONE = "NONE"
OUTCOME_DISCARD = "DISCARD"
# ----------------------------------------------


def _pick_first_present(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None


def _ensure_datetime(series: pd.Series) -> pd.Series:
    if np.issubdtype(series.dtype, np.datetime64):
        return series
    return pd.to_datetime(series, errors="coerce", utc=False)


def _read_bars(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"bars file not found: {p}")

    if p.suffix.lower() in [".parquet"]:
        df = pd.read_parquet(p)
    elif p.suffix.lower() in [".csv"]:
        df = pd.read_csv(p)
    else:
        raise ValueError(f"Unsupported bars file type: {p.suffix} (use .parquet or .csv)")

    if df.empty:
        raise ValueError("bars dataframe is empty")

    # Identify time column
    time_col = _pick_first_present(df.columns, ["time", "bar_ts", "ts", "timestamp", "datetime"])
    if time_col is None:
        raise ValueError("bars missing time column. Expected one of: time, bar_ts, ts, timestamp, datetime")

    df = df.copy()
    df[time_col] = _ensure_datetime(df[time_col])
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    df = df.rename(columns={time_col: "bar_ts"})

    # Required OHLC
    for c in ["open", "high", "low", "close"]:
        if c not in df.columns:
            raise ValueError(f"bars missing required column: {c}")
            
    # Create canonical X from OHLC (fixed, no tuning)
    # X = rolling mean of bar range (high-low)
    df["X"] = (df["high"] - df["low"]).rolling(window=20, min_periods=20).mean()


    # Optional: state/quality
    if "state_hat" not in df.columns:
        maybe = _pick_first_present(df.columns, ["state", "state_pred", "state_label"])
        if maybe is not None:
            df = df.rename(columns={maybe: "state_hat"})
    if "quality_label" not in df.columns:
        maybe = _pick_first_present(df.columns, ["ql", "quality", "quality_hat"])
        if maybe is not None:
            df = df.rename(columns={maybe: "quality_label"})

    return df


def _read_events(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"events file not found: {p}")

    if p.suffix.lower() != ".csv":
        raise ValueError("events must be a .csv (decisions_with_side.csv)")

    df = pd.read_csv(p)
    if df.empty:
        raise ValueError("events dataframe is empty")

    # Identify timestamp column
    ts_col = _pick_first_present(df.columns, ["bar_ts", "time", "ts", "timestamp", "datetime"])
    if ts_col is None:
        raise ValueError("events missing timestamp column. Expected one of: bar_ts, time, ts, timestamp, datetime")

    df = df.copy()
    df[ts_col] = _ensure_datetime(df[ts_col])
    df = df.dropna(subset=[ts_col]).rename(columns={ts_col: "bar_ts"})

    # Identify setup_family (optional but recommended)
    setup_col = _pick_first_present(df.columns, ["setup_family", "setup", "family", "setup_name", "template"])
    if setup_col is None:
        df["setup_family"] = "UNKNOWN"
    else:
        df = df.rename(columns={setup_col: "setup_family"})
        df["setup_family"] = df["setup_family"].astype(str)

    # Filter ALLOW
    # Accept any of these conventions:
    # - decision == "ALLOW"
    # - allow == 1 / True
    # - is_allow == 1 / True
    allow_col = _pick_first_present(df.columns, ["decision", "allow", "is_allow", "gate", "action"])
    if allow_col is None:
        raise ValueError("events missing ALLOW indicator column. Expected one of: decision, allow, is_allow, gate, action")

    def _is_allow(v) -> bool:
        if pd.isna(v):
            return False
        if isinstance(v, (int, np.integer, float, np.floating)):
            return float(v) == 1.0
        s = str(v).strip().upper()
        return s in {"ALLOW", "1", "TRUE", "YES", "Y"}

    allow_mask = df[allow_col].apply(_is_allow)
    df = df.loc[allow_mask].copy()

    if df.empty:
        raise ValueError("No ALLOW events found in events file after filtering.")

    # Keep only what we need, but keep extra columns too (harmless)
    df = df.sort_values("bar_ts").reset_index(drop=True)
    return df


def _compute_outcome_for_event(
    bars: pd.DataFrame,
    idx: int,
    base: float,
    X: float,
    horizon: int,
) -> Tuple[str, Optional[int]]:
    """
    Looks at next `horizon` bars (idx+1..idx+horizon) and returns:
      - outcome: UP / DOWN / DISCARD / NONE
      - bars_to_touch: 1..horizon for UP/DOWN/DISCARD, None for NONE
    """
    if not np.isfinite(base) or not np.isfinite(X) or X <= 0:
        return OUTCOME_NONE, None

    U = base + K_FIXED * X
    D = base - K_FIXED * X

    n = len(bars)
    max_fwd = min(idx + horizon, n - 1)
    if idx >= n - 1 or max_fwd <= idx:
        return OUTCOME_NONE, None

    for j in range(idx + 1, max_fwd + 1):
        hi = float(bars.at[j, "high"])
        lo = float(bars.at[j, "low"])
        hit_up = hi >= U
        hit_dn = lo <= D

        if hit_up and hit_dn:
            return OUTCOME_DISCARD, j - idx
        if hit_up:
            return OUTCOME_UP, j - idx
        if hit_dn:
            return OUTCOME_DOWN, j - idx

    return OUTCOME_NONE, None


def _summarize(df_events: pd.DataFrame, group_cols: Optional[list] = None) -> pd.DataFrame:
    if group_cols is None:
        group_cols = []

    df = df_events.copy()
    df["is_touch"] = df["outcome"].isin([OUTCOME_UP, OUTCOME_DOWN])
    df["is_discard"] = df["outcome"].eq(OUTCOME_DISCARD)
    df["is_none"] = df["outcome"].eq(OUTCOME_NONE)

    def agg_fn(g: pd.DataFrame) -> pd.Series:
        n_total = len(g)
        n_discard = int(g["is_discard"].sum())
        n_valid = n_total - n_discard  # for touch_rate denominator
        n_touch = int(g["is_touch"].sum())
        n_up = int((g["outcome"] == OUTCOME_UP).sum())
        n_down = int((g["outcome"] == OUTCOME_DOWN).sum())
        n_none = int(g["is_none"].sum())

        touch_rate = (n_touch / n_valid) if n_valid > 0 else np.nan
        discard_rate = n_discard / n_total if n_total > 0 else np.nan
        none_rate_valid = (n_none / n_valid) if n_valid > 0 else np.nan

        mean_bars_to_touch = (
            g.loc[g["is_touch"], "bars_to_touch"].astype(float).mean() if n_touch > 0 else np.nan
        )
        med_bars_to_touch = (
            g.loc[g["is_touch"], "bars_to_touch"].astype(float).median() if n_touch > 0 else np.nan
        )
        p90_bars_to_touch = (
            g.loc[g["is_touch"], "bars_to_touch"].astype(float).quantile(0.9) if n_touch > 0 else np.nan
        )

        return pd.Series(
            {
                "n_events": n_total,
                "n_valid_ex_discard": n_valid,
                "n_touch": n_touch,
                "n_up": n_up,
                "n_down": n_down,
                "n_none": n_none,
                "n_discard": n_discard,
                "touch_rate": touch_rate,
                "discard_rate": discard_rate,
                "none_rate_ex_discard": none_rate_valid,
                "mean_bars_to_touch": mean_bars_to_touch,
                "median_bars_to_touch": med_bars_to_touch,
                "p90_bars_to_touch": p90_bars_to_touch,
            }
        )

    if group_cols:
        out = df.groupby(group_cols, dropna=False).apply(agg_fn).reset_index()
    else:
        out = agg_fn(df).to_frame().T

    # Sort nicely if possible
    if "touch_rate" in out.columns:
        out = out.sort_values(["touch_rate", "n_events"], ascending=[False, False])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=False, default="", help="Symbol label (for report headers only)")
    ap.add_argument("--tf", required=True, choices=["H2", "M30"], help="Timeframe for audit (contract fixed per TF)")
    ap.add_argument("--events", required=True, help="Path to decisions_with_side.csv (must contain ALLOW events)")
    ap.add_argument("--bars", required=True, help="Path to bars (.parquet/.csv) containing OHLC + X column")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    horizon = HORIZON_BARS[args.tf]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bars = _read_bars(args.bars)
    events = _read_events(args.events)
    
    # Ensure sorted for asof merge
    bars2 = bars.copy().sort_values("bar_ts").reset_index(drop=True)
    bars2["bar_idx"] = np.arange(len(bars2))
    
    events2 = events.copy().sort_values("bar_ts").reset_index(drop=True)
    
    # Align each event to the nearest bar at or before event timestamp (no future leak)
    aligned = pd.merge_asof(
        events2,
        bars2,
        on="bar_ts",
        direction="backward",
        tolerance=pd.Timedelta("2H") if args.tf == "H2" else pd.Timedelta("30min"),
    )
    
    # Drop events that couldn't be aligned
    aligned = aligned.dropna(subset=["bar_idx"]).copy()
    aligned["bar_idx"] = aligned["bar_idx"].astype(int)
    
    # Horizon cutoff: need at least `horizon` bars ahead
    aligned = aligned[aligned["bar_idx"] <= (len(bars2) - 1 - horizon)].copy()
    
    rows = []
    for _, ev in aligned.iterrows():
        idx = int(ev["bar_idx"])
        base = float(bars2.at[idx, "close"])
        X = float(bars2.at[idx, "X"])
        if not np.isfinite(X) or X <= 0:
            continue
    
        outcome, bars_to_touch = _compute_outcome_for_event(bars2, idx, base, X, horizon)
        year = pd.Timestamp(ev["bar_ts"]).year
    
        row = {
            "symbol": args.symbol,
            "tf": args.tf,
            "bar_ts": ev["bar_ts"],
            "year": year,
            "setup_family": ev.get("setup_family", "UNKNOWN"),
            "base_close": base,
            "X": X,
            "k": K_FIXED,
            "horizon_bars": horizon,
            "outcome": outcome,
            "bars_to_touch": bars_to_touch,
        }
        if "state_hat" in bars2.columns:
            row["state_hat"] = bars2.at[idx, "state_hat"]
        if "quality_label" in bars2.columns:
            row["quality_label"] = bars2.at[idx, "quality_label"]
    
        rows.append(row)
    
    df_out = pd.DataFrame(rows)
    
    # Debug counts (print)
    print(f"aligned_events_after_asof={len(aligned)} out_events_after_X_filter={len(df_out)}")


    if df_out.empty:
        raise ValueError("No evaluable events after alignment + horizon cutoff.")

    # Write per-event outcomes
    events_path = out_dir / "expansion_scalp_events.csv"
    df_out.to_csv(events_path, index=False)

    # Summaries
    global_summary = _summarize(df_out)
    global_path = out_dir / "summary_global.csv"
    global_summary.to_csv(global_path, index=False)

    by_setup = _summarize(df_out, group_cols=["setup_family"])
    by_setup_path = out_dir / "summary_by_setup_family.csv"
    by_setup.to_csv(by_setup_path, index=False)

    by_year = _summarize(df_out, group_cols=["year"])
    by_year_path = out_dir / "summary_by_year.csv"
    by_year.to_csv(by_year_path, index=False)

    # Helpful console output
    print("=== Expansion Scalp Audit (post-ALLOW) ===")
    print(f"symbol={args.symbol} tf={args.tf} k={K_FIXED} horizon_bars={horizon}")
    print(f"bars: {args.bars}")
    print(f"events: {args.events}")
    print(f"out: {out_dir.resolve()}")
    print("\nGLOBAL SUMMARY:")
    print(global_summary.to_string(index=False))


if __name__ == "__main__":
    main()
