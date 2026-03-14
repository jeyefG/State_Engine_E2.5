"""Build Phase D base context and audit/broadcast for Phase E coverage telemetry."""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path

import pandas as pd

# --- ensure project root is on PYTHONPATH ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from state_engine.config_loader import load_config
from state_engine.features import FeatureConfig, FeatureEngineer
from state_engine.gating import GatingPolicy
from state_engine.labels import StateLabels
from state_engine.model import StateEngineModel
from state_engine.mt5_connector import MT5Connector
from state_engine.pipeline_phase_d import build_context_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase D base context, audit it, and broadcast to intraday.",
        epilog=(
            "Example:\n"
            "  python scripts/build_phase_e_context_audit.py \\\n"
            "    --symbol XAUUSD.mg \\\n"
            "    --start 2024-01-01 --end 2025-12-31 \\\n"
            "    --context-tf H1 --score-tf M5 --window-hours 24 \\\n"
            "    --out outputs/phase_e/phase_e_audit_XAUUSD.mg_H1_to_M5_2024-01-01_2025-12-31.csv"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--symbol", required=True, help="Símbolo MT5 (ej. XAUUSD.mg)")
    parser.add_argument("--start", required=True, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument(
        "--context-tf",
        required=True,
        choices=["H1", "H2"],
        help="Timeframe base del State Engine (H1 o H2)",
    )
    parser.add_argument(
        "--score-tf",
        required=True,
        choices=["M5", "M15"],
        help="Timeframe intradía para broadcast (M5 o M15)",
    )
    parser.add_argument(
        "--window-hours",
        required=True,
        type=int,
        help="Ventana temporal (horas) para features en TF base",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "phase_e",
        help="CSV output path",
    )
    parser.add_argument(
        "--fail-on-audit",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Abortar con exit code=2 si falla el audit",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=PROJECT_ROOT / "state_engine" / "models",
        help="Directorio base de modelos (.pkl)",
    )
    return parser.parse_args()


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("phase_e_context_audit")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)-8s %(asctime)s | %(message)s")
    handler.setFormatter(formatter)
    logger.handlers = []
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def safe_filename(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def load_symbol_config(symbol: str, logger: logging.Logger) -> dict:
    config_path = PROJECT_ROOT / "configs" / "symbols" / f"{symbol}.yaml"
    if not config_path.exists():
        logger.warning("symbol config missing: %s", config_path)
        return {}
    config = load_config(config_path)
    logger.info("Loaded symbol config from configs/symbols/%s.yaml", symbol)
    return config if isinstance(config, dict) else {}


def derive_base_state(state_hat: pd.Series) -> pd.Series:
    mapping = {
        StateLabels.BALANCE: "BALANCE",
        StateLabels.TRANSITION: "TRANSITION",
        StateLabels.TREND: "TREND",
        int(StateLabels.BALANCE): "BALANCE",
        int(StateLabels.TRANSITION): "TRANSITION",
        int(StateLabels.TREND): "TREND",
        "balance": "BALANCE",
        "transition": "TRANSITION",
        "trend": "TREND",
        "BALANCE": "BALANCE",
        "TRANSITION": "TRANSITION",
        "TREND": "TREND",
    }
    return state_hat.map(mapping).fillna("UNKNOWN")


def look_for_base_state_map(symbol_cfg: dict | None) -> dict[str, str]:
    if not isinstance(symbol_cfg, dict):
        return {}
    phase_d = symbol_cfg.get("phase_d")
    if not isinstance(phase_d, dict):
        return {}
    look_fors = phase_d.get("look_fors")
    if not isinstance(look_fors, dict):
        return {}
    base_state_map: dict[str, str] = {}
    for look_for_name, rule_cfg in look_fors.items():
        if not isinstance(rule_cfg, dict):
            continue
        base_state = rule_cfg.get("base_state") or rule_cfg.get("anchor_state")
        if base_state is None:
            continue
        base_state_map[look_for_name] = str(base_state).strip().upper()
    return base_state_map


def infer_base_state_from_name(look_for_name: str) -> str | None:
    name = look_for_name.lower()
    if "look_for_balance" in name:
        return "BALANCE"
    if "look_for_transition" in name:
        return "TRANSITION"
    if "look_for_trend" in name:
        return "TREND"
    return None


def audit_context_base(
    ctx_df: pd.DataFrame,
    look_for_cols: list[str],
    symbol_cfg: dict | None,
    logger: logging.Logger,
) -> tuple[bool, dict[str, int]]:
    failures: dict[str, int] = {}

    if ctx_df.empty:
        failures["empty_ctx"] = 1
        logger.error("Audit FAIL: ctx_df is empty.")
        return False, failures

    if pd.isna(ctx_df["state_hat"].iloc[0]):
        failures["first_row_state_hat_nan"] = 1
    if "margin" in ctx_df.columns and pd.isna(ctx_df["margin"].iloc[0]):
        failures["first_row_margin_nan"] = 1

    base_state = ctx_df.get("base_state")
    if base_state is not None:
        base_state = base_state.astype(str)

    quality_label_full = ctx_df.get("quality_label_full")
    if quality_label_full is not None and base_state is not None:
        quality_series = quality_label_full.astype(str)
        classified = ~quality_series.str.contains("UNCLASSIFIED", na=True)
        quality_prefix = quality_series.str.extract(r"^(BALANCE|TRANSITION|TREND)", expand=False)
        mismatches = classified & quality_prefix.notna() & (quality_prefix != base_state)
        mismatch_count = int(mismatches.sum())
        if mismatch_count:
            failures["quality_base_mismatch"] = mismatch_count

    base_state_map = look_for_base_state_map(symbol_cfg)
    for look_for_name in look_for_cols:
        expected_base = base_state_map.get(look_for_name) or infer_base_state_from_name(look_for_name)
        if expected_base is None or base_state is None:
            continue
        if expected_base == "ANY":
            continue
        active = ctx_df[look_for_name] == 1
        mismatches = active & (base_state != "UNKNOWN") & (base_state != expected_base)
        mismatch_count = int(mismatches.sum())
        if mismatch_count:
            failures[f"look_for_base_mismatch:{look_for_name}"] = mismatch_count

    warmup_cols = [col for col in ctx_df.columns if col.startswith("ctx_")]
    if warmup_cols:
        nan_rates = {col: float(ctx_df[col].isna().mean()) for col in warmup_cols}
        logger.info("Warm-up NaN rates (ctx_*): %s", nan_rates)

    passed = not failures
    if passed:
        logger.info("Audit PASS")
    else:
        logger.error("Audit FAIL | failures=%s", failures)
    return passed, failures


def merge_context_intraday(
    ctx_df: pd.DataFrame,
    ohlcv_score: pd.DataFrame,
    logger: logging.Logger,
) -> pd.DataFrame:
    ctx = ctx_df.copy().sort_index()
    score = ohlcv_score.copy().sort_index()
    if getattr(ctx.index, "tz", None) is not None:
        ctx.index = ctx.index.tz_localize(None)
    if getattr(score.index, "tz", None) is not None:
        score.index = score.index.tz_localize(None)
    ctx = ctx.reset_index().rename(columns={ctx.index.name or "index": "time"})
    score = score.reset_index().rename(columns={score.index.name or "index": "time"})
    merged = pd.merge_asof(
        score,
        ctx,
        on="time",
        direction="backward",
        allow_exact_matches=True,
    )
    merged = merged.set_index("time")
    logger.info("Broadcast merge complete rows=%s", len(merged))
    return merged


def _add_date_col(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Soporta index datetime o columna time
    if isinstance(out.index, pd.DatetimeIndex):
        out["_date"] = out.index.normalize()
    elif "time" in out.columns:
        out["_date"] = pd.to_datetime(out["time"]).dt.normalize()
    else:
        raise ValueError("df_score_ctx must have DatetimeIndex or a 'time' column.")
    return out

def build_summaries(
    df_score_ctx: pd.DataFrame,
    symbol: str,
    score_tf: str,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      (summary_universe, summary_lookfor_events, summary_coverage)

    - summary_universe: cobertura por (base_state, quality_label_full) SIN condicionar a LOOK_FOR
    - summary_lookfor_events: resumen condicionado a LOOK_FOR==1
    - summary_coverage: sanity counts para no perderse
    """
    df = _add_date_col(df_score_ctx)

    required = ["base_state", "quality_label_full"]
    missing_req = [c for c in required if c not in df.columns]
    if missing_req:
        raise ValueError(f"Missing required columns in df_score_ctx: {missing_req}")

    look_for_cols = [c for c in df.columns if c.startswith("LOOK_FOR_")]
    any_lookfor = None
    if look_for_cols:
        any_lookfor = df[look_for_cols].fillna(0).astype(int).sum(axis=1) > 0
    else:
        any_lookfor = pd.Series(False, index=df.index)

    # -------------------------
    # C) Coverage / sanity
    # -------------------------
    summary_coverage = pd.DataFrame(
        [{
            "symbol": symbol,
            "score_tf": score_tf,
            "rows_total": int(len(df)),
            "rows_any_lookfor": int(any_lookfor.sum()),
            "pct_any_lookfor": float(any_lookfor.mean()) if len(df) else 0.0,
            "rows_base_state_na": int(df["base_state"].isna().sum()),
            "rows_quality_full_na": int(df["quality_label_full"].isna().sum()),
            "look_for_cols": int(len(look_for_cols)),
        }]
    )

    # -------------------------
    # A) Universe (no lookfor filter)
    # -------------------------
    group_cols_u = ["base_state", "quality_label_full"]
    grouped_u = df.groupby(group_cols_u, dropna=False)

    universe_rows: list[dict[str, object]] = []
    for (base_state, quality_label_full), g in grouped_u:
        n_bars = int(len(g))
        n_days = int(g["_date"].nunique())
        bars_per_day = n_bars / n_days if n_days else 0.0
        avg_margin = float(g["margin"].mean()) if "margin" in g.columns else None
        nan_rate = float(g["ctx_dist_vwap_atr"].isna().mean()) if "ctx_dist_vwap_atr" in g.columns else None

        universe_rows.append(
            {
                "symbol": symbol,
                "score_tf": score_tf,
                "base_state": base_state,
                "quality_label_full": quality_label_full,
                "look_for_rule": "__UNIVERSE__",
                "n_bars": n_bars,
                "n_days": n_days,
                "bars_per_day": float(bars_per_day),
                "avg_margin": avg_margin,
                "nan_rate_ctx_dist_vwap_atr": nan_rate,
            }
        )

    summary_universe = pd.DataFrame(universe_rows)
    if not summary_universe.empty:
        summary_universe = summary_universe.sort_values("n_bars", ascending=False)

    # -------------------------
    # B) LOOK_FOR events
    # -------------------------
    if not look_for_cols:
        logger.warning("No LOOK_FOR columns found; lookfor_events summary will be empty.")
        summary_lookfor = pd.DataFrame(
            columns=[
                "symbol",
                "score_tf",
                "base_state",
                "quality_label_full",
                "look_for_rule",
                "n_events",
                "n_days",
                "events_per_day",
                "avg_margin",
                "nan_rate_ctx_dist_vwap_atr",
            ]
        )
        return summary_universe, summary_lookfor, summary_coverage

    summary_rows: list[dict[str, object]] = []
    for look_for_name in look_for_cols:
        subset = df[df[look_for_name] == 1]
        n_events = int(len(subset))
        logger.info("LOOK_FOR events=%s count=%s", look_for_name, n_events)
        if n_events == 0:
            continue

        grouped = subset.groupby(group_cols_u, dropna=False)
        for (base_state, quality_label_full), g in grouped:
            n_group_events = int(len(g))
            n_days = int(g["_date"].nunique())
            events_per_day = n_group_events / n_days if n_days else 0.0
            avg_margin = float(g["margin"].mean()) if "margin" in g.columns else None
            nan_rate = float(g["ctx_dist_vwap_atr"].isna().mean()) if "ctx_dist_vwap_atr" in g.columns else None

            summary_rows.append(
                {
                    "symbol": symbol,
                    "score_tf": score_tf,
                    "base_state": base_state,
                    "quality_label_full": quality_label_full,
                    "look_for_rule": look_for_name,
                    "n_events": n_group_events,
                    "n_days": n_days,
                    "events_per_day": float(events_per_day),
                    "avg_margin": avg_margin,
                    "nan_rate_ctx_dist_vwap_atr": nan_rate,
                }
            )

    summary_lookfor = pd.DataFrame(summary_rows)
    if not summary_lookfor.empty:
        summary_lookfor = summary_lookfor.sort_values("n_events", ascending=False)

    return summary_universe, summary_lookfor, summary_coverage

def main() -> None:
    args = parse_args()
    logger = setup_logging()

    symbol = args.symbol
    context_tf = args.context_tf.upper()
    score_tf = args.score_tf.upper()
    start = pd.to_datetime(args.start)
    end = pd.to_datetime(args.end)

    bars_per_hour = {"H1": 1, "H2": 0.5}
    derived_bars = math.ceil(args.window_hours * bars_per_hour[context_tf])
    if derived_bars < 4:
        raise ValueError(f"Context window too small: {derived_bars} bars (min=4).")
    logger.info(
        "window_hours=%s context_tf=%s derived_bars=%s",
        args.window_hours,
        context_tf,
        derived_bars,
    )

    symbol_cfg = load_symbol_config(symbol, logger)

    logger.info("download start symbol=%s tf=%s", symbol, context_tf)
    connector = MT5Connector()
    ohlcv_ctx = connector.obtener_ohlcv(symbol, context_tf, start, end)
    logger.info("download done rows=%s", len(ohlcv_ctx))

    model_path = args.model_dir / f"{safe_filename(symbol)}_state_engine.pkl"
    logger.info("load model path=%s", model_path)
    model = StateEngineModel()
    model.load(model_path)

    feature_engineer = FeatureEngineer(FeatureConfig(window=derived_bars))
    gating_policy = GatingPolicy()

    logger.info("build Phase D base context")
    try:
        context_bundle = build_context_bundle(
            symbol=symbol,
            context_tf=context_tf,
            score_tf=context_tf,
            ohlcv_ctx=ohlcv_ctx,
            ohlcv_score=ohlcv_ctx,
            state_model=model,
            feature_engineer=feature_engineer,
            gating_policy=gating_policy,
            symbol_cfg=symbol_cfg,
            phase_e=False,
            logger=logger,
            quality_labels=None,
            causal_shift=False,
        )
    except ValueError as exc:
        if "missing columns" in str(exc).lower():
            logger.error("filter inactive due to missing columns")
        raise

    ctx_df = context_bundle.ctx_df.copy()
    look_for_cols = [col for col in ctx_df.columns if col.startswith("LOOK_FOR_")]
    if look_for_cols:
        ctx_df[look_for_cols] = ctx_df[look_for_cols].fillna(0).astype(int)

    ctx_df["base_state"] = derive_base_state(ctx_df["state_hat"])
    if "quality_label_full" not in ctx_df.columns:
        ctx_df["quality_label_full"] = ctx_df["base_state"].astype(str) + "_UNCLASSIFIED"

    audit_passed, _ = audit_context_base(ctx_df, look_for_cols, symbol_cfg, logger)
    if not audit_passed and args.fail_on_audit:
        raise SystemExit(2)

    logger.info("download start symbol=%s tf=%s", symbol, score_tf)
    ohlcv_score = connector.obtener_ohlcv(symbol, score_tf, start, end)
    logger.info("download done rows=%s", len(ohlcv_score))
    
    df_score_ctx = merge_context_intraday(ctx_df, ohlcv_score, logger)
    
    look_for_cols = [c for c in df_score_ctx.columns if c.startswith("LOOK_FOR_")]
    any_lf = df_score_ctx[look_for_cols].fillna(0).astype(int).sum(axis=1) > 0 if look_for_cols else pd.Series(False, index=df_score_ctx.index)
    
    logger.info("SANITY df_score_ctx rows=%s", len(df_score_ctx))
    logger.info("SANITY base_state vc:\n%s", df_score_ctx["base_state"].value_counts(dropna=False).head(20).to_string())
    logger.info("SANITY quality_label_full vc:\n%s", df_score_ctx["quality_label_full"].value_counts(dropna=False).head(30).to_string())
    logger.info("SANITY any_lookfor pct=%.2f%%", 100.0 * float(any_lf.mean()))
    logger.info("SANITY universe distinct pairs=%s",
                df_score_ctx[["base_state","quality_label_full"]].drop_duplicates().shape[0])

    
    # NEW: dos salidas (universo completo + eventos look_for)
    summary_universe, summary_lookfor, summary_cov = build_summaries(df_score_ctx, symbol, score_tf, logger)
    
    out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    out_universe = out_path.with_name(out_path.stem + "_universe.csv")
    out_lookfor = out_path.with_name(out_path.stem + "_lookfor.csv")
    out_cov = out_path.with_name(out_path.stem + "_coverage.csv")
    
    summary_universe.to_csv(out_universe, index=False)
    summary_lookfor.to_csv(out_lookfor, index=False)
    summary_cov.to_csv(out_cov, index=False)
    
    logger.info("export done universe path=%s rows=%s", out_universe, len(summary_universe))
    logger.info("export done lookfor path=%s rows=%s", out_lookfor, len(summary_lookfor))
    logger.info("export done coverage path=%s rows=%s", out_cov, len(summary_cov))
    
    logger.info("export done universe path=%s rows=%s", out_universe, len(summary_universe))
    logger.info("export done lookfor path=%s rows=%s", out_lookfor, len(summary_lookfor))


if __name__ == "__main__":
    main()
