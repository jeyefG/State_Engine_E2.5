"""
First Touch Asymmetry (FTA) — minimal, auditable, repo-ready.

Qué hace:
- Toma eventos ALLOW (decisions_with_side.csv) con columna ts
- Toma barstream H2 con OHLC (parquet enriquecido) con columna time
- Para cada evento:
    base = close de la barra H2 asociada (merge_asof backward)
    Upper = base + X
    Lower = base - X
    Mira las próximas N barras H2 (t+1..t+N)
    Clasifica primer toque: UP / DOWN / NONE / DISCARD (si toca ambos en misma barra)
- Exporta:
    fta_per_event.parquet
    fta_summary_by_setup.csv
    fta_summary_by_setup_year.csv

Diseño anti p-hacking:
- X fijo (no tuning)
- horizonte fijo (no tuning)
- DISCARD cuando ambos tocan en misma barra futura
"""

from __future__ import annotations

from pathlib import Path
import argparse
import numpy as np
import pandas as pd


# -----------------------------
# Utils
# -----------------------------
def ensure_datetime_ns_naive(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Convierte columna a datetime64[ns] naive. Revienta si hay NaT."""
    if col not in df.columns:
        raise KeyError(f"Missing required timestamp column: {col}")

    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce")

    if out[col].isna().any():
        bad = out[out[col].isna()].head(5)
        raise ValueError(
            f"Found NaT in {col} after to_datetime. Example rows:\n{bad}"
        )

    # Normaliza tz: si viene tz-aware, lo pasamos a naive
    try:
        tz = getattr(out[col].dt, "tz", None)
        if tz is not None:
            out[col] = out[col].dt.tz_convert(None)
    except Exception:
        # fallback conservador
        try:
            out[col] = out[col].dt.tz_localize(None)
        except Exception as e:
            raise RuntimeError(f"Failed to normalize timezone for {col}: {e}")

    # Asegura ns
    out[col] = out[col].astype("datetime64[ns]")
    return out


def summarize_block(df: pd.DataFrame) -> pd.Series:
    n = len(df)
    n_up = int((df["fta_outcome"] == "UP").sum())
    n_dn = int((df["fta_outcome"] == "DOWN").sum())
    n_none = int((df["fta_outcome"] == "NONE").sum())
    n_disc = int((df["fta_outcome"] == "DISCARD").sum())

    touched = n_up + n_dn + n_disc          # tocó algún nivel (incluye discards)
    dir_touched = n_up + n_dn               # tocó direccionalmente (excluye discards)

    denom_dir = max(dir_touched, 1)
    ratio_up = n_up / denom_dir
    ratio_dn = n_dn / denom_dir

    discard_rate_on_touched = n_disc / max(touched, 1)
    touch_rate = touched / max(n, 1)
    dir_touch_rate = dir_touched / max(n, 1)

    return pd.Series({
        "n_eventos": n,
        "n_up_first": n_up,
        "n_down_first": n_dn,
        "n_none": n_none,
        "n_discard": n_disc,
        "ratio_up": ratio_up,
        "ratio_down": ratio_dn,
        "touch_rate": touch_rate,
        "dir_touch_rate": dir_touch_rate,
        "discard_rate_on_touched": discard_rate_on_touched,
    })


# -----------------------------
# Core FTA
# -----------------------------
def compute_fta(
    events: pd.DataFrame,
    bars: pd.DataFrame,
    x_value: float,
    horizon_n: int,
    events_ts_col: str = "ts",
    bars_ts_col: str = "time",
    setup_col: str = "setup_family",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      per_event, summary_by_setup, summary_by_setup_year
    """
    if x_value <= 0:
        raise ValueError("x_value must be > 0. Paste your abs_ret_mean_h2_h1 (or chosen fixed X).")
    if horizon_n <= 0:
        raise ValueError("horizon_n must be >= 1")

    required_bars_cols = [bars_ts_col, "open", "high", "low", "close"]
    for c in required_bars_cols:
        if c not in bars.columns:
            raise KeyError(f"Bars missing required column: {c}")

    # Orden para merge_asof + forward scan
    bars = bars.sort_values(bars_ts_col).reset_index(drop=True)
    events = events.sort_values(events_ts_col).reset_index(drop=True)

    # Si no existe setup_family, colapsa en ALL
    if setup_col not in events.columns:
        events = events.copy()
        events[setup_col] = "ALL"

    # Calzar cada evento con su barra H2 (<= ts evento)
    right = bars[[bars_ts_col, "open", "high", "low", "close"]].rename(columns={bars_ts_col: "__bar_ts"})
    merged = pd.merge_asof(
        events,
        right,
        left_on=events_ts_col,
        right_on="__bar_ts",
        direction="backward",
        allow_exact_matches=True,
    )

    # Filtra eventos sin match
    merged = merged.dropna(subset=["__bar_ts", "close"]).copy()

    # Exact match rate (auditoría)
    merged["is_exact_match"] = (merged[events_ts_col].astype("datetime64[ns]") == merged["__bar_ts"].astype("datetime64[ns]"))

    # Base/Upper/Lower
    merged["base"] = merged["close"].astype(float)
    merged["X"] = float(x_value)
    merged["upper"] = merged["base"] + merged["X"]
    merged["lower"] = merged["base"] - merged["X"]
    merged["year"] = pd.to_datetime(merged["__bar_ts"]).dt.year

    # Index robusto para lookup: datetime64[ns]
    bars_ts_ns = bars[bars_ts_col].astype("datetime64[ns]").values
    ts_to_pos = pd.Series(np.arange(len(bars)), index=bars_ts_ns)

    bars_high = bars["high"].to_numpy(dtype=float)
    bars_low = bars["low"].to_numpy(dtype=float)

    outcomes = []
    first_touch_offset = []  # 1..N o NaN

    # Iteración (610 eventos: ok)
    for _, row in merged.iterrows():
        bar_ts = np.datetime64(row["__bar_ts"], "ns")
        pos = ts_to_pos.get(bar_ts, None)

        if pos is None:
            outcomes.append("NONE")
            first_touch_offset.append(np.nan)
            continue

        upper = float(row["upper"])
        lower = float(row["lower"])

        # mira t+1..t+N
        start = int(pos) + 1
        end = min(int(pos) + 1 + horizon_n, len(bars))

        if start >= end:
            outcomes.append("NONE")
            first_touch_offset.append(np.nan)
            continue

        outcome = "NONE"
        fto = np.nan
        for k, j in enumerate(range(start, end), start=1):
            hit_up = bars_high[j] >= upper
            hit_dn = bars_low[j] <= lower

            if hit_up and hit_dn:
                outcome = "DISCARD"
                fto = k
                break
            if hit_up:
                outcome = "UP"
                fto = k
                break
            if hit_dn:
                outcome = "DOWN"
                fto = k
                break

        outcomes.append(outcome)
        first_touch_offset.append(fto)

    merged["fta_outcome"] = outcomes
    merged["fta_first_touch_offset"] = first_touch_offset

    # Resúmenes
    summary_by_setup = (
        merged.groupby(setup_col, dropna=False)
        .apply(summarize_block)
        .reset_index()
        .sort_values(["n_eventos"], ascending=False)
    )

    summary_by_setup_year = (
        merged.groupby([setup_col, "year"], dropna=False)
        .apply(summarize_block)
        .reset_index()
        .sort_values([setup_col, "year"])
    )

    return merged, summary_by_setup, summary_by_setup_year


# -----------------------------
# CLI / Main
# -----------------------------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events_csv", required=True, help="decisions_with_side.csv (must include ts)")
    ap.add_argument("--bars_parquet", required=True, help="H2 barstream enriched parquet (must include time, open/high/low/close)")
    ap.add_argument("--out_dir", required=True, help="output directory for FTA artifacts")

    ap.add_argument("--x_value", type=float, required=True, help="Fixed X (e.g., abs_ret_mean_h2_h1). Must be > 0.")
    ap.add_argument("--horizon_n", type=int, default=3, help="How many future H2 bars to look ahead (default 3)")

    ap.add_argument("--events_ts_col", default="ts", help="timestamp column in events csv (default ts)")
    ap.add_argument("--bars_ts_col", default="time", help="timestamp column in bars parquet (default time)")
    ap.add_argument("--setup_col", default="setup_family", help="setup family column in events (default setup_family)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    events_path = Path(args.events_csv)
    bars_path = Path(args.bars_parquet)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    events = pd.read_csv(events_path)
    bars = pd.read_parquet(bars_path)

    events = ensure_datetime_ns_naive(events, args.events_ts_col)
    bars = ensure_datetime_ns_naive(bars, args.bars_ts_col)

    per_event, summary_setup, summary_setup_year = compute_fta(
        events=events,
        bars=bars,
        x_value=args.x_value,
        horizon_n=args.horizon_n,
        events_ts_col=args.events_ts_col,
        bars_ts_col=args.bars_ts_col,
        setup_col=args.setup_col,
    )

    # Auditoría extra: exact match rate
    exact_rate = float(per_event["is_exact_match"].mean()) if len(per_event) else 0.0
    with open(out_dir / "fta_meta.txt", "w", encoding="utf-8") as f:
        f.write(f"events_csv={events_path}\n")
        f.write(f"bars_parquet={bars_path}\n")
        f.write(f"x_value={args.x_value}\n")
        f.write(f"horizon_n={args.horizon_n}\n")
        f.write(f"events_ts_col={args.events_ts_col}\n")
        f.write(f"bars_ts_col={args.bars_ts_col}\n")
        f.write(f"setup_col={args.setup_col}\n")
        f.write(f"exact_match_rate={exact_rate:.6f}\n")
        f.write(f"n_events_used={len(per_event)}\n")

    per_event.to_parquet(out_dir / "fta_per_event.parquet", index=False)
    summary_setup.to_csv(out_dir / "fta_summary_by_setup.csv", index=False)
    summary_setup_year.to_csv(out_dir / "fta_summary_by_setup_year.csv", index=False)

    print("[OK] FTA audit finished")
    print("  n_events_used:", len(per_event))
    print(f"  exact_match_rate: {exact_rate:.4%}")
    print("  outputs:", out_dir.resolve())


if __name__ == "__main__":
    main()
