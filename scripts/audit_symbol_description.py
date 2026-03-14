# scripts/audit_symbol_description.py
# ------------------------------------------------------------
# Audit estructural (read-only) de "descripción" por símbolo:
# Phase D (LOOK_FOR flags en parquet) + Phase E (CSV edge_baseline)
#
# Objetivo:
# - Evitar reproceso de pipeline por confusiones.
# - Chequear "cariño conceptual" sin p-hacking:
#   D1: inventory + activity LOOK_FOR
#   D2: richness Phase E (top uplift/top n_bars/bands/coverage por estado)
#   D3: redundancia (Jaccard entre flags)
#   D4: segmentación estructural por sesión/QL/ctx features (sin outcomes)
#
# Entradas:
# - --symbol
# - --phase_e_dir: outputs/phase_e/<SYMBOL>_PhaseE_..._edge_baseline
# - --enriched_parquet: parquet con columnas LOOK_FOR_*, base_state/QL/ctx
# - --out_dir: carpeta para outputs (csv + report yaml)
#
# Salidas:
# - Consola (resumen)
# - out_dir/:
#    - d1_lookfor_activity.csv
#    - d2_phasee_rules_state_filtered.csv
#    - d2_phasee_rules_state_ql_filtered.csv (si existe)
#    - d2_bands_by_uplift.csv
#    - d3_jaccard_pairs.csv
#    - d4_by_session.csv
#    - d4_by_quality.csv
#    - report.yaml
# ------------------------------------------------------------

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml


# -----------------------------
# Config fija (no tuning por CLI)
# -----------------------------
JACCARD_ALERT_THRESHOLD = 0.70
DOMINANCE_ALERT_THRESHOLD = 0.60  # top1 share
MIN_RULES_ALERT = 4              # heurística suave: <4 reglas totales suele ser "pobre"
BANDS = [(-np.inf, 0.0, "Band <0"),
         (0.0, 4.0, "Band 0–4"),
         (4.0, 6.0, "Band 4–6"),
         (6.0, np.inf, "Band >=6")]


# -----------------------------
# Helpers
# -----------------------------
def _safe_float(x) -> float:
    try:
        if pd.isna(x):
            return np.nan
    except Exception:
        pass
    try:
        return float(x)
    except Exception:
        return np.nan


def _safe_int(x) -> int:
    try:
        if pd.isna(x):
            return 0
    except Exception:
        pass
    try:
        return int(float(x))
    except Exception:
        return 0


def _read_csv_if_exists(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    return pd.read_csv(path)


def _find_phase_e_files(phase_e_dir: Path, symbol: str) -> Dict[str, Path]:
    """
    Busca archivos Phase E estándar dentro de edge_baseline dir.
    Esperados (nombres típicos del repo):
      - <symbol>_..._lookfor_state_filtered.csv
      - <symbol>_..._lookfor_state_ql_filtered.csv
    También puede existir _lookfor_state.csv y _lookfor_state_ql.csv sin filtered.
    """
    if not phase_e_dir.exists():
        raise FileNotFoundError(f"--phase_e_dir no existe: {phase_e_dir}")

    # Prefer filtered
    candidates = list(phase_e_dir.glob(f"{symbol}_*lookfor_state_filtered.csv"))
    state_filtered = candidates[0] if candidates else None

    candidates = list(phase_e_dir.glob(f"{symbol}_*lookfor_state_ql_filtered.csv"))
    state_ql_filtered = candidates[0] if candidates else None

    # Fallback non-filtered
    candidates = list(phase_e_dir.glob(f"{symbol}_*lookfor_state.csv"))
    state_all = candidates[0] if candidates else None

    candidates = list(phase_e_dir.glob(f"{symbol}_*lookfor_state_ql.csv"))
    state_ql_all = candidates[0] if candidates else None

    out = {}
    if state_filtered:
        out["state_filtered"] = state_filtered
    elif state_all:
        out["state_filtered"] = state_all  # keep key stable

    if state_ql_filtered:
        out["state_ql_filtered"] = state_ql_filtered
    elif state_ql_all:
        out["state_ql_filtered"] = state_ql_all

    return out


def _infer_time_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["time", "ts", "timestamp", "datetime"]:
        if c in df.columns:
            return c
    return None


def _normalize_bool_flag(s: pd.Series) -> pd.Series:
    # Accepts 0/1, True/False, NaN. Normalize to {0,1}
    x = s.copy()
    # numeric
    try:
        x = pd.to_numeric(x, errors="coerce")
        x = x.fillna(0.0)
        return (x > 0.5).astype(int)
    except Exception:
        # fallback: string compare
        return x.fillna(0).astype(int)


def _list_lookfor_cols(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if isinstance(c, str) and c.startswith("LOOK_FOR_")]


def _print_df(df: pd.DataFrame, title: str, max_rows: int = 20) -> None:
    print("\n" + title)
    if df is None or df.empty:
        print("(empty)")
        return
    with pd.option_context("display.max_rows", max_rows,
                           "display.max_columns", 50,
                           "display.width", 140,
                           "display.max_colwidth", 80):
        print(df.head(max_rows).to_string(index=False))


# -----------------------------
# D1: LOOK_FOR inventory + activity
# -----------------------------
def d1_lookfor_activity(enriched: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    lf_cols = _list_lookfor_cols(enriched)
    if not lf_cols:
        return pd.DataFrame(), {"n_lookfor_cols": 0}

    sums = []
    for c in lf_cols:
        active_bars = int(_normalize_bool_flag(enriched[c]).sum())
        sums.append({"look_for_flag": c, "active_bars": active_bars})
    d1 = pd.DataFrame(sums).sort_values("active_bars", ascending=False).reset_index(drop=True)

    total_active = int(d1["active_bars"].sum())
    top1_share = (d1.loc[0, "active_bars"] / total_active) if total_active > 0 else np.nan
    inactive = d1[d1["active_bars"] == 0].copy()

    stats = {
        "n_lookfor_cols": int(len(lf_cols)),
        "total_active_bars_across_flags": total_active,
        "top1_flag": str(d1.loc[0, "look_for_flag"]) if not d1.empty else None,
        "top1_share_of_activity": float(top1_share) if np.isfinite(top1_share) else None,
        "inactive_flags_n": int(len(inactive)),
    }
    return d1, stats


# -----------------------------
# D2: Phase E richness
# -----------------------------
def _phasee_min_cols_ok(df: pd.DataFrame) -> bool:
    need = {"base_state", "look_for_rule", "baseline_id", "n_bars", "uplift_pp"}
    return need.issubset(set(df.columns))


def d2_phasee_richness(phase_e_files: Dict[str, Path]) -> Tuple[Dict[str, pd.DataFrame], Dict]:
    out_dfs: Dict[str, pd.DataFrame] = {}
    stats: Dict = {"files_found": {k: str(v) for k, v in phase_e_files.items()}}

    if "state_filtered" not in phase_e_files:
        return out_dfs, {**stats, "error": "No Phase E lookfor_state(_filtered).csv found in phase_e_dir"}

    df_state = pd.read_csv(phase_e_files["state_filtered"])
    if not _phasee_min_cols_ok(df_state):
        return out_dfs, {**stats, "error": f"Phase E state file missing cols. Found={list(df_state.columns)}"}

    # normalize types
    df_state = df_state.copy()
    df_state["n_bars"] = df_state["n_bars"].apply(_safe_float)
    df_state["uplift_pp"] = df_state["uplift_pp"].apply(_safe_float)

    out_dfs["phasee_state_filtered"] = df_state

    # Optional state_ql
    df_state_ql = None
    if "state_ql_filtered" in phase_e_files:
        df_state_ql = pd.read_csv(phase_e_files["state_ql_filtered"])
        if _phasee_min_cols_ok(df_state_ql):
            df_state_ql = df_state_ql.copy()
            df_state_ql["n_bars"] = df_state_ql["n_bars"].apply(_safe_float)
            df_state_ql["uplift_pp"] = df_state_ql["uplift_pp"].apply(_safe_float)
            out_dfs["phasee_state_ql_filtered"] = df_state_ql
        else:
            stats["warn_state_ql_missing_cols"] = list(df_state_ql.columns)

    # Top by uplift and by n_bars (state file)
    top_uplift = df_state.sort_values(["uplift_pp", "n_bars"], ascending=[False, False]).head(20)
    top_nbars = df_state.sort_values(["n_bars", "uplift_pp"], ascending=[False, False]).head(20)

    counts_by_state = df_state["base_state"].value_counts().rename_axis("base_state").reset_index(name="n_rules")

    # Bands summary
    band_rows = []
    for lo, hi, name in BANDS:
        sub = df_state[(df_state["uplift_pp"] >= lo) & (df_state["uplift_pp"] < hi)].copy()
        band_rows.append({
            "band": name,
            "rules": int(len(sub)),
            "total_n_bars": float(sub["n_bars"].sum()) if not sub.empty else 0.0,
            "max_uplift_pp": float(sub["uplift_pp"].max()) if not sub.empty else np.nan,
            "min_uplift_pp": float(sub["uplift_pp"].min()) if not sub.empty else np.nan,
        })
    bands_df = pd.DataFrame(band_rows)

    out_dfs["top_uplift_state"] = top_uplift
    out_dfs["top_nbars_state"] = top_nbars
    out_dfs["counts_by_state"] = counts_by_state
    out_dfs["bands_by_uplift"] = bands_df

    stats.update({
        "n_rules_total_state": int(len(df_state)),
        "n_rules_by_state": {k: int(v) for k, v in df_state["base_state"].value_counts().to_dict().items()},
        "max_uplift_pp": float(df_state["uplift_pp"].max()) if len(df_state) else None,
        "median_uplift_pp": float(df_state["uplift_pp"].median()) if len(df_state) else None,
        "dominant_rule_share_by_nbars": float(df_state["n_bars"].max() / df_state["n_bars"].sum()) if df_state["n_bars"].sum() else None,
    })

    return out_dfs, stats


# -----------------------------
# D3: Redundancia Jaccard
# -----------------------------
def d3_jaccard(enriched: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    lf_cols = _list_lookfor_cols(enriched)
    if len(lf_cols) < 2:
        return pd.DataFrame(), {"n_pairs": 0}

    # binarize
    X = {}
    for c in lf_cols:
        X[c] = _normalize_bool_flag(enriched[c]).values.astype(bool)

    pairs = []
    for i in range(len(lf_cols)):
        a = lf_cols[i]
        A = X[a]
        for j in range(i + 1, len(lf_cols)):
            b = lf_cols[j]
            B = X[b]
            inter = int(np.logical_and(A, B).sum())
            union = int(np.logical_or(A, B).sum())
            jac = (inter / union) if union > 0 else np.nan
            pairs.append({
                "a": a,
                "b": b,
                "intersect": inter,
                "union": union,
                "jaccard": float(jac) if np.isfinite(jac) else np.nan,
            })

    d3 = pd.DataFrame(pairs).sort_values("jaccard", ascending=False).reset_index(drop=True)
    max_j = float(d3["jaccard"].max()) if not d3.empty else None
    stats = {
        "n_pairs": int(len(d3)),
        "max_jaccard": max_j,
        "alert_pairs_n": int((d3["jaccard"] >= JACCARD_ALERT_THRESHOLD).sum()) if not d3.empty else 0,
        "threshold": JACCARD_ALERT_THRESHOLD,
    }
    return d3, stats


# -----------------------------
# D4: Segmentación estructural
# -----------------------------
def d4_segmentation(enriched: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    lf_cols = _list_lookfor_cols(enriched)
    if not lf_cols:
        return pd.DataFrame(), pd.DataFrame(), {"n_rules": 0}

    # pick segmentation columns
    session_col = "ctx_session_bucket" if "ctx_session_bucket" in enriched.columns else None
    ql_col = "quality_label_full" if "quality_label_full" in enriched.columns else ("quality_label" if "quality_label" in enriched.columns else None)

    # numeric context columns (optional)
    num_cols = []
    for c in ["ctx_state_age", "ctx_dist_vwap_atr"]:
        if c in enriched.columns:
            num_cols.append(c)

    rows_session = []
    rows_ql = []

    for lf in lf_cols:
        active = _normalize_bool_flag(enriched[lf]) == 1
        n_active = int(active.sum())
        if n_active == 0:
            continue

        sub = enriched.loc[active].copy()

        # session breakdown
        if session_col:
            vc = sub[session_col].astype(str).value_counts()
            total = float(vc.sum())
            for k, v in vc.items():
                rows_session.append({
                    "look_for_rule": lf,
                    "segment": "session",
                    "segment_value": k,
                    "n": int(v),
                    "share": float(v / total) if total > 0 else np.nan,
                    **{f"{nc}_mean": float(pd.to_numeric(sub[nc], errors="coerce").mean()) if nc in sub.columns else np.nan for nc in num_cols},
                    **{f"{nc}_std": float(pd.to_numeric(sub[nc], errors="coerce").std()) if nc in sub.columns else np.nan for nc in num_cols},
                })

        # quality breakdown
        if ql_col:
            vcq = sub[ql_col].astype(str).value_counts()
            totalq = float(vcq.sum())
            for k, v in vcq.items():
                rows_ql.append({
                    "look_for_rule": lf,
                    "segment": "quality_label",
                    "segment_value": k,
                    "n": int(v),
                    "share": float(v / totalq) if totalq > 0 else np.nan,
                })

    d4_session = pd.DataFrame(rows_session).sort_values(["look_for_rule", "n"], ascending=[True, False]).reset_index(drop=True) if rows_session else pd.DataFrame()
    d4_ql = pd.DataFrame(rows_ql).sort_values(["look_for_rule", "n"], ascending=[True, False]).reset_index(drop=True) if rows_ql else pd.DataFrame()

    stats = {
        "n_rules": int(len(lf_cols)),
        "has_session": bool(session_col is not None),
        "has_quality": bool(ql_col is not None),
        "ctx_numeric_cols": num_cols,
    }
    return d4_session, d4_ql, stats


# -----------------------------
# Alerts (no-go/go *flags*, not decisions)
# -----------------------------
def compute_alerts(d1_stats: Dict, d2_stats: Dict, d3_stats: Dict) -> List[str]:
    alerts = []

    # D1 dominance / no flags
    if d1_stats.get("n_lookfor_cols", 0) == 0:
        alerts.append("WARN_NO_LOOKFOR_COLUMNS_IN_PARQUET")
    else:
        top1_share = d1_stats.get("top1_share_of_activity")
        if top1_share is not None and np.isfinite(top1_share) and top1_share >= DOMINANCE_ALERT_THRESHOLD:
            alerts.append(f"WARN_LOOKFOR_DOMINANCE_TOP1_GE_{int(DOMINANCE_ALERT_THRESHOLD*100)}PCT")

    # D2 richness
    n_rules = d2_stats.get("n_rules_total_state")
    if isinstance(n_rules, int) and n_rules < MIN_RULES_ALERT:
        alerts.append(f"WARN_LOW_RULE_COUNT_LT_{MIN_RULES_ALERT}")

    by_state = d2_stats.get("n_rules_by_state", {})
    if isinstance(by_state, dict):
        # if any of BALANCE/TRANSITION/TREND missing
        for s in ["BALANCE", "TRANSITION", "TREND"]:
            if by_state.get(s, 0) == 0:
                alerts.append(f"WARN_STATE_MISSING_{s}")

    # D3 redundancy
    if d3_stats.get("alert_pairs_n", 0) > 0:
        alerts.append(f"WARN_REDUNDANCY_JACCARD_GE_{JACCARD_ALERT_THRESHOLD:.2f}")

    return alerts


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--phase_e_dir", required=True, help='outputs/phase_e/<symbol>_PhaseE_..._edge_baseline')
    ap.add_argument("--enriched_parquet", required=True, help="Phase D/F enriched parquet (must contain LOOK_FOR_* cols)")
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    symbol = args.symbol
    phase_e_dir = Path(args.phase_e_dir)
    enriched_path = Path(args.enriched_parquet)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not enriched_path.exists():
        raise SystemExit(f"Missing enriched parquet: {enriched_path}")

    # Load enriched parquet (filter symbol if present)
    enriched = pd.read_parquet(enriched_path)
    if "symbol" in enriched.columns:
        enriched = enriched[enriched["symbol"].astype(str) == symbol].copy()

    # D1
    d1_df, d1_stats = d1_lookfor_activity(enriched)
    d1_out = out_dir / "d1_lookfor_activity.csv"
    d1_df.to_csv(d1_out, index=False)

    # D2
    phase_e_files = _find_phase_e_files(phase_e_dir, symbol=symbol)
    d2_dfs, d2_stats = d2_phasee_richness(phase_e_files)

    # Save D2 tables if present
    if "phasee_state_filtered" in d2_dfs:
        d2_dfs["phasee_state_filtered"].to_csv(out_dir / "d2_phasee_rules_state_filtered.csv", index=False)
    if "phasee_state_ql_filtered" in d2_dfs:
        d2_dfs["phasee_state_ql_filtered"].to_csv(out_dir / "d2_phasee_rules_state_ql_filtered.csv", index=False)
    if "bands_by_uplift" in d2_dfs:
        d2_dfs["bands_by_uplift"].to_csv(out_dir / "d2_bands_by_uplift.csv", index=False)

    # D3
    d3_df, d3_stats = d3_jaccard(enriched)
    d3_out = out_dir / "d3_jaccard_pairs.csv"
    d3_df.to_csv(d3_out, index=False)

    # D4
    d4_session, d4_quality, d4_stats = d4_segmentation(enriched)
    (out_dir / "d4_by_session.csv").write_text("", encoding="utf-8")  # ensure file exists even if empty
    (out_dir / "d4_by_quality.csv").write_text("", encoding="utf-8")
    if not d4_session.empty:
        d4_session.to_csv(out_dir / "d4_by_session.csv", index=False)
    if not d4_quality.empty:
        d4_quality.to_csv(out_dir / "d4_by_quality.csv", index=False)

    alerts = compute_alerts(d1_stats, d2_stats, d3_stats)

    report = {
        "symbol": symbol,
        "inputs": {
            "phase_e_dir": str(phase_e_dir),
            "enriched_parquet": str(enriched_path),
        },
        "outputs": {
            "d1_lookfor_activity": str(d1_out),
            "d2_state_filtered": str(out_dir / "d2_phasee_rules_state_filtered.csv"),
            "d2_state_ql_filtered": str(out_dir / "d2_phasee_rules_state_ql_filtered.csv"),
            "d2_bands": str(out_dir / "d2_bands_by_uplift.csv"),
            "d3_jaccard_pairs": str(d3_out),
            "d4_by_session": str(out_dir / "d4_by_session.csv"),
            "d4_by_quality": str(out_dir / "d4_by_quality.csv"),
        },
        "stats": {
            "d1": d1_stats,
            "d2": d2_stats,
            "d3": d3_stats,
            "d4": d4_stats,
        },
        "alerts": alerts,
        "notes": [
            "Este audit es estructural (ontología). No usa EV ni decide GO/NO-GO.",
            "Si alerts aparecen, sugiere revisar YAML Phase D (look_fors) o Phase E export schema, no 'tunear' thresholds.",
        ],
    }

    report_path = out_dir / "report.yaml"
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f, sort_keys=False, allow_unicode=True)

    # -----------------------------
    # Console summary (Spyder friendly)
    # -----------------------------
    print("\n" + "=" * 60)
    print(f"AUDIT SYMBOL DESCRIPTION — {symbol}")
    print("=" * 60)
    print(f"- Phase E dir:        {phase_e_dir}")
    print(f"- Enriched parquet:   {enriched_path}")
    print(f"- Out dir:            {out_dir}")
    print(f"- Alerts:             {alerts if alerts else 'NONE'}")

    print("\n[D1] LOOK_FOR inventory/activity")
    print(f"  n_lookfor_cols: {d1_stats.get('n_lookfor_cols')}")
    print(f"  top1_flag:      {d1_stats.get('top1_flag')}")
    print(f"  top1_share:     {d1_stats.get('top1_share_of_activity')}")
    _print_df(d1_df, "Top LOOK_FOR by activity:", max_rows=15)

    if "phasee_state_filtered" in d2_dfs:
        df_state = d2_dfs["phasee_state_filtered"]
        print("\n[D2] Phase E richness (state_filtered)")
        print(f"  n_rules_total: {d2_stats.get('n_rules_total_state')}")
        print(f"  n_rules_by_state: {d2_stats.get('n_rules_by_state')}")
        _print_df(d2_dfs.get("top_uplift_state"), "Top by uplift_pp (state_filtered):", max_rows=15)
        _print_df(d2_dfs.get("top_nbars_state"), "Top by n_bars (state_filtered):", max_rows=15)
        _print_df(d2_dfs.get("bands_by_uplift"), "Bands by uplift_pp (state_filtered):", max_rows=10)
        _print_df(d2_dfs.get("counts_by_state"), "Counts by base_state (state_filtered):", max_rows=10)
    else:
        print("\n[D2] Phase E richness: (missing or invalid) -> see report.yaml error")

    print("\n[D3] Redundancy (Jaccard)")
    if d3_df.empty:
        print("  (not enough LOOK_FOR cols for Jaccard)")
    else:
        _print_df(d3_df, f"Top Jaccard pairs (>= {JACCARD_ALERT_THRESHOLD:.2f} flagged):", max_rows=15)

    print("\n[D4] Segmentation")
    if d4_session.empty:
        print("  session segmentation: (none or missing ctx_session_bucket)")
    else:
        _print_df(d4_session, "Top session breakdown rows:", max_rows=20)

    if d4_quality.empty:
        print("  quality segmentation: (none or missing quality_label/full)")
    else:
        _print_df(d4_quality, "Top quality breakdown rows:", max_rows=20)

    print("\n[OK] Wrote report:", report_path)
    print("     (CSV outputs in out_dir for diffing / sharing)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())