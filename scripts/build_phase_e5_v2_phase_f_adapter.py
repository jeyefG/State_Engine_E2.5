from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_E5_COLUMNS = {
    "side": "e5_side",
    "has_prediction": "e5_has_prediction",
    "long_score": "e5_long_score",
    "short_score": "e5_short_score",
    "abstain_score": "e5_abstain_score",
    "margin": "e5_margin",
    "confidence": "e5_confidence",
    "model_tag": "e5_model_tag",
}


def _load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _resolve_col(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise RuntimeError(f"Could not resolve {label}. Tried: {candidates}")


def _to_naive_datetime(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def _load_contract(path: str | None) -> dict[str, Any]:
    if not path:
        return {}

    cfg_path = Path(path)
    text = cfg_path.read_text(encoding="utf-8")
    if cfg_path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text) or {}
    return json.loads(text)


def _normalize_side(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.strip()


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Build a Phase F compatible decisions artifact by injecting Phase E.5 V2 side-layer "
            "under a side-only-on-ALLOW contract (decision gate untouched)."
        )
    )
    ap.add_argument("--decisions", required=True, help="Phase F decisions CSV/Parquet (source of ALLOW/BLOCK gate).")
    ap.add_argument("--e5-side-layer", required=True, help="Bar-level E.5 V2 side-layer CSV/Parquet.")
    ap.add_argument("--enriched", default=None, help="Optional enriched/context parquet for sanity coverage checks.")
    ap.add_argument("--contract-config", default=None, help="Optional YAML/JSON config for column names and contract options.")
    ap.add_argument("--symbol", default=None, help="Optional symbol filter.")
    ap.add_argument("--out-path", required=True, help="Output artifact path (.csv or .parquet).")
    ap.add_argument("--replace-side-intent", action="store_true", help="Also replace side_intent with side_intent_final for backtest compatibility.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    contract = _load_contract(args.contract_config)
    e5_cols = {**DEFAULT_E5_COLUMNS, **(contract.get("e5_columns", {}) if isinstance(contract, dict) else {})}

    decisions = _load_table(Path(args.decisions)).copy()
    e5 = _load_table(Path(args.e5_side_layer)).copy()

    decision_time = _resolve_col(decisions, ["ts", "time", "timestamp", "datetime"], "decision timestamp column")
    e5_time = _resolve_col(e5, ["time", "ts", "timestamp", "datetime"], "E5 timestamp column")

    if "symbol" not in decisions.columns:
        if args.symbol is None:
            raise RuntimeError("decisions input has no 'symbol' column; use --symbol to force a symbol.")
        decisions["symbol"] = str(args.symbol)

    if "symbol" not in e5.columns:
        if args.symbol is None:
            raise RuntimeError("e5-side-layer input has no 'symbol' column; use --symbol to force a symbol.")
        e5["symbol"] = str(args.symbol)

    decisions["ts"] = _to_naive_datetime(decisions[decision_time])
    e5["ts"] = _to_naive_datetime(e5[e5_time])

    decisions = decisions.dropna(subset=["ts"]).copy()
    e5 = e5.dropna(subset=["ts"]).copy()

    if args.symbol is not None:
        decisions = decisions[decisions["symbol"].astype(str) == str(args.symbol)].copy()
        e5 = e5[e5["symbol"].astype(str) == str(args.symbol)].copy()

    if "decision" not in decisions.columns:
        raise RuntimeError("decisions input missing required column: decision")
    if "side_intent" not in decisions.columns:
        raise RuntimeError("decisions input missing required column: side_intent")

    decisions["decision"] = _normalize_side(decisions["decision"])
    decisions["side_intent_orig"] = _normalize_side(decisions["side_intent"])

    # Map E.5 columns to canonical names
    e5_work = e5[["symbol", "ts"]].copy()
    for canonical, src in e5_cols.items():
        if src in e5.columns:
            e5_work[f"e5_{canonical}"] = e5[src]

    # Required traceability columns with sane defaults
    for c in ["e5_has_prediction", "e5_side", "e5_long_score", "e5_short_score", "e5_abstain_score", "e5_margin", "e5_confidence", "e5_model_tag"]:
        if c not in e5_work.columns:
            e5_work[c] = pd.NA

    e5_work["e5_side"] = _normalize_side(e5_work["e5_side"].fillna("ABSTAIN"))
    e5_work["e5_has_prediction"] = e5_work["e5_has_prediction"].fillna(0).astype(int)

    e5_work = e5_work.drop_duplicates(subset=["symbol", "ts"], keep="last")

    out = decisions.merge(e5_work, on=["symbol", "ts"], how="left")

    out["e5_has_prediction"] = out["e5_has_prediction"].fillna(0).astype(int)
    out["e5_side"] = _normalize_side(out["e5_side"].fillna("ABSTAIN"))

    is_allow = out["decision"].eq("ALLOW")
    has_e5_side = out["e5_side"].isin(["LONG", "SHORT"])
    has_pred = out["e5_has_prediction"].eq(1)

    use_e5 = is_allow & has_pred & has_e5_side
    fallback_abstain = is_allow & has_pred & (~has_e5_side)
    fallback_missing = is_allow & (~has_pred)

    out["side_intent_final"] = out["side_intent_orig"]
    out.loc[use_e5, "side_intent_final"] = out.loc[use_e5, "e5_side"]

    # 1 si E.5 fue usado como fuente del side final
    out["e5_override_applied"] = use_e5.astype(int)

    # 1 si efectivamente el side final quedó distinto al original
    out["e5_side_changed"] = (out["side_intent_orig"] != out["side_intent_final"]).astype(int)

    out["e5_override_reason"] = "no_change_non_allow"
    out.loc[use_e5, "e5_override_reason"] = "use_e5_side"
    out.loc[fallback_abstain, "e5_override_reason"] = "fallback_abstain"
    out.loc[fallback_missing, "e5_override_reason"] = "fallback_missing"

    if args.replace_side_intent:
        out["side_intent"] = out["side_intent_final"]

    if args.enriched:
        enriched = _load_table(Path(args.enriched)).copy()
        if "symbol" not in enriched.columns and args.symbol:
            enriched["symbol"] = str(args.symbol)
        if "symbol" in enriched.columns:
            enr_time = _resolve_col(enriched, ["time", "ts", "timestamp", "datetime"], "enriched timestamp column")
            enriched["ts"] = _to_naive_datetime(enriched[enr_time])
            enr_cov = out.merge(
                enriched[["symbol", "ts"]].dropna().drop_duplicates(),
                on=["symbol", "ts"],
                how="left",
                indicator=True,
            )["_merge"].eq("both").mean()
            print(f"- enriched_timestamp_match_rate: {enr_cov:.4f}")

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".parquet":
        out.to_parquet(out_path, index=False)
    else:
        out.to_csv(out_path, index=False)

    # Sanity checks requested
    e5_match_n = int((out["e5_has_prediction"] == 1).sum())
    allow_n = int(is_allow.sum())
    allow_pred_n = int((is_allow & (out["e5_has_prediction"] == 1)).sum())
    override_n = int(out["e5_override_applied"].sum())
    fallback_abstain_n = int((out["e5_override_reason"] == "fallback_abstain").sum())
    fallback_missing_n = int((out["e5_override_reason"] == "fallback_missing").sum())
    changed_side_n = int(out["e5_side_changed"].sum())

    print("OK - Phase E.5 V2 -> Phase F adapter built")
    print(f"- input_rows_original: {len(decisions)}")
    print(f"- rows_with_e5_match: {e5_match_n}")
    print(f"- rows_allow: {allow_n}")
    print(f"- rows_allow_with_e5_prediction: {allow_pred_n}")
    print(f"- overrides_applied: {override_n}")
    print(f"- fallbacks_abstain: {fallback_abstain_n}")
    print(f"- fallbacks_missing: {fallback_missing_n}")
    print("- side_intent_final_distribution:")
    print(out["side_intent_final"].value_counts(dropna=False).to_string())
    print(f"- changed_side_count: {changed_side_n}")
    print(f"- out_path: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
