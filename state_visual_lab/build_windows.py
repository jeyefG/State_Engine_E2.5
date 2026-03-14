# state_visual_lab/build_windows.py
from pathlib import Path
import numpy as np
import pandas as pd

from config import (
    PARQUET_PATH,
    OUT_DIR,
    TIME_COL,
    STATE_COL,
    QL_COL,
    VWAP_COL,
    L,
    R,
)


def normalize_by_anchor(arr: np.ndarray, anchor: float) -> np.ndarray:
    if pd.isna(anchor) or anchor == 0:
        return np.full_like(arr, np.nan, dtype=float)
    return (arr / anchor) - 1.0


def main():
    out_dir = Path(OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(PARQUET_PATH).copy()
    df = df.sort_values(TIME_COL).reset_index(drop=True)

    rows = []

    for i in range(L, len(df) - R):
        state = df.at[i, STATE_COL]
        if pd.isna(state):
            continue

        w = df.iloc[i - L : i + R + 1].copy()
        if len(w) != (L + R + 1):
            continue

        req_cols = ["open", "high", "low", "close", VWAP_COL]
        if w[req_cols].isna().any().any():
            continue

        anchor_close = float(df.at[i, "close"])

        open_n = normalize_by_anchor(w["open"].to_numpy(dtype=float), anchor_close)
        high_n = normalize_by_anchor(w["high"].to_numpy(dtype=float), anchor_close)
        low_n  = normalize_by_anchor(w["low"].to_numpy(dtype=float), anchor_close)
        close_n = normalize_by_anchor(w["close"].to_numpy(dtype=float), anchor_close)
        vwap_n = normalize_by_anchor(w[VWAP_COL].to_numpy(dtype=float), anchor_close)

        row = {
            "anchor_idx": i,
            "anchor_time": df.at[i, TIME_COL],
            "state_hat": state,
        }

        if QL_COL in df.columns:
            row["quality_label"] = df.at[i, QL_COL]

        for j in range(L + R + 1):
            row[f"open_{j}"] = float(open_n[j])
            row[f"high_{j}"] = float(high_n[j])
            row[f"low_{j}"] = float(low_n[j])
            row[f"close_{j}"] = float(close_n[j])
            row[f"vwap_{j}"] = float(vwap_n[j])

        rows.append(row)

    windows = pd.DataFrame(rows)

    out_path = out_dir / "windows_by_state_ohlc_vwap.parquet"
    windows.to_parquet(out_path, index=False)

    print("windows_rows:", len(windows))
    print("state_counts:")
    print(windows["state_hat"].value_counts(dropna=False).sort_index())
    print("anchor close should be ~0:")
    print(windows["close_24"].describe())
    print("out_path:", out_path)


if __name__ == "__main__":
    main()