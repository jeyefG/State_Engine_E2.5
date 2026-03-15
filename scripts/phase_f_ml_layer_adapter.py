from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


ALLOW_LABELS_DEFAULT = ("LONG", "SHORT")


def _to_naive_datetime(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def _resolve_time_col(df: pd.DataFrame, preferred: str | None = None) -> str:
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(["timestamp", "time", "ts", "datetime"])
    for c in candidates:
        if c in df.columns:
            return c
    raise RuntimeError("No timestamp column found. Expected one of timestamp/time/ts/datetime.")


def _normalize_pred_label(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.strip()


def _build_base_from_ml(
    ml_df: pd.DataFrame,
    symbol: str,
    time_col: str,
    pred_label_col: str,
    allow_labels: Iterable[str],
) -> pd.DataFrame:
    out = ml_df.copy()

    if "symbol" not in out.columns:
        out["symbol"] = symbol

    out = out[out["symbol"].astype(str) == str(symbol)].copy()
    out["ts"] = _to_naive_datetime(out[time_col])
    out = out.dropna(subset=["ts"]).copy()

    if pred_label_col not in out.columns:
        raise RuntimeError(f"Missing required column in ML predictions: {pred_label_col}")

    allow_set = {x.upper().strip() for x in allow_labels}
    out["pred_label_norm"] = _normalize_pred_label(out[pred_label_col])

    out["decision"] = out["pred_label_norm"].map(lambda x: "ALLOW" if x in allow_set else "BLOCK")
    out["side_intent"] = out["pred_label_norm"].where(out["pred_label_norm"].isin(allow_set), "NONE")

    # Single canonical setup family for this ML layer.
    out["setup_family"] = out["decision"].map(lambda x: "ml_phase_e5_v1" if x == "ALLOW" else "blocked_ml")

    return out


def _optional_merge_phase_f_context(base: pd.DataFrame, decisions_path: Path) -> pd.DataFrame:
    dec = pd.read_csv(decisions_path)
    d_time = _resolve_time_col(dec, preferred="ts")
    dec["ts"] = _to_naive_datetime(dec[d_time])

    keep = ["symbol", "ts"]
    for c in ["context_key", "baseline_id", "meta_baseline_id", "lf", "ql", "state"]:
        if c in dec.columns:
            keep.append(c)

    dec_keep = dec[keep].drop_duplicates(subset=["symbol", "ts"], keep="last")
    out = base.merge(dec_keep, on=["symbol", "ts"], how="left")

    if "meta_baseline_id" not in out.columns and "baseline_id" in out.columns:
        out["meta_baseline_id"] = out["baseline_id"]
    elif "meta_baseline_id" in out.columns and "baseline_id" in out.columns:
        out["meta_baseline_id"] = out["meta_baseline_id"].fillna(out["baseline_id"])

    return out


def _optional_merge_enriched(base: pd.DataFrame, enriched_path: Path, symbol: str) -> pd.DataFrame:
    enr = pd.read_parquet(enriched_path)
    if "symbol" not in enr.columns:
        enr["symbol"] = symbol
    enr = enr[enr["symbol"].astype(str) == str(symbol)].copy()

    tcol = _resolve_time_col(enr, preferred="time")
    enr["ts"] = _to_naive_datetime(enr[tcol])

    keep = ["symbol", "ts"]
    for c in [
        "open", "high", "low", "close",
        "ctx_vwap", "ctx_vwap_sigma", "ctx_vwap_hi", "ctx_vwap_lo",
        "ctx_session_bucket",
    ]:
        if c in enr.columns:
            keep.append(c)

    enr_keep = enr[keep].drop_duplicates(subset=["symbol", "ts"], keep="last")
    return base.merge(enr_keep, on=["symbol", "ts"], how="left")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Convert train_phase_e5_v1_model predictions into Phase-F/backtest compatible decisions_with_side.csv"
    )
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--ml_predictions", required=True, help="Parquet/CSV from train_phase_e5_v1_model.py")
    ap.add_argument("--out_csv", required=True)

    ap.add_argument("--time_col", default="timestamp")
    ap.add_argument("--pred_label_col", default="pred_label")
    ap.add_argument("--allow_labels", default="LONG,SHORT")

    ap.add_argument(
        "--phase_f_decisions_csv",
        default=None,
        help="Optional run_phase_f decisions.csv to merge context_key/meta_baseline_id columns.",
    )
    ap.add_argument(
        "--enriched_parquet",
        default=None,
        help="Optional enriched parquet to append OHLC/VWAP columns.",
    )
    return ap.parse_args()


def _load_ml_predictions(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> int:
    args = parse_args()

    ml_path = Path(args.ml_predictions)
    out_path = Path(args.out_csv)

    ml = _load_ml_predictions(ml_path)
    time_col = _resolve_time_col(ml, preferred=args.time_col)
    allow_labels = [x.strip() for x in str(args.allow_labels).split(",") if x.strip()]

    out = _build_base_from_ml(
        ml_df=ml,
        symbol=args.symbol,
        time_col=time_col,
        pred_label_col=args.pred_label_col,
        allow_labels=allow_labels,
    )

    if args.phase_f_decisions_csv:
        out = _optional_merge_phase_f_context(out, Path(args.phase_f_decisions_csv))

    if args.enriched_parquet:
        out = _optional_merge_enriched(out, Path(args.enriched_parquet), symbol=args.symbol)

    # Keep core contract first
    preferred = [
        "symbol", "ts", "decision", "setup_family", "side_intent",
        "context_key", "meta_baseline_id", "baseline_id", "state", "ql", "lf",
        "pred", "pred_label", "proba_NO_TRADE", "proba_LONG", "proba_SHORT",
        "open", "high", "low", "close",
        "ctx_vwap", "ctx_vwap_sigma", "ctx_vwap_hi", "ctx_vwap_lo", "ctx_session_bucket",
    ]
    cols = [c for c in preferred if c in out.columns] + [c for c in out.columns if c not in preferred]
    out = out[cols].sort_values(["symbol", "ts"]).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    allow_n = int((out["decision"] == "ALLOW").sum()) if "decision" in out.columns else 0
    print("OK - ML predictions adapted to decisions_with_side contract")
    print(f"- out_csv: {out_path}")
    print(f"- rows: {len(out)}")
    print(f"- allow_rows: {allow_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
