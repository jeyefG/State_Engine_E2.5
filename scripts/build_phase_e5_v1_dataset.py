#build_phase_e5_v1_dataset.py
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


LABEL_MAP = {0: "NO_TRADE", 1: "LONG", 2: "SHORT"}


@dataclass(frozen=True)
class BuildConfig:
    context_tf: str
    window_hours: int
    horizon_bars: int
    min_move_scale: float
    dominance_ratio: float
    scale_col: str
    entry_price_mode: str
    unit: str
    include_current_bar: bool


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Build Phase E.5 V1 dataset directly from enriched D/E context"
    )
    ap.add_argument("--symbol", required=True)
    ap.add_argument(
        "--context-parquet",
        required=True,
        help="Phase D/E enriched context parquet with OHLC",
    )
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--context-tf", default="H1", help="Context timeframe, e.g. H1/H2/M30")
    ap.add_argument("--window-hours", type=int, default=12, help="Lookback window in hours")
    ap.add_argument("--horizon-bars", type=int, default=8, help="Forward horizon in bars")
    ap.add_argument(
        "--min-move-scale",
        type=float,
        default=1.0,
        help="Minimum normalized excursion required to consider a directional resolution",
    )
    ap.add_argument(
        "--dominance-ratio",
        type=float,
        default=1.25,
        help="Required dominance ratio between winning and losing excursion",
    )
    ap.add_argument(
        "--scale-col",
        default="ctx_vwap_sigma",
        help="Column used as local volatility scale for excursion normalization",
    )
    ap.add_argument(
        "--entry-price-mode",
        default="next_open",
        choices=["next_open", "close"],
        help="Entry anchor used for target construction",
    )
    ap.add_argument(
        "--unit",
        default="episode_start",
        choices=["episode_start", "decision_bar"],
        help="episode_start reduces redundancy; decision_bar keeps all bars",
    )
    ap.add_argument(
        "--include-current-bar",
        action="store_true",
        help="Include current bar inside lookback summary window. Default uses only prior bars.",
    )
    ap.add_argument("--train-frac", type=float, default=0.60)
    ap.add_argument("--val-frac", type=float, default=0.20)
    ap.add_argument("--train-end", default=None, help="Optional explicit train end date YYYY-MM-DD")
    ap.add_argument("--val-end", default=None, help="Optional explicit validation end date YYYY-MM-DD")
    ap.add_argument(
        "--phase-e-registry-csv",
        default=None,
        help="Optional historical/causal Phase E registry snapshot. Ignored in V1 by default to avoid leakage.",
    )
    return ap.parse_args()


# ------------------------------
# Time helpers
# ------------------------------

def timeframe_to_minutes(tf: str) -> int:
    s = str(tf).upper().strip()
    if s.startswith("M"):
        return int(s[1:])
    if s.startswith("H"):
        return int(s[1:]) * 60
    if s.startswith("D"):
        return int(s[1:]) * 24 * 60
    raise ValueError(f"Unsupported context_tf: {tf}")


def derive_window_bars(context_tf: str, window_hours: int) -> int:
    minutes = timeframe_to_minutes(context_tf)
    total_minutes = int(window_hours * 60)
    return max(1, total_minutes // minutes)


# ------------------------------
# Loading / normalization
# ------------------------------

def normalize_time_col(df: pd.DataFrame, desired: str) -> pd.DataFrame:
    out = df.copy()
    if desired not in out.columns:
        idx_name = out.index.name
        if idx_name == desired:
            out = out.reset_index()
        elif "time" in out.columns and desired != "time":
            out = out.rename(columns={"time": desired})
        elif "ts" in out.columns and desired != "ts":
            out = out.rename(columns={"ts": desired})
        else:
            out = out.reset_index().rename(columns={out.index.name or "index": desired})
    out[desired] = pd.to_datetime(out[desired])
    return out


def load_context(path: Path, symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "symbol" in df.columns:
        df = df[df["symbol"].astype(str) == str(symbol)].copy()
    df = normalize_time_col(df, "time")
    df = df.sort_values(["symbol", "time"] if "symbol" in df.columns else ["time"]).reset_index(drop=True)
    return df


def _safe_int(x: object) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def _safe_float(x: object) -> float:
    try:
        return float(x)
    except Exception:
        return np.nan


def active_lf_signature(row: pd.Series, lf_cols: list[str]) -> str:
    active = [c for c in lf_cols if _safe_int(row.get(c, 0)) == 1]
    if not active:
        return "NONE"
    return "|".join(sorted(active))


# ------------------------------
# Episode construction
# ------------------------------

def ql_col_name(ctx: pd.DataFrame) -> str | None:
    if "quality_label_full" in ctx.columns:
        return "quality_label_full"
    if "quality_label" in ctx.columns:
        return "quality_label"
    return None


def mark_episode_starts_from_context(ctx_rows: pd.DataFrame, context_tf: str, ql_col: str | None) -> pd.DataFrame:
    """
    New episode if:
    - first row
    - temporal gap > 1.5 * bar interval
    - LF signature changes
    - state_hat changes
    - quality label changes
    """
    out = ctx_rows.copy()
    out = out.sort_values(["symbol", "time"] if "symbol" in out.columns else ["time"]).reset_index(drop=True)

    interval = pd.Timedelta(minutes=timeframe_to_minutes(context_tf))
    gap_limit = interval * 1.5

    if "symbol" in out.columns:
        prev_time = out.groupby("symbol", dropna=False)["time"].shift(1)
        prev_lf = out.groupby("symbol", dropna=False)["lf_signature_ctx"].shift(1)
        prev_state = out.groupby("symbol", dropna=False)["state_hat"].shift(1) if "state_hat" in out.columns else pd.Series(index=out.index, dtype="object")
        if ql_col is not None and ql_col in out.columns:
            prev_ql = out.groupby("symbol", dropna=False)[ql_col].shift(1)
        else:
            prev_ql = pd.Series(["NA"] * len(out), index=out.index, dtype="object")
    else:
        prev_time = out["time"].shift(1)
        prev_lf = out["lf_signature_ctx"].shift(1)
        prev_state = out["state_hat"].shift(1) if "state_hat" in out.columns else pd.Series(index=out.index, dtype="object")
        if ql_col is not None and ql_col in out.columns:
            prev_ql = out[ql_col].shift(1)
        else:
            prev_ql = pd.Series(["NA"] * len(out), index=out.index, dtype="object")

    gap_break = prev_time.isna() | ((out["time"] - prev_time) > gap_limit)
    lf_break = prev_lf.isna() | (out["lf_signature_ctx"] != prev_lf)

    if "state_hat" in out.columns:
        state_break = prev_state.isna() | (out["state_hat"] != prev_state)
    else:
        state_break = pd.Series([False] * len(out), index=out.index)

    if ql_col is not None and ql_col in out.columns:
        ql_break = prev_ql.isna() | (out[ql_col].astype(str) != prev_ql.astype(str))
    else:
        ql_break = pd.Series([False] * len(out), index=out.index)

    out["episode_start"] = gap_break | lf_break | state_break | ql_break
    return out


def build_candidate_universe_from_context(
    ctx: pd.DataFrame,
    context_tf: str,
    unit: str,
    lf_cols: list[str],
    ql_col: str | None,
) -> pd.DataFrame:
    """
    Full context universe.
    No Phase F filtering.
    """
    out = ctx.copy()

    if lf_cols:
        out["lf_signature_ctx"] = out.apply(lambda r: active_lf_signature(r, lf_cols), axis=1)
        out["lf_active_any"] = (out[lf_cols].fillna(0).astype(int).sum(axis=1) > 0)
    else:
        out["lf_signature_ctx"] = "NONE"
        out["lf_active_any"] = False

    out = mark_episode_starts_from_context(out, context_tf=context_tf, ql_col=ql_col)

    if unit == "episode_start":
        out = out[out["episode_start"]].copy()

    return out.sort_values(["symbol", "time"] if "symbol" in out.columns else ["time"]).reset_index(drop=True)


# ------------------------------
# Feature engineering
# ------------------------------

def state_name(v: object) -> str:
    try:
        iv = int(v)
    except Exception:
        return "NA"
    return {0: "BALANCE", 1: "TRANSITION", 2: "TREND"}.get(iv, "NA")


def add_context_row_features(base: dict, row: pd.Series, lf_cols: list[str], ql_col: str | None) -> dict:
    base["state_hat"] = _safe_int(row.get("state_hat", np.nan))
    base["state_name"] = state_name(row.get("state_hat", np.nan))
    base["quality_label"] = str(row.get(ql_col, "NA")) if ql_col is not None else "NA"
    base["ctx_session_bucket"] = str(row.get("ctx_session_bucket", "NA"))
    base["ctx_state_age"] = _safe_float(row.get("ctx_state_age", np.nan))
    base["margin_now"] = _safe_float(row.get("margin", np.nan))
    base["dist_vwap_atr_now"] = _safe_float(row.get("ctx_dist_vwap_atr", np.nan))
    base["close_now"] = _safe_float(row.get("close", np.nan))
    base["vwap_now"] = _safe_float(row.get("ctx_vwap", np.nan))
    base["vwap_sigma_now"] = _safe_float(row.get("ctx_vwap_sigma", np.nan))
    base["spread_now"] = _safe_float(row.get("spread", np.nan))

    close = base["close_now"]
    vwap = base["vwap_now"]
    sig = base["vwap_sigma_now"]
    if np.isfinite(close) and np.isfinite(vwap) and np.isfinite(sig) and sig != 0:
        base["z_vwap_now"] = (close - vwap) / sig
    else:
        base["z_vwap_now"] = np.nan

    base["lf_signature_now"] = active_lf_signature(row, lf_cols)
    base["lf_active_count_now"] = int(sum(_safe_int(row.get(c, 0)) == 1 for c in lf_cols))
    for c in lf_cols:
        base[c] = _safe_int(row.get(c, 0))

    if "context_key" in row.index:
        base["context_key"] = str(row.get("context_key", "NA"))
    if "baseline_id" in row.index:
        base["baseline_id"] = str(row.get("baseline_id", "NA"))
    elif "meta_baseline_id" in row.index:
        base["meta_baseline_id"] = str(row.get("meta_baseline_id", "NA"))

    return base


def summarize_window(base: dict, hist: pd.DataFrame, lf_cols: list[str], ql_col: str | None) -> dict:
    w = hist.copy()
    n = len(w)
    base["window_n_bars"] = n
    if n == 0:
        return base

    states = w["state_hat"].astype("Int64") if "state_hat" in w.columns else pd.Series(dtype="Int64")
    for v, name in [(0, "balance"), (1, "transition"), (2, "trend")]:
        base[f"share_state_{name}"] = float((states == v).mean()) if len(states) else np.nan

    if len(states):
        s = states.astype(str).fillna("NA")
        base["n_state_changes"] = int((s != s.shift(1)).sum() - 1) if len(s) > 0 else 0
    else:
        base["n_state_changes"] = np.nan

    if ql_col is not None and ql_col in w.columns:
        q = w[ql_col].astype(str).fillna("NA")
        current_ql = q.iloc[-1]
        base["share_current_ql"] = float((q == current_ql).mean())
        base["n_ql_changes"] = int((q != q.shift(1)).sum() - 1)
        base["ql_last"] = current_ql
    else:
        base["share_current_ql"] = np.nan
        base["n_ql_changes"] = np.nan
        base["ql_last"] = "NA"

    if lf_cols:
        lf_sig = w.apply(lambda r: active_lf_signature(r, lf_cols), axis=1)
        current_lf = lf_sig.iloc[-1]
        base["share_current_lf"] = float((lf_sig == current_lf).mean())
        base["n_lf_changes"] = int((lf_sig != lf_sig.shift(1)).sum() - 1)
        for c in lf_cols:
            base[f"share_{c}"] = float((w[c].fillna(0).astype(int) == 1).mean())
    else:
        base["share_current_lf"] = np.nan
        base["n_lf_changes"] = np.nan

    if "close" in w.columns:
        closes = w["close"].astype(float)
        if len(closes) >= 2:
            base["ret_window"] = float(closes.iloc[-1] / closes.iloc[0] - 1.0)
            base["ret_last_bar"] = float(closes.iloc[-1] / closes.iloc[-2] - 1.0)
            x = np.arange(len(closes), dtype=float)
            y = closes.values.astype(float)
            x_center = x - x.mean()
            denom = np.dot(x_center, x_center)
            slope = np.dot(x_center, y - y.mean()) / denom if denom > 0 else 0.0
            base["slope_close_per_bar"] = float(slope)
        else:
            base["ret_window"] = np.nan
            base["ret_last_bar"] = np.nan
            base["slope_close_per_bar"] = np.nan

        lo = float(closes.min())
        hi = float(closes.max())
        base["range_recent_low"] = lo
        base["range_recent_high"] = hi
        base["range_recent_width"] = hi - lo
        base["pos_in_recent_range"] = float((closes.iloc[-1] - lo) / (hi - lo)) if hi > lo else np.nan
        rets = closes.pct_change().dropna()
        base["ret_std_window"] = float(rets.std()) if len(rets) else np.nan
    else:
        base["ret_window"] = np.nan
        base["ret_last_bar"] = np.nan
        base["slope_close_per_bar"] = np.nan
        base["range_recent_low"] = np.nan
        base["range_recent_high"] = np.nan
        base["range_recent_width"] = np.nan
        base["pos_in_recent_range"] = np.nan
        base["ret_std_window"] = np.nan

    if {"ctx_vwap", "ctx_vwap_sigma", "close"}.issubset(w.columns):
        sig = w["ctx_vwap_sigma"].astype(float)
        vw = w["ctx_vwap"].astype(float)
        cl = w["close"].astype(float)
        z = np.where((sig.notna()) & (sig != 0), (cl - vw) / sig, np.nan)
        z = pd.Series(z, index=w.index)
        base["z_vwap_mean"] = float(z.mean()) if z.notna().any() else np.nan
        base["z_vwap_std"] = float(z.std()) if z.notna().sum() > 1 else np.nan
        base["z_vwap_last"] = float(z.iloc[-1]) if pd.notna(z.iloc[-1]) else np.nan
        base["z_vwap_abs_max"] = float(z.abs().max()) if z.notna().any() else np.nan
    else:
        base["z_vwap_mean"] = np.nan
        base["z_vwap_std"] = np.nan
        base["z_vwap_last"] = np.nan
        base["z_vwap_abs_max"] = np.nan

    if "ctx_dist_vwap_atr" in w.columns:
        d = w["ctx_dist_vwap_atr"].astype(float)
        base["dist_vwap_atr_mean"] = float(d.mean()) if d.notna().any() else np.nan
        base["dist_vwap_atr_last"] = float(d.iloc[-1]) if pd.notna(d.iloc[-1]) else np.nan
        base["dist_vwap_atr_max"] = float(d.max()) if d.notna().any() else np.nan
    else:
        base["dist_vwap_atr_mean"] = np.nan
        base["dist_vwap_atr_last"] = np.nan
        base["dist_vwap_atr_max"] = np.nan

    if "margin" in w.columns:
        mg = w["margin"].astype(float)
        base["margin_mean"] = float(mg.mean()) if mg.notna().any() else np.nan
        base["margin_last"] = float(mg.iloc[-1]) if pd.notna(mg.iloc[-1]) else np.nan
        base["margin_std"] = float(mg.std()) if mg.notna().sum() > 1 else np.nan
        base["margin_min"] = float(mg.min()) if mg.notna().any() else np.nan
    else:
        base["margin_mean"] = np.nan
        base["margin_last"] = np.nan
        base["margin_std"] = np.nan
        base["margin_min"] = np.nan

    if {"high", "low", "close"}.issubset(w.columns):
        rng = (w["high"].astype(float) - w["low"].astype(float)) / w["close"].astype(float)
        base["bar_range_mean"] = float(rng.mean()) if rng.notna().any() else np.nan
        base["bar_range_last"] = float(rng.iloc[-1]) if pd.notna(rng.iloc[-1]) else np.nan
        base["bar_range_std"] = float(rng.std()) if rng.notna().sum() > 1 else np.nan
    else:
        base["bar_range_mean"] = np.nan
        base["bar_range_last"] = np.nan
        base["bar_range_std"] = np.nan

    return base


# ------------------------------
# Target construction
# ------------------------------

def resolve_local_scale(ctx: pd.DataFrame, row_idx: int, scale_col: str) -> float:
    row = ctx.iloc[row_idx]

    if scale_col in row.index:
        scale = _safe_float(row.get(scale_col, np.nan))
        if np.isfinite(scale) and scale > 0:
            return float(scale)

    hi = _safe_float(row.get("high", np.nan))
    lo = _safe_float(row.get("low", np.nan))
    if np.isfinite(hi) and np.isfinite(lo) and hi > lo:
        return float(hi - lo)

    close = _safe_float(row.get("close", np.nan))
    if np.isfinite(close) and close > 0:
        return float(close * 0.001)

    return np.nan


def excursion_dominance_target(
    ctx: pd.DataFrame,
    row_idx: int,
    horizon_bars: int,
    min_move_scale: float,
    dominance_ratio: float,
    scale_col: str = "ctx_vwap_sigma",
    entry_price_mode: str = "next_open",
) -> tuple[int, dict]:
    if entry_price_mode == "next_open":
        if row_idx + 1 >= len(ctx):
            return 0, {
                "target_reason": "no_future",
                "up_excursion": np.nan,
                "down_excursion": np.nan,
                "dominance_ratio_realized": np.nan,
                "local_scale": np.nan,
            }
        entry_px = _safe_float(ctx.iloc[row_idx + 1].get("open", np.nan))
        future = ctx.iloc[row_idx + 1: row_idx + 1 + horizon_bars]
    else:
        entry_px = _safe_float(ctx.iloc[row_idx].get("close", np.nan))
        future = ctx.iloc[row_idx + 1: row_idx + 1 + horizon_bars]

    if not np.isfinite(entry_px) or entry_px <= 0:
        return 0, {
            "target_reason": "bad_entry_px",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "dominance_ratio_realized": np.nan,
            "local_scale": np.nan,
        }

    if len(future) < horizon_bars:
        return 0, {
            "target_reason": "no_future",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "dominance_ratio_realized": np.nan,
            "local_scale": np.nan,
        }

    local_scale = resolve_local_scale(ctx, row_idx, scale_col)
    if not np.isfinite(local_scale) or local_scale <= 0:
        return 0, {
            "target_reason": "bad_scale",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "dominance_ratio_realized": np.nan,
            "local_scale": local_scale,
        }

    max_future_high = pd.to_numeric(future["high"], errors="coerce").max()
    min_future_low = pd.to_numeric(future["low"], errors="coerce").min()

    if not np.isfinite(max_future_high) or not np.isfinite(min_future_low):
        return 0, {
            "target_reason": "bad_future_path",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "dominance_ratio_realized": np.nan,
            "local_scale": local_scale,
        }

    up_excursion = (float(max_future_high) - entry_px) / local_scale
    down_excursion = (entry_px - float(min_future_low)) / local_scale

    eps = 1e-9
    dominance_up = up_excursion / max(down_excursion, eps)
    dominance_down = down_excursion / max(up_excursion, eps)
    dominance_realized = dominance_up if up_excursion >= down_excursion else dominance_down

    if up_excursion >= min_move_scale and dominance_up >= dominance_ratio:
        return 1, {
            "target_reason": "long_excursion_dominance",
            "up_excursion": float(up_excursion),
            "down_excursion": float(down_excursion),
            "dominance_ratio_realized": float(dominance_up),
            "local_scale": float(local_scale),
        }

    if down_excursion >= min_move_scale and dominance_down >= dominance_ratio:
        return 2, {
            "target_reason": "short_excursion_dominance",
            "up_excursion": float(up_excursion),
            "down_excursion": float(down_excursion),
            "dominance_ratio_realized": float(dominance_down),
            "local_scale": float(local_scale),
        }

    return 0, {
        "target_reason": "no_clear_dominance",
        "up_excursion": float(up_excursion),
        "down_excursion": float(down_excursion),
        "dominance_ratio_realized": float(dominance_realized),
        "local_scale": float(local_scale),
    }


# ------------------------------
# Split
# ------------------------------

def temporal_split(ts: pd.Series, train_frac: float, val_frac: float, train_end: str | None, val_end: str | None) -> pd.Series:
    t = pd.to_datetime(ts)
    if train_end or val_end:
        tr_end = pd.Timestamp(train_end) if train_end else t.quantile(train_frac)
        va_end = pd.Timestamp(val_end) if val_end else t.quantile(train_frac + val_frac)
    else:
        tr_end = t.quantile(train_frac)
        va_end = t.quantile(train_frac + val_frac)

    split = pd.Series(index=t.index, dtype="object")
    split.loc[t <= tr_end] = "train"
    split.loc[(t > tr_end) & (t <= va_end)] = "val"
    split.loc[t > va_end] = "test"
    return split


# ------------------------------
# Main build
# ------------------------------

def main() -> None:
    args = parse_args()
    cfg = BuildConfig(
        context_tf=args.context_tf,
        window_hours=args.window_hours,
        horizon_bars=args.horizon_bars,
        min_move_scale=args.min_move_scale,
        dominance_ratio=args.dominance_ratio,
        scale_col=args.scale_col,
        entry_price_mode=args.entry_price_mode,
        unit=args.unit,
        include_current_bar=bool(args.include_current_bar),
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ctx = load_context(Path(args.context_parquet), args.symbol)
    if ctx.empty:
        raise ValueError("Context parquet has no rows after symbol filter")

    lf_cols = sorted([c for c in ctx.columns if c.startswith("LOOK_FOR_")])
    ql_col = ql_col_name(ctx)

    if args.phase_e_registry_csv:
        print(
            "[WARN] --phase-e-registry-csv provided but ignored in V1. "
            "Using static Phase E registry as a feature can leak if it was fit on the same full sample."
        )

    candidates = build_candidate_universe_from_context(
        ctx=ctx,
        context_tf=cfg.context_tf,
        unit=cfg.unit,
        lf_cols=lf_cols,
        ql_col=ql_col,
    )
    if candidates.empty:
        raise ValueError("No candidate rows built from context parquet")

    ctx_full = ctx.sort_values(["symbol", "time"] if "symbol" in ctx.columns else ["time"]).reset_index(drop=True)

    key_to_idx: dict[tuple, int] = {}
    for i, r in ctx_full.iterrows():
        k = (r.get("symbol", args.symbol), pd.Timestamp(r["time"]))
        key_to_idx[k] = i

    window_bars = derive_window_bars(cfg.context_tf, cfg.window_hours)
    records: list[dict] = []

    for _, row in candidates.iterrows():
        sym = row.get("symbol", args.symbol)
        ts = pd.Timestamp(row["time"])
        idx = key_to_idx.get((sym, ts))
        if idx is None:
            continue

        start = max(0, idx - window_bars + (1 if cfg.include_current_bar else 0))
        end = idx + 1 if cfg.include_current_bar else idx
        hist = ctx_full.iloc[start:end].copy()

        feat: dict = {
            "timestamp": ts,
            "symbol": sym,
            "sample_unit": cfg.unit,
            "window_bars": window_bars,
            "horizon_bars": cfg.horizon_bars,
            "min_move_scale": cfg.min_move_scale,
            "dominance_ratio": cfg.dominance_ratio,
            "scale_col": cfg.scale_col,
            "entry_price_mode": cfg.entry_price_mode,
        }

        feat = add_context_row_features(feat, row, lf_cols, ql_col)
        feat = summarize_window(feat, hist, lf_cols, ql_col)

        y, meta = excursion_dominance_target(
            ctx=ctx_full,
            row_idx=idx,
            horizon_bars=cfg.horizon_bars,
            min_move_scale=cfg.min_move_scale,
            dominance_ratio=cfg.dominance_ratio,
            scale_col=cfg.scale_col,
            entry_price_mode=cfg.entry_price_mode,
        )
        feat["target"] = int(y)
        feat["target_label"] = LABEL_MAP[int(y)]
        feat.update(meta)
        records.append(feat)

    ds = pd.DataFrame(records)
    if ds.empty:
        raise ValueError("No rows built for dataset")

    ds = ds[~ds["target_reason"].isin(["no_future", "bad_entry_px", "bad_scale", "bad_future_path"])].copy()
    if ds.empty:
        raise ValueError("Dataset empty after dropping invalid target rows")

    ds = ds.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    ds["split"] = temporal_split(ds["timestamp"], args.train_frac, args.val_frac, args.train_end, args.val_end)

    stem = (
        f"PhaseE5V1_{args.symbol}_{cfg.context_tf}"
        f"_wh{cfg.window_hours}"
        f"_hb{cfg.horizon_bars}"
        f"_mm{str(cfg.min_move_scale).replace('.', 'p')}"
        f"_dr{str(cfg.dominance_ratio).replace('.', 'p')}"
        f"_{cfg.unit}"
    )
    parquet_path = out_dir / f"{stem}.parquet"
    csv_path = out_dir / f"{stem}.csv"
    meta_path = out_dir / f"{stem}_meta.json"

    ds.to_parquet(parquet_path, index=False)
    ds.to_csv(csv_path, index=False)

    meta = {
        "symbol": args.symbol,
        "context_tf": cfg.context_tf,
        "window_hours": cfg.window_hours,
        "window_bars": window_bars,
        "horizon_bars": cfg.horizon_bars,
        "min_move_scale": cfg.min_move_scale,
        "dominance_ratio": cfg.dominance_ratio,
        "scale_col": cfg.scale_col,
        "entry_price_mode": cfg.entry_price_mode,
        "unit": cfg.unit,
        "include_current_bar": cfg.include_current_bar,
        "n_rows": int(len(ds)),
        "split_counts": ds["split"].value_counts(dropna=False).to_dict(),
        "target_counts": ds["target_label"].value_counts(dropna=False).to_dict(),
        "lf_cols": lf_cols,
        "ql_col": ql_col,
        "notes": [
            "V1 ignores static Phase E registry fields by default to avoid leakage.",
            "Target is based on normalized future excursion dominance over horizon_bars.",
            "Universe is the full enriched context, not a Phase F allow subset.",
            "episode_start reduces redundancy; decision_bar keeps all bars.",
        ],
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    print("DATASET_BUILT")
    print({
        "rows": int(len(ds)),
        "targets": ds["target_label"].value_counts(dropna=False).to_dict(),
        "splits": ds["split"].value_counts(dropna=False).to_dict(),
        "parquet": str(parquet_path),
        "csv": str(csv_path),
        "meta": str(meta_path),
    })


if __name__ == "__main__":
    main()