# scripts/build_prices_h2.py
from __future__ import annotations

from pathlib import Path
import pandas as pd
import inspect

# Ajusta el import al path real de tu repo
from state_engine.mt5_connector import MT5Connector


def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    """
    Repo convention:
    - timestamps are naive, interpreted in MT5 server time
    - no conversion to UTC / local
    - if tz-aware sneaks in, we drop tz info (no convert)
    """
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    # If tz-aware, make naive without converting
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_localize(None)
    return dt

def fetch_ohlcv(mt5, symbol: str, timeframe: str, t0, t1):
    """
    Adapter to support different MT5Connector.obtener_ohlcv signatures across repo versions.
    Tries common parameter names without changing the connector.
    """
    fn = mt5.obtener_ohlcv
    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    # Most probable variants
    candidates = [
        dict(symbol=symbol, timeframe=timeframe, time_from=t0, time_to=t1),
        dict(symbol=symbol, timeframe=timeframe, from_dt=t0, to_dt=t1),
        dict(symbol=symbol, timeframe=timeframe, date_from=t0, date_to=t1),
        dict(symbol=symbol, timeframe=timeframe, start=t0, end=t1),
        dict(symbol=symbol, timeframe=timeframe, t0=t0, t1=t1),
        dict(symbol=symbol, timeframe=timeframe, since=t0, until=t1),
    ]

    # Keep only kwargs that exist in this signature
    for kw in candidates:
        filtered = {k: v for k, v in kw.items() if k in params}
        # Must contain symbol+timeframe and at least one time boundary
        if "symbol" in filtered and "timeframe" in filtered and any(k in filtered for k in ["time_from","from_dt","date_from","start","t0","since"]):
            try:
                return fn(**filtered)
            except TypeError:
                continue

    # Last resort: maybe signature is (symbol, timeframe, t0, t1) positional
    try:
        return fn(symbol, timeframe, t0, t1)
    except Exception as e:
        raise TypeError(
            f"No pude llamar MT5Connector.obtener_ohlcv con ninguna firma conocida. "
            f"Signature={sig}"
        ) from e

def main(
    symbol: str,
    context_parquet: str,
    out_prices_parquet: str,
    timeframe: str = "H2",
    pad_hours: int = 48,
) -> None:
    ctx = pd.read_parquet(context_parquet, columns=["symbol", "time"])
    ctx["time"] = to_server_naive_datetime(ctx["time"])
    ctx = ctx.sort_values(["symbol", "time"])

    # Time window from context (server-naive)
    t0 = ctx["time"].min() - pd.Timedelta(hours=pad_hours)
    t1 = ctx["time"].max() + pd.Timedelta(hours=pad_hours)

    mt5 = MT5Connector()

    # Assumes obtener_ohlcv returns DataFrame indexed by time (server-naive),
    # or includes a 'time' column.
    df = fetch_ohlcv(mt5, symbol=symbol, timeframe=timeframe, t0=t0, t1=t1)


    if isinstance(df.index, pd.DatetimeIndex):
        prices = df.reset_index().rename(columns={df.index.name or "index": "time"})
    else:
        prices = df.copy()
        if "time" not in prices.columns:
            raise RuntimeError("MT5 OHLCV no trae índice datetime ni columna 'time'.")

    prices["symbol"] = symbol
    prices["time"] = to_server_naive_datetime(prices["time"])
    prices = prices.sort_values(["symbol", "time"])

    # Keep minimal columns
    base_cols = ["symbol", "time", "open", "high", "low", "close"]
    optional_cols = [c for c in ["spread", "tick_volume", "real_volume"] if c in prices.columns]
    keep_cols = base_cols + optional_cols

    missing = [c for c in base_cols if c not in prices.columns]
    if missing:
        raise RuntimeError(f"MT5 OHLCV no trae columnas requeridas: {missing}")

    prices = prices[keep_cols]

    # Hard checks
    if prices.duplicated(["symbol", "time"]).any():
        d = prices[prices.duplicated(["symbol", "time"], keep=False)].head(10)
        raise RuntimeError(f"Duplicados detectados en prices (symbol,time). Ejemplos:\n{d}")

    bad_ohlc = ~(
        (prices["low"] <= prices[["open", "close"]].min(axis=1))
        & (prices["high"] >= prices[["open", "close"]].max(axis=1))
        & (prices["low"] <= prices["high"])
    )
    if bad_ohlc.any():
        raise RuntimeError(f"OHLC inválido en {int(bad_ohlc.sum())} filas.")

    outp = Path(out_prices_parquet)
    outp.parent.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(outp, index=False)

    print(
        "[OK] prices saved:",
        str(outp),
        "| rows=", len(prices),
        "| range=", prices["time"].min(), "->", prices["time"].max(),
        "| cols=", keep_cols
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--context_parquet", required=True)
    ap.add_argument("--out_prices_parquet", required=True)
    ap.add_argument("--timeframe", default="H2")
    ap.add_argument("--pad_hours", type=int, default=48)
    args = ap.parse_args()

    main(
        symbol=args.symbol,
        context_parquet=args.context_parquet,
        out_prices_parquet=args.out_prices_parquet,
        timeframe=args.timeframe,
        pad_hours=args.pad_hours,
    )
