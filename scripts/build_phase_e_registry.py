# scripts/build_phase_e_registry.py
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from state_engine.phase_f.registry import build_context_key


REQUIRED_OUT_COLS = ["context_key", "baseline_id", "uplift_pp", "n_bars"]


def _read_csv(path: Path) -> pd.DataFrame:
    # assume standard comma; if your exports are ';', change here.
    return pd.read_csv(path)


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    colmap = {}

    if "look_for_rule" in df.columns:
        colmap["look_for_rule"] = "look_for_rule"
    elif "look_for" in df.columns:
        colmap["look_for"] = "look_for_rule"

    if "base_state" in df.columns:
        colmap["base_state"] = "base_state"
    elif "state" in df.columns:
        colmap["state"] = "base_state"

    if "quality_label_full" in df.columns:
        colmap["quality_label_full"] = "quality_label_full"
    elif "ql" in df.columns:
        colmap["ql"] = "quality_label_full"

    if "uplift_pp" in df.columns:
        colmap["uplift_pp"] = "uplift_pp"
    elif "uplift_bp" in df.columns:
        colmap["uplift_bp"] = "uplift_bp"
    elif "uplift_pct" in df.columns:
        colmap["uplift_pct"] = "uplift_pct"
    elif "uplift" in df.columns:
        colmap["uplift"] = "uplift_pp"

    if "n_bars" in df.columns:
        colmap["n_bars"] = "n_bars"
    elif "count" in df.columns:
        colmap["count"] = "n_bars"

    if "wf_score" in df.columns:
        colmap["wf_score"] = "wf_score"
    elif "wf" in df.columns:
        colmap["wf"] = "wf_score"

    df = df.rename(columns=colmap).copy()
    return df


def _ensure_uplift_pp(df: pd.DataFrame) -> pd.DataFrame:
    if "uplift_pp" in df.columns:
        return df
    if "uplift_bp" in df.columns:
        df["uplift_pp"] = df["uplift_bp"].astype(float) / 100.0
        return df
    if "uplift_pct" in df.columns:
        df["uplift_pp"] = df["uplift_pct"].astype(float)
        return df
    raise KeyError("No uplift column found (expected uplift_pp or uplift_bp or uplift_pct or uplift)")


def _make_baseline_id(df: pd.DataFrame, mode: str) -> pd.Series:
    if mode == "state":
        return "BASE:STATE:" + df["base_state"].astype(str)
    if mode == "state_ql":
        return "BASE:STATE_QL:" + df["base_state"].astype(str) + "|QL:" + df["quality_label_full"].astype(str)
    raise ValueError(f"Unknown baseline_mode: {mode}")


def _make_context_key(df: pd.DataFrame, include_ql: bool) -> pd.Series:
    """
    IMPORTANT: call build_context_key with POSITIONAL args to avoid
    parameter-name mismatches across versions.
    Expected semantic args:
      (look_for_rule, base_state, quality_label_full_or_None)
    """
    if include_ql:
        return df.apply(
            lambda r: build_context_key(
                str(r["look_for_rule"]),
                str(r["base_state"]),
                str(r["quality_label_full"]),
            ),
            axis=1,
        )
    else:
        return df.apply(
            lambda r: build_context_key(
                str(r["look_for_rule"]),
                str(r["base_state"]),
                None,
            ),
            axis=1,
        )


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["n_bars"] = df["n_bars"].astype(float)

    def wavg(x: pd.Series, w: pd.Series) -> float:
        wsum = w.sum()
        if wsum <= 0:
            return float(x.mean())
        return float((x * w).sum() / wsum)

    has_wf = "wf_score" in df.columns

    grouped = []
    for (ck, bid), g in df.groupby(["context_key", "baseline_id"], dropna=False):
        row = {
            "context_key": ck,
            "baseline_id": bid,
            "n_bars": float(g["n_bars"].sum()),
            "uplift_pp": wavg(g["uplift_pp"].astype(float), g["n_bars"]),
        }
        if has_wf:
            row["wf_score"] = wavg(g["wf_score"].astype(float), g["n_bars"])
        grouped.append(row)

    out = pd.DataFrame(grouped)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="Symbol including suffix, e.g., XAUUSD.mg")
    ap.add_argument("--state_csv", required=True, help="Phase E *_lookfor_state_filtered.csv")
    ap.add_argument("--state_ql_csv", required=True, help="Phase E *_lookfor_state_ql_filtered.csv")
    ap.add_argument("--out", required=True, help="Output parquet path, e.g., outputs/phase_e_registry/XAUUSD.mg.parquet")
    args = ap.parse_args()

    state_path = Path(args.state_csv)
    state_ql_path = Path(args.state_ql_csv)
    out_path = Path(args.out)

    if not state_path.exists():
        raise SystemExit(f"Missing input: {state_path}")
    if not state_ql_path.exists():
        raise SystemExit(f"Missing input: {state_ql_path}")

    df_state = _ensure_uplift_pp(_normalize_cols(_read_csv(state_path)))
    df_state_ql = _ensure_uplift_pp(_normalize_cols(_read_csv(state_ql_path)))

    for name, df, needs_ql in [
        ("state", df_state, False),
        ("state_ql", df_state_ql, True),
    ]:
        required = ["look_for_rule", "base_state", "uplift_pp", "n_bars"]
        if needs_ql:
            required.append("quality_label_full")
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SystemExit(f"Input {name} missing columns: {missing}")

    df_state["context_key"] = _make_context_key(df_state, include_ql=False)
    df_state["baseline_id"] = _make_baseline_id(df_state, mode="state")

    df_state_ql["context_key"] = _make_context_key(df_state_ql, include_ql=True)
    df_state_ql["baseline_id"] = _make_baseline_id(df_state_ql, mode="state_ql")

    keep_cols = ["context_key", "baseline_id", "uplift_pp", "n_bars"]
    if "wf_score" in df_state.columns:
        keep_cols.append("wf_score")
    df_state = df_state[[c for c in keep_cols if c in df_state.columns]].copy()

    keep_cols_ql = ["context_key", "baseline_id", "uplift_pp", "n_bars"]
    if "wf_score" in df_state_ql.columns:
        keep_cols_ql.append("wf_score")
    df_state_ql = df_state_ql[[c for c in keep_cols_ql if c in df_state_ql.columns]].copy()

    df_all = pd.concat([df_state, df_state_ql], ignore_index=True)
    df_out = _aggregate(df_all)

    missing_out = [c for c in REQUIRED_OUT_COLS if c not in df_out.columns]
    if missing_out:
        raise SystemExit(f"Output missing required columns: {missing_out}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_parquet(out_path, index=False)

    print("OK - Phase E registry built")
    print(f"- symbol: {args.symbol}")
    print(f"- out:    {out_path}")
    print(f"- rows:   {len(df_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
