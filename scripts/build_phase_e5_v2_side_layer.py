from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_SCORE_COLS = {
    "e5_long_score",
    "e5_short_score",
    "e5_abstain_score",
    "e5_margin",
    "e5_confidence",
    "e5_recommended_side",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Build a bar-level Phase E.5 V2 side-layer artifact from enriched context + "
            "episode_start-level E.5 score predictions."
        )
    )
    ap.add_argument("--context-parquet", nargs="+", required=True, help="One or more enriched context parquet files.")
    ap.add_argument("--scores-parquet", nargs="+", required=True, help="One or more E.5 V2 scores parquet files (episode_start unit).")
    ap.add_argument("--out-path", required=True, help="Output path (.parquet or .csv).")
    ap.add_argument("--context-tf", default="H1", help="Context timeframe used by E.5 V2 episode builder.")
    ap.add_argument("--model-tag", default="phase_e5_v2", help="Model tag to store in e5_model_tag.")
    ap.add_argument("--side-threshold", type=float, default=0.55)
    ap.add_argument("--abstain-threshold", type=float, default=0.55)
    ap.add_argument("--margin-threshold", type=float, default=0.05)
    ap.add_argument("--symbol", default=None, help="Optional symbol filter.")
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
        elif "datetime" in out.columns:
            out = out.rename(columns={"datetime": desired})
        else:
            out = out.reset_index().rename(columns={out.index.name or "index": desired})
    out[desired] = pd.to_datetime(out[desired], errors="coerce")
    out = out[out[desired].notna()].copy()
    return out


def load_parquet_union(paths: list[str], symbol: str | None) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    for p in paths:
        df = pd.read_parquet(Path(p))
        df = normalize_time_col(df, "time")
        chunks.append(df)

    out = pd.concat(chunks, ignore_index=True)

    if "symbol" not in out.columns:
        out["symbol"] = str(symbol) if symbol else "UNKNOWN"

    if symbol is not None:
        out = out[out["symbol"].astype(str) == str(symbol)].copy()

    return out.sort_values(["symbol", "time"]).reset_index(drop=True)


def ql_col_name(df: pd.DataFrame) -> str | None:
    for c in ["quality_label_full", "quality_label"]:
        if c in df.columns:
            return c
    return None


def discover_lf_cols(df: pd.DataFrame) -> list[str]:
    return sorted([c for c in df.columns if c.startswith("LOOK_FOR_")])


def _safe_int(x: object) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def active_lf_signature(row: pd.Series, lf_cols: list[str]) -> str:
    active = [c for c in lf_cols if _safe_int(row.get(c, 0)) == 1]
    return "|".join(active) if active else "NONE"


def add_backbone_columns(df: pd.DataFrame, lf_cols: list[str], ql_col: str | None) -> pd.DataFrame:
    out = df.copy()
    out["quality_label"] = out[ql_col].astype(str) if ql_col else "NA"
    out["lf_signature"] = out.apply(lambda r: active_lf_signature(r, lf_cols), axis=1)
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

    out["e5_is_episode_start"] = gap_break | lf_break | st_break | ql_break
    out["e5_episode_id"] = out.groupby("symbol", dropna=False)["e5_is_episode_start"].cumsum().astype(int)
    return out


def validate_scores(scores: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_SCORE_COLS if c not in scores.columns]
    if missing:
        raise ValueError(f"Missing required score columns: {sorted(missing)}")


def build_side_layer(
    context: pd.DataFrame,
    scores: pd.DataFrame,
    context_tf: str,
    model_tag: str,
    side_threshold: float,
    abstain_threshold: float,
    margin_threshold: float,
) -> pd.DataFrame:
    lf_cols = discover_lf_cols(context)
    ql_col = ql_col_name(context)

    ctx = add_backbone_columns(context, lf_cols=lf_cols, ql_col=ql_col)
    ctx = mark_episode_starts(ctx, context_tf=context_tf)

    validate_scores(scores)
    score_keep = ["symbol", "time", *sorted(REQUIRED_SCORE_COLS)]
    available_keep = [c for c in score_keep if c in scores.columns]
    score_base = scores[available_keep].copy()
    score_base["e5_has_prediction"] = 1

    merged = ctx.merge(score_base, on=["symbol", "time"], how="left", validate="m:1")

    for col in REQUIRED_SCORE_COLS:
        if col not in merged.columns:
            merged[col] = np.nan
    merged["e5_has_prediction"] = merged["e5_has_prediction"].fillna(0).astype(int)

    carry_cols = [
        "e5_long_score",
        "e5_short_score",
        "e5_abstain_score",
        "e5_margin",
        "e5_confidence",
        "e5_recommended_side",
    ]
    merged[carry_cols] = merged.groupby(["symbol", "e5_episode_id"], dropna=False)[carry_cols].ffill()

    merged["e5_side"] = merged["e5_recommended_side"].fillna("ABSTAIN").astype(str)
    merged["e5_model_tag"] = str(model_tag)
    merged["e5_side_threshold"] = float(side_threshold)
    merged["e5_abstain_threshold"] = float(abstain_threshold)
    merged["e5_margin_threshold"] = float(margin_threshold)

    out_cols = [
        "symbol",
        "time",
        "e5_episode_id",
        "e5_is_episode_start",
        "e5_has_prediction",
        "e5_side",
        "e5_long_score",
        "e5_short_score",
        "e5_abstain_score",
        "e5_margin",
        "e5_confidence",
        "e5_model_tag",
        "e5_side_threshold",
        "e5_abstain_threshold",
        "e5_margin_threshold",
    ]
    out = merged[out_cols].sort_values(["symbol", "time"]).reset_index(drop=True)
    return out


def write_output(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".csv":
        df.to_csv(out_path, index=False)
    else:
        df.to_parquet(out_path, index=False)


def main() -> int:
    args = parse_args()

    context = load_parquet_union(args.context_parquet, symbol=args.symbol)
    scores = load_parquet_union(args.scores_parquet, symbol=args.symbol)

    side_layer = build_side_layer(
        context=context,
        scores=scores,
        context_tf=args.context_tf,
        model_tag=args.model_tag,
        side_threshold=args.side_threshold,
        abstain_threshold=args.abstain_threshold,
        margin_threshold=args.margin_threshold,
    )

    out_path = Path(args.out_path)
    write_output(side_layer, out_path)

    coverage = float((side_layer["e5_long_score"].notna() | side_layer["e5_short_score"].notna() | side_layer["e5_abstain_score"].notna()).mean()) if len(side_layer) else 0.0
    side_counts = side_layer["e5_side"].value_counts(dropna=False).to_dict() if len(side_layer) else {}

    print("OK - E.5 V2 side layer built (bar-level, no ALLOW/BLOCK)")
    print(f"- input_context_rows: {len(context)}")
    print(f"- input_scores_rows: {len(scores)}")
    print(f"- output_rows: {len(side_layer)}")
    print(f"- prediction_coverage: {coverage:.4f}")
    print(f"- e5_side_counts: {side_counts}")
    print(f"- out_path: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
