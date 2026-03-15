from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BuildConfig:
    context_tf: str
    lookback_bars: int
    horizon_bars: int
    scale_col: str
    min_move_scale: float
    conflict_penalty: float
    target_temperature: float
    unit: str
    include_current_bar: bool


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Build Phase E.5 V2 dataset from D/E enriched context only (no Phase F dependencies)."
    )
    ap.add_argument("--context-parquet", nargs="+", required=True, help="One or more context parquet files")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--symbol", default=None, help="Optional single-symbol filter")
    ap.add_argument("--context-tf", default="H1")
    ap.add_argument("--lookback-bars", type=int, default=12)
    ap.add_argument("--horizon-bars", type=int, default=8)
    ap.add_argument("--scale-col", default="ctx_vwap_sigma")
    ap.add_argument("--min-move-scale", type=float, default=0.8)
    ap.add_argument("--conflict-penalty", type=float, default=0.65)
    ap.add_argument("--target-temperature", type=float, default=0.45)
    ap.add_argument("--unit", choices=["episode_start", "decision_bar"], default="episode_start")
    ap.add_argument("--include-current-bar", action="store_true")
    ap.add_argument("--require-lf-active", action="store_true", help="Optional strict subset from context (not Phase F)")
    ap.add_argument("--train-frac", type=float, default=0.6)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--train-end", default=None)
    ap.add_argument("--val-end", default=None)
    return ap.parse_args()


def timeframe_to_minutes(tf: str) -> int:
    s = str(tf).upper().strip()
    if s.startswith("M"):
        return int(s[1:])
    if s.startswith("H"):
        return int(s[1:]) * 60
    if s.startswith("D"):
        return int(s[1:]) * 24 * 60
    raise ValueError(f"Unsupported context_tf: {tf}")


def normalize_time_col(df: pd.DataFrame, desired: str = "time") -> pd.DataFrame:
    out = df.copy()
    if desired not in out.columns:
        idx_name = out.index.name
        if idx_name == desired:
            out = out.reset_index()
        elif "timestamp" in out.columns:
            out = out.rename(columns={"timestamp": desired})
        elif "ts" in out.columns:
            out = out.rename(columns={"ts": desired})
        elif "time" in out.columns:
            out = out.rename(columns={"time": desired})
        else:
            out = out.reset_index().rename(columns={out.index.name or "index": desired})
    out[desired] = pd.to_datetime(out[desired], errors="coerce")
    out = out[out[desired].notna()].copy()
    return out


def load_context(paths: list[str], symbol: str | None) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    for p in paths:
        df = pd.read_parquet(Path(p))
        df = normalize_time_col(df, "time")
        chunks.append(df)
    out = pd.concat(chunks, ignore_index=True)

    if "symbol" not in out.columns:
        if symbol is None:
            out["symbol"] = "UNKNOWN"
        else:
            out["symbol"] = str(symbol)

    if symbol is not None:
        out = out[out["symbol"].astype(str) == str(symbol)].copy()

    out = out.sort_values(["symbol", "time"]).reset_index(drop=True)
    return out


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


def ql_col_name(df: pd.DataFrame) -> str | None:
    for c in ["quality_label_full", "quality_label"]:
        if c in df.columns:
            return c
    return None


def discover_lf_cols(df: pd.DataFrame) -> list[str]:
    return sorted([c for c in df.columns if c.startswith("LOOK_FOR_")])


def active_lf_signature(row: pd.Series, lf_cols: list[str]) -> str:
    active = [c for c in lf_cols if _safe_int(row.get(c, 0)) == 1]
    return "|".join(active) if active else "NONE"


def add_backbone_columns(df: pd.DataFrame, lf_cols: list[str], ql_col: str | None) -> pd.DataFrame:
    out = df.copy()
    out["quality_label"] = out[ql_col].astype(str) if ql_col else "NA"
    out["lf_signature"] = out.apply(lambda r: active_lf_signature(r, lf_cols), axis=1)
    out["lf_active_count"] = out[lf_cols].fillna(0).astype(int).sum(axis=1) if lf_cols else 0

    if {"close", "ctx_vwap", "ctx_vwap_sigma"}.issubset(out.columns):
        sig = pd.to_numeric(out["ctx_vwap_sigma"], errors="coerce")
        close = pd.to_numeric(out["close"], errors="coerce")
        vwap = pd.to_numeric(out["ctx_vwap"], errors="coerce")
        out["z_vwap"] = np.where((sig.notna()) & (sig != 0), (close - vwap) / sig, np.nan)
    elif "z_vwap" not in out.columns:
        out["z_vwap"] = np.nan

    return out


def mark_episode_starts(df: pd.DataFrame, context_tf: str) -> pd.DataFrame:
    out = df.copy()
    interval = pd.Timedelta(minutes=timeframe_to_minutes(context_tf))
    gap_limit = interval * 1.5

    prev_time = out.groupby("symbol", dropna=False)["time"].shift(1)
    prev_lf = out.groupby("symbol", dropna=False)["lf_signature"].shift(1)
    prev_state = out.groupby("symbol", dropna=False)["state_hat"].shift(1) if "state_hat" in out.columns else pd.Series(index=out.index, dtype="object")
    prev_ql = out.groupby("symbol", dropna=False)["quality_label"].shift(1)

    gap_break = prev_time.isna() | ((out["time"] - prev_time) > gap_limit)
    lf_break = prev_lf.isna() | (out["lf_signature"] != prev_lf)
    st_break = prev_state.isna() | (out["state_hat"] != prev_state)
    ql_break = prev_ql.isna() | (out["quality_label"].astype(str) != prev_ql.astype(str))

    out["episode_start"] = gap_break | lf_break | st_break | ql_break
    out["episode_id"] = out.groupby("symbol", dropna=False)["episode_start"].cumsum().astype(int)
    out["episode_bar_index"] = out.groupby(["symbol", "episode_id"], dropna=False).cumcount().astype(int)
    return out


def add_window_features(hist: pd.DataFrame, base: dict, lf_cols: list[str]) -> dict:
    n = len(hist)
    base["window_n_bars"] = int(n)
    if n == 0:
        return base

    for col in ["margin", "ctx_dist_vwap_atr", "z_vwap", "ctx_state_age"]:
        if col in hist.columns:
            s = pd.to_numeric(hist[col], errors="coerce")
            base[f"{col}_mean"] = float(s.mean()) if s.notna().any() else np.nan
            base[f"{col}_std"] = float(s.std()) if s.notna().sum() > 1 else np.nan
            base[f"{col}_last"] = float(s.iloc[-1]) if pd.notna(s.iloc[-1]) else np.nan
        else:
            base[f"{col}_mean"] = np.nan
            base[f"{col}_std"] = np.nan
            base[f"{col}_last"] = np.nan

    states = hist["state_hat"].astype("Int64") if "state_hat" in hist.columns else pd.Series(dtype="Int64")
    for v, name in [(0, "balance"), (1, "transition"), (2, "trend")]:
        base[f"share_state_{name}"] = float((states == v).mean()) if len(states) else np.nan
    if len(states):
        ss = states.astype(str).fillna("NA")
        base["n_state_changes_window"] = int((ss != ss.shift(1)).sum() - 1)

    q = hist["quality_label"].astype(str).fillna("NA")
    base["n_quality_changes_window"] = int((q != q.shift(1)).sum() - 1)
    base["share_current_quality_window"] = float((q == q.iloc[-1]).mean())

    lf_sig = hist["lf_signature"].astype(str)
    base["n_lf_changes_window"] = int((lf_sig != lf_sig.shift(1)).sum() - 1)
    base["share_current_lf_window"] = float((lf_sig == lf_sig.iloc[-1]).mean())

    for c in lf_cols:
        base[f"share_{c}"] = float((hist[c].fillna(0).astype(int) == 1).mean())

    return base


def resolve_local_scale(ctx: pd.DataFrame, row_idx: int, scale_col: str) -> float:
    row = ctx.iloc[row_idx]
    if scale_col in row.index:
        s = _safe_float(row.get(scale_col, np.nan))
        if np.isfinite(s) and s > 0:
            return float(s)

    hi = _safe_float(row.get("high", np.nan))
    lo = _safe_float(row.get("low", np.nan))
    if np.isfinite(hi) and np.isfinite(lo) and hi > lo:
        return float(hi - lo)

    close = _safe_float(row.get("close", np.nan))
    if np.isfinite(close) and close > 0:
        return float(close * 0.001)
    return np.nan


def sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def build_soft_targets(
    ctx: pd.DataFrame,
    row_idx: int,
    horizon_bars: int,
    scale_col: str,
    min_move_scale: float,
    conflict_penalty: float,
    temperature: float,
) -> dict:
    next_idx = row_idx + 1
    if next_idx >= len(ctx):
        return {
            "target_ready": 0,
            "target_reason": "no_future",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "long_target": np.nan,
            "short_target": np.nan,
            "abstain_target": np.nan,
        }

    entry = _safe_float(ctx.iloc[next_idx].get("open", np.nan))
    future = ctx.iloc[next_idx: next_idx + horizon_bars]
    if len(future) < horizon_bars or not np.isfinite(entry) or entry <= 0:
        return {
            "target_ready": 0,
            "target_reason": "no_future",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "long_target": np.nan,
            "short_target": np.nan,
            "abstain_target": np.nan,
        }

    scale = resolve_local_scale(ctx, row_idx, scale_col)
    if not np.isfinite(scale) or scale <= 0:
        return {
            "target_ready": 0,
            "target_reason": "bad_scale",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "long_target": np.nan,
            "short_target": np.nan,
            "abstain_target": np.nan,
        }

    hi = pd.to_numeric(future["high"], errors="coerce").max()
    lo = pd.to_numeric(future["low"], errors="coerce").min()
    if not np.isfinite(hi) or not np.isfinite(lo):
        return {
            "target_ready": 0,
            "target_reason": "bad_future",
            "up_excursion": np.nan,
            "down_excursion": np.nan,
            "long_target": np.nan,
            "short_target": np.nan,
            "abstain_target": np.nan,
        }

    up = (float(hi) - entry) / scale
    down = (entry - float(lo)) / scale

    t = max(temperature, 1e-6)
    long_raw = (up - (conflict_penalty * down) - min_move_scale) / t
    short_raw = (down - (conflict_penalty * up) - min_move_scale) / t
    long_score = sigmoid(long_raw)
    short_score = sigmoid(short_raw)

    amb = 1.0 - abs(up - down) / (abs(up) + abs(down) + 1e-9)
    abstain = float(np.clip(0.5 * (1.0 - max(long_score, short_score)) + 0.5 * amb, 0.0, 1.0))

    return {
        "target_ready": 1,
        "target_reason": "ok",
        "local_scale": float(scale),
        "up_excursion": float(up),
        "down_excursion": float(down),
        "long_target": float(long_score),
        "short_target": float(short_score),
        "abstain_target": abstain,
    }


def assign_time_split(df: pd.DataFrame, train_frac: float, val_frac: float, train_end: str | None, val_end: str | None) -> pd.DataFrame:
    out = df.copy()
    t = pd.to_datetime(out["timestamp"])

    if train_end and val_end:
        te = pd.Timestamp(train_end)
        ve = pd.Timestamp(val_end)
        out["split"] = np.where(t <= te, "train", np.where(t <= ve, "val", "test"))
        return out

    q1 = float(train_frac)
    q2 = float(train_frac + val_frac)
    a = t.quantile(q1)
    b = t.quantile(min(max(q2, q1 + 0.01), 0.99))
    out["split"] = np.where(t <= a, "train", np.where(t <= b, "val", "test"))
    return out


def state_name(v: object) -> str:
    try:
        iv = int(v)
    except Exception:
        return "NA"
    return {0: "BALANCE", 1: "TRANSITION", 2: "TREND"}.get(iv, "NA")


def build_dataset(ctx: pd.DataFrame, cfg: BuildConfig, require_lf_active: bool) -> pd.DataFrame:
    lf_cols = discover_lf_cols(ctx)
    ql_col = ql_col_name(ctx)

    # Contexto enriquecido para features
    ctx_feat = add_backbone_columns(ctx, lf_cols=lf_cols, ql_col=ql_col)
    ctx_feat = mark_episode_starts(ctx_feat, context_tf=cfg.context_tf)

    universe = ctx_feat.copy()
    if require_lf_active:
        universe = universe[universe["lf_active_count"] > 0].copy()

    if cfg.unit == "episode_start":
        universe = universe[universe["episode_start"]].copy()

    universe = universe.sort_values(["symbol", "time"]).reset_index(drop=True)

    rows: list[dict] = []
    for symbol, g in universe.groupby("symbol", dropna=False):
        # Para features de ventana usar contexto enriquecido
        g_feat = ctx_feat[ctx_feat["symbol"].astype(str) == str(symbol)].sort_values("time").reset_index(drop=True)
        # Para targets futuros basta con OHLC + scale; ctx_feat también lo contiene
        g_target = g_feat

        time_to_idx = {t: i for i, t in enumerate(g_feat["time"])}

        for _, r in g.iterrows():
            ts = r["time"]
            if ts not in time_to_idx:
                continue
            ridx = time_to_idx[ts]

            left = max(0, ridx - cfg.lookback_bars + (1 if cfg.include_current_bar else 0))
            right = ridx + 1 if cfg.include_current_bar else ridx
            hist = g_feat.iloc[left:right].copy()

            base = {
                "timestamp": ts,
                "symbol": str(symbol),
                "state_hat": _safe_int(r.get("state_hat", np.nan)),
                "state_name": state_name(r.get("state_hat", np.nan)),
                "quality_label": str(r.get("quality_label", "NA")),
                "ctx_session_bucket": str(r.get("ctx_session_bucket", "NA")),
                "ctx_state_age": _safe_float(r.get("ctx_state_age", np.nan)),
                "lf_signature": str(r.get("lf_signature", "NONE")),
                "lf_active_count": _safe_int(r.get("lf_active_count", 0)),
                "episode_id": _safe_int(r.get("episode_id", 0)),
                "episode_bar_index": _safe_int(r.get("episode_bar_index", 0)),
            }
            for c in lf_cols:
                base[c] = _safe_int(r.get(c, 0))

            base = add_window_features(hist, base, lf_cols)
            target = build_soft_targets(
                g_target,
                ridx,
                cfg.horizon_bars,
                cfg.scale_col,
                cfg.min_move_scale,
                cfg.conflict_penalty,
                cfg.target_temperature,
            )
            rows.append({**base, **target})

    ds = pd.DataFrame(rows)
    ds = ds.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    return ds



def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = BuildConfig(
        context_tf=args.context_tf,
        lookback_bars=args.lookback_bars,
        horizon_bars=args.horizon_bars,
        scale_col=args.scale_col,
        min_move_scale=args.min_move_scale,
        conflict_penalty=args.conflict_penalty,
        target_temperature=args.target_temperature,
        unit=args.unit,
        include_current_bar=bool(args.include_current_bar),
    )

    ctx = load_context(args.context_parquet, args.symbol)
    ds = build_dataset(ctx, cfg, require_lf_active=bool(args.require_lf_active))
    ds = ds[ds["target_ready"] == 1].copy()
    ds = assign_time_split(ds, args.train_frac, args.val_frac, args.train_end, args.val_end)

    stem = "all_symbols" if args.symbol is None else str(args.symbol)
    out_data = out_dir / f"phase_e5_v2_dataset_{stem}.parquet"
    out_meta = out_dir / f"phase_e5_v2_dataset_{stem}_meta.json"

    ds.to_parquet(out_data, index=False)

    meta = {
        "rows": int(len(ds)),
        "symbols": sorted(ds["symbol"].astype(str).unique().tolist()) if len(ds) else [],
        "split_counts": ds["split"].value_counts().to_dict() if "split" in ds.columns else {},
        "target_means": {
            "long_target": float(ds["long_target"].mean()) if len(ds) else np.nan,
            "short_target": float(ds["short_target"].mean()) if len(ds) else np.nan,
            "abstain_target": float(ds["abstain_target"].mean()) if len(ds) else np.nan,
        },
        "config": {
            **cfg.__dict__,
            "require_lf_active": bool(args.require_lf_active),
            "context_parquet": args.context_parquet,
        },
    }
    out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(json.dumps({"dataset": str(out_data), "meta": str(out_meta), **meta}, indent=2))


if __name__ == "__main__":
    main()
