#train_phase_e5_v1_model.py
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

try:
    from lightgbm import LGBMClassifier
    HAS_LGBM = True
except Exception:
    from sklearn.ensemble import HistGradientBoostingClassifier
    HAS_LGBM = False


LABEL_MAP = {0: "NO_TRADE", 1: "LONG", 2: "SHORT"}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train Phase E.5 V1 multiclass model")
    ap.add_argument("--dataset", required=True, help="Parquet/CSV produced by build_phase_e5_v1_dataset.py")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--target-col", default="target")
    ap.add_argument("--split-col", default="split")
    ap.add_argument("--time-col", default="timestamp")
    ap.add_argument("--drop-cols", default="timestamp,symbol,target,target_label,split,target_reason")
    ap.add_argument("--random-state", type=int, default=42)
    ap.add_argument("--learning-rate", type=float, default=0.05)
    ap.add_argument("--n-estimators", type=int, default=300)
    ap.add_argument("--num-leaves", type=int, default=31)
    ap.add_argument("--min-child-samples", type=int, default=30)
    ap.add_argument(
        "--class-weight",
        default="balanced",
        help="LightGBM class_weight. Use 'balanced' or JSON dict string. Ignored for fallback model.",
    )
    return ap.parse_args()


RESERVED_COLS = {
    "timestamp",
    "symbol",
    "target",
    "target_label",
    "split",
    "target_reason",
    "bars_ahead_hit",
    # leakage del target
    "up_excursion",
    "down_excursion",
    "dominance_ratio_realized",
    "local_scale",
}


def load_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def infer_feature_columns(df: pd.DataFrame, target_col: str, split_col: str, drop_cols: Iterable[str]) -> list[str]:
    banned = set(drop_cols) | RESERVED_COLS | {target_col, split_col}
    return [c for c in df.columns if c not in banned]


def make_ohe() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_pipeline(X: pd.DataFrame, args: argparse.Namespace) -> Pipeline:
    cat_cols = [c for c in X.columns if str(X[c].dtype) in {"object", "category", "bool"}]
    num_cols = [c for c in X.columns if c not in cat_cols]

    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num_cols),
            (
                "cat",
                Pipeline([
                    ("imp", SimpleImputer(strategy="most_frequent")),
                    ("ohe", make_ohe()),
                ]),
                cat_cols,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    if HAS_LGBM:
        class_weight = args.class_weight
        if isinstance(class_weight, str) and class_weight.strip().startswith("{"):
            class_weight = json.loads(class_weight)
        model = LGBMClassifier(
            objective="multiclass",
            num_class=3,
            random_state=args.random_state,
            learning_rate=args.learning_rate,
            n_estimators=args.n_estimators,
            num_leaves=args.num_leaves,
            min_child_samples=args.min_child_samples,
            class_weight=class_weight,
            n_jobs=-1,
        )
    else:
        model = HistGradientBoostingClassifier(
            learning_rate=args.learning_rate,
            max_iter=max(200, args.n_estimators),
            random_state=args.random_state,
        )

    pipe = Pipeline([
        ("pre", pre),
        ("model", model),
    ])
    return pipe


def feature_importances(pipe: Pipeline) -> pd.DataFrame:
    pre = pipe.named_steps["pre"]
    model = pipe.named_steps["model"]
    feat_names = pre.get_feature_names_out()
    if hasattr(model, "feature_importances_"):
        imp = pd.DataFrame({"feature": feat_names, "importance": model.feature_importances_})
        return imp.sort_values("importance", ascending=False).reset_index(drop=True)
    return pd.DataFrame({"feature": feat_names, "importance": np.nan})


def print_block(title: str, payload: object) -> None:
    print(f"\n{title}")
    if isinstance(payload, pd.DataFrame):
        print(payload.to_string(index=False))
    else:
        print(payload)


def build_prediction_frame(df: pd.DataFrame, time_col: str, target_col: str, split_col: str, pred: np.ndarray, proba: np.ndarray | None) -> pd.DataFrame:
    cols = [c for c in [time_col, "symbol", target_col, "target_label", split_col] if c in df.columns]
    out = df[cols].copy()
    out["pred"] = pred
    out["pred_label"] = out["pred"].map(LABEL_MAP)
    if proba is not None:
        for i, name in LABEL_MAP.items():
            out[f"proba_{name}"] = proba[:, i]
    return out


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ds = load_dataset(Path(args.dataset))
    if args.time_col in ds.columns:
        ds[args.time_col] = pd.to_datetime(ds[args.time_col])

    drop_cols = [c.strip() for c in args.drop_cols.split(",") if c.strip()]
    feature_cols = infer_feature_columns(ds, args.target_col, args.split_col, drop_cols)

    # Remove constant columns to reduce useless noise
    constant_cols = [c for c in feature_cols if ds[c].nunique(dropna=False) <= 1]
    feature_cols = [c for c in feature_cols if c not in constant_cols]
    if not feature_cols:
        raise ValueError("No usable feature columns after dropping reserved and constant columns")

    train = ds[ds[args.split_col] == "train"].copy()
    val = ds[ds[args.split_col] == "val"].copy()
    test = ds[ds[args.split_col] == "test"].copy()
    if train.empty or val.empty or test.empty:
        raise ValueError("Expected non-empty train/val/test splits")

    X_train = train[feature_cols].copy()
    y_train = train[args.target_col].astype(int)
    X_val = val[feature_cols].copy()
    y_val = val[args.target_col].astype(int)
    X_test = test[feature_cols].copy()
    y_test = test[args.target_col].astype(int)

    expected_classes = {0, 1, 2}
    train_classes = set(y_train.unique())
    if train_classes != expected_classes:
        raise ValueError(f"Train split must contain classes {expected_classes}, got {train_classes}")

    pipe = build_pipeline(X_train, args)
    pipe.fit(X_train, y_train)

    val_pred = pipe.predict(X_val)
    test_pred = pipe.predict(X_test)

    val_proba = pipe.predict_proba(X_val) if hasattr(pipe, "predict_proba") else None
    test_proba = pipe.predict_proba(X_test) if hasattr(pipe, "predict_proba") else None

    labels = [0, 1, 2]
    target_names = [LABEL_MAP[i] for i in labels]

    val_cm = confusion_matrix(y_val, val_pred, labels=labels)
    test_cm = confusion_matrix(y_test, test_pred, labels=labels)

    # Naive baseline: always NO_TRADE
    naive_val_pred = np.zeros(len(y_val), dtype=int)
    naive_test_pred = np.zeros(len(y_test), dtype=int)

    summary = {
        "rows": int(len(ds)),
        "train": int(len(train)),
        "val": int(len(val)),
        "test": int(len(test)),
        "target_distribution_train": train[args.target_col].map(LABEL_MAP).value_counts().to_dict(),
        "feature_count": len(feature_cols),
        "constant_cols_dropped": constant_cols,
        "model": "LightGBM" if HAS_LGBM else "HistGradientBoosting(fallback)",
        "val_accuracy": float(accuracy_score(y_val, val_pred)),
        "test_accuracy": float(accuracy_score(y_test, test_pred)),
        "val_macro_f1": float(f1_score(y_val, val_pred, average="macro", zero_division=0)),
        "test_macro_f1": float(f1_score(y_test, test_pred, average="macro", zero_division=0)),
        "naive_val_accuracy": float(accuracy_score(y_val, naive_val_pred)),
        "naive_test_accuracy": float(accuracy_score(y_test, naive_test_pred)),
        "naive_val_macro_f1": float(f1_score(y_val, naive_val_pred, average="macro", zero_division=0)),
        "naive_test_macro_f1": float(f1_score(y_test, naive_test_pred, average="macro", zero_division=0)),
    }

    print_block("DATASET", summary)
    print_block("VAL_REPORT", classification_report(y_val, val_pred, labels=labels, target_names=target_names, digits=4, zero_division=0))
    print_block("TEST_REPORT", classification_report(y_test, test_pred, labels=labels, target_names=target_names, digits=4, zero_division=0))
    print_block("VAL_CONFUSION", pd.DataFrame(val_cm, index=[f"true_{x}" for x in target_names], columns=[f"pred_{x}" for x in target_names]))
    print_block("TEST_CONFUSION", pd.DataFrame(test_cm, index=[f"true_{x}" for x in target_names], columns=[f"pred_{x}" for x in target_names]))

    importances = feature_importances(pipe)
    print_block("TOP_FEATURES", importances.head(30))

    stem = Path(args.dataset).stem
    model_path = out_dir / f"{stem}_phase_e5_v1_model.pkl"
    feat_path = out_dir / f"{stem}_feature_importances.csv"
    pred_val_path = out_dir / f"{stem}_predictions_val.parquet"
    pred_test_path = out_dir / f"{stem}_predictions_test.parquet"
    meta_path = out_dir / f"{stem}_train_meta.json"

    with open(model_path, "wb") as f:
        pickle.dump({
            "pipeline": pipe,
            "feature_cols": feature_cols,
            "label_map": LABEL_MAP,
            "dataset": str(args.dataset),
            "constant_cols_dropped": constant_cols,
        }, f)

    importances.to_csv(feat_path, index=False)

    pred_val = build_prediction_frame(val, args.time_col, args.target_col, args.split_col, val_pred, val_proba)
    pred_test = build_prediction_frame(test, args.time_col, args.target_col, args.split_col, test_pred, test_proba)
    pred_val.to_parquet(pred_val_path, index=False)
    pred_test.to_parquet(pred_test_path, index=False)

    meta = {
        "model": "LightGBM" if HAS_LGBM else "HistGradientBoosting(fallback)",
        "dataset": str(args.dataset),
        "feature_cols": feature_cols,
        "constant_cols_dropped": constant_cols,
        "drop_cols": drop_cols,
        "target_col": args.target_col,
        "split_col": args.split_col,
        "label_map": LABEL_MAP,
        "summary": summary,
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    print_block("ARTIFACTS", {
        "model": str(model_path),
        "feature_importances": str(feat_path),
        "predictions_val": str(pred_val_path),
        "predictions_test": str(pred_test_path),
        "meta": str(meta_path),
    })


if __name__ == "__main__":
    main()