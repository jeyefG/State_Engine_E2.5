# scripts/audit_expansion_scalp_baselines.py
# ------------------------------------------------------------
# Baselines for Expansion Scalp with the SAME FIXED contract:
# - K = 0.5  (±0.5X)
# - Horizon bars: H2 -> 1, M30 -> 3
# - X is computed from OHLC: rolling_mean(high-low, window=20, min_periods=20)
#
# Baselines:
#   B0_unconditional:
#       Sample timestamps uniformly from the eligible universe (same N as ALLOW).
#
#   B1_state_matched:
#       Sample timestamps matched by state_hat (optionally (state_hat, quality_label) if --use_quality_match).
#
#   B3_setup_state_matched (conservative, valid for by-setup reporting):
#       Sample timestamps matched by state_hat (optionally quality), but carry over ALLOW's setup_family labels
#       so we can compare ALLOW setups vs a conservative state-matched baseline.
#       NOTE: setup_family does NOT exist in bars, so this is not a "setup-matched" sampler in the universe.
#
# Outputs:
# - baseline_B0_events.csv, baseline_B1_events.csv, baseline_B3_events.csv
# - baseline_compare.csv (global ALLOW vs B0/B1)
# - baseline_compare_by_year.csv
# - baseline_compare_by_setup_family.csv (ALLOW vs B3)
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

    time_col = _pick_first_present(df.columns, ["time", "bar_ts", "ts", "timestamp", "datetime"])
    if time_col is None:
        raise ValueError("bars missing time column. Expected one of: time, bar_ts, ts, timestamp, datetime")

    df = df.copy()
    df[time_col] = _ensure_datetime(df[time_col])
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    df = df.rename(columns={time_col: "bar_ts"})

    for c in ["open", "high", "low", "close"]:
        if c not in df.columns:
            raise ValueError(f"bars missing required column: {c}")

    # Create canonical X from OHLC (fixed, no tuning)
    df["X"] = (df["high"] - df["low"]).rolling(window=20, min_periods=20).mean()

    if "state_hat" not in df.columns:
        maybe = _pick_first_present(df.columns, ["state", "state_pred", "state_label"])
        if maybe is not None:
            df = df.rename(columns={maybe: "state_hat"})
    if "quality_label" not in df.columns:
        maybe = _pick_first_present(df.columns, ["ql", "quality", "quality_hat"])
        if maybe is not None:
            df = df.rename(columns={maybe: "quality_label"})

    return df


def _compute_outcome_for_event(
    bars: pd.DataFrame,
    idx: int,
    base: float,
    X: float,
    horizon: int,
) -> Tuple[str, Optional[int]]:
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
        n_valid = n_total - n_discard
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
            }
        )

    if group_cols:
        out = df.groupby(group_cols, dropna=False).apply(agg_fn).reset_index()
    else:
        out = agg_fn(df).to_frame().T

    return out


def _build_ts_to_idx(bars: pd.DataFrame) -> Dict[pd.Timestamp, int]:
    return {ts: i for i, ts in enumerate(bars["bar_ts"].values)}


def _sample_unconditional(
    bars_eval: pd.DataFrame,
    n: int,
    rng: np.random.Generator,
) -> np.ndarray:
    ts = bars_eval["bar_ts"].values
    if len(ts) == 0:
        raise ValueError("No eligible bars to sample from (check horizon cutoff).")
    replace = n > len(ts)
    idx = rng.choice(len(ts), size=n, replace=replace)
    return ts[idx]


def _sample_state_matched(
    bars_eval: pd.DataFrame,
    allow_df: pd.DataFrame,
    rng: np.random.Generator,
    use_quality: bool,
) -> np.ndarray:
    if "state_hat" not in bars_eval.columns or "state_hat" not in allow_df.columns:
        return _sample_unconditional(bars_eval, len(allow_df), rng)

    if use_quality and ("quality_label" in bars_eval.columns) and ("quality_label" in allow_df.columns):
        key_cols = ["state_hat", "quality_label"]
    else:
        key_cols = ["state_hat"]

    pools: Dict[tuple, np.ndarray] = {}
    for key, g in bars_eval.groupby(key_cols, dropna=False):
        pools[tuple(key) if isinstance(key, tuple) else (key,)] = g["bar_ts"].values

    out = []
    for _, row in allow_df.iterrows():
        if len(key_cols) == 2:
            key = (row.get("state_hat"), row.get("quality_label"))
        else:
            key = (row.get("state_hat"),)

        pool = pools.get(key)
        if pool is None or len(pool) == 0:
            # fallback: same-state only (if quality missing), else unconditional
            if len(key_cols) == 2:
                pool2 = bars_eval.loc[bars_eval["state_hat"] == row.get("state_hat"), "bar_ts"].values
                pool = pool2 if len(pool2) else bars_eval["bar_ts"].values
            else:
                pool = bars_eval["bar_ts"].values

        j = rng.integers(0, len(pool))
        out.append(pool[j])

    return np.array(out)


def _sample_setup_state_matched(
    bars_eval: pd.DataFrame,
    allow_df: pd.DataFrame,
    rng: np.random.Generator,
    use_quality: bool,
) -> np.ndarray:
    """
    Conservative baseline for by-setup comparisons:
    - We preserve setup_family labels from ALLOW rows (carried to baseline events)
    - Sampling is matched on state_hat (and optionally quality_label) because those exist in bars.
    NOTE: This does NOT "match setup" in the bars (setup_family doesn't exist there). It's still valid
    for comparing ALLOW setups vs a conservative state-matched baseline.
    """
    if "state_hat" not in bars_eval.columns or "state_hat" not in allow_df.columns:
        return _sample_unconditional(bars_eval, len(allow_df), rng)

    if use_quality and ("quality_label" in bars_eval.columns) and ("quality_label" in allow_df.columns):
        key_cols = ["state_hat", "quality_label"]
    else:
        key_cols = ["state_hat"]

    pools: Dict[tuple, np.ndarray] = {}
    for key, g in bars_eval.groupby(key_cols, dropna=False):
        pools[tuple(key) if isinstance(key, tuple) else (key,)] = g["bar_ts"].values

    out = []
    for _, row in allow_df.iterrows():
        if len(key_cols) == 2:
            key = (row.get("state_hat"), row.get("quality_label"))
        else:
            key = (row.get("state_hat"),)

        pool = pools.get(key)
        if pool is None or len(pool) == 0:
            pool = bars_eval["bar_ts"].values

        j = rng.integers(0, len(pool))
        out.append(pool[j])

    return np.array(out)


def _evaluate_ts_list(
    bars: pd.DataFrame,
    ts_list: np.ndarray,
    tf: str,
    label: str,
    setup_families: Optional[np.ndarray] = None,
) -> pd.DataFrame:
    horizon = HORIZON_BARS[tf]
    ts_to_idx = _build_ts_to_idx(bars)

    rows = []
    missing = 0
    for i, ts in enumerate(ts_list):
        if ts not in ts_to_idx:
            missing += 1
            continue

        idx = ts_to_idx[ts]
        base = float(bars.at[idx, "close"])
        X = float(bars.at[idx, "X"])
        outcome, bars_to_touch = _compute_outcome_for_event(bars, idx, base, X, horizon)
        year = pd.Timestamp(ts).year

        row = {
            "baseline": label,
            "tf": tf,
            "bar_ts": ts,
            "year": year,
            "base_close": base,
            "X": X,
            "k": K_FIXED,
            "horizon_bars": horizon,
            "outcome": outcome,
            "bars_to_touch": bars_to_touch,
        }

        if setup_families is not None:
            row["setup_family"] = str(setup_families[i])

        if "state_hat" in bars.columns:
            row["state_hat"] = bars.at[idx, "state_hat"]
        if "quality_label" in bars.columns:
            row["quality_label"] = bars.at[idx, "quality_label"]

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"No baseline events evaluated for {label}. missing_ts={missing}")
    return df


def _compare_summaries(allow_sum: pd.DataFrame, base_sum: pd.DataFrame, key_cols: list) -> pd.DataFrame:
    merged = allow_sum.merge(base_sum, on=key_cols, how="left", suffixes=("_allow", "_base"))
    merged["uplift_touch_rate"] = merged["touch_rate_allow"] - merged["touch_rate_base"]
    merged["uplift_discard_rate"] = merged["discard_rate_allow"] - merged["discard_rate_base"]
    merged["uplift_mean_bars_to_touch"] = merged["mean_bars_to_touch_allow"] - merged["mean_bars_to_touch_base"]
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=False, default="", help="Symbol label (for report headers only)")
    ap.add_argument("--tf", required=True, choices=["H2", "M30"])
    ap.add_argument("--events_summary", required=True, help="Path to expansion_scalp_events.csv from audit_expansion_scalp.py")
    ap.add_argument("--bars", required=True, help="Path to bars (.parquet/.csv) containing OHLC")
    ap.add_argument("--seed", required=False, type=int, default=42, help="RNG seed (reproducibility)")
    ap.add_argument("--out", required=True, help="Output directory (same folder as audit is fine)")
    ap.add_argument("--use_quality_match", action="store_true", help="If set, baseline B1 matches (state_hat, quality_label) when available")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    allow_df = pd.read_csv(args.events_summary)
    if allow_df.empty:
        raise ValueError("events_summary is empty")

    if "bar_ts" not in allow_df.columns:
        raise ValueError("events_summary missing bar_ts column")
    allow_df["bar_ts"] = _ensure_datetime(allow_df["bar_ts"])
    allow_df = allow_df.dropna(subset=["bar_ts"]).sort_values("bar_ts").reset_index(drop=True)

    # Ensure setup_family exists for by-setup reports
    if "setup_family" not in allow_df.columns:
        allow_df["setup_family"] = "UNKNOWN"

    bars = _read_bars(args.bars)

    horizon = HORIZON_BARS[args.tf]
    last_valid_idx = len(bars) - 1 - horizon
    if last_valid_idx < 1:
        raise ValueError("bars too short for the requested horizon")
    bars_eval = bars.loc[:last_valid_idx].copy().reset_index(drop=True)

    rng = np.random.default_rng(args.seed)
    n = len(allow_df)

    # --- Baseline B0: Unconditional
    ts_b0 = _sample_unconditional(bars_eval, n=n, rng=rng)
    df_b0 = _evaluate_ts_list(bars, ts_b0, tf=args.tf, label="B0_unconditional")

    # --- Baseline B1: State(+Quality) matched
    ts_b1 = _sample_state_matched(
        bars_eval=bars_eval,
        allow_df=allow_df,
        rng=rng,
        use_quality=args.use_quality_match,
    )
    df_b1 = _evaluate_ts_list(bars, ts_b1, tf=args.tf, label="B1_state_matched")

    # --- Baseline B3: setup-labeled + state matched (conservative, valid)
    setup_labels = allow_df["setup_family"].astype(str).values
    ts_b3 = _sample_setup_state_matched(
        bars_eval=bars_eval,
        allow_df=allow_df,
        rng=rng,
        use_quality=args.use_quality_match,
    )
    df_b3 = _evaluate_ts_list(
        bars,
        ts_b3,
        tf=args.tf,
        label="B3_setup_state_matched",
        setup_families=setup_labels,
    )

    # Save baseline event-level outputs
    df_b0.to_csv(out_dir / "baseline_B0_events.csv", index=False)
    df_b1.to_csv(out_dir / "baseline_B1_events.csv", index=False)
    df_b3.to_csv(out_dir / "baseline_B3_events.csv", index=False)

    # ALLOW summaries
    allow_df2 = allow_df.copy()
    allow_df2["year"] = _ensure_datetime(allow_df2["bar_ts"]).dt.year

    if "outcome" not in allow_df2.columns:
        raise ValueError("events_summary missing outcome column (did you pass the correct file?)")
    if "bars_to_touch" not in allow_df2.columns:
        allow_df2["bars_to_touch"] = np.nan

    allow_global = _summarize(allow_df2)
    allow_by_year = _summarize(allow_df2, group_cols=["year"])

    # Baseline summaries
    b0_global = _summarize(df_b0)
    b0_by_year = _summarize(df_b0, group_cols=["year"])

    b1_global = _summarize(df_b1)
    b1_by_year = _summarize(df_b1, group_cols=["year"])

    # Compare: global
    allow_global["key"] = 1
    b0_global["key"] = 1
    b1_global["key"] = 1

    comp_b0_global = _compare_summaries(allow_global, b0_global, key_cols=["key"]).drop(columns=["key"])
    comp_b1_global = _compare_summaries(allow_global, b1_global, key_cols=["key"]).drop(columns=["key"])

    comp_global = pd.concat(
        [
            comp_b0_global.assign(baseline="B0_unconditional"),
            comp_b1_global.assign(baseline="B1_state_matched"),
        ],
        ignore_index=True,
    )

    # Compare: by year
    comp_b0_year = _compare_summaries(allow_by_year, b0_by_year, key_cols=["year"]).assign(baseline="B0_unconditional")
    comp_b1_year = _compare_summaries(allow_by_year, b1_by_year, key_cols=["year"]).assign(baseline="B1_state_matched")
    comp_by_year = pd.concat([comp_b0_year, comp_b1_year], ignore_index=True)

    # Compare: by setup_family (ALLOW vs B3 conservative)
    allow_by_setup = _summarize(allow_df2, group_cols=["setup_family"])
    b3_by_setup = _summarize(df_b3, group_cols=["setup_family"])
    comp_by_setup = _compare_summaries(allow_by_setup, b3_by_setup, key_cols=["setup_family"]).assign(
        baseline="B3_setup_state_matched"
    )
    comp_by_setup = comp_by_setup.sort_values(["uplift_touch_rate", "n_events_allow"], ascending=[False, False])
    comp_by_setup.to_csv(out_dir / "baseline_compare_by_setup_family.csv", index=False)

    # Write compares
    comp_global.to_csv(out_dir / "baseline_compare.csv", index=False)
    comp_by_year.to_csv(out_dir / "baseline_compare_by_year.csv", index=False)

    # Write baseline summaries (handy)
    allow_global.to_csv(out_dir / "allow_summary_global.csv", index=False)
    allow_by_year.to_csv(out_dir / "allow_summary_by_year.csv", index=False)
    b0_global.to_csv(out_dir / "baseline_B0_summary_global.csv", index=False)
    b0_by_year.to_csv(out_dir / "baseline_B0_summary_by_year.csv", index=False)
    b1_global.to_csv(out_dir / "baseline_B1_summary_global.csv", index=False)
    b1_by_year.to_csv(out_dir / "baseline_B1_summary_by_year.csv", index=False)

    # Console output
    print("=== Expansion Scalp Baselines ===")
    print(f"symbol={args.symbol} tf={args.tf} k={K_FIXED} horizon_bars={horizon} seed={args.seed}")
    print(f"bars: {args.bars}")
    print(f"ALLOW events_summary: {args.events_summary} (n={n})")
    print(f"out: {out_dir.resolve()}")
    print("\nGLOBAL COMPARE (ALLOW vs baseline):")
    cols = [
        "baseline",
        "n_events_allow",
        "touch_rate_allow",
        "touch_rate_base",
        "uplift_touch_rate",
        "discard_rate_allow",
        "discard_rate_base",
        "uplift_discard_rate",
        "mean_bars_to_touch_allow",
        "mean_bars_to_touch_base",
        "uplift_mean_bars_to_touch",
    ]
    print(comp_global[cols].to_string(index=False))
    print("\nWrote baseline_compare_by_setup_family.csv (ALLOW vs B3_setup_state_matched).")


if __name__ == "__main__":
    main()
