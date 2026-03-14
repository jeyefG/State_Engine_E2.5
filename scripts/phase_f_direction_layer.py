# scripts/phase_f_direction_layer.py
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


# ---------------------------------------------------------------------
# Helpers: datetime normalization
# ---------------------------------------------------------------------
def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    """
    Convert any datetime-like Series to "server-naive" timestamps (no timezone).
    This avoids silent tz-mismatch merges (common when parquet has tz-aware time).
    """
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        # If tz-aware, drop tz info to become naive
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        # Some pandas versions / mixed dtype can throw; keep best-effort.
        pass
    return dt


# ---------------------------------------------------------------------
# Price-action features on H2 stream (computed from enriched parquet OHLC)
# ---------------------------------------------------------------------
def compute_pa_features_h2(
    df_h2: pd.DataFrame,
    k_trend: int = 6,
    k_range: int = 12,
    flat_bps: float = 2.0,
) -> pd.DataFrame:
    """
    Adds:
      - trend_dir_h2: UP / DOWN / FLAT based on k_trend bars change and flat_bps threshold
      - range_pos_h2: position of close within rolling [low, high] over k_range bars (0..1)
    """
    df = df_h2.sort_values("time").copy()

    close = df["close"].astype(float)

    # Trend direction (simple delta with small dead-zone "flat_bps")
    delta = close - close.shift(k_trend)
    thr = (flat_bps / 10000.0) * close
    df["trend_dir_h2"] = np.where(delta > thr, "UP", np.where(delta < -thr, "DOWN", "FLAT"))

    # Range position within rolling window
    roll_low = df["low"].astype(float).rolling(k_range, min_periods=k_range).min()
    roll_high = df["high"].astype(float).rolling(k_range, min_periods=k_range).max()
    denom = (roll_high - roll_low).replace(0, np.nan)
    df["range_pos_h2"] = ((close - roll_low) / denom).clip(0, 1)

    return df


# ---------------------------------------------------------------------
# Direction layer: map baseline -> (setup_family, side_intent)
# NOTE: This logic is intentionally "template-like" (not in Phase E).
# ---------------------------------------------------------------------
def pick_setup_and_side(row) -> tuple[str, str]:
    decision = str(row.get("decision", "")).upper()
    if decision != "ALLOW":
        return "blocked", "NONE"

    baseline = row.get("meta_baseline_id")
    if baseline is None or (isinstance(baseline, float) and np.isnan(baseline)):
        return "allow_missing_baseline", "NONE"

    baseline = str(baseline)
    trend_dir = str(row.get("trend_dir_h2", "FLAT")).upper()

    # -------------------------
    # TREND-ish baselines
    # -------------------------
    if baseline == "STATE_REINFORCEMENT":
        if trend_dir == "UP":
            return "state_reinforcement", "LONG"
        if trend_dir == "DOWN":
            return "state_reinforcement", "SHORT"
        return "state_reinforcement_flat", "NONE"

    # EURUSD: trend-ish
    if baseline == "STATE_FRAGILITY":
        if trend_dir == "UP":
            return "state_fragility", "LONG"
        if trend_dir == "DOWN":
            return "state_fragility", "SHORT"
        return "state_fragility_flat", "NONE"
    
    # FX / noise baselines: directionless by default (no agenda)
    if baseline == "TRANSITION_NOISE":
        return "transition_noise", "NONE"

    # TRANSITION directionally tradable (US500)
    if baseline == "TRANSITION_RESOLUTION":
        if trend_dir == "UP":
            return "transition_resolution", "LONG"
        if trend_dir == "DOWN":
            return "transition_resolution", "SHORT"
        return "transition_resolution_flat", "NONE"

    # XAU: transition persistence directionally tradable
    if baseline == "TRANSITION_PERSISTENCE":
        if trend_dir == "UP":
            return "transition_persistence", "LONG"
        if trend_dir == "DOWN":
            return "transition_persistence", "SHORT"
        return "transition_persistence_flat", "NONE"

    # -------------------------
    # BALANCE baseline: use VWAP z-score to decide fade/center/tail
    # IMPORTANT: this REQUIRES close/vwap/sigma to be present (from enriched parquet)
    # -------------------------
    if baseline == "BALANCE_STABILITY":
        close_ = row.get("close", np.nan)
        vwap = row.get("ctx_vwap", np.nan)
        sigma = row.get("ctx_vwap_sigma", np.nan)

        # If we can't compute z, we keep setup but do not trade directionally
        if np.isnan(close_) or np.isnan(vwap) or np.isnan(sigma) or sigma == 0:
            return "balance_stability", "NONE"

        z = (close_ - vwap) / sigma

        if abs(z) <= 0.8:
            return "balance_stability_center", "NONE"
        if abs(z) >= 2.0:
            return "balance_stability_tail", "NONE"

        # "fade": above vwap => short, below vwap => long
        if z > 0:
            return "balance_stability_fade", "SHORT"
        return "balance_stability_fade", "LONG"

    return "allow_unmapped_baseline", "NONE"


# ---------------------------------------------------------------------
# Policy helper: which baselines are declared tradeable by YAML (sanity check)
# ---------------------------------------------------------------------
def _load_tradeable_baselines_from_phase_f_policy(phase_f_policy_path: str) -> set[str]:
    with open(phase_f_policy_path, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f) or {}

    tradeable: set[str] = set()
    for item in policy.get("go_contexts", []) or []:
        exp = item.get("expected_baseline_id")
        if exp:
            tradeable.add(str(exp))
    return tradeable


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main(symbol: str, enriched_parquet: str, decisions_csv: str, out_csv: str, phase_f_policy: str):
    """
    Robust wiring:
      - Load decisions.csv (ts OR time)
      - Load enriched parquet (must have time; ideally OHLC + vwap bands)
      - Normalize datetime to server-naive
      - Merge on (symbol + timestamp) so that direction layer has OHLC + VWAP columns
      - Compute PA features on merged frame and assign setup_family / side_intent
      - Export a richer decisions_with_side.csv including OHLC+VWAP columns
        to avoid downstream "missing close/ctx_vwap/ctx_vwap_sigma" failures.
    """

    # --- policy sanity (optional but useful)
    tradeable_baselines = _load_tradeable_baselines_from_phase_f_policy(phase_f_policy)
    if tradeable_baselines:
        print(f"[INFO] tradeable_baselines (from Phase F policy) = {sorted(tradeable_baselines)}")
    else:
        print("[WARN] tradeable_baselines empty (no expected_baseline_id in go_contexts). Sanity check disabled.")

    # -----------------------------------------------------------------
    # Load inputs
    # -----------------------------------------------------------------
    dec = pd.read_csv(decisions_csv)
    enr = pd.read_parquet(enriched_parquet)
    
    # --- detect timestamp column in decisions (ts is usual; some runs may already call it time)
    ts_col = "ts" if "ts" in dec.columns else ("time" if "time" in dec.columns else None)
    if ts_col is None:
        raise RuntimeError("decisions_csv must contain 'ts' or 'time' column for merge with enriched parquet")
    
    # --- normalize datetimes to server-naive
    dec[ts_col] = to_server_naive_datetime(dec[ts_col])
    
    if "time" not in enr.columns:
        raise RuntimeError("enriched_parquet must contain 'time' column")
    enr["time"] = to_server_naive_datetime(enr["time"])
    
    # --- ensure symbol columns (do NOT overwrite if present)
    if "symbol" not in dec.columns:
        dec["symbol"] = symbol
    if "symbol" not in enr.columns:
        enr["symbol"] = symbol
    
    # --- filter to symbol early (keeps merge clean and faster)
    dec = dec[dec["symbol"] == symbol].copy()
    enr = enr[enr["symbol"] == symbol].copy()
    
    # --- avoid collision when decisions uses 'time'
    ts_decision_col = ts_col
    if ts_col == "time":
        ts_decision_col = "ts_decision"
        dec = dec.rename(columns={"time": ts_decision_col})
    
    # --- ensure required columns exist in decisions
    if "decision" not in dec.columns:
        raise RuntimeError("decisions_csv missing required column: decision")
    
    # Backward-compatible schema: some runners export 'baseline_id'
    if "meta_baseline_id" not in dec.columns:
        if "baseline_id" in dec.columns:
            dec["meta_baseline_id"] = dec["baseline_id"]
        else:
            raise RuntimeError("decisions_csv missing required column: meta_baseline_id (or baseline_id)")
    
    # --- choose enriched columns to bring (fat output for auditing & Balance templates)
    need_cols = [
        "symbol", "time",
        "open", "high", "low", "close",
        "ctx_vwap", "ctx_vwap_sigma", "ctx_vwap_hi", "ctx_vwap_lo",
        "ctx_session_bucket",
    ]
    have_cols = [c for c in need_cols if c in enr.columns]
    
    # --- merge: symbol + timestamp
    merged = dec.merge(
        enr[have_cols],
        left_on=["symbol", ts_decision_col],
        right_on=["symbol", "time"],
        how="left",
    )
    
    # --- quick merge audit (this is your early warning for wiring problems)
    hit_close = float(merged["close"].notna().mean()) if "close" in merged.columns else 0.0
    print(f"[merge] hit_rate close: {hit_close:.3f} (expected ~1.0)")
    
    # --- OPTIONAL: compute PA features only if we have OHLC (needed for trend_dir_h2)
    # if OHLC missing, trend_dir_h2 will default to FLAT in pick_setup_and_side
    if all(c in merged.columns for c in ["time", "open", "high", "low", "close"]):
        tmp = merged.dropna(subset=["time"]).copy()
        tmp = tmp.sort_values("time")
        tmp = compute_pa_features_h2(tmp, k_trend=6, k_range=12, flat_bps=2.0)
        # re-attach computed cols back to merged (by symbol+time)
        merged = merged.drop(columns=[c for c in ["trend_dir_h2", "range_pos_h2"] if c in merged.columns], errors="ignore")
        merged = merged.merge(
            tmp[["symbol", "time"] + [c for c in ["trend_dir_h2", "range_pos_h2"] if c in tmp.columns]],
            on=["symbol", "time"],
            how="left",
        )
    
    # --- decide setup_family + side_intent
    out_setup = merged.apply(pick_setup_and_side, axis=1, result_type="expand")
    merged["setup_family"] = out_setup[0]
    merged["side_intent"] = out_setup[1]
    
    # --- allow distribution sanity print (helps detect unexpected collapse to NONE)
    allow = merged[merged["decision"].astype(str).str.upper().eq("ALLOW")].copy()
    if not allow.empty:
        summary = (
            allow.groupby(["meta_baseline_id", "setup_family", "side_intent"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        print("[INFO] ALLOW distribution (top 15):")
        print(summary.head(15).to_string(index=False))
    
    # --- export: fat decisions_with_side
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    
    keep_cols = [
        "symbol",
        ts_decision_col,   # decisions ts (ts or ts_decision)
        "time",            # enriched bar time
        "decision",
        "context_key",
        "meta_baseline_id",
        "setup_family",
        "side_intent",
        # enriched/audit columns
        "open", "high", "low", "close",
        "ctx_vwap", "ctx_vwap_sigma", "ctx_vwap_hi", "ctx_vwap_lo",
        "ctx_session_bucket",
        # PA features (optional)
        "trend_dir_h2", "range_pos_h2",
    ]
    
    keep_cols = [c for c in keep_cols if c in merged.columns]
    merged[keep_cols].to_csv(out_csv, index=False)
    print(f"[OK] wrote {out_csv} cols={len(keep_cols)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--enriched_parquet", required=True)
    ap.add_argument("--decisions_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument(
        "--phase_f_policy",
        required=True,
        help="Phase F policy YAML (configs/phase_f/<symbol>.yaml). Used for baseline sanity check.",
    )
    args = ap.parse_args()

    main(
        symbol=args.symbol,
        enriched_parquet=args.enriched_parquet,
        decisions_csv=args.decisions_csv,
        out_csv=args.out_csv,
        phase_f_policy=args.phase_f_policy,
    )