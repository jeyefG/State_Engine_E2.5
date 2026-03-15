from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


TARGET_COLS = ["long_target", "short_target", "abstain_target"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train Phase E.5 V2 contextual resolver (scores, not trade decisions).")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--split-col", default="split")
    ap.add_argument("--time-col", default="timestamp")
    ap.add_argument("--drop-cols", default="timestamp,symbol,split,target_reason,target_ready")
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--learning-rate", type=float, default=0.05)
    ap.add_argument("--n-estimators", type=int, default=350)
    ap.add_argument("--min-samples-leaf", type=int, default=40)
    ap.add_argument("--side-threshold", type=float, default=0.55)
    ap.add_argument("--abstain-threshold", type=float, default=0.55)
    ap.add_argument("--margin-threshold", type=float, default=0.05)
    ap.add_argument("--random-state", type=int, default=42)
    return ap.parse_args()


def load_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def make_ohe() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def infer_feature_columns(df: pd.DataFrame, split_col: str, drop_cols: Iterable[str]) -> list[str]:
    banned = set(drop_cols) | set(TARGET_COLS) | {split_col}
    banned |= {
        "up_excursion",
        "down_excursion",
        "local_scale",
        "episode_id",
        "episode_bar_index",
    }
    return [c for c in df.columns if c not in banned]


def build_pipeline(X: pd.DataFrame, args: argparse.Namespace) -> Pipeline:
    cat_cols = [c for c in X.columns if str(X[c].dtype) in {"object", "category", "bool"}]
    num_cols = [c for c in X.columns if c not in cat_cols]

    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num_cols),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("ohe", make_ohe())]), cat_cols),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    base = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=args.learning_rate,
        max_depth=args.max_depth,
        max_iter=args.n_estimators,
        min_samples_leaf=args.min_samples_leaf,
        random_state=args.random_state,
    )

    model = MultiOutputRegressor(base)
    return Pipeline([("pre", pre), ("model", model)])


def _clip01(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, 1.0)


def to_outputs(pred: np.ndarray, side_threshold: float, abstain_threshold: float, margin_threshold: float) -> pd.DataFrame:
    long_s = _clip01(pred[:, 0])
    short_s = _clip01(pred[:, 1])
    abstain_s = _clip01(pred[:, 2])

    margin = long_s - short_s
    confidence = np.maximum(long_s, short_s)

    recommended = np.where(
        (abstain_s >= abstain_threshold) | (confidence < side_threshold) | (np.abs(margin) < margin_threshold),
        "ABSTAIN",
        np.where(long_s >= short_s, "LONG", "SHORT"),
    )
    
    return pd.DataFrame(
        {
            "e5_long_score": long_s,
            "e5_short_score": short_s,
            "e5_abstain_score": abstain_s,
            "e5_margin": margin,
            "e5_confidence": confidence,
            "e5_recommended_side": recommended,
        }
    )


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    out: dict[str, float] = {}
    for i, c in enumerate(TARGET_COLS):
        out[f"mae_{c}"] = float(mean_absolute_error(y_true[:, i], y_pred[:, i]))
        out[f"rmse_{c}"] = float(np.sqrt(mean_squared_error(y_true[:, i], y_pred[:, i])))
    out["mae_mean"] = float(np.mean([out[f"mae_{c}"] for c in TARGET_COLS]))
    out["rmse_mean"] = float(np.mean([out[f"rmse_{c}"] for c in TARGET_COLS]))
    return out


def pseudo_true_side(df: pd.DataFrame, side_threshold: float, abstain_threshold: float) -> np.ndarray:
    long_s = df["long_target"].to_numpy(dtype=float)
    short_s = df["short_target"].to_numpy(dtype=float)
    abstain_s = df["abstain_target"].to_numpy(dtype=float)
    conf = np.maximum(long_s, short_s)
    return np.where(
        (abstain_s >= abstain_threshold) | (conf < side_threshold),
        "ABSTAIN",
        np.where(long_s >= short_s, "LONG", "SHORT"),
    )


def side_accuracy(pred_side: np.ndarray, true_side: np.ndarray) -> float:
    if len(pred_side) == 0:
        return np.nan
    return float((pred_side == true_side).mean())


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ds = load_dataset(Path(args.dataset))
    ds[args.time_col] = pd.to_datetime(ds[args.time_col], errors="coerce")
    ds = ds[ds[args.time_col].notna()].copy()

    for c in TARGET_COLS:
        if c not in ds.columns:
            raise ValueError(f"Missing required target column: {c}")

    drop_cols = [c.strip() for c in args.drop_cols.split(",") if c.strip()]
    feature_cols = infer_feature_columns(ds, args.split_col, drop_cols)
    constant_cols = [c for c in feature_cols if ds[c].nunique(dropna=False) <= 1]
    feature_cols = [c for c in feature_cols if c not in constant_cols]

    if not feature_cols:
        raise ValueError("No features available after removing reserved/constant columns")

    train = ds[ds[args.split_col] == "train"].copy()
    val = ds[ds[args.split_col] == "val"].copy()
    test = ds[ds[args.split_col] == "test"].copy()
    if train.empty or val.empty or test.empty:
        raise ValueError("Dataset must include train/val/test rows")

    X_train = train[feature_cols]
    y_train = train[TARGET_COLS].to_numpy(dtype=float)
    X_val = val[feature_cols]
    y_val = val[TARGET_COLS].to_numpy(dtype=float)
    X_test = test[feature_cols]
    y_test = test[TARGET_COLS].to_numpy(dtype=float)

    pipe = build_pipeline(X_train, args)
    pipe.fit(X_train, y_train)

    pred_val = pipe.predict(X_val)
    pred_test = pipe.predict(X_test)

    val_scores = to_outputs(pred_val, args.side_threshold, args.abstain_threshold, args.margin_threshold)
    test_scores = to_outputs(pred_test, args.side_threshold, args.abstain_threshold, args.margin_threshold)

    true_side_val = pseudo_true_side(val, args.side_threshold, args.abstain_threshold)
    true_side_test = pseudo_true_side(test, args.side_threshold, args.abstain_threshold)

    summary = {
        "rows": int(len(ds)),
        "n_train": int(len(train)),
        "n_val": int(len(val)),
        "n_test": int(len(test)),
        "feature_count": len(feature_cols),
        "constant_cols_dropped": constant_cols,
        "metrics_val": {
            **metrics(y_val, pred_val),
            "derived_side_agreement": side_accuracy(val_scores["e5_recommended_side"].to_numpy(), true_side_val),
        },
        "metrics_test": {
            **metrics(y_test, pred_test),
            "derived_side_agreement": side_accuracy(test_scores["e5_recommended_side"].to_numpy(), true_side_test),
        },
    }

    stem = Path(args.dataset).stem
    model_path = out_dir / f"{stem}_phase_e5_v2_model.pkl"
    meta_path = out_dir / f"{stem}_phase_e5_v2_train_meta.json"
    val_path = out_dir / f"{stem}_phase_e5_v2_scores_val.parquet"
    test_path = out_dir / f"{stem}_phase_e5_v2_scores_test.parquet"

    with open(model_path, "wb") as f:
        pickle.dump(
            {
                "pipeline": pipe,
                "feature_cols": feature_cols,
                "target_cols": TARGET_COLS,
                "side_threshold": args.side_threshold,
                "abstain_threshold": args.abstain_threshold,
                "dataset": str(args.dataset),
            },
            f,
        )

    meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    keep = [c for c in [args.time_col, "symbol", args.split_col] if c in val.columns]
    out_val = val[keep].reset_index(drop=True).join(val_scores)
    out_test = test[keep].reset_index(drop=True).join(test_scores)

    out_val.to_parquet(val_path, index=False)
    out_test.to_parquet(test_path, index=False)

    print(json.dumps({
        "model": str(model_path),
        "meta": str(meta_path),
        "scores_val": str(val_path),
        "scores_test": str(test_path),
        **summary,
    }, indent=2))


if __name__ == "__main__":
    main()
