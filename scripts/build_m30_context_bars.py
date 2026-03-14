import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def ensure_dt(s):
    if np.issubdtype(s.dtype, np.datetime64):
        return s
    return pd.to_datetime(s, errors="coerce")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", required=True)
    ap.add_argument("--universe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tolerance", default="0min")  # si timestamps calzan exacto, deja 0min
    args = ap.parse_args()

    # --- load prices ---
    prices = pd.read_parquet(args.prices).copy()
    
    # detect time col in prices
    price_time_col = None
    for c in ["time", "bar_ts", "ts", "timestamp", "datetime"]:
        if c in prices.columns:
            price_time_col = c
            break
    if price_time_col is None:
        raise ValueError(f"prices missing time column. Found: {list(prices.columns)}")
    
    prices[price_time_col] = pd.to_datetime(prices[price_time_col], errors="coerce")
    prices = prices.dropna(subset=[price_time_col]).sort_values(price_time_col).reset_index(drop=True)
    prices = prices.rename(columns={price_time_col: "time"})
    
    # --- load universe ---
    uni = pd.read_csv(args.universe).copy()
    
    # try to find timestamp col in universe
    uni_time_col = None
    for c in ["time", "bar_ts", "ts", "timestamp", "datetime"]:
        if c in uni.columns:
            uni_time_col = c
            break
    
    if uni_time_col is not None:
        uni[uni_time_col] = pd.to_datetime(uni[uni_time_col], errors="coerce")
        uni = uni.dropna(subset=[uni_time_col]).sort_values(uni_time_col).reset_index(drop=True)
        uni = uni.rename(columns={uni_time_col: "time"})
    else:
        # --- AUTO-RECOVER (robust): universe has no timestamp column ---
        # Try to reconstruct uni["time"] by matching OHLCV rows against prices.
    
        # columns we can use to match (must exist in BOTH)
        candidate_cols = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
        join_cols = [c for c in candidate_cols if (c in uni.columns and c in prices.columns)]
    
        # need at least OHLC to have a chance
        if not all(c in join_cols for c in ["open", "high", "low", "close"]):
            raise ValueError(
                "universe has no timestamp column and cannot match by OHLC (missing one of open/high/low/close). "
                f"universe cols={list(uni.columns)} prices cols={list(prices.columns)}"
            )
    
        # add row ids to keep one-to-one mapping as best effort
        uni = uni.reset_index(drop=True).copy()
        uni["_uni_row_id"] = np.arange(len(uni), dtype=np.int64)
    
        prices2 = prices[["time"] + join_cols].copy()
        prices2 = prices2.reset_index(drop=True)
        prices2["_price_row_id"] = np.arange(len(prices2), dtype=np.int64)
    
        # IMPORTANT: to avoid float representation mismatches, round OHLC a bit
        for c in ["open", "high", "low", "close"]:
            if c in join_cols:
                uni[c] = pd.to_numeric(uni[c], errors="coerce").round(5)
                prices2[c] = pd.to_numeric(prices2[c], errors="coerce").round(5)
    
        # match
        m = uni.merge(
            prices2,
            on=join_cols,
            how="left",
            suffixes=("", "_p"),
        )
    
        # How many got matched at least once?
        n_matched = int(m["time"].notna().sum())
        if n_matched == 0:
            raise ValueError(
                "Failed to reconstruct time: zero OHLCV matches between universe and prices. "
                "This usually means universe was generated from a different price source/timezone/precision."
            )
    
        # There may be duplicates (same OHLCV repeated) -> pick the earliest price time per uni row
        m = m.sort_values(["_uni_row_id", "time", "_price_row_id"])
        picked = m.groupby("_uni_row_id", as_index=False).first()[["_uni_row_id", "time"]]
    
        # attach back
        uni = uni.merge(picked, on="_uni_row_id", how="left")
    
        n_missing = int(uni["time"].isna().sum())
        if n_missing > 0:
            # If only a few are missing, drop them (they can't be aligned anyway)
            # Print a helpful warning message.
            print(f"WARN: could not reconstruct time for {n_missing}/{len(uni)} universe rows; dropping them.")
            uni = uni.dropna(subset=["time"]).reset_index(drop=True)
    
        # cleanup
        uni = uni.drop(columns=["_uni_row_id"])
    
    # normalize context column names (optional but recommended)
    if "state_hat" not in uni.columns and "state_hat_H2" in uni.columns:
        uni = uni.rename(columns={"state_hat_H2": "state_hat"})
    if "margin" not in uni.columns and "margin_H2" in uni.columns:
        uni = uni.rename(columns={"margin_H2": "margin"})
    
    # detectar columna de timestamp automáticamente
    ts_col = None
    for c in ["time", "ts", "bar_ts", "timestamp", "datetime"]:
        if c in uni.columns:
            ts_col = c
            break
    
    
    uni[ts_col] = ensure_dt(uni[ts_col])
    uni = uni.dropna(subset=[ts_col]).sort_values(ts_col).reset_index(drop=True)
    
    # renombramos a 'time' para merge consistente
    uni = uni.rename(columns={ts_col: "time"})

    # columnas mínimas de contexto que queremos inyectar
    ctx_cols = [c for c in ["state_hat", "quality_label", "quality_label_full", "setup_family"] if c in uni.columns]

    # si setup_family no existe en universe, lo podemos crear desde flags LOOK_FOR_* (opcional)
    if "setup_family" not in uni.columns:
        # intenta derivarlo desde cualquier columna LOOK_FOR_ activa
        lf_cols = [c for c in uni.columns if c.startswith("LOOK_FOR_")]
        if lf_cols:
            def synth_family(row):
                actives = [c for c in lf_cols if row.get(c, 0) == 1]
                return actives[0] if actives else "NONE"
            uni["setup_family"] = uni.apply(synth_family, axis=1)
            ctx_cols.append("setup_family")

    tol = pd.Timedelta(args.tolerance)

    # merge_asof para tolerancia si hay descalce
    out = pd.merge_asof(
        prices,
        uni[["time"] + ctx_cols],
        on="time",
        direction="nearest",
        tolerance=tol if tol > pd.Timedelta(0) else None,
    )

    # renombra time->bar_ts para que tu auditoría lo entienda fácil
    out = out.rename(columns={"time": "bar_ts"})

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)
    print("Wrote:", args.out)
    print("Rows:", len(out), "missing_state_hat:", out["state_hat"].isna().mean() if "state_hat" in out.columns else "NA")

if __name__ == "__main__":
    main()