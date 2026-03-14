# scripts/audit_phase_d_canonical.py
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- ensure project root is on PYTHONPATH ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE_STATES = ["BALANCE", "TRANSITION", "TREND"]


# -------------------------
# CLI
# -------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="audit_phase_d_canonical",
        description="Phase D canonical audit (CSV/Parquet). Prints PASS/FAIL checks."
    )
    p.add_argument(
        "path",
        nargs="?",
        default=str(
            PROJECT_ROOT
            / "outputs"
            / "phase_d_context"
            / "phase_d_context_base_XAUUSD.mg_H2_2024-01-01_2025-12-31.parquet"
        ),
        help="Path to CSV/Parquet."
    )
    p.add_argument("--path", dest="path_opt", default=None, help="Explicit path override.")
    p.add_argument("--no-sort-by-time", action="store_true", help="Disable sorting by 'time' column.")
    p.add_argument(
        "--lookfor-must-be-zero-outside-state",
        action="store_true",
        help="If set, any active LOOK_FOR outside base_state => FAIL."
    )
    p.add_argument(
        "--max-lookfor-bad-pct",
        type=float,
        default=0.001,
        help="Threshold for pct of bad LOOK_FOR rows (default 0.001 = 0.1%%)."
    )
    return p.parse_args(argv)


# -------------------------
# IO
# -------------------------
def load_any(path: str) -> pd.DataFrame:
    path_l = path.lower()
    if path_l.endswith(".parquet"):
        return pd.read_parquet(path)
    if path_l.endswith(".csv"):
        return pd.read_csv(path)
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.read_csv(path)


# -------------------------
# Helpers
# -------------------------
def infer_look_for_base_state(col: str) -> str | None:
    m = re.match(r"^LOOK_FOR_(balance|transition|trend)_", col, re.IGNORECASE)
    return m.group(1).upper() if m else None


def map_state_codes_to_names(s: pd.Series) -> pd.Series:
    """
    If s looks like coded states (0/1/2), map to BALANCE/TRANSITION/TREND.
    Otherwise return s as uppercase string.
    """
    raw = s.copy()
    num = pd.to_numeric(raw, errors="coerce")
    uniq = set(num.dropna().unique().tolist())
    coded = len(uniq) > 0 and uniq.issubset({0.0, 1.0, 2.0})
    if coded:
        mapping = {0.0: "BALANCE", 1.0: "TRANSITION", 2.0: "TREND"}
        return num.map(mapping).astype("string")
    return raw.astype("string").str.upper()


def extract_base_from_state_hat(state_hat: pd.Series) -> pd.Series:
    s = state_hat.astype("string").str.upper()
    extracted = s.str.extract(r"^(BALANCE|TRANSITION|TREND)", expand=False)
    fallback = s.str.split("_", n=1).str[0]
    return extracted.fillna(fallback).astype("string").str.upper()


def derive_base_state(df: pd.DataFrame) -> pd.Series:
    """
    Prefer explicit 'base_state' if present (supports coded 0/1/2 or text).
    Else derive from state_hat (supports coded 0/1/2 or text like BALANCE_LEAKING).
    """
    if "base_state" in df.columns:
        return map_state_codes_to_names(df["base_state"])

    if "state_hat" not in df.columns:
        return pd.Series([""] * len(df), dtype="string")

    mapped = map_state_codes_to_names(df["state_hat"])
    ratio = float(mapped.isin(BASE_STATES).mean())
    if ratio > 0.80:
        return mapped

    return extract_base_from_state_hat(df["state_hat"])


def shift_suspicion_score(a: pd.Series) -> dict:
    x = a.astype("string")
    return {
        "match_with_shift(+1)": float((x == x.shift(1)).mean()),
        "match_with_shift(-1)": float((x == x.shift(-1)).mean()),
    }


def is_active_series(v: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(v):
        return v.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(v):
        return v.fillna(0).astype(float) > 0
    s = v.astype("string").fillna("")
    return s.str.lower().isin(["1", "true", "t", "yes", "y"])


def extract_quality_prefix(q: pd.Series) -> pd.Series:
    """
    Extracts BALANCE / TRANSITION / TREND prefix from quality_label if present.
    Returns NaN if no prefix.
    """
    q = q.astype("string").str.upper()
    return q.str.extract(r"^(BALANCE|TRANSITION|TREND)_", expand=False)

def best_shift_alignment(base_state: pd.Series, q_prefix: pd.Series, max_lag: int = 2) -> dict:
    """
    Tests small shifts of base_state vs quality_prefix to see if mismatch drops.
    Returns best lag and mismatch rates.
    lag meaning: compare base_state.shift(lag) against q_prefix
      lag = +1 => using previous base_state for current quality (base shifted down)
      lag = -1 => using next base_state for current quality
    """
    has_prefix = q_prefix.notna()
    out = {"current_pct_bad": None, "best_lag": 0, "best_pct_bad": None, "grid": {}}

    def pct_bad(bs: pd.Series) -> float:
        bad = has_prefix & (q_prefix != bs)
        return float(bad.mean())

    out["current_pct_bad"] = pct_bad(base_state)

    best_lag = 0
    best_val = out["current_pct_bad"]

    for lag in range(-max_lag, max_lag + 1):
        bs_lag = base_state.shift(lag)
        val = pct_bad(bs_lag)
        out["grid"][lag] = val
        if val < best_val:
            best_val = val
            best_lag = lag

    out["best_lag"] = best_lag
    out["best_pct_bad"] = best_val
    return out


# -------------------------
# Core audit
# -------------------------
def audit(
    path: str,
    sort_by_time: bool = True,
    max_lookfor_bad_pct: float = 0.001,
    lookfor_must_be_zero_outside_state: bool = False
) -> int:
    df = load_any(path)

    if sort_by_time and ("time" in df.columns):
        df = df.sort_values("time").reset_index(drop=True)

    look_for_cols = [c for c in df.columns if c.startswith("LOOK_FOR_")]
    ctx_cols = [c for c in df.columns if c.startswith("ctx_")]

    if "state_hat" not in df.columns:
        print("FAIL: missing required column: state_hat")
        return 2

    base_state = derive_base_state(df)

    # -------------------------
    # CHECK 0: first row NaN (shift smell)
    # -------------------------
    first_row_nan = {}
    for c in ["state_hat", "margin", *ctx_cols]:
        if c in df.columns:
            first_row_nan[c] = bool(pd.isna(df.loc[0, c]))

    # -------------------------
    # CHECK 1: LOOK_FOR vs base_state
    # -------------------------
    look_for_mismatches = []
    total_active = 0
    total_bad = 0

    for c in look_for_cols:
        expected_state = infer_look_for_base_state(c)
        if expected_state is None:
            continue

        active = is_active_series(df[c])
        n_active = int(active.sum())
        if n_active == 0:
            continue

        total_active += n_active
        bad = active & (base_state != expected_state)
        n_bad = int(bad.sum())
        total_bad += n_bad

        look_for_mismatches.append((c, expected_state, n_active, n_bad, (n_bad / max(n_active, 1))))

    pct_bad_look_for = (total_bad / max(total_active, 1)) if total_active > 0 else 0.0

    # -------------------------
    # CHECK 2: state ↔ quality coherence
    # -------------------------
    q_raw_col = "quality_label" if "quality_label" in df.columns else None
    quality_report = {}
    pct_quality_bad = 0.0

    if q_raw_col is None:
        quality_report["FAIL_missing_quality_label"] = True
        pct_quality_bad = 1.0
    else:
        q_prefix = extract_quality_prefix(df[q_raw_col])
        has_prefix = q_prefix.notna()
        bad = has_prefix & (q_prefix != base_state)

        pct_quality_bad = float(bad.mean())
        quality_report["pct_bad"] = pct_quality_bad
        quality_report["rows_with_quality_prefix_pct"] = float(has_prefix.mean())

        if pct_quality_bad > 0:
            idx_bad = bad[bad].index[:5].tolist()
            quality_report["bad_examples"] = [
                {
                    "i": int(i),
                    "state_hat": str(df.loc[i, "state_hat"]),
                    "base_state": str(base_state.loc[i]),
                    "quality_label": str(df.loc[i, q_raw_col]),
                    "quality_prefix": str(q_prefix.loc[i]),
                }
                for i in idx_bad
            ]
            # CHECK 2B: does a small shift explain the mismatch?
            quality_report["shift_diagnosis"] = best_shift_alignment(base_state, q_prefix, max_lag=2)

    # -------------------------
    # CHECK 3: shift suspicion
    # -------------------------
    shift_report = {
        "state_hat": shift_suspicion_score(df["state_hat"]),
        "base_state": shift_suspicion_score(base_state),
    }
    for c in ctx_cols:
        shift_report[c] = shift_suspicion_score(df[c])

    # -------------------------
    # PRINT RESULTS
    # -------------------------
    print("=== Phase D Canonical Audit ===")
    print(f"path={path}")
    print(f"rows={len(df):,}")
    print(f"cols={len(df.columns):,}")
    print(f"look_for_cols={len(look_for_cols):,} ctx_cols={len(ctx_cols):,}")

    # Debug base_state distribution when any look_for is active
    if look_for_cols:
        any_active = np.zeros(len(df), dtype=bool)
        for c in look_for_cols:
            any_active |= is_active_series(df[c]).to_numpy()
        vc = base_state[any_active].value_counts(dropna=False).head(10)
        print("\n[DEBUG] base_state top when ANY LOOK_FOR active (top 10):")
        print(vc.to_string())

    print("\n[CHECK 0] first-row-NaN (sospecha shift/downshift):")
    print(first_row_nan)

    print("\n[CHECK 1] LOOK_FOR vs base_state:")
    print(f"active_total={total_active:,} bad_total={total_bad:,} pct_bad={pct_bad_look_for:.4%}")
    if look_for_mismatches:
        look_for_mismatches.sort(key=lambda x: x[4], reverse=True)
        print("worst_look_for (top 10): col | expected_base | active | bad | bad_pct")
        for col, exp, na, nb, bp in look_for_mismatches[:10]:
            print(f"- {col} | {exp} | {na} | {nb} | {bp:.2%}")

    print("\n[CHECK 2] state ↔ quality coherence:")
    print(quality_report)

    print("\n[CHECK 3] shift suspicion (match with self shifted):")
    keys = list(shift_report.keys())
    for k in keys[:10]:
        print(f"- {k}: {shift_report[k]}")
    if len(keys) > 10:
        print(f"... ({len(keys)-10} ctx cols más)")

    # -------------------------
    # VEREDICT
    # -------------------------
    fail_lookfor = False
    fail_quality = False
    fail_shift = False

    if lookfor_must_be_zero_outside_state:
        fail_lookfor = total_bad > 0
    else:
        fail_lookfor = pct_bad_look_for > max_lookfor_bad_pct

    fail_quality = pct_quality_bad > 0.0 or (q_raw_col is None)

    sh_state_hat = shift_report["state_hat"]["match_with_shift(+1)"]
    sh_base = shift_report["base_state"]["match_with_shift(+1)"]
    fail_shift = bool(first_row_nan.get("state_hat", False) and max(sh_state_hat, sh_base) > 0.50)

    FAIL = fail_lookfor or fail_quality or fail_shift

    print("\n=== VEREDICT ===")
    print("FAIL" if FAIL else "PASS")
    print(f"components: lookfor={'FAIL' if fail_lookfor else 'PASS'} | quality={'FAIL' if fail_quality else 'PASS'} | shift={'FAIL' if fail_shift else 'PASS'}")

    return 1 if FAIL else 0


def main_entry(argv=None) -> int:
    args = parse_args(argv)
    path = args.path_opt or args.path

    if not path:
        print("FAIL: no input path provided. Provide positional <path> or --path.")
        return 2
    if not os.path.exists(path):
        print(f"FAIL: file not found: {path}")
        return 2

    sort_by_time = not args.no_sort_by_time
    return audit(
        path=path,
        sort_by_time=sort_by_time,
        max_lookfor_bad_pct=args.max_lookfor_bad_pct,
        lookfor_must_be_zero_outside_state=args.lookfor_must_be_zero_outside_state,
    )


if __name__ == "__main__":
    code = main_entry(sys.argv[1:])
    # solo falla duro en errores reales
    if code == 2:
        raise SystemExit(code)
    print(f"(exit_code={code})")
