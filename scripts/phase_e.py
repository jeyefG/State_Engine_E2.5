"""
Build canonical Phase D context at the State Engine base timeframe and continuing with Phase E.

Phase E REFACTOR (baseline registry mode):
- Lens-agnostic, governed by:
  1) baseline_registry.yaml (canonical, closed)
  2) narrative -> baseline mapping in configs/symbols/<symbol>.yaml
  3) hierarchical control group defaults = PARENT_ESTRATO
- Keeps all current outputs + adds:
  - baseline_state_ql_uplift: uplift of STATE+QL vs STATE (stratum-2 vs parent)
  - diagnostics: avg_run_length and flip_rate per state (TF base)
- Backward compatibility:
  - If registry YAML missing and NOT strict: uses legacy default_baseline_by_state (hardcoded or YAML-default section)
  - If strict: fails explicitly
- k_eval is retrospective ONLY (never affects entry timing).
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- ensure project root is on PYTHONPATH ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from state_engine.config_loader import load_config
from state_engine.features import FeatureConfig, FeatureEngineer
from state_engine.gating import GatingPolicy
from state_engine.model import StateEngineModel
from state_engine.mt5_connector import MT5Connector
from state_engine.pipeline_phase_d import audit_phase_d_contamination, build_context_bundle
from state_engine.pipeline_phase_d import _merge_context_score as merge_context_intraday
from state_engine.pipeline_phase_d import _normalize_state_labels
from state_engine.quality import (
    assign_quality_labels,
    default_quality_config_dict,
    validate_quality_config_dict,
    _config_from_dict,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# -------------------------
# CLI
# -------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase D context (TF base) + optional Phase E.")
    parser.add_argument("--symbol", required=True, help="Símbolo MT5 (ej. XAUUSD.mg)")
    parser.add_argument("--start", required=True, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument(
        "--timeframe",
        required=True,
        choices=["H1", "H2"],
        help="Timeframe base del State Engine (H1 o H2)",
    )
    parser.add_argument(
        "--model-path",
        default=str(PROJECT_ROOT / "state_engine" / "models"),
        help="Ruta base de modelos .pkl (el archivo se resuelve por símbolo)",
    )
    parser.add_argument(
        "--window-hours",
        required=True,
        type=int,
        help="Ventana temporal (horas) para features/quality en TF base",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "outputs" / "phase_d_context"),
        help="Directorio de salida",
    )
    parser.add_argument(
        "--phase-e",
        action="store_true",
        help="Continuar con Phase E usando ctx_df en memoria",
    )
    parser.add_argument(
        "--score-tf",
        default=None,
        help="Timeframe intradía para Phase E (ej. M5/M15).",
    )
    parser.add_argument(
        "--out-phase-e",
        default=str(PROJECT_ROOT / "outputs" / "phase_e"),
        help="Ruta base de salida para Phase E (sin sufijo).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Ruta base de salida compartida (Phase E usa sufijos _universe/_lookfor/_coverage).",
    )
    parser.add_argument(
        "--fail-on-audit",
        action="store_true",
        help="Abortar si falla la auditoría canónica de Phase D.",
    )
    parser.add_argument(
        "--debug-allow-missing-quality",
        action="store_true",
        help="DEBUG: permitir quality_labels=None (no recomendado).",
    )

    # -------------------------
    # Phase E edge evaluation
    # -------------------------
    parser.add_argument(
        "--edge-mode",
        choices=["baseline", "legacy_price"],
        default="baseline",
        help="Phase E target mode. baseline=registry state-only baselines (recommended). legacy_price=old price-based Y.",
    )
    parser.add_argument(
        "--edge-k",
        type=int,
        default=None,
        help="Horizon k (bars) for Phase E edge metrics. If omitted, uses a sensible default by score_tf.",
    )
    parser.add_argument(
        "--edge-min-events",
        type=int,
        default=200,
        help="Minimum number of events (rows) per group to show in filtered edge tables/logs.",
    )
    parser.add_argument(
        "--edge-min-days",
        type=int,
        default=20,
        help="Minimum number of distinct days per group to show in filtered edge tables/logs.",
    )

    # -------------------------
    # Phase E baseline registry (new)
    # -------------------------
    parser.add_argument(
        "--baseline-registry",
        default=str(PROJECT_ROOT / "configs" / "baseline_registry.yaml"),
        help="Path to canonical baseline_registry.yaml (closed catalog).",
    )
    parser.add_argument(
        "--strict-baseline-registry",
        action="store_true",
        help="If set, Phase E baseline mode fails when baseline_registry.yaml is missing/invalid.",
    )

    return parser.parse_args()


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("phase_d_context")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)-8s %(asctime)s | %(message)s")
    handler.setFormatter(formatter)
    logger.handlers = []
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def load_symbol_config(symbol: str, logger: logging.Logger) -> dict:
    config_path = PROJECT_ROOT / "configs" / "symbols" / f"{symbol}.yaml"
    if not config_path.exists():
        return {}
    try:
        config = load_config(config_path)
    except Exception as exc:
        logger.warning("symbol config load failed for %s: %s", symbol, exc)
        return {}
    return config if isinstance(config, dict) else {}


def safe_filename(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def _deep_merge_dicts(base: dict, updates: dict) -> dict:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_quality_config(symbol_cfg: dict, logger: logging.Logger):
    defaults = default_quality_config_dict()
    quality_cfg = None
    if isinstance(symbol_cfg, dict):
        phase_c_cfg = symbol_cfg.get("phase_c")
        if isinstance(phase_c_cfg, dict) and isinstance(phase_c_cfg.get("quality"), dict):
            quality_cfg = phase_c_cfg.get("quality")
        elif isinstance(symbol_cfg.get("quality"), dict):
            quality_cfg = symbol_cfg.get("quality")
    if quality_cfg is None:
        logger.info("quality config: using defaults (no symbol override).")
        merged = defaults
    else:
        validate_quality_config_dict(quality_cfg)
        merged = _deep_merge_dicts(defaults, quality_cfg)
    return _config_from_dict(merged)


def _run_phase_d_audit(logger: logging.Logger, *, fail_on_audit: bool) -> None:
    audit_handler = logging.Handler()
    audit_handler.setLevel(logging.ERROR)
    audit_records: list[logging.LogRecord] = []

    def _capture(record: logging.LogRecord) -> None:
        audit_records.append(record)

    audit_handler.emit = _capture  # type: ignore[assignment]
    logger.addHandler(audit_handler)
    try:
        audit_phase_d_contamination(logger=logger)
    finally:
        logger.removeHandler(audit_handler)
    audit_failed = any("AUDIT_FAIL" in record.getMessage() for record in audit_records)
    if audit_failed and fail_on_audit:
        logger.error("Phase D audit failed; aborting (--fail-on-audit).")
        raise SystemExit(2)


def _default_edge_k(score_tf: str) -> int:
    tf = str(score_tf).upper().strip()
    if tf == "M1":
        return 60  # 1h
    if tf == "M5":
        return 24  # 2h
    if tf == "M15":
        return 8   # 2h
    if tf == "M30":
        return 4   # 2h
    if tf == "H1":
        return 2   # 2h
    return 24


def _add_date_col(df: pd.DataFrame) -> pd.DataFrame:
    if "_date" not in df.columns:
        df = df.copy()
        df["_date"] = df.index.normalize()
    return df


# -------------------------
# Phase E: legacy better_is direction config (kept)
# -------------------------
def _resolve_phase_e_better_is_by_state(symbol_cfg: dict, logger: logging.Logger) -> tuple[dict[str, str], str]:
    defaults = {"TREND": "HIGHER", "BALANCE": "HIGHER", "TRANSITION": "HIGHER"}
    src = "default"

    if not isinstance(symbol_cfg, dict):
        logger.info("Phase E better_is: using defaults (symbol_cfg not a dict).")
        return defaults, src

    phase_e = symbol_cfg.get("phase_e")
    if not isinstance(phase_e, dict):
        logger.info("Phase E better_is: using defaults (phase_e missing).")
        return defaults, src

    edge_metric = phase_e.get("edge_metric")
    if not isinstance(edge_metric, dict):
        logger.info("Phase E better_is: using defaults (phase_e.edge_metric missing).")
        return defaults, src

    by_state = edge_metric.get("by_state")
    if not isinstance(by_state, dict):
        logger.info("Phase E better_is: using defaults (phase_e.edge_metric.by_state missing).")
        return defaults, src

    merged = dict(defaults)
    any_override = False
    for state, cfg in by_state.items():
        if not isinstance(state, str):
            continue
        state_norm = state.upper().strip()
        if state_norm not in merged:
            continue
        better_is = None
        if isinstance(cfg, dict):
            better_is = cfg.get("better_is")
        elif isinstance(cfg, str):
            better_is = cfg
        if better_is is None:
            continue
        bi = str(better_is).upper().strip()
        if bi not in ("HIGHER", "LOWER"):
            logger.warning("Phase E better_is invalid for state=%s: %r (ignored)", state_norm, better_is)
            continue
        merged[state_norm] = bi
        any_override = True

    if any_override:
        src = "symbol_cfg"
        logger.info("Phase E better_is loaded from symbol_cfg: %s", merged)
    else:
        logger.info("Phase E better_is: using defaults (no valid overrides found).")

    return merged, src


# ============================================================
# Phase E BASELINE REGISTRY (new)
# ============================================================

_ALLOWED_Y_IDS = {
    "STAY_IN_CURRENT_STATE_WITHIN_K",
    "EXIT_CURRENT_STATE_WITHIN_K",
    "HIT_STATE_WITHIN_K",
    "NOT_HIT_STATE_WITHIN_K",
    "HIT_SPECIFIC_STATE_WITHIN_K",
    "EXIT_AND_REENTER_STATE_WITHIN_K",
}

_ALLOWED_CONTROL_MODES = {"PARENT_ESTRATO", "GLOBAL_BASELINE"}

_DEFAULT_LEGACY_DEFAULT_BASELINE_BY_STATE = {
    "TREND": "STATE_FRAGILITY",        # exit TREND within K
    "BALANCE": "BALANCE_ESCAPE",       # hit TREND within K
    "TRANSITION": "TRANSITION_NOISE",  # NOT hit TREND within K
}


def _get_nested(d: dict, path: list[str], default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def load_baseline_registry(
    registry_path: Path,
    logger: logging.Logger,
    *,
    strict: bool,
) -> dict:
    """
    Loads and validates the canonical baseline registry YAML.
    Expected schema:
      phase_e:
        baseline_registry: { <BASELINE_ID>: { y_id, params, better_is, description } }
        default_baseline_by_state: { TREND: ..., BALANCE: ..., TRANSITION: ... }
        control_group_defaults: { STRATUM_STATE_QL: PARENT_ESTRATO, STRATUM_STATE_QL_LF: PARENT_ESTRATO }
        allowed_control_group_modes: [...]
    """
    if not registry_path.exists():
        msg = f"baseline_registry.yaml not found at: {registry_path}"
        if strict:
            logger.error(msg)
            raise SystemExit(2)
        logger.warning("%s | Using legacy defaults (non-strict).", msg)
        return {
            "baseline_registry": {},
            "default_baseline_by_state": dict(_DEFAULT_LEGACY_DEFAULT_BASELINE_BY_STATE),
            "control_group_defaults": {
                "STRATUM_STATE_QL": "PARENT_ESTRATO",
                "STRATUM_STATE_QL_LF": "PARENT_ESTRATO",
            },
            "allowed_control_group_modes": ["PARENT_ESTRATO"],
            "_source": "legacy_fallback_missing_yaml",
        }

    try:
        raw = load_config(registry_path)
    except Exception as exc:
        msg = f"baseline_registry load failed: {exc}"
        if strict:
            logger.error(msg)
            raise SystemExit(2)
        logger.warning("%s | Using legacy defaults (non-strict).", msg)
        return {
            "baseline_registry": {},
            "default_baseline_by_state": dict(_DEFAULT_LEGACY_DEFAULT_BASELINE_BY_STATE),
            "control_group_defaults": {
                "STRATUM_STATE_QL": "PARENT_ESTRATO",
                "STRATUM_STATE_QL_LF": "PARENT_ESTRATO",
            },
            "allowed_control_group_modes": ["PARENT_ESTRATO"],
            "_source": "legacy_fallback_invalid_yaml",
        }

    if not isinstance(raw, dict):
        msg = "baseline_registry.yaml root is not a dict"
        if strict:
            logger.error(msg)
            raise SystemExit(2)
        logger.warning("%s | Using legacy defaults (non-strict).", msg)
        return {
            "baseline_registry": {},
            "default_baseline_by_state": dict(_DEFAULT_LEGACY_DEFAULT_BASELINE_BY_STATE),
            "control_group_defaults": {
                "STRATUM_STATE_QL": "PARENT_ESTRATO",
                "STRATUM_STATE_QL_LF": "PARENT_ESTRATO",
            },
            "allowed_control_group_modes": ["PARENT_ESTRATO"],
            "_source": "legacy_fallback_bad_schema",
        }

    phase_e = raw.get("phase_e") if isinstance(raw.get("phase_e"), dict) else {}
    baseline_registry = phase_e.get("baseline_registry") if isinstance(phase_e.get("baseline_registry"), dict) else {}
    default_by_state = phase_e.get("default_baseline_by_state") if isinstance(phase_e.get("default_baseline_by_state"), dict) else {}
    control_defaults = phase_e.get("control_group_defaults") if isinstance(phase_e.get("control_group_defaults"), dict) else {}
    allowed_modes = phase_e.get("allowed_control_group_modes") if isinstance(phase_e.get("allowed_control_group_modes"), list) else ["PARENT_ESTRATO"]

    # Validate allowed modes
    for m in allowed_modes:
        if str(m) not in _ALLOWED_CONTROL_MODES:
            msg = f"Invalid control group mode in allowed_control_group_modes: {m}"
            if strict:
                logger.error(msg)
                raise SystemExit(2)
            logger.warning("%s | Forcing to PARENT_ESTRATO only.", msg)
            allowed_modes = ["PARENT_ESTRATO"]
            break

    # Validate baselines
    clean_registry: dict[str, dict] = {}
    for bid, cfg in baseline_registry.items():
        if not isinstance(bid, str) or not isinstance(cfg, dict):
            continue
        y_id = str(cfg.get("y_id", "")).strip().upper()
        if y_id not in _ALLOWED_Y_IDS:
            msg = f"Baseline {bid} has invalid y_id: {y_id}"
            if strict:
                logger.error(msg)
                raise SystemExit(2)
            logger.warning("%s | Baseline ignored.", msg)
            continue
        params = cfg.get("params") if isinstance(cfg.get("params"), dict) else {}
        better_is = str(cfg.get("better_is", "HIGHER")).strip().upper()
        if better_is not in ("HIGHER", "LOWER"):
            msg = f"Baseline {bid} has invalid better_is: {better_is}"
            if strict:
                logger.error(msg)
                raise SystemExit(2)
            logger.warning("%s | Forcing HIGHER.", msg)
            better_is = "HIGHER"
        clean_registry[bid] = {
            "description": cfg.get("description", ""),
            "y_id": y_id,
            "params": params,
            "better_is": better_is,
        }

    # Validate default_by_state
    clean_default_by_state = dict(_DEFAULT_LEGACY_DEFAULT_BASELINE_BY_STATE)
    for st in ("TREND", "BALANCE", "TRANSITION"):
        if st in default_by_state:
            cand = str(default_by_state[st]).strip()
            clean_default_by_state[st] = cand

    # Ensure defaults reference existing baseline ids if registry is present
    if clean_registry:
        for st, bid in clean_default_by_state.items():
            if bid not in clean_registry:
                msg = f"default_baseline_by_state[{st}] references unknown baseline_id: {bid}"
                if strict:
                    logger.error(msg)
                    raise SystemExit(2)
                logger.warning("%s | Keeping legacy default mapping may be inconsistent.", msg)

    # Validate control defaults
    c_ql = str(control_defaults.get("STRATUM_STATE_QL", "PARENT_ESTRATO")).strip().upper()
    c_lf = str(control_defaults.get("STRATUM_STATE_QL_LF", "PARENT_ESTRATO")).strip().upper()
    if c_ql not in _ALLOWED_CONTROL_MODES:
        c_ql = "PARENT_ESTRATO"
    if c_lf not in _ALLOWED_CONTROL_MODES:
        c_lf = "PARENT_ESTRATO"

    out = {
        "baseline_registry": clean_registry,
        "default_baseline_by_state": clean_default_by_state,
        "control_group_defaults": {
            "STRATUM_STATE_QL": c_ql,
            "STRATUM_STATE_QL_LF": c_lf,
        },
        "allowed_control_group_modes": list(allowed_modes),
        "_source": str(registry_path),
    }

    logger.info(
        "Phase E baseline registry loaded | baselines=%s source=%s",
        len(clean_registry),
        out["_source"],
    )
    logger.info("Phase E default_baseline_by_state=%s", clean_default_by_state)
    logger.info("Phase E control_group_defaults=%s", out["control_group_defaults"])
    return out


def load_narrative_to_baseline_mapping(symbol_cfg: dict, logger: logging.Logger) -> dict[str, str]:
    """
    Expected (minimum) in symbol YAML:
      phase_e:
        narrative_to_baseline:
          LOOK_FOR_xxx: BASELINE_ID
    """
    mapping = {}
    if not isinstance(symbol_cfg, dict):
        return mapping
    phase_e = symbol_cfg.get("phase_e")
    if not isinstance(phase_e, dict):
        return mapping
    m = phase_e.get("narrative_to_baseline") or phase_e.get("narrative_baseline_map")
    if not isinstance(m, dict):
        return mapping
    for k, v in m.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        mapping[str(k).strip()] = str(v).strip()
    if mapping:
        logger.info("Phase E narrative_to_baseline loaded from symbol_cfg | n=%s", len(mapping))
    return mapping


# -------------------------
# Baseline outcome functions (state-only)
# -------------------------
def _fwd_any(flag: pd.Series, k: int) -> pd.Series:
    """True if occurs at least once in [t+1, t+k]. Requires full window."""
    s = flag.astype(int)
    return s.shift(-1)[::-1].rolling(k, min_periods=k).max()[::-1].fillna(0).astype(bool)


def _fwd_any_state_is(state: pd.Series, target: str, k: int) -> pd.Series:
    return _fwd_any(state.astype(str).eq(target), k)


def _compute_y_from_def(df: pd.DataFrame, k: int, baseline_def: dict, logger: logging.Logger) -> pd.Series:
    """
    baseline_def: {y_id, params, better_is, ...}
    Returns float series (0/1) with NaN on last k bars (due to forward window).
    """
    if k < 1:
        raise ValueError(f"edge_k must be >= 1 (got {k})")
    if "base_state" not in df.columns:
        raise ValueError("Missing required column: base_state")

    state = df["base_state"].astype(str)
    y_id = str(baseline_def.get("y_id", "")).upper().strip()
    params = baseline_def.get("params") if isinstance(baseline_def.get("params"), dict) else {}

    # Precompute generic components
    # "exit current state within K": any change in base_state within the next k
    # We approximate by looking at future differences vs current state:
    #   exit_any[t] = any(state[t+i] != state[t]) for i=1..k
    # This is different from "change at least once" across the path (which is always true if any differs from t).
    # That aligns better with "exit current state".
    def _exit_current_within_k(state_series: pd.Series, kk: int) -> pd.Series:
        cur = state_series.astype(str)
        # build forward "any != current"
        # using rolling over shifted comparisons is tricky; simplest vectorized:
        # compute for each i 1..k then OR. k is small (<=60 typically), OK.
        out = pd.Series(False, index=cur.index)
        for i in range(1, kk + 1):
            out = out | (cur.shift(-i) != cur)
        # last kk bars will have NaN comparisons; keep False but we’ll NaN mask later
        return out

    def _hit_target_within_k(state_series: pd.Series, target_state: str, kk: int) -> pd.Series:
        return _fwd_any_state_is(state_series, target_state, kk)

    def _hit_specific_within_k(state_series: pd.Series, target_series: pd.Series, kk: int) -> pd.Series:
        # target_series is per-row target state (e.g., previous_state)
        out = pd.Series(False, index=state_series.index)
        for i in range(1, kk + 1):
            out = out | (state_series.shift(-i).astype(str) == target_series.astype(str))
        return out

    y = pd.Series(np.nan, index=df.index, dtype=float)

    if y_id == "STAY_IN_CURRENT_STATE_WITHIN_K":
        stay = ~_exit_current_within_k(state, k)
        y[:] = stay.astype(float)

    elif y_id == "EXIT_CURRENT_STATE_WITHIN_K":
        exit_any = _exit_current_within_k(state, k)
        y[:] = exit_any.astype(float)

    elif y_id == "HIT_STATE_WITHIN_K":
        target = str(params.get("target", "")).upper().strip()
        if not target:
            raise ValueError("HIT_STATE_WITHIN_K requires params.target")
        if target == "PREVIOUS_STATE":
            prev = state.shift(1).fillna(method="bfill")
            hit_prev = _hit_specific_within_k(state, prev, k)
            y[:] = hit_prev.astype(float)
        else:
            hit = _hit_target_within_k(state, target, k)
            y[:] = hit.astype(float)

    elif y_id == "NOT_HIT_STATE_WITHIN_K":
        target = str(params.get("target", "")).upper().strip()
        if not target:
            raise ValueError("NOT_HIT_STATE_WITHIN_K requires params.target")
        if target == "PREVIOUS_STATE":
            prev = state.shift(1).fillna(method="bfill")
            hit_prev = _hit_specific_within_k(state, prev, k)
            y[:] = (~hit_prev).astype(float)
        else:
            hit = _hit_target_within_k(state, target, k)
            y[:] = (~hit).astype(float)

    elif y_id == "HIT_SPECIFIC_STATE_WITHIN_K":
        target = str(params.get("target", "")).upper().strip()
        if not target:
            raise ValueError("HIT_SPECIFIC_STATE_WITHIN_K requires params.target")
        if target == "PREVIOUS_STATE":
            prev = state.shift(1).fillna(method="bfill")
            hit_prev = _hit_specific_within_k(state, prev, k)
            y[:] = hit_prev.astype(float)
        else:
            hit = _hit_target_within_k(state, target, k)
            y[:] = hit.astype(float)

    elif y_id == "EXIT_AND_REENTER_STATE_WITHIN_K":
        # Exit current state at least once, AND later re-enter within K.
        cur = state.astype(str)
        exited = pd.Series(False, index=cur.index)
        reentered = pd.Series(False, index=cur.index)
        for i in range(1, k + 1):
            exited = exited | (cur.shift(-i) != cur)
        # Re-enter: exists j>i such that state[t+j] == state[t]
        for j in range(1, k + 1):
            reentered = reentered | (cur.shift(-j) == cur)
        y[:] = (exited & reentered).astype(float)

    else:
        raise ValueError(f"Unsupported y_id: {y_id}")

    # Mask last k bars as NaN to be honest about forward window
    if k > 0:
        y.iloc[-k:] = np.nan

    logger.debug("computed baseline y | y_id=%s k=%s nan_rate=%.4f", y_id, k, float(y.isna().mean()))
    return y


def _baseline_id_for_state(default_by_state: dict, st: object) -> str:
    # unwrap groupby key when grouping by a list of cols (pandas returns tuple)
    if isinstance(st, tuple) and len(st) == 1:
        st = st[0]

    st_norm = "" if st is None else str(st)
    st_norm = st_norm.strip().upper()

    bid = "" if default_by_state is None else default_by_state.get(st_norm, "")
    bid = "" if bid is None else str(bid).strip()

    if not bid:
        raise ValueError(
            f"Missing baseline mapping for base_state='{st_norm}'. "
            f"default_baseline_by_state keys={list(default_by_state.keys()) if isinstance(default_by_state, dict) else default_by_state}"
        )
    return bid


# -------------------------
# Phase E: LEGACY MODE (price-based) kept as-is
# -------------------------
def compute_state_conditional_edge_y(df: pd.DataFrame, k: int, logger: logging.Logger) -> pd.Series:
    if k < 1:
        raise ValueError(f"edge_k must be >= 1 (got {k})")

    required_cols = ["close", "high", "low", "base_state"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for legacy Phase E edge metrics: {missing}")

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    log_close = np.log(close.replace(0, np.nan))

    fwd_high = high.shift(-1)[::-1].rolling(k, min_periods=k).max()[::-1]
    fwd_low = low.shift(-1)[::-1].rolling(k, min_periods=k).min()[::-1]

    y_trend = (np.log(fwd_high) - log_close).abs()

    break_up = (fwd_high - high).clip(lower=0)
    break_down = (low - fwd_low).clip(lower=0)
    max_break = np.maximum(break_up, break_down)
    range_t = (high - low).replace(0, np.nan)
    y_balance = max_break / range_t

    mfe = np.log(fwd_high) - log_close
    mae = log_close - np.log(fwd_low)
    y_transition = mfe - mae

    base_state = df["base_state"].astype(str)
    y = pd.Series(np.nan, index=df.index, dtype=float)
    y.loc[base_state == "TREND"] = y_trend.loc[base_state == "TREND"]
    y.loc[base_state == "BALANCE"] = y_balance.loc[base_state == "BALANCE"]
    y.loc[base_state == "TRANSITION"] = y_transition.loc[base_state == "TRANSITION"]

    logger.info("Phase E legacy edge_y computed | k=%s nan_rate=%.4f", k, float(y.isna().mean()))
    return y


# ============================================================
# Phase E reports (refactored baseline mode)
# ============================================================

def build_edge_reports(
    df_score_ctx: pd.DataFrame,
    symbol: str,
    score_tf: str,
    edge_k: int,
    logger: logging.Logger,
    *,
    min_events: int = 200,
    min_days: int = 20,
    edge_mode: str = "baseline",
    better_is_by_state: dict[str, str] | None = None,
    better_is_source: str = "default",
    baseline_registry_bundle: dict | None = None,
    narrative_to_baseline: dict[str, str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Outputs (keeps existing keys) + adds:
      - baseline_state_ql_uplift (STATE+QL vs STATE), baseline mode only
    """
    df = _add_date_col(df_score_ctx)

    if "quality_label_full" not in df.columns:
        df = df.copy()
        df["quality_label_full"] = df["base_state"].astype(str) + "_UNCLASSIFIED"

    look_for_cols = [c for c in df.columns if c.startswith("LOOK_FOR_")]

    df = df.copy()

    # -------------------------
    # Phase E: normalize/sanitize base_state (single source of truth = build_edge_reports for now)
    # -------------------------
    if "base_state" not in df.columns:
        raise ValueError("Phase E: missing required column 'base_state' in df_score_ctx (NO-GO).")
    
    def _norm_state(x):
        # unwrap tuple keys like ('TREND',)
        if isinstance(x, tuple) and len(x) == 1:
            x = x[0]
        if x is None:
            return ""
        s = str(x).strip().upper()
    
        # handle stringified tuples like "('TREND',)"
        if s.startswith("(") and s.endswith(")") and "," in s:
            s = s.replace("(", "").replace(")", "").replace("'", "").replace(",", "").strip().upper()
    
        return s
    
    df["base_state"] = df["base_state"].map(_norm_state)
    
    bad = df["base_state"].isna() | (df["base_state"] == "") | (df["base_state"] == "NAN")
    if bad.any():
        logger.warning(
            "Phase E: dropping %s rows with bad base_state (NaN/empty) before edge evaluation.",
            int(bad.sum()),
        )
        df = df.loc[~bad].copy()
    
    # Optional strictness (NO-GO if unknown): recommended for stability
    allowed = {"TREND", "BALANCE", "TRANSITION"}
    unknown = ~df["base_state"].isin(allowed)
    if unknown.any():
        sample = df.loc[unknown, "base_state"].value_counts().head(10).to_string()
        raise ValueError(
            "Phase E: base_state contains unknown values (NO-GO). "
            f"allowed={sorted(allowed)}\nTop unknown:\n{sample}"
        )


    # -------------------------
    # BASELINE MODE (registry)
    # -------------------------
    if edge_mode == "baseline":
        if baseline_registry_bundle is None:
            raise ValueError("baseline_registry_bundle is required for baseline mode.")
        baseline_registry = baseline_registry_bundle.get("baseline_registry", {}) if isinstance(baseline_registry_bundle, dict) else {}
        default_by_state = baseline_registry_bundle.get("default_baseline_by_state", {}) if isinstance(baseline_registry_bundle, dict) else {}
        control_defaults = baseline_registry_bundle.get("control_group_defaults", {}) if isinstance(baseline_registry_bundle, dict) else {
            "STRATUM_STATE_QL": "PARENT_ESTRATO",
            "STRATUM_STATE_QL_LF": "PARENT_ESTRATO",
        }
        mapping = narrative_to_baseline or {}
        
        # ------------------------------------------------------------
        # Determine which baseline_ids must exist per base_state
        # (default baseline + any mapped baseline actually used by LF events in that state)
        # ------------------------------------------------------------
        used_bids_by_state: dict[str, set[str]] = {}
        
        # start with defaults for states present
        for st in df["base_state"].unique():
            bid = _baseline_id_for_state(default_by_state, st)
            used_bids_by_state.setdefault(st, set()).add(bid)
        
        # add mapped baselines that are actually used by events per state
        for lf in look_for_cols:
            mapped_bid = str(mapping.get(lf, "")).strip()
            if not mapped_bid:
                continue
            ev = df[df[lf] == 1]
            if ev.empty:
                continue
            for st in ev["base_state"].unique():
                used_bids_by_state.setdefault(st, set()).add(mapped_bid)

        # Cache: compute y series per baseline_id (so same outcome definition for event + its control)
        y_cache: dict[str, pd.Series] = {}

        def _get_y_for_baseline_id(baseline_id):
            bid = "" if baseline_id is None else str(baseline_id)
            bid = bid.strip()
            if not bid:
                raise ValueError(
                    "Empty baseline_id encountered. "
                    "Likely cause: base_state contains NaN/empty OR default_baseline_by_state missing a key. "
                    "Check Phase E base_state sanitation and baseline_registry defaults."
                )
            if bid in y_cache:
                return y_cache[bid]
            if baseline_registry:
                if bid not in baseline_registry:
                    raise ValueError(f"baseline_id not in canonical registry: {bid}")
                bdef = baseline_registry[bid]
            else:
                # legacy fallback: emulate prior baseline behavior by state defaults
                # We map ids to simple defs if missing registry (still state-only)
                # NOTE: This only works if you use the template IDs; otherwise strict should be enabled.
                bdef = {"y_id": "EXIT_CURRENT_STATE_WITHIN_K", "params": {}, "better_is": "HIGHER"}
                if bid == "STATE_REINFORCEMENT":
                    bdef = {"y_id": "STAY_IN_CURRENT_STATE_WITHIN_K", "params": {}, "better_is": "HIGHER"}
                elif bid == "STATE_FRAGILITY":
                    bdef = {"y_id": "EXIT_CURRENT_STATE_WITHIN_K", "params": {}, "better_is": "HIGHER"}
                elif bid == "BALANCE_ESCAPE":
                    bdef = {"y_id": "HIT_STATE_WITHIN_K", "params": {"target": "TREND"}, "better_is": "HIGHER"}
                elif bid == "BALANCE_CONTAINMENT":
                    bdef = {"y_id": "NOT_HIT_STATE_WITHIN_K", "params": {"target": "TREND"}, "better_is": "HIGHER"}
                elif bid == "TRANSITION_RESOLUTION":
                    bdef = {"y_id": "HIT_STATE_WITHIN_K", "params": {"target": "TREND"}, "better_is": "HIGHER"}
                elif bid == "TRANSITION_NOISE":
                    bdef = {"y_id": "NOT_HIT_STATE_WITHIN_K", "params": {"target": "TREND"}, "better_is": "HIGHER"}
                elif bid == "TRANSITION_POLARITY_BIAS":
                    bdef = {"y_id": "HIT_SPECIFIC_STATE_WITHIN_K", "params": {"target": "PREVIOUS_STATE"}, "better_is": "HIGHER"}
                elif bid == "FALSE_SIGNAL_RETURN":
                    bdef = {"y_id": "EXIT_AND_REENTER_STATE_WITHIN_K", "params": {}, "better_is": "HIGHER"}

            y_cache[bid] = _compute_y_from_def(df, edge_k, bdef, logger)
            return y_cache[bid]

        # Aggregations
        base_cols_state = "base_state"                     # <- string, NO lista
        base_cols_ql = ["base_state", "quality_label_full"] # <- este se queda igual

        def _agg_prob(g: pd.DataFrame, y: pd.Series) -> pd.Series:
            yy = y.reindex(g.index)
            return pd.Series(
                {
                    "n_bars": int(len(g)),
                    "n_days": int(g["_date"].nunique()),
                    "bars_per_day": float(len(g) / g["_date"].nunique()) if g["_date"].nunique() else 0.0,
                    "p_mean": float(yy.mean()),
                    "p_std": float(yy.std(ddof=1)),
                    "p_nan_rate": float(yy.isna().mean()),
                }
            )

        # 1) Baseline by STATE (STATE x baseline_id universe)
        baseline_state_rows = []
        for st, g in df.groupby("base_state", dropna=False):
            bids = sorted(used_bids_by_state.get(st, set()))
            if not bids:
                raise ValueError(f"Phase E: no baseline_ids resolved for base_state={st!r} (NO-GO).")
            for bid in bids:
                y = _get_y_for_baseline_id(bid)
                row = _agg_prob(g, y)
                row["baseline_id"] = bid
                row["base_state"] = st
                baseline_state_rows.append(row)
        
        baseline_state = pd.DataFrame(baseline_state_rows)
        baseline_state.insert(0, "symbol", symbol)
        baseline_state.insert(1, "score_tf", score_tf)
        baseline_state.insert(2, "edge_mode", edge_mode)
        

        # 2) Baseline by STATE+QL (STATE+QL x baseline_id universe)
        baseline_ql_rows = []
        for (st, ql), g in df.groupby(["base_state", "quality_label_full"], dropna=False):
            for bid in sorted(used_bids_by_state.get(st, set())):
                y = _get_y_for_baseline_id(bid)
                row = _agg_prob(g, y)
                row["baseline_id"] = bid
                row["base_state"] = st
                row["quality_label_full"] = ql
                baseline_ql_rows.append(row)
        
        baseline_ql = pd.DataFrame(baseline_ql_rows)
        baseline_ql.insert(0, "symbol", symbol)
        baseline_ql.insert(1, "score_tf", score_tf)
        baseline_ql.insert(2, "edge_mode", edge_mode)
        
        # 2b) Uplift of STATE+QL vs STATE (control = parent stratum, same baseline_id)
        baseline_ql_uplift = baseline_ql.merge(
            baseline_state[["base_state", "baseline_id", "p_mean"]].rename(columns={"p_mean": "control_p_mean"}),
            on=["base_state", "baseline_id"],
            how="left",
        )
        baseline_ql_uplift["uplift"] = baseline_ql_uplift["p_mean"] - baseline_ql_uplift["control_p_mean"]
        baseline_ql_uplift["uplift_pp"] = baseline_ql_uplift["uplift"] * 100.0
        baseline_ql_uplift.insert(3, "control_mode", str(control_defaults.get("STRATUM_STATE_QL", "PARENT_ESTRATO")))


        # 3) LOOK_FOR events (state-level and state+QL)
        lookfor_state_rows: list[pd.DataFrame] = []
        lookfor_ql_rows: list[pd.DataFrame] = []

        def _filter(df_in: pd.DataFrame) -> pd.DataFrame:
            if df_in.empty:
                return df_in
            return df_in[(df_in["n_bars"] >= min_events) & (df_in["n_days"] >= min_days)].copy()

        for lf in look_for_cols:
            ev = df[df[lf] == 1]
            if ev.empty:
                continue

            # baseline_id used for this narrative
            mapped_bid = str(mapping.get(lf, "")).strip()

            # ---- state-level: group by base_state; control = baseline_state for that base_state
            rows = []
            for st, g in ev.groupby("base_state", dropna=False):
                bid = mapped_bid or _baseline_id_for_state(default_by_state, st)
                y = _get_y_for_baseline_id(bid)
                row = _agg_prob(g, y)
                row["look_for_rule"] = lf
                row["baseline_id"] = bid
                row["base_state"] = st
                rows.append(row)
            ev_state = pd.DataFrame(rows)
            if not ev_state.empty:
                ev_state = ev_state.merge(
                    baseline_state[["base_state", "baseline_id", "p_mean"]].rename(columns={"p_mean": "control_p_mean"}),
                    on=["base_state", "baseline_id"],
                    how="left",
                )
                ev_state["uplift"] = ev_state["p_mean"] - ev_state["control_p_mean"]
                ev_state["uplift_pp"] = ev_state["uplift"] * 100.0
                ev_state.insert(0, "score_tf", score_tf)
                ev_state.insert(0, "symbol", symbol)
                ev_state.insert(2, "edge_mode", edge_mode)
                ev_state.insert(3, "control_mode", str(control_defaults.get("PARENT_ESTRATO_STATE", "PARENT_ESTRATO")))
                lookfor_state_rows.append(ev_state)

            # ---- state+QL-level: group by (base_state, quality_label_full); control = baseline_ql for same (state, ql)
            rows = []
            for (st, ql), g in ev.groupby(["base_state", "quality_label_full"], dropna=False):
                bid = mapped_bid or _baseline_id_for_state(default_by_state, st)
                y = _get_y_for_baseline_id(bid)
                row = _agg_prob(g, y)
                row["look_for_rule"] = lf
                row["baseline_id"] = bid
                row["base_state"] = st
                row["quality_label_full"] = ql
                rows.append(row)
            ev_ql = pd.DataFrame(rows)
            if not ev_ql.empty:
                ev_ql = ev_ql.merge(
                    baseline_ql[["base_state", "quality_label_full", "baseline_id", "p_mean"]].rename(columns={"p_mean": "control_p_mean"}),
                    on=["base_state", "quality_label_full", "baseline_id"],
                    how="left",
                )
                ev_ql["uplift"] = ev_ql["p_mean"] - ev_ql["control_p_mean"]
                ev_ql["uplift_pp"] = ev_ql["uplift"] * 100.0
                ev_ql.insert(0, "score_tf", score_tf)
                ev_ql.insert(0, "symbol", symbol)
                ev_ql.insert(2, "edge_mode", edge_mode)
                ev_ql.insert(3, "control_mode", str(control_defaults.get("STRATUM_STATE_QL_LF", "PARENT_ESTRATO")))
                lookfor_ql_rows.append(ev_ql)

        lookfor_state = pd.concat(lookfor_state_rows, ignore_index=True) if lookfor_state_rows else pd.DataFrame()
        lookfor_ql = pd.concat(lookfor_ql_rows, ignore_index=True) if lookfor_ql_rows else pd.DataFrame()

        lookfor_state_f = _filter(lookfor_state)
        lookfor_ql_f = _filter(lookfor_ql)

        # Logging top
        if not lookfor_state_f.empty:
            cols = ["look_for_rule", "baseline_id", "base_state", "n_bars", "n_days", "p_mean", "control_p_mean", "uplift_pp"]
            top = lookfor_state_f.sort_values(["uplift_pp", "n_bars"], ascending=[False, False]).head(10)[cols]
            logger.info("Phase E edge top (baseline+registry, state-level, filtered):\n%s", top.to_string(index=False))

        if not lookfor_ql_f.empty:
            cols = [
                "look_for_rule",
                "baseline_id",
                "base_state",
                "quality_label_full",
                "n_bars",
                "n_days",
                "p_mean",
                "control_p_mean",
                "uplift_pp",
            ]
            top = lookfor_ql_f.sort_values(["uplift_pp", "n_bars"], ascending=[False, False]).head(10)[cols]
            logger.info("Phase E edge top (baseline+registry, state+QL+LF, filtered):\n%s", top.to_string(index=False))

        return {
            "baseline_state": baseline_state,
            "baseline_state_ql": baseline_ql,
            "baseline_state_ql_uplift": baseline_ql_uplift,
            "lookfor_state": lookfor_state,
            "lookfor_state_ql": lookfor_ql,
            "lookfor_state_filtered": lookfor_state_f,
            "lookfor_state_ql_filtered": lookfor_ql_f,
        }

    # -------------------------
    # LEGACY PRICE MODE (kept)
    # -------------------------
    # (original structure, unchanged except function boundary)
    use_better_is = True
    df["edge_y"] = compute_state_conditional_edge_y(df, edge_k, logger)

    _defaults_bi = {"TREND": "HIGHER", "BALANCE": "HIGHER", "TRANSITION": "HIGHER"}
    if better_is_by_state is None:
        better_is_by_state = dict(_defaults_bi)
        better_is_source = "default"
    else:
        tmp = dict(_defaults_bi)
        for k_state, v in better_is_by_state.items():
            tmp[str(k_state).upper().strip()] = str(v).upper().strip()
        better_is_by_state = tmp

    logger.info(
        "Phase E uplift interpretation (legacy only) better_is_by_state=%s source=%s",
        better_is_by_state,
        better_is_source,
    )

    def _apply_better_is_flip(df_ev: pd.DataFrame) -> pd.DataFrame:
        if (not use_better_is) or df_ev.empty:
            return df_ev
        df_ev = df_ev.copy()
        bi_used = df_ev["base_state"].astype(str).str.upper().map(better_is_by_state).fillna("HIGHER")  # type: ignore[arg-type]
        df_ev["better_is_used"] = bi_used
        df_ev["better_is_source"] = better_is_source
        mask = df_ev["better_is_used"] == "LOWER"
        if "uplift" in df_ev.columns:
            df_ev.loc[mask, "uplift"] = -df_ev.loc[mask, "uplift"]
        if "uplift_pct" in df_ev.columns:
            df_ev.loc[mask, "uplift_pct"] = -df_ev.loc[mask, "uplift_pct"]
        return df_ev

    def _agg(g: pd.DataFrame) -> pd.Series:
        y = g["edge_y"]
        return pd.Series(
            {
                "n_bars": int(len(g)),
                "n_days": int(g["_date"].nunique()),
                "bars_per_day": float(len(g) / g["_date"].nunique()) if g["_date"].nunique() else 0.0,
                "y_mean": float(y.mean()),
                "y_median": float(y.median()),
                "y_p75": float(y.quantile(0.75)),
                "y_p90": float(y.quantile(0.90)),
                "y_std": float(y.std(ddof=1)),
                "y_nan_rate": float(y.isna().mean()),
            }
        )

    base_cols_state = ["base_state"]
    base_cols_ql = ["base_state", "quality_label_full"]

    baseline_state = df.groupby(base_cols_state, dropna=False).apply(_agg).reset_index()
    baseline_state.insert(0, "symbol", symbol)
    baseline_state.insert(1, "score_tf", score_tf)
    baseline_state.insert(2, "edge_mode", edge_mode)

    baseline_ql = df.groupby(base_cols_ql, dropna=False).apply(_agg).reset_index()
    baseline_ql.insert(0, "symbol", symbol)
    baseline_ql.insert(1, "score_tf", score_tf)
    baseline_ql.insert(2, "edge_mode", edge_mode)

    lookfor_state_rows: list[pd.DataFrame] = []
    lookfor_ql_rows: list[pd.DataFrame] = []

    for lf in look_for_cols:
        ev = df[df[lf] == 1]
        if ev.empty:
            continue

        ev_state = ev.groupby(base_cols_state, dropna=False).apply(_agg).reset_index()
        ev_state.insert(0, "look_for_rule", lf)
        ev_state = ev_state.merge(
            baseline_state[["base_state", "y_mean"]].rename(columns={"y_mean": "baseline_y_mean"}),
            on="base_state",
            how="left",
        )
        ev_state["uplift"] = ev_state["y_mean"] - ev_state["baseline_y_mean"]
        ev_state["uplift_pct"] = ev_state["uplift"] / ev_state["baseline_y_mean"].replace(0, np.nan)
        ev_state = _apply_better_is_flip(ev_state)
        ev_state.insert(0, "score_tf", score_tf)
        ev_state.insert(0, "symbol", symbol)
        ev_state.insert(2, "edge_mode", edge_mode)
        lookfor_state_rows.append(ev_state)

        ev_ql = ev.groupby(base_cols_ql, dropna=False).apply(_agg).reset_index()
        ev_ql.insert(0, "look_for_rule", lf)
        ev_ql = ev_ql.merge(
            baseline_ql[["base_state", "quality_label_full", "y_mean"]].rename(columns={"y_mean": "baseline_y_mean"}),
            on=["base_state", "quality_label_full"],
            how="left",
        )
        ev_ql["uplift"] = ev_ql["y_mean"] - ev_ql["baseline_y_mean"]
        ev_ql["uplift_pct"] = ev_ql["uplift"] / ev_ql["baseline_y_mean"].replace(0, np.nan)
        ev_ql = _apply_better_is_flip(ev_ql)
        ev_ql.insert(0, "score_tf", score_tf)
        ev_ql.insert(0, "symbol", symbol)
        ev_ql.insert(2, "edge_mode", edge_mode)
        lookfor_ql_rows.append(ev_ql)

    lookfor_state = pd.concat(lookfor_state_rows, ignore_index=True) if lookfor_state_rows else pd.DataFrame()
    lookfor_ql = pd.concat(lookfor_ql_rows, ignore_index=True) if lookfor_ql_rows else pd.DataFrame()

    def _filter(df_in: pd.DataFrame) -> pd.DataFrame:
        if df_in.empty:
            return df_in
        return df_in[(df_in["n_bars"] >= min_events) & (df_in["n_days"] >= min_days)].copy()

    lookfor_state_f = _filter(lookfor_state)
    lookfor_ql_f = _filter(lookfor_ql)

    if not lookfor_state_f.empty:
        cols = ["look_for_rule", "base_state", "n_bars", "n_days", "y_mean", "baseline_y_mean", "uplift_pct"]
        if "better_is_used" in lookfor_state_f.columns:
            cols = ["look_for_rule", "base_state", "better_is_used", "n_bars", "n_days", "y_mean", "baseline_y_mean", "uplift_pct"]
        top = lookfor_state_f.sort_values(["uplift_pct", "n_bars"], ascending=[False, False]).head(10)[cols]
        logger.info("Phase E edge top (legacy mode, state-level, filtered):\n%s", top.to_string(index=False))

    if not lookfor_ql_f.empty:
        cols = ["look_for_rule", "base_state", "quality_label_full", "n_bars", "n_days", "y_mean", "baseline_y_mean", "uplift_pct"]
        if "better_is_used" in lookfor_ql_f.columns:
            cols = ["look_for_rule", "base_state", "quality_label_full", "better_is_used", "n_bars", "n_days", "y_mean", "baseline_y_mean", "uplift_pct"]
        top = lookfor_ql_f.sort_values(["uplift_pct", "n_bars"], ascending=[False, False]).head(10)[cols]
        logger.info("Phase E edge top (legacy mode, state+QL, filtered):\n%s", top.to_string(index=False))

    return {
        "baseline_state": baseline_state,
        "baseline_state_ql": baseline_ql,
        "lookfor_state": lookfor_state,
        "lookfor_state_ql": lookfor_ql,
        "lookfor_state_filtered": lookfor_state_f,
        "lookfor_state_ql_filtered": lookfor_ql_f,
    }


# ============================================================
# Diagnostics: avg_run_length + flip_rate per state (TF base)
# ============================================================

def compute_state_run_diagnostics(ctx_df_base: pd.DataFrame, context_tf: str, logger: logging.Logger) -> pd.DataFrame:
    """
    ctx_df_base: context_bundle.ctx_df (indexed by time) at TF base.
    Computes:
      - avg_run_length: mean length of contiguous runs per state
      - flip_rate: P(state changes on next bar) conditional on being in that state (approx)
    """
    df = ctx_df_base.copy()
    state_col = f"state_hat_{context_tf}"
    if state_col in df.columns:
        s = _normalize_state_labels(df[state_col]).astype(str)
    elif "state_hat" in df.columns:
        s = _normalize_state_labels(df["state_hat"]).astype(str)
    else:
        raise ValueError("No state_hat found in ctx_df_base for diagnostics.")

    # Run lengths
    change = s.ne(s.shift(1)).fillna(True)
    run_id = change.cumsum()
    run_len = s.groupby(run_id).size()
    run_state = s.groupby(run_id).first()

    runs = pd.DataFrame({"state": run_state.values, "run_len": run_len.values})
    avg_run = runs.groupby("state")["run_len"].mean()

    # Flip rate: count transitions out of state / count bars in state
    flip = s.ne(s.shift(-1))
    flip_counts = flip.groupby(s).sum()
    bar_counts = s.groupby(s).size()
    flip_rate = (flip_counts / bar_counts).replace([np.inf, -np.inf], np.nan)

    out = pd.DataFrame(
        {
            "base_state": avg_run.index.astype(str),
            "avg_run_length": avg_run.values.astype(float),
            "flip_rate": flip_rate.reindex(avg_run.index).values.astype(float),
            "n_bars": bar_counts.reindex(avg_run.index).values.astype(int),
            "n_runs": runs.groupby("state").size().reindex(avg_run.index).values.astype(int),
        }
    ).sort_values("base_state")

    logger.info("Phase E diagnostics (TF base) computed | states=%s", len(out))
    return out


# ============================================================
# Main
# ============================================================

def main() -> None:
    args = parse_args()
    logger = setup_logging()

    symbol = args.symbol
    context_tf = args.timeframe.upper()
    start = pd.to_datetime(args.start)
    end = pd.to_datetime(args.end)

    bars_per_hour = {"H1": 1, "H2": 0.5}
    derived_bars = math.ceil(args.window_hours * bars_per_hour[context_tf])
    if derived_bars < 4:
        raise ValueError(f"Context window too small: {derived_bars} bars (min=4).")
    logger.info("window_hours=%s context_tf=%s derived_bars=%s", args.window_hours, context_tf, derived_bars)

    _run_phase_d_audit(logger, fail_on_audit=args.fail_on_audit)

    logger.info("download start symbol=%s tf=%s", symbol, context_tf)
    connector = MT5Connector()
    ohlcv_ctx = connector.obtener_ohlcv(symbol, context_tf, start, end)
    logger.info("download done rows=%s", len(ohlcv_ctx))

    model_root = Path(args.model_path)
    if model_root.is_dir() or model_root.suffix.lower() != ".pkl":
        model_path = model_root / f"{safe_filename(symbol)}_state_engine.pkl"
    else:
        model_path = model_root
    logger.info("predict start model_path=%s", model_path)

    model = StateEngineModel()
    model.load(model_path)

    feature_engineer = FeatureEngineer(FeatureConfig(window=derived_bars))
    full_features = feature_engineer.compute_features(ohlcv_ctx)
    features = feature_engineer.training_features(full_features)
    outputs = model.predict_outputs(features)
    logger.info("predict done rows=%s", len(outputs))

    logger.info("quality start")
    symbol_cfg = load_symbol_config(symbol, logger)
    if args.debug_allow_missing_quality:
        logger.warning("DEBUG: quality_labels=None (Phase C skipped).")
        quality_labels = None
    else:
        quality_config = _resolve_quality_config(symbol_cfg, logger)
        quality_labels, quality_assign_warnings = assign_quality_labels(
            outputs["state_hat"],
            full_features.reindex(outputs.index),
            quality_config,
        )
        if quality_assign_warnings:
            logger.warning("quality assign warnings: %s", quality_assign_warnings)
    logger.info("quality done")

    logger.info("look_for start")
    gating_policy = GatingPolicy()
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
        quality_labels=quality_labels,
    )
    ctx_df = context_bundle.ctx_df.copy()
    logger.info("look_for done")

    if (quality_labels is None) and (not args.debug_allow_missing_quality):
        logger.error("quality_labels=None no permitido en flujo principal (Phase C faltante).")
        raise SystemExit(2)

    if (not args.debug_allow_missing_quality) and ctx_df["quality_label_full"].nunique() <= 3:
        logger.error("quality_label_full degenerado (nunique<=3). Phase C no aplicado correctamente.")
        raise SystemExit(2)

    # -------------------------
    # Phase D export (audit artifact)
    # -------------------------
    look_for_cols = [col for col in ctx_df.columns if col.startswith("LOOK_FOR_")]
    if look_for_cols:
        ctx_df[look_for_cols] = ctx_df[look_for_cols].fillna(0).astype(int)
    else:
        ctx_df["LOOK_FOR_NONE"] = 1
        look_for_cols = ["LOOK_FOR_NONE"]

    ctx_df["symbol"] = symbol
    index_name = ctx_df.index.name or "time"
    ctx_df_export = ctx_df.reset_index().rename(columns={index_name: "time"})

    ordered_cols = ["time", "symbol", "state_hat", "quality_label"]
    ordered_cols += sorted(look_for_cols)
    optional_cols = []
    if "margin" in ctx_df_export.columns:
        optional_cols.append("margin")
    optional_cols += sorted(col for col in ctx_df_export.columns if col.startswith("ctx_"))
    remaining_cols = [col for col in ctx_df_export.columns if col not in set(ordered_cols + optional_cols)]
    ordered_cols += optional_cols + remaining_cols
    ctx_df_export = ctx_df_export.loc[:, ordered_cols]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"phase_d_context_base_{safe_filename(symbol)}_{context_tf}_{args.start}_{args.end}.parquet"
    output_path = output_dir / filename
    logger.info("export start path=%s", output_path)
    ctx_df_export.to_parquet(output_path, index=False)
    logger.info("export done rows=%s", len(ctx_df_export))

    # -------------------------
    # Phase E
    # -------------------------
    if args.phase_e:
        score_tf = args.score_tf
        if score_tf is None:
            score_tf = symbol_cfg.get("event_scorer", {}).get("score_tf") if isinstance(symbol_cfg, dict) else None
        if score_tf is None:
            score_tf = "M5"
        score_tf = str(score_tf).upper()

        logger.info("Phase E mode=%s", args.edge_mode)
        logger.info("Phase E download start symbol=%s tf=%s", symbol, score_tf)
        ohlcv_score = connector.obtener_ohlcv(symbol, score_tf, start, end)
        logger.info("Phase E download done rows=%s", len(ohlcv_score))

        df_score_ctx = merge_context_intraday(
            context_bundle.ctx_df.copy(),
            ohlcv_score,
            context_tf=context_tf,
            logger=logger,
        )

        state_col = f"state_hat_{context_tf}"
        if state_col in df_score_ctx.columns:
            base_state = _normalize_state_labels(df_score_ctx[state_col])
        else:
            base_state = _normalize_state_labels(df_score_ctx["state_hat"])
        df_score_ctx["base_state"] = base_state
        
        # -------------------------
        # Phase E: sanitize base_state (avoid NaN/empty groups)
        # -------------------------
        df_score_ctx["base_state"] = (
            df_score_ctx["base_state"]
            .astype("string")
            .str.upper()
            .str.strip()
        )
        
        bad = df_score_ctx["base_state"].isna() | (df_score_ctx["base_state"] == "")
        if bad.any():
            logger.warning(
                "Phase E base_state has %s bad rows (NaN/empty). Dropping them before edge evaluation.",
                int(bad.sum()),
            )
            df_score_ctx = df_score_ctx.loc[~bad].copy()

        look_for_cols = [col for col in df_score_ctx.columns if col.startswith("LOOK_FOR_")]
        if look_for_cols:
            df_score_ctx[look_for_cols] = df_score_ctx[look_for_cols].fillna(0).astype(int)
        any_lookfor = df_score_ctx[look_for_cols].any(axis=1) if look_for_cols else pd.Series(False, index=df_score_ctx.index)

        logger.info("Phase E df_score_ctx rows=%s", len(df_score_ctx))
        logger.info("Phase E base_state value_counts:\n%s", df_score_ctx["base_state"].value_counts().to_string())
        logger.info(
            "Phase E quality_label_full value_counts (top10):\n%s",
            df_score_ctx["quality_label_full"].value_counts().head(10).to_string(),
        )
        logger.info("Phase E pct_any_lookfor=%.2f%%", float(any_lookfor.mean() * 100.0))

        # better_is only for legacy_price mode
        better_is_by_state = None
        better_is_source = "n/a"
        if args.edge_mode == "legacy_price":
            better_is_by_state, better_is_source = _resolve_phase_e_better_is_by_state(symbol_cfg, logger)

        edge_k = args.edge_k if args.edge_k is not None else _default_edge_k(score_tf)

        # Baseline registry + narrative mapping (baseline mode only)
        baseline_bundle = None
        narrative_to_baseline = None
        if args.edge_mode == "baseline":
            baseline_bundle = load_baseline_registry(
                Path(args.baseline_registry),
                logger,
                strict=args.strict_baseline_registry,
            )
            narrative_to_baseline = load_narrative_to_baseline_mapping(symbol_cfg, logger)

            # Validate mapping against closed catalog (if registry present)
            reg = baseline_bundle.get("baseline_registry", {}) if isinstance(baseline_bundle, dict) else {}
            if reg and narrative_to_baseline:
                bad = [(k, v) for k, v in narrative_to_baseline.items() if v not in reg]
                if bad:
                    msg = f"narrative_to_baseline contains baseline_ids not in canonical registry: {bad[:10]}"
                    if args.strict_baseline_registry:
                        logger.error(msg)
                        raise SystemExit(2)
                    logger.warning("%s | These mappings will fail if invoked.", msg)

        edge_reports = build_edge_reports(
            df_score_ctx=df_score_ctx,
            symbol=symbol,
            score_tf=score_tf,
            edge_k=edge_k,
            logger=logger,
            min_events=args.edge_min_events,
            min_days=args.edge_min_days,
            edge_mode=args.edge_mode,
            better_is_by_state=better_is_by_state,
            better_is_source=better_is_source,
            baseline_registry_bundle=baseline_bundle,
            narrative_to_baseline=narrative_to_baseline,
        )

        # Diagnostics (TF base)
        diag_df = compute_state_run_diagnostics(context_bundle.ctx_df.copy(), context_tf, logger)

        distinct_pairs = (
            df_score_ctx[["base_state", "quality_label_full"]]
            .drop_duplicates()
            .sort_values(["base_state", "quality_label_full"])
        )
        logger.info(
            "Phase E distinct (base_state, quality_label_full) pairs=%s\n%s",
            len(distinct_pairs),
            distinct_pairs.to_string(index=False),
        )

        universe_events = df_score_ctx.copy()
        lookfor_events = df_score_ctx.loc[any_lookfor].copy()

        coverage_df = pd.DataFrame()
        if look_for_cols:
            total_rows = len(df_score_ctx)
            covered_rows = int(any_lookfor.sum())
            coverage_df = pd.DataFrame(
                [
                    {
                        "total_rows": total_rows,
                        "rows_with_look_for": covered_rows,
                        "coverage_pct": (covered_rows / max(total_rows, 1)) * 100.0,
                    }
                ]
            )

        # -----------------------------
        # Phase E exports (robusto)
        # -----------------------------
        base_out = Path(args.out_phase_e or args.out or output_dir).resolve()
        base_out.mkdir(parents=True, exist_ok=True)
        
        # símbolo primero + PhaseE + tf + rango
        file_prefix = f"{safe_filename(symbol)}_PhaseE_{score_tf}_{args.start}_{args.end}"
        
        universe_path = (base_out / f"{file_prefix}_universe.csv").resolve()
        lookfor_path  = (base_out / f"{file_prefix}_lookfor.csv").resolve()
        coverage_path = (base_out / f"{file_prefix}_coverage.csv").resolve()
        diag_path     = (base_out / f"{file_prefix}_diagnostics_state_runs.csv").resolve()
        
        universe_events.to_csv(universe_path, index=False)
        lookfor_events.to_csv(lookfor_path, index=False)
        if not coverage_df.empty:
            coverage_df.to_csv(coverage_path, index=False)
        diag_df.to_csv(diag_path, index=False)
        
        logger.info("Phase E export universe=%s", universe_path)
        logger.info("Phase E export lookfor=%s", lookfor_path)
        if not coverage_df.empty:
            logger.info("Phase E export coverage=%s", coverage_path)
        logger.info("Phase E export diagnostics=%s", diag_path)
        
        # -----------------------------------------------
        # Export Phase E edge reports (baseline + uplift)
        # -----------------------------------------------
        edge_tag = "baseline" if args.edge_mode == "baseline" else "legacy"
        edge_dir = (base_out / f"{file_prefix}_edge_{edge_tag}").resolve()
        edge_dir.mkdir(parents=True, exist_ok=True)
        
        baseline_state_path = (edge_dir / f"{file_prefix}_baseline_state.csv").resolve()
        baseline_state_ql_path = (edge_dir / f"{file_prefix}_baseline_state_ql.csv").resolve()
        baseline_state_ql_uplift_path = (edge_dir / f"{file_prefix}_baseline_state_ql_uplift.csv").resolve()
        
        lookfor_state_path = (edge_dir / f"{file_prefix}_lookfor_state.csv").resolve()
        lookfor_state_ql_path = (edge_dir / f"{file_prefix}_lookfor_state_ql.csv").resolve()
        lookfor_state_filtered_path = (edge_dir / f"{file_prefix}_lookfor_state_filtered.csv").resolve()
        lookfor_state_ql_filtered_path = (edge_dir / f"{file_prefix}_lookfor_state_ql_filtered.csv").resolve()
        
        # baseline siempre
        edge_reports["baseline_state"].to_csv(baseline_state_path, index=False)
        edge_reports["baseline_state_ql"].to_csv(baseline_state_ql_path, index=False)
        
        # NEW (baseline mode only)
        if "baseline_state_ql_uplift" in edge_reports and not edge_reports["baseline_state_ql_uplift"].empty:
            edge_reports["baseline_state_ql_uplift"].to_csv(baseline_state_ql_uplift_path, index=False)
        
        # lookfor (solo si hay data)
        if not edge_reports["lookfor_state"].empty:
            edge_reports["lookfor_state"].to_csv(lookfor_state_path, index=False)
        if not edge_reports["lookfor_state_ql"].empty:
            edge_reports["lookfor_state_ql"].to_csv(lookfor_state_ql_path, index=False)
        
        if not edge_reports["lookfor_state_filtered"].empty:
            edge_reports["lookfor_state_filtered"].to_csv(lookfor_state_filtered_path, index=False)
        if not edge_reports["lookfor_state_ql_filtered"].empty:
            edge_reports["lookfor_state_ql_filtered"].to_csv(lookfor_state_ql_filtered_path, index=False)
        
        logger.info("Phase E export edge baseline_state=%s", baseline_state_path)
        logger.info("Phase E export edge baseline_state_ql=%s", baseline_state_ql_path)
        if "baseline_state_ql_uplift" in edge_reports and not edge_reports["baseline_state_ql_uplift"].empty:
            logger.info("Phase E export edge baseline_state_ql_uplift=%s", baseline_state_ql_uplift_path)
        
        if not edge_reports["lookfor_state"].empty:
            logger.info("Phase E export edge lookfor_state=%s", lookfor_state_path)
        if not edge_reports["lookfor_state_ql"].empty:
            logger.info("Phase E export edge lookfor_state_ql=%s", lookfor_state_ql_path)
        if not edge_reports["lookfor_state_filtered"].empty:
            logger.info("Phase E export edge lookfor_state_filtered=%s", lookfor_state_filtered_path)
        if not edge_reports["lookfor_state_ql_filtered"].empty:
            logger.info("Phase E export edge lookfor_state_ql_filtered=%s", lookfor_state_ql_filtered_path)



if __name__ == "__main__":
    main()

# Ejemplos CLI:
# (baseline recommended)
# python scripts/build_phase_d_context.py --symbol XAUUSD.mg --start 2024-01-01 --end 2024-02-01 --timeframe H1 --window-hours 48 \
#   --phase-e --score-tf M5 --edge-mode baseline --edge-k 24 --baseline-registry configs/baseline_registry.yaml --out-phase-e outputs/phase_e_XAUUSD
#
# (legacy price mode)
# python scripts/build_phase_d_context.py --symbol XAUUSD.mg --start 2024-01-01 --end 2024-02-01 --timeframe H1 --window-hours 48 \
#   --phase-e --score-tf M5 --edge-mode legacy_price --edge-k 24 --out-phase-e outputs/phase_e_XAUUSD