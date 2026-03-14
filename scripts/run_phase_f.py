# scripts/run_phase_f.py
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List
import pandas as pd

from state_engine.phase_f.types import ContextRow
from state_engine.phase_f.policy_engine import PolicyEngine
from state_engine.phase_f.registry import PhaseECSVRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _default_policy_path(symbol: str) -> Path:
    return PROJECT_ROOT / "configs" / "phase_f" / f"{symbol}.yaml"


def _default_symbol_config_path(symbol: str) -> Path:
    return PROJECT_ROOT / "configs" / "symbols" / f"{symbol}.yaml"


def _preflight(policy_path: Path, bar_path: Path, registry_paths: list[Path], symbol_cfg_path: Path) -> None:
    errs = []
    if not policy_path.exists():
        errs.append(f"Missing policy YAML: {policy_path}")
    if not bar_path.exists():
        errs.append(f"Missing bar stream parquet: {bar_path}")
    if not symbol_cfg_path.exists():
        errs.append(f"Missing symbol YAML: {symbol_cfg_path}")
    if not registry_paths:
        errs.append("No registry CSV provided (--registry_csv required, repeatable).")
    for rp in registry_paths:
        if not rp.exists():
            errs.append(f"Missing registry CSV: {rp}")
        if rp.suffix.lower() != ".csv":
            errs.append(f"Registry must be CSV for current repo (PhaseECSVRegistry). Got: {rp}")
    if errs:
        msg = "\n".join(["PRE-FLIGHT FAILED:"] + [f"- {e}" for e in errs])
        raise SystemExit(msg)


def _pick_time_col(df: pd.DataFrame) -> str:
    for c in ["time", "ts", "timestamp", "datetime"]:
        if c in df.columns:
            return c
    raise KeyError("No time column found (expected one of: time, ts, timestamp, datetime)")


def _as_token(x, none_token: str) -> str:
    # Normalize None/NaN/empty/"nan"/"none"/"null" -> none_token
    if x is None:
        return none_token
    try:
        if pd.isna(x):
            return none_token
    except Exception:
        pass
    s = str(x).strip()
    if s == "":
        return none_token
    low = s.lower()
    if low in {"nan", "none", "null", "na", "n/a"}:
        return none_token
    return s


def _map_state_hat_to_name(state_hat, none_token: str) -> str:
    """
    Barstream trae state_hat como int {0,1,2}.
    Registry/Phase E usa nombres: BALANCE/TRANSITION/TREND.
    """
    try:
        sid = int(state_hat)
    except Exception:
        return _as_token(state_hat, none_token)
    return {0: "BALANCE", 1: "TRANSITION", 2: "TREND"}.get(sid, _as_token(state_hat, none_token))


def _extract_look_for_flags(row: pd.Series) -> dict[str, int]:
    out = {}
    for c in row.index:
        if isinstance(c, str) and c.startswith("LOOK_FOR_"):
            try:
                out[c] = int(row[c])
            except Exception:
                out[c] = 0
    return out


def _synth_lf_from_flags(flags: dict[str, int], none_token: str, priority: Optional[List[str]]) -> str:
    # Choose first active flag by priority; fallback lexical for determinism.
    active = [k for k, v in flags.items() if v == 1]
    if not active:
        return none_token

    if priority:
        for lf in priority:
            if lf in active:
                return lf

    return sorted(active)[0]


def _force_string_contract(df: pd.DataFrame, cols: list[str], none_token: str) -> None:
    """
    Enforce: column exists -> object dtype -> NaN/None -> none_token -> str.
    Esto evita que pandas infiera float y exporte 0.0 o cosas raras.
    """
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("object")
            df[c] = df[c].where(df[c].notna(), none_token)
            df[c] = df[c].astype(str)
            df[c] = df[c].map(lambda x: _as_token(x, none_token))


def _build_context_key(state: str, ql: str, lf: str, none_token: str) -> str:
    """
    Contexto descriptivo real del bar (sin fallback del resolver/policy).
    """
    s = _as_token(state, none_token)
    q = _as_token(ql, none_token)
    l = _as_token(lf, none_token)
    return f"STATE={s}|QL={q}|LF={l}"


def _extract_ql_from_context_key(context_key: str, none_token: str) -> str:
    try:
        for part in str(context_key).split("|"):
            if part.startswith("QL="):
                return _as_token(part.split("=", 1)[1], none_token)
    except Exception:
        pass
    return none_token


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="Symbol name including suffix, e.g., XAUUSD.mg")
    ap.add_argument("--policy", default=None, help="Path to policy YAML. Default: configs/phase_f/{symbol}.yaml")
    ap.add_argument(
        "--symbol_config",
        default=None,
        help="Path to symbol YAML (configs/symbols/{symbol}.yaml). Used to annotate baseline_id via phase_e.narrative_to_baseline.",
    )
    ap.add_argument("--barstream", required=True, help="Path to outputs/phase_d_context/phase_d_context_base_<symbol>_*.parquet")
    ap.add_argument(
        "--registry_csv",
        action="append",
        required=True,
        help="Phase E filtered CSV(s). Repeat: --registry_csv <state_filtered.csv> --registry_csv <state_ql_filtered.csv>",
    )
    ap.add_argument("--outdir", default=None, help="Output directory. Default: outputs/phase_f_runs/<symbol>/<run_id>")
    ap.add_argument("--run_id", default=None, help="Optional run id folder name. Default: YYYYMMDD_HHMMSS")
    ap.add_argument("--max_rows", type=int, default=0, help="For smoke tests: process only first N rows (0 = all).")
    args = ap.parse_args()

    symbol = args.symbol
    policy_path = Path(args.policy) if args.policy else _default_policy_path(symbol)
    symbol_cfg_path = Path(args.symbol_config) if args.symbol_config else _default_symbol_config_path(symbol)

    bar_path = Path(args.barstream)
    registry_paths = [Path(p) for p in args.registry_csv]

    import datetime as _dt
    run_id = args.run_id or _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.outdir:
        out_dir = Path(args.outdir)
    else:
        out_dir = PROJECT_ROOT / "outputs" / "phase_f_runs" / symbol / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    _preflight(policy_path, bar_path, registry_paths, symbol_cfg_path)

    import yaml

    # Load policy yaml only to get lf_synth (priority + none_token) for resolver + lf synthesis.
    with policy_path.open("r", encoding="utf-8") as f:
        policy_cfg = yaml.safe_load(f) or {}

    # -----------------------------
    # Guardrail: policy context_key format must include QL=...
    # because ContextResolver always emits keys with QL component (even QL=NONE).
    # Without this, GO contexts will never match -> ALLOW=0 silent failure.
    # -----------------------------
    bad = []
    for item in (policy_cfg.get("go_contexts", []) or []):
        ck = str(item.get("context_key", "")).strip()
        if ck and ("QL=" not in ck):
            bad.append(ck)

    for item in (policy_cfg.get("risk_off", []) or []):
        ck = str(item.get("context_key", "")).strip()
        if ck and ("QL=" not in ck):
            bad.append(ck)

    if bad:
        raise SystemExit(
            "Policy YAML has context_key without 'QL=' which will never match resolver candidates. "
            f"Fix configs/phase_f/{symbol}.yaml. Examples: {bad[:5]}"
        )

    bad2 = []
    for item in (policy_cfg.get("go_contexts", []) or []):
        ck = str(item.get("context_key", "")).strip()
        if ck and ("LF=" not in ck):
            bad2.append(ck)
    if bad2:
        raise SystemExit("Policy YAML context_key missing 'LF='... Examples: " + str(bad2[:5]))

    lf_cfg = policy_cfg.get("lf_synth", {}) if isinstance(policy_cfg, dict) else {}
    none_token = lf_cfg.get("none_token", "NONE")
    priority = lf_cfg.get("priority", None)
    if priority is not None and not isinstance(priority, list):
        priority = None

    # Load symbol config to annotate baseline_id (Phase E narrative mapping)
    with symbol_cfg_path.open("r", encoding="utf-8") as f:
        symbol_cfg = yaml.safe_load(f) or {}

    n2b = {}
    try:
        if isinstance(symbol_cfg, dict):
            phase_e_cfg = symbol_cfg.get("phase_e", {}) or {}
            if isinstance(phase_e_cfg, dict):
                n2b = phase_e_cfg.get("narrative_to_baseline", {}) or {}
    except Exception:
        n2b = {}

    if not isinstance(n2b, dict):
        n2b = {}

    # Build registry + engine
    registry = PhaseECSVRegistry(symbol=symbol, csv_paths=registry_paths, none_token=none_token)
    engine = PolicyEngine(str(policy_path), registry)

    df = pd.read_parquet(bar_path)
    if args.max_rows and args.max_rows > 0:
        df = df.iloc[: args.max_rows].copy()

    time_col = _pick_time_col(df)
    if time_col != "time":
        df = df.rename(columns={time_col: "time"})

    # Required barstream columns
    required = ["time", "symbol", "state_hat"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Bar stream missing required columns: {missing}")

    # QL fallback: prefer already-normalized ql, else full, else simple, else NONE
    ql_col = (
        "ql" if "ql" in df.columns else
        ("quality_label_full" if "quality_label_full" in df.columns else
         ("quality_label" if "quality_label" in df.columns else None))
    )

    decisions_rows = []
    stats = {
        "n_rows": 0,
        "decision_counts": {},
        "none_lf_rate": 0,
        "baseline_id_null_rate": 0,
        "baseline_id_counts": {},
        "top1_candidate_match_rate": None,
        "lf_context_mismatch_count": 0,
        "ql_context_mismatch_count": 0,
    }

    n_none_lf = 0
    n_null_baseline = 0

    for _, row in df.iterrows():
        flags = _extract_look_for_flags(row)
        lf = _synth_lf_from_flags(flags, none_token=none_token, priority=priority)

        if lf == none_token:
            n_none_lf += 1

        baseline_id = n2b.get(lf) if lf != none_token else None
        if baseline_id is None:
            n_null_baseline += 1

        r = ContextRow(
            symbol=_as_token(row.get("symbol"), none_token),
            ts=row.get("time"),
            state=_map_state_hat_to_name(row.get("state_hat"), none_token),
            ql=_as_token(row.get(ql_col), none_token) if ql_col else none_token,
            lf=_as_token(lf, none_token),
            atr=None,
            spread=None,
            session=_as_token(row.get("ctx_session_bucket"), none_token) if "ctx_session_bucket" in df.columns else None,
        )

        # Contexto descriptivo real del bar (sin fallback)
        engine_context_key = _build_context_key(r.state, r.ql, r.lf, none_token)

        # Resolver/policy context
        cands = engine.resolver.candidates(r)
        dec = engine.decide(r)

        d = asdict(dec)
        meta = d.pop("meta", None) or {}
        if isinstance(meta, dict):
            for k, v in meta.items():
                d[f"meta_{k}"] = v

        # --- Phase E alignment annotation ---
        d["baseline_id"] = baseline_id if baseline_id is not None else None

        # ---- candidates: SIEMPRE tokens ----
        d["candidate_0"] = _as_token(cands[0], none_token) if len(cands) > 0 else none_token
        d["candidate_1"] = _as_token(cands[1], none_token) if len(cands) > 1 else none_token
        d["candidate_2"] = _as_token(cands[2], none_token) if len(cands) > 2 else none_token

        # include minimal barstream context for debugging
        d["ts"] = r.ts
        d["state"] = _as_token(r.state, none_token)
        d["ql"] = _as_token(r.ql, none_token)
        d["lf"] = _as_token(r.lf, none_token)
        d["session"] = _as_token(r.session, none_token) if r.session is not None else none_token

        # --- DEBUG / AUDIT ---
        d["lf_resolved"] = _as_token(r.lf, none_token)
        d["lf_active_flags_n"] = int(sum(1 for v in flags.values() if v == 1))
        d["lf_active_flags"] = "|".join([k for k, v in flags.items() if v == 1]) if flags else ""
        d["first_candidate"] = _as_token(cands[0], none_token) if cands else none_token
        d["candidates_joined"] = "|".join([_as_token(x, none_token) for x in cands]) if cands else ""

        # Contexto descriptivo real del engine
        d["engine_context_key"] = engine_context_key

        # Contexto seleccionado por policy sigue siendo context_key
        d["context_key"] = _as_token(d.get("context_key"), none_token)

        # --- AUDIT GUARDRAILS ---
        ck = d["context_key"]
        lf_token = _as_token(r.lf, none_token)
        ql_token = _as_token(r.ql, none_token)
        selected_ql = _extract_ql_from_context_key(ck, none_token)

        # If synthesized LF is a LOOK_FOR_* but context_key degrades to LF=NONE, flag it.
        lf_mismatch = int(lf_token.startswith("LOOK_FOR_") and ("LF=NONE" in ck))
        d["lf_context_mismatch"] = lf_mismatch
        if lf_mismatch:
            stats["lf_context_mismatch_count"] += 1

        # If row carries real QL but selected context falls back to QL=NONE, flag it.
        ql_mismatch = int(ql_token != selected_ql)
        d["ql_context_mismatch"] = ql_mismatch
        if ql_mismatch:
            stats["ql_context_mismatch_count"] += 1

        decisions_rows.append(d)

        stats["n_rows"] += 1
        stats["decision_counts"][dec.decision] = stats["decision_counts"].get(dec.decision, 0) + 1

        key = baseline_id if baseline_id is not None else "NULL"
        stats["baseline_id_counts"][key] = stats["baseline_id_counts"].get(key, 0) + 1

    stats["none_lf_rate"] = (n_none_lf / stats["n_rows"]) if stats["n_rows"] else 0.0
    stats["baseline_id_null_rate"] = (n_null_baseline / stats["n_rows"]) if stats["n_rows"] else 0.0

    decisions_df = pd.DataFrame(decisions_rows)

    # Ensure audit flags are numeric
    for c in ["lf_context_mismatch", "ql_context_mismatch"]:
        if c in decisions_df.columns:
            decisions_df[c] = decisions_df[c].fillna(0).astype(int)

    # ---- CONTRACT ENFORCEMENT ----
    _force_string_contract(
        decisions_df,
        cols=[
            "decision",
            "context_key",
            "engine_context_key",
            "meta_reason",
            "state",
            "ql",
            "lf",
            "lf_resolved",
            "session",
            "candidate_0",
            "candidate_1",
            "candidate_2",
            "first_candidate",
            "candidates_joined",
            "lf_active_flags",
        ],
        none_token=none_token,
    )

    # baseline_id: leave explicit NULL
    if "baseline_id" in decisions_df.columns:
        decisions_df["baseline_id"] = decisions_df["baseline_id"].astype("object")
        decisions_df["baseline_id"] = decisions_df["baseline_id"].where(decisions_df["baseline_id"].notna(), "NULL")
        decisions_df["baseline_id"] = decisions_df["baseline_id"].astype(str)

    decisions_path = out_dir / "decisions.csv"
    decisions_df.to_csv(decisions_path, index=False)

    report = {
        "symbol": symbol,
        "policy_path": str(policy_path),
        "symbol_config_path": str(symbol_cfg_path),
        "barstream_path": str(bar_path),
        "registry_csv_paths": [str(p) for p in registry_paths],
        "out_dir": str(out_dir),
        "stats": stats,
    }

    report_path = out_dir / "run_report.yaml"
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f, sort_keys=False)

    print("OK - Phase F decisions-only run complete")
    print(f"- out_dir:   {out_dir}")
    print(f"- decisions: {decisions_path}")
    print(f"- report:    {report_path}")
    if stats.get("lf_context_mismatch_count", 0) > 0:
        print(f"WARN - lf/context_key mismatches: {stats['lf_context_mismatch_count']}")
    if stats.get("ql_context_mismatch_count", 0) > 0:
        print(f"WARN - ql/context_key mismatches: {stats['ql_context_mismatch_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())