#scripts/build_phase_f_enriched_vwap_bands.py
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import numpy as np

# Reusar EXACTAMENTE la lógica de Phase D/E (sí, son helpers "privados", pero garantizan igualdad)
from state_engine.context_features import (
    _resolve_vwap_day_anchor,
    _compute_standard_vwap,
)

def _ensure_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    df = df.copy()
    df[col] = pd.to_datetime(df[col], utc=False)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--in_parquet", required=True, help="Phase F enriched with OHLC parquet")
    ap.add_argument("--out_parquet", required=True)
    ap.add_argument("--vwap_window", type=int, default=50, help="MUST match ContextFeatureConfig.vwap_window default (Phase D/E)")
    ap.add_argument("--band_window", type=int, default=50, help="Rolling window for sigma (kept equal to vwap_window by default)")
    ap.add_argument("--sigma_k", type=float, default=2.0)
    args = ap.parse_args()

    p_in = Path(args.in_parquet)
    df = pd.read_parquet(p_in)

    required = {"symbol","time","high","low","close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in input parquet: {sorted(missing)}")

    df = _ensure_datetime(df, "time")
    df = df.sort_values(["symbol","time"]).reset_index(drop=True)

    # Filtra símbolo (por seguridad)
    df_sym = df[df["symbol"] == args.symbol].copy()
    if df_sym.empty:
        raise ValueError(f"No rows for symbol={args.symbol} in {p_in}")

    # Index para reusar funciones
    df_sym = df_sym.set_index("time")

    # Anchor EXACTO que usa Phase D/E (para XAUUSD => ny_rollover_17)
    anchor = _resolve_vwap_day_anchor(args.symbol, anchor=None)  # None => resolver default por símbolo
    # compute_standard_vwap espera ohlcv con index datetime + cols high/low/close + vol cols opcionales
    vwap = _compute_standard_vwap(
        df_sym,
        day_anchor=anchor,
        vwap_window=args.vwap_window,
    )
    if vwap is None:
        raise ValueError("VWAP compute returned None (unexpected).")

    df_sym["ctx_vwap"] = pd.to_numeric(vwap, errors="coerce")

    # Sigma/bandas: rolling std del "precio vs vwap" (modelo simple, cerrado)
    # Nota: no es parte de Phase D/E, pero es derivado mecánico de la misma VWAP.
    dev = df_sym["close"] - df_sym["ctx_vwap"]
    sigma = dev.rolling(args.band_window, min_periods=1).std()

    df_sym["ctx_vwap_sigma"] = sigma
    df_sym["ctx_vwap_hi"] = df_sym["ctx_vwap"] + args.sigma_k * df_sym["ctx_vwap_sigma"]
    df_sym["ctx_vwap_lo"] = df_sym["ctx_vwap"] - args.sigma_k * df_sym["ctx_vwap_sigma"]

    # Volver a DF original, merge por (symbol,time)
    out = df.copy()
    add_cols = df_sym.reset_index()[["time","symbol","ctx_vwap","ctx_vwap_sigma","ctx_vwap_hi","ctx_vwap_lo"]]
    out = out.merge(add_cols, on=["symbol","time"], how="left")

    p_out = Path(args.out_parquet)
    p_out.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p_out, index=False)

    # Quick audit
    nan_rate = out[["ctx_vwap","ctx_vwap_hi","ctx_vwap_lo"]].isna().mean() * 100
    print("[OK] wrote:", p_out)
    print("[AUDIT] NaN%:", nan_rate.to_dict())
    print("[AUDIT] anchor:", anchor, "vwap_window:", args.vwap_window, "band_window:", args.band_window, "k:", args.sigma_k)

if __name__ == "__main__":
    main()