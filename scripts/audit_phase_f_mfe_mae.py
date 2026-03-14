# scripts/audit_phase_f_mfe_mae.py
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import numpy as np


# -----------------------------
# Config cerrada (sin tuning por CLI)
# -----------------------------
# Horizonte fijo por setup "root".
HORIZON_BY_SETUP = {
    "state_reinforcement": 16,     # TCP
    "balance_stability": 10,        # RIS
    "transition_resolution": 16,    # Expansión / breakout (auditoría inicial)
    "transition_noise": 16,          # <-- ADD USDCLP (diagnóstico fijo)
    "state_fragility_flat": 16,
    "state_fragility": 16,
    # --- ADD (XAU / Phase E validated) ---
    "transition_persistence": 16,
    "transition_persistence_flat": 16,
}

# Normalización de nombres (compat / variantes históricas)
SETUP_ALIASES = {
    "state_reinforcement_flat": "state_reinforcement",
    "balance_stability_center": "balance_stability",
    "balance_stability_fade": "balance_stability",
    "balance_stability_tail": "balance_stability",
    "state_fragility_flat": "state_fragility",
}

# Order-of-touch (OOTO) para monetización tipo expansión
# (config cerrada: no flags nuevos, no archivos nuevos)
OOTO_SETUPS = {"transition_resolution"}  # puedes ampliar después si corresponde
OOTO_TP_BPS = 80.0
OOTO_SL_BPS = 40.0


@dataclass(frozen=True)
class Episode:
    symbol: str
    setup_family: str
    side_intent: str
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    n_bars: int


def _normalize_setup(setup_family: str) -> str:
    s = str(setup_family)
    return SETUP_ALIASES.get(s, s)


def _read_decisions(decisions_with_side_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(decisions_with_side_csv)

    # Alias timestamp -> "time"
    if "time" not in df.columns:
        if "ts" in df.columns:
            df = df.rename(columns={"ts": "time"})
        elif "bar_ts" in df.columns:
            df = df.rename(columns={"bar_ts": "time"})

    expected_cols = {"time", "symbol", "decision", "setup_family", "side_intent", "meta_baseline_id"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Faltan columnas en decisions_with_side: {sorted(missing)}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    df["time"] = pd.to_datetime(df["time"], utc=False)
    df = df.sort_values(["symbol", "time"]).reset_index(drop=True)

    # Normaliza setup_family temprano para consistencia
    df["setup_family"] = df["setup_family"].map(_normalize_setup)

    return df


def _read_ohlc(enriched_parquet: Path) -> pd.DataFrame:
    df = pd.read_parquet(enriched_parquet)
    expected_cols = {"time", "symbol", "open", "high", "low", "close"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLC en enriched parquet: {sorted(missing)}")

    df["time"] = pd.to_datetime(df["time"], utc=False)
    df = df.sort_values(["symbol", "time"]).reset_index(drop=True)
    return df


def build_episodes(df_allow: pd.DataFrame) -> pd.DataFrame:
    """
    Episodio = run de ALLOW consecutivo (por filas) con mismo setup_family + side_intent (por símbolo).
    """
    df = df_allow.copy()
    df = df[df["decision"] == "ALLOW"].copy()
    if df.empty:
        raise ValueError("No hay filas ALLOW en decisions_with_side.")

    df["setup_family"] = df["setup_family"].map(_normalize_setup)

    # episode_id: cambia cuando cambia (setup_family, side_intent) o símbolo
    key = df["setup_family"].astype(str) + "|" + df["side_intent"].astype(str)
    prev_key = key.shift(1)
    prev_symbol = df["symbol"].shift(1)

    new_ep = (key != prev_key) | (df["symbol"] != prev_symbol)
    df["episode_id"] = new_ep.cumsum()

    agg = df.groupby(["symbol", "episode_id"], as_index=False).agg(
        setup_family=("setup_family", "first"),
        side_intent=("side_intent", "first"),
        meta_baseline_id=("meta_baseline_id", "first"),
        start_ts=("time", "min"),
        end_ts=("time", "max"),
        n_bars=("time", "size"),
    )
    return agg


def _horizon_for_setup(setup_root: str) -> int | None:
    return HORIZON_BY_SETUP.get(setup_root)


def episodes_to_trade_intents(episodes: pd.DataFrame) -> pd.DataFrame:
    """
    Regla cerrada (auditoría):
    - state_reinforcement: 1 intent por episodio, usando side_intent LONG/SHORT.
    - balance_stability: 2 intents virtuales (LONG/SHORT).
    - transition_resolution:
        - si viene LONG/SHORT => usarlo
        - si viene NONE/FLAT/otro => 2 intents virtuales LONG/SHORT (solo auditoría)
    """
    rows = []
    skipped_unknown_setup = 0

    for _, ep in episodes.iterrows():
        setup = _normalize_setup(ep["setup_family"])
        side = str(ep["side_intent"])
        symbol = str(ep["symbol"])
        start_ts = ep["start_ts"]
        baseline = str(ep["meta_baseline_id"])
        ep_id = int(ep["episode_id"])

        H = _horizon_for_setup(setup)
        if H is None:
            skipped_unknown_setup += 1
            continue

        if setup in {"state_reinforcement", "state_fragility", "transition_persistence", "transition_persistence_flat"}:
            if side not in {"LONG", "SHORT"}:
                continue
            rows.append({
                "symbol": symbol,
                "setup_family": setup,
                "baseline_id": baseline,
                "episode_id": ep_id,
                "intent_side": side,
                "entry_ts": start_ts,
                "horizon_bars": int(H),
                "is_virtual_pair": False,
            })

        elif setup == "balance_stability":
            for virtual_side in ("LONG", "SHORT"):
                rows.append({
                    "symbol": symbol,
                    "setup_family": setup,
                    "baseline_id": baseline,
                    "episode_id": ep_id,
                    "intent_side": virtual_side,
                    "entry_ts": start_ts,
                    "horizon_bars": int(H),
                    "is_virtual_pair": True,
                })

        elif setup in {"transition_resolution", "transition_noise"}:
            if side in {"LONG", "SHORT"}:
                rows.append({
                    "symbol": symbol,
                    "setup_family": setup,
                    "baseline_id": baseline,
                    "episode_id": ep_id,
                    "intent_side": side,
                    "entry_ts": start_ts,
                    "horizon_bars": int(H),
                    "is_virtual_pair": False,
                })
            else:
                for virtual_side in ("LONG", "SHORT"):
                    rows.append({
                        "symbol": symbol,
                        "setup_family": setup,
                        "baseline_id": baseline,
                        "episode_id": ep_id,
                        "intent_side": virtual_side,
                        "entry_ts": start_ts,
                        "horizon_bars": int(H),
                        "is_virtual_pair": True,
                    })

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("No se generaron trade intents (¿todo quedó en NONE/FLAT o setups sin horizonte?).")

    if skipped_unknown_setup:
        print(f"[WARN] Se saltaron {skipped_unknown_setup} episodios por setup_family sin horizonte definido.")

    return out.sort_values(["symbol", "entry_ts", "setup_family", "intent_side"]).reset_index(drop=True)


def _order_of_touch(window: pd.DataFrame, entry: float, side: str, tp_bps: float, sl_bps: float) -> str:
    """
    Determina qué se toca primero dentro de la ventana:
    WIN     => TP se toca antes que SL
    LOSS    => SL se toca antes que TP
    NONE    => ninguno se toca
    DISCARD => en la misma barra se tocan ambos (ambigüedad intrabar)
    """
    if entry == 0 or not np.isfinite(entry):
        return "NONE"

    for _, row in window.iterrows():
        hi = float(row["high"])
        lo = float(row["low"])

        if side == "LONG":
            tp = entry * (1.0 + tp_bps / 1e4)
            sl = entry * (1.0 - sl_bps / 1e4)
            hit_tp = hi >= tp
            hit_sl = lo <= sl

        elif side == "SHORT":
            tp = entry * (1.0 - tp_bps / 1e4)
            sl = entry * (1.0 + sl_bps / 1e4)
            hit_tp = lo <= tp
            hit_sl = hi >= sl

        else:
            return "NONE"

        if hit_tp and hit_sl:
            return "DISCARD"
        if hit_tp:
            return "WIN"
        if hit_sl:
            return "LOSS"

    return "NONE"


def compute_mfe_mae(intents: pd.DataFrame, ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    Usa OHLC desde entry_ts hacia adelante por horizon_bars (incluye barra de entry).
    """
    out_rows = []

    for symbol, ohlc_sym in ohlc.groupby("symbol"):
        ohlc_sym = ohlc_sym.sort_values("time").reset_index(drop=True)
        times = ohlc_sym["time"].values

        intents_sym = intents[intents["symbol"] == symbol]
        if intents_sym.empty:
            continue

        for _, it in intents_sym.iterrows():
            entry_ts = pd.Timestamp(it["entry_ts"])
            H = int(it["horizon_bars"])
            side = str(it["intent_side"])
            setup = str(it["setup_family"])

            i = int(np.searchsorted(times, np.datetime64(entry_ts), side="left"))
            if i >= len(ohlc_sym) or pd.Timestamp(ohlc_sym.loc[i, "time"]) != entry_ts:
                # match exacto requerido (sanity)
                continue

            j = min(i + H, len(ohlc_sym))  # slice [i, j)
            window = ohlc_sym.iloc[i:j]

            entry = float(window.iloc[0]["close"])
            hi = float(window["high"].max())
            lo = float(window["low"].min())

            if side == "LONG":
                mfe = hi - entry
                mae = entry - lo
            elif side == "SHORT":
                mfe = entry - lo
                mae = hi - entry
            else:
                continue

            mfe_bps = 1e4 * (mfe / entry) if entry != 0 else np.nan
            mae_bps = 1e4 * (mae / entry) if entry != 0 else np.nan

            # OOTO solo para setups configurados
            ooto_outcome = ""
            ooto_tp_bps = np.nan
            ooto_sl_bps = np.nan
            if setup in OOTO_SETUPS and side in {"LONG", "SHORT"}:
                ooto_outcome = _order_of_touch(window, entry, side, OOTO_TP_BPS, OOTO_SL_BPS)
                ooto_tp_bps = OOTO_TP_BPS
                ooto_sl_bps = OOTO_SL_BPS

            out_rows.append({
                "symbol": symbol,
                "episode_id": int(it["episode_id"]),
                "setup_family": setup,
                "baseline_id": str(it["baseline_id"]),
                "intent_side": side,
                "entry_ts": entry_ts,
                "horizon_bars": H,
                "entry_close": entry,
                "mfe_points": mfe,
                "mae_points": mae,
                "mfe_bps": mfe_bps,
                "mae_bps": mae_bps,
                "mfe_gt_mae": bool(mfe_bps > mae_bps) if np.isfinite(mfe_bps) and np.isfinite(mae_bps) else False,
                "exit_ts": pd.Timestamp(window.iloc[-1]["time"]),
                "n_window": int(len(window)),
                "is_virtual_pair": bool(it.get("is_virtual_pair", False)),
                "ooto_tp_bps": ooto_tp_bps,
                "ooto_sl_bps": ooto_sl_bps,
                "ooto_outcome": ooto_outcome,
            })

    res = pd.DataFrame(out_rows)
    if res.empty:
        raise ValueError("compute_mfe_mae produjo 0 filas. Revisa join time exacto y columnas.")
    return res.sort_values(["symbol", "setup_family", "intent_side", "entry_ts"]).reset_index(drop=True)


def summarize_go_nogo(mfe_mae: pd.DataFrame) -> pd.DataFrame:
    def _rate(series: pd.Series, label: str) -> float:
        # Si no hay outcomes (todo ""), devuelve NaN.
        if not (series != "").any():
            return np.nan
        return float((series == label).mean())

    grp = mfe_mae.groupby(["setup_family", "intent_side"], as_index=False).agg(
        n=("mfe_bps", "size"),
        median_mfe_bps=("mfe_bps", "median"),
        median_mae_bps=("mae_bps", "median"),
        p_mfe_gt_mae=("mfe_gt_mae", "mean"),
        ooto_win_rate=("ooto_outcome", lambda s: _rate(s, "WIN")),
        ooto_loss_rate=("ooto_outcome", lambda s: _rate(s, "LOSS")),
        ooto_discard_rate=("ooto_outcome", lambda s: _rate(s, "DISCARD")),
        ooto_none_rate=("ooto_outcome", lambda s: _rate(s, "NONE")),
    )

    # Regla GO/NO-GO original se mantiene (para direccional).
    grp["go_nogo"] = np.where(
        (grp["n"] >= 100) & (grp["median_mfe_bps"] > grp["median_mae_bps"]) & (grp["p_mfe_gt_mae"] >= 0.55),
        "GO",
        np.where((grp["n"] >= 100) & (grp["p_mfe_gt_mae"] <= 0.50), "NO-GO", "HOLD")
    )
    return grp.sort_values(["setup_family", "intent_side"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions_with_side_csv", type=str, required=True)
    ap.add_argument("--enriched_ohlc_parquet", type=str, required=True)
    ap.add_argument("--out_dir", type=str, required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df_dec = _read_decisions(Path(args.decisions_with_side_csv))
    df_ohlc = _read_ohlc(Path(args.enriched_ohlc_parquet))

    df_allow = df_dec[df_dec["decision"] == "ALLOW"].copy()
    episodes = build_episodes(df_allow)
    intents = episodes_to_trade_intents(episodes)
    mfe_mae = compute_mfe_mae(intents, df_ohlc)
    summary = summarize_go_nogo(mfe_mae)

    episodes.to_csv(out_dir / "episodes.csv", index=False)
    intents.to_csv(out_dir / "trade_intents.csv", index=False)
    mfe_mae.to_csv(out_dir / "mfe_mae_by_intent.csv", index=False)
    summary.to_csv(out_dir / "mfe_mae_summary_go_nogo.csv", index=False)

    print("Wrote:")
    print(" -", out_dir / "episodes.csv")
    print(" -", out_dir / "trade_intents.csv")
    print(" -", out_dir / "mfe_mae_by_intent.csv")
    print(" -", out_dir / "mfe_mae_summary_go_nogo.csv")


if __name__ == "__main__":
    main()