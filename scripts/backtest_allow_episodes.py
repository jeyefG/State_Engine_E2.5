# scripts/backtest_allow_episodes.py
from __future__ import annotations

from pathlib import Path
import argparse
import pandas as pd
import numpy as np


def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    """
    Repo convention:
    - timestamps are naive, interpreted in MT5 server time
    - no conversion to UTC / local
    - if tz-aware appears, drop tz info (no convert)
    """
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min())


def _parse_setup_family_arg(s: str) -> list[str]:
    """
    Accept:
      "state_reinforcement"
      "transition_resolution"
      "state_reinforcement,transition_resolution"
    """
    if s is None:
        return ["state_reinforcement"]
    parts = [p.strip() for p in str(s).split(",") if p.strip()]
    return parts or ["state_reinforcement"]


def _normalize_side_filter(side: str) -> set[str]:
    side = str(side or "BOTH").upper().strip()
    if side == "LONG":
        return {"LONG"}
    if side == "SHORT":
        return {"SHORT"}
    if side == "NONE":
        return {"NONE"}
    return {"LONG", "SHORT"}  # BOTH


def _infer_bar_seconds(times: pd.Series) -> float:
    # robust: use median diff
    t = pd.to_datetime(times, errors="coerce")
    dt = t.diff().dropna().dt.total_seconds()
    if dt.empty:
        return 0.0
    return float(dt.median())


def _add_allow_block_id(dec: pd.DataFrame, *, bar_seconds: float | None = None) -> pd.DataFrame:
    """
    Add allow_block_id.

    Case 1 (preferred): decisions stream includes BLOCK rows -> contiguous ALLOW runs.
    Case 2 (fallback): decisions stream contains mostly/only ALLOW -> break blocks by time gaps
                       larger than ~1.5 bars.
    """
    dec = dec.sort_values(["symbol", "ts"]).reset_index(drop=True).copy()
    is_allow = dec["decision"].astype(str).str.upper().eq("ALLOW")

    prev_sym = dec["symbol"].shift(1)
    new_sym = dec["symbol"].ne(prev_sym)

    has_any_block = (dec["decision"].astype(str).str.upper() == "BLOCK").any()

    if has_any_block:
        prev_allow = is_allow.shift(1, fill_value=False)
        start = is_allow & (~prev_allow | new_sym)
        block_id = start.cumsum()
        dec["allow_block_id"] = np.where(is_allow, block_id, np.nan)
        return dec

    # ---- fallback: split by time gaps (needs bar_seconds) ----
    if not bar_seconds or bar_seconds <= 0:
        # worst-case: each ALLOW is its own block (still prevents "all 1 block")
        start = is_allow & (new_sym | ~is_allow.shift(1, fill_value=False))
        block_id = start.cumsum()
        dec["allow_block_id"] = np.where(is_allow, block_id, np.nan)
        return dec

    ts = pd.to_datetime(dec["ts"], errors="coerce")
    gap = ts.diff().dt.total_seconds().fillna(0.0)
    gap_break = gap > (1.5 * float(bar_seconds))  # tolerate minor irregularities

    prev_allow = is_allow.shift(1, fill_value=False)
    start = is_allow & ((~prev_allow) | new_sym | gap_break)
    block_id = start.cumsum()
    dec["allow_block_id"] = np.where(is_allow, block_id, np.nan)
    return dec


def _audit_decisions_vs_enriched(df, dec, operable, *, symbol, exit_mode, trigger_unit, side_allow,
                                allow_overlapping_trades, max_positions):

    print("\n[AUDIT] backtest input sanity")

    print("symbol:", symbol)
    print("enriched rows:", len(df))
    print("time span:", df["time"].iloc[0], "->", df["time"].iloc[-1])

    print("decisions rows:", len(dec))

    # --- decision distribution (if available)
    if "decision" in dec.columns:
        vc = dec["decision"].astype(str).str.upper().value_counts()
        allow_n = vc.get("ALLOW", 0)
        block_n = vc.get("BLOCK", 0)

        print("ALLOW:", allow_n, "BLOCK:", block_n)

        if len(dec) > 0 and allow_n > 0:
            print("ALLOW%:", f"{allow_n/len(dec):.2%}")

        if trigger_unit == "episodes" and block_n == 0:
            print("[WARN] episodes requested but no BLOCK rows present (fallback uses time gaps)")

    else:
        print("[INFO] decision column not present (subset decisions file)")

    # --- timestamp hit rate
    time_index = set(df["time"])

    if "ts" in dec.columns:
        hit = dec["ts"].isin(time_index)
        hit_rate = float(hit.mean()) if len(hit) else 0.0
        print("ts hit_rate:", f"{hit_rate:.4f}")

        if hit_rate < 0.995:
            print("[WARN] timestamp mismatch with enriched grid")

    else:
        print("[INFO] ts column missing")

    # --- operable sanity
    print("operable rows:", len(operable))
    if len(dec) > 0:
        print("operable %:", f"{len(operable)/len(dec):.2%}")

    # --- setup family
    if "setup_family" in operable.columns:
        print("setup_family breakdown:")
        print(operable["setup_family"].value_counts().head())

    # --- side intent
    if "side_intent" in operable.columns:
        print("side_intent breakdown:")
        print(operable["side_intent"].value_counts().head())

    print("side_allow:", sorted(side_allow))
    print("trigger_unit:", trigger_unit)
    print("allow_overlapping_trades:", bool(allow_overlapping_trades), "max_positions:", int(max_positions))

    # --- allow block sanity
    if "allow_block_id" in operable.columns:
        blocks = operable["allow_block_id"].dropna()

        if len(blocks) > 0:
            n_blocks = int(blocks.nunique())
            print("allow_block_id unique:", n_blocks)

            sizes = operable.groupby("allow_block_id").size().sort_values(ascending=False).head()
            print("top block sizes:")
            print(sizes)

            if trigger_unit == "episodes" and n_blocks <= 1:
                print("[WARN] episodes mode but only one block detected")

    # --- sigma coverage
    if exit_mode == "fixed":
        if "ctx_vwap_sigma" in df.columns:
            sigma_ok = float(df["ctx_vwap_sigma"].notna().mean())
            print("sigma coverage:", f"{sigma_ok:.3f}")

            if sigma_ok < 0.95:
                print("[WARN] sigma coverage low")


def _derive_sigma_from_bands(row: pd.Series) -> float:
    """
    If ctx_vwap_sigma not present, derive sigma from vwap bands assuming +/- 2 sigma:
      sigma ~= min((vwap_hi - vwap)/2, (vwap - vwap_lo)/2)
    """
    vwap = row.get("ctx_vwap", np.nan)
    hi = row.get("ctx_vwap_hi", np.nan)
    lo = row.get("ctx_vwap_lo", np.nan)

    if not np.isfinite(vwap) or not np.isfinite(hi) or not np.isfinite(lo):
        return np.nan

    s1 = (hi - vwap) / 2.0
    s2 = (vwap - lo) / 2.0

    if not np.isfinite(s1) or not np.isfinite(s2):
        return np.nan

    sigma = float(min(s1, s2))
    if sigma <= 0:
        return np.nan
    return sigma


def _infer_point_from_prices(df: pd.DataFrame) -> float:
    """
    Infer broker point size from observed OHLC decimals.
    Examples:
      GBPUSD 1.25159 -> 1e-5
      XAUUSD  2654.23 -> 1e-2
      US500   5234.25 -> 1e-2
    """
    cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    if not cols:
        return 1e-4

    vals = pd.concat([df[c] for c in cols], axis=0).dropna().astype(float)
    if vals.empty:
        return 1e-4

    max_dec = 0
    for x in vals.iloc[:5000]:
        s = f"{float(x):.10f}".rstrip("0").rstrip(".")
        dec = len(s.split(".")[1]) if "." in s else 0
        max_dec = max(max_dec, dec)

    return float(10 ** (-max_dec)) if max_dec > 0 else 1.0


def main(
    symbol: str,
    enriched_parquet: str,
    decisions_csv: str,
    out_dir: str,
    time_stop_bars: int = 10,
    entry_mode: str = "next_open",          # for GO/NO-GO we use next_open
    mode: str = "long",                     # long | short | abs_move (kept for compatibility)
    use_spread: bool = False,
    tp_k: float = 1.5,
    sl_k: float = 1.0,
    setup_family: str = "state_reinforcement",
    side: str = "BOTH",                     # LONG | SHORT | BOTH | NONE
    trigger_unit: str = "episodes",         # bars | episodes  (NEW: separated from stacking)
    exit_mode: str = "fixed",               # fixed | state_change
    catastrophic_sl_bps: float = 350.0,
    arm_state_value: float = 2.0,
    perf_gate_days: int = 0,
    perf_gate_min_trades: int = 0,
    perf_gate_ev_min_bps: float = 0.0,
    # --- NEW: stacking / overlap control (conservative defaults) ---
    allow_overlapping_trades: bool = False,
    max_positions: int = 1,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    setup_families = _parse_setup_family_arg(setup_family)
    side_set = _normalize_side_filter(side)

    trigger_unit = str(trigger_unit or "episodes").lower().strip()
    if trigger_unit not in {"bars", "episodes"}:
        raise RuntimeError("trigger_unit must be 'bars' or 'episodes'.")

    # Load enriched barstream (OHLC + spread etc.)
    df = pd.read_parquet(enriched_parquet)
    for col in ["symbol", "time", "open", "high", "low", "close"]:
        if col not in df.columns:
            raise RuntimeError(f"Enriched parquet missing required column: {col}")

    df["time"] = to_server_naive_datetime(df["time"])
    df = df.sort_values(["symbol", "time"]).reset_index(drop=True)

    has_spread = "spread" in df.columns

    # Filter symbol
    df = df[df["symbol"] == symbol].copy()
    if df.empty:
        raise RuntimeError(f"No rows for symbol={symbol} in enriched parquet.")
    df = df.sort_values("time").reset_index(drop=True)
    point_size = _infer_point_from_prices(df)

    # exit_mode validation + required cols
    if exit_mode not in {"fixed", "state_change"}:
        raise RuntimeError(f"Invalid exit_mode={exit_mode}. Use fixed|state_change.")

    if exit_mode == "state_change":
        if "state_hat" not in df.columns:
            raise RuntimeError("exit_mode=state_change requires 'state_hat' column in enriched parquet.")

    # Map time -> positional index
    time_index = pd.Series(df.index.values, index=df["time"].values)
    times = df["time"].values

    # Load decisions_with_side.csv (must include setup_family, side_intent)
    dec = pd.read_csv(decisions_csv)
    need = {"decision", "ts", "setup_family", "side_intent"}
    missing = need - set(dec.columns)
    if missing:
        raise RuntimeError(f"decisions_with_side missing columns: {sorted(missing)}")

    if "symbol" not in dec.columns:
        dec["symbol"] = symbol

    dec = dec[dec["symbol"] == symbol].copy()
    dec["ts"] = to_server_naive_datetime(dec["ts"])
    dec = dec.dropna(subset=["ts"]).copy()

    dec["decision"] = dec["decision"].astype(str).str.upper()
    dec["setup_family"] = dec["setup_family"].astype(str)
    dec["side_intent"] = dec["side_intent"].astype(str).str.upper()

    dec = dec.sort_values("ts").reset_index(drop=True)

    bar_seconds = _infer_bar_seconds(df["time"])
    dec_full = _add_allow_block_id(dec, bar_seconds=bar_seconds)

    # --- Operable universe filter (extended: allow NONE when mode=abs_move)
    if mode == "abs_move":
        # abs_move puede operar con side_intent NONE (neutral)
        if side == "BOTH":
            side_allow = {"LONG", "SHORT", "NONE"}
        else:
            side_allow = {str(side).upper()}
    else:
        # comportamiento legacy: BOTH = LONG/SHORT
        side_allow = {"LONG", "SHORT"} if side == "BOTH" else {str(side).upper()}

    operable = (
        dec_full[
            (dec_full["decision"] == "ALLOW")
            & (dec_full["setup_family"].isin(setup_families))
            & (dec_full["side_intent"].astype(str).str.upper().isin(side_allow))
        ]
        .sort_values("ts")
        .reset_index(drop=True)
    )

    # NEW separation:
    # - trigger_unit=episodes => 1 candidate per allow_block_id
    # - trigger_unit=bars     => 1 candidate per ALLOW row
    if trigger_unit == "episodes":
        if "allow_block_id" not in operable.columns:
            raise RuntimeError("trigger_unit=episodes requires allow_block_id (failed to build).")
        operable = (
            operable.sort_values("ts")
            .drop_duplicates(subset=["allow_block_id"], keep="first")
            .reset_index(drop=True)
        )

    if operable.empty:
        raise RuntimeError(
            "No operable rows after filtering. "
            f"setup_families={setup_families}, side={side}, mode={mode}, side_allow={sorted(side_allow)}."
        )

    _audit_decisions_vs_enriched(
        df=df,
        dec=dec_full,
        operable=operable,
        symbol=symbol,
        exit_mode=exit_mode,
        trigger_unit=trigger_unit,
        side_allow=side_allow,
        allow_overlapping_trades=allow_overlapping_trades,
        max_positions=max_positions,
    )

    # --- Build trades (candidates) + enforce stacking/overlap rules robustly
    TP_K = float(tp_k)
    SL_K = float(sl_k)
    TIMEOUT_BARS = int(time_stop_bars)

    def _simulate_trade_from_row(r) -> dict | None:
        t0 = r["ts"]
        side_intent = str(r["side_intent"]).upper().strip()  # LONG / SHORT / NONE

        if t0 not in time_index.index:
            return None
        i0 = int(time_index.loc[t0])

        i_entry = i0 + 1  # next_open
        if i_entry >= len(df):
            return None

        entry_time = times[i_entry]
        entry_px = float(df.loc[i_entry, "open"])
        if not np.isfinite(entry_px) or entry_px <= 0:
            return None

        entry_spread_points = 0.0
        if has_spread and "spread" in df.columns:
            sp = df.loc[i_entry, "spread"]
            if pd.notna(sp):
                entry_spread_points = float(sp)

        i_max = min(i_entry + TIMEOUT_BARS - 1, len(df) - 1)

        exit_i = i_max
        exit_reason = "timeout"
        exit_px = float(df.loc[exit_i, "close"])

        sigma = np.nan
        if "ctx_vwap_sigma" in df.columns:
            sigma = float(df.loc[i_entry, "ctx_vwap_sigma"])
        else:
            sigma = _derive_sigma_from_bands(df.loc[i_entry])

        is_directional = side_intent in {"LONG", "SHORT"}
        is_abs_move = (side_intent == "NONE" and mode == "abs_move")

        if not is_directional and not is_abs_move:
            return None

        if exit_mode == "fixed":
            if not np.isfinite(sigma) or sigma <= 0:
                return None

            tp_pts = TP_K * sigma
            sl_pts = SL_K * sigma

            for j in range(i_entry, i_max + 1):
                hi = float(df.loc[j, "high"])
                lo = float(df.loc[j, "low"])

                # -----------------------------
                # LONG
                # -----------------------------
                if side_intent == "LONG":
                    tp = entry_px + tp_pts
                    sl = entry_px - sl_pts
                    hit_tp = np.isfinite(hi) and hi >= tp
                    hit_sl = np.isfinite(lo) and lo <= sl

                    if hit_tp and hit_sl:
                        exit_i, exit_px, exit_reason = j, sl, "both_hit_sl"
                        break
                    if hit_sl:
                        exit_i, exit_px, exit_reason = j, sl, "sl"
                        break
                    if hit_tp:
                        exit_i, exit_px, exit_reason = j, tp, "tp"
                        break

                # -----------------------------
                # SHORT
                # -----------------------------
                elif side_intent == "SHORT":
                    tp = entry_px - tp_pts
                    sl = entry_px + sl_pts
                    hit_tp = np.isfinite(lo) and lo <= tp
                    hit_sl = np.isfinite(hi) and hi >= sl

                    if hit_tp and hit_sl:
                        exit_i, exit_px, exit_reason = j, sl, "both_hit_sl"
                        break
                    if hit_sl:
                        exit_i, exit_px, exit_reason = j, sl, "sl"
                        break
                    if hit_tp:
                        exit_i, exit_px, exit_reason = j, tp, "tp"
                        break

                # -----------------------------
                # ABS_MOVE / NONE
                # -----------------------------
                else:
                    hit_up = np.isfinite(hi) and (hi - entry_px) >= tp_pts
                    hit_dn = np.isfinite(lo) and (entry_px - lo) >= tp_pts

                    # Con OHLC no sabemos el orden intrabar.
                    # Supuesto conservador: si toca ambos lados, cuenta como pérdida.
                    if hit_up and hit_dn:
                        exit_i, exit_px, exit_reason = j, entry_px - sl_pts, "both_hit_sl_abs"
                        break

                    if hit_up or hit_dn:
                        exit_i, exit_px, exit_reason = j, entry_px + tp_pts, "tp_abs"
                        break

            # timeout queda como está

        else:
            # state_change solo tiene sentido para trades direccionales
            if not is_directional:
                return None

            armed = False
            if side_intent == "LONG":
                cat_sl = entry_px * (1.0 - catastrophic_sl_bps / 1e4)
            else:
                cat_sl = entry_px * (1.0 + catastrophic_sl_bps / 1e4)

            for j in range(i_entry, i_max + 1):
                hi = float(df.loc[j, "high"])
                lo = float(df.loc[j, "low"])

                st_raw = df.loc[j, "state_hat"]
                st = float(st_raw) if pd.notna(st_raw) else np.nan

                if side_intent == "LONG":
                    if np.isfinite(lo) and lo <= cat_sl:
                        exit_i, exit_px, exit_reason = j, cat_sl, "cat_sl"
                        break
                else:
                    if np.isfinite(hi) and hi >= cat_sl:
                        exit_i, exit_px, exit_reason = j, cat_sl, "cat_sl"
                        break

                if np.isfinite(st) and st == float(arm_state_value):
                    armed = True
                    continue

                if armed and np.isfinite(st) and st != float(arm_state_value):
                    exit_i = j
                    exit_px = float(df.loc[j, "close"])
                    exit_reason = "state_change"
                    break

        exit_time = times[exit_i]

        # -----------------------------
        # Signed return
        # -----------------------------
        if side_intent == "LONG":
            ret_gross = (exit_px - entry_px) / entry_px
        elif side_intent == "SHORT":
            ret_gross = (entry_px - exit_px) / entry_px
        else:
            if exit_reason == "tp_abs":
                ret_gross = tp_pts / entry_px
            elif exit_reason == "both_hit_sl_abs":
                ret_gross = -sl_pts / entry_px
            elif exit_reason == "timeout":
                ret_gross = 0.0
            else:
                ret_gross = 0.0

        return dict(
            symbol=symbol,
            t0=t0,
            allow_block_id=r.get("allow_block_id", np.nan),
            setup_family=str(r.get("setup_family", "")),
            side_intent=side_intent,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_px=entry_px,
            exit_px=exit_px,
            sigma=sigma,
            tp_k=TP_K,
            sl_k=SL_K,
            time_stop_bars=TIMEOUT_BARS,
            trigger_unit=trigger_unit,
            exit_mode=exit_mode,
            arm_state_value=float(arm_state_value),
            catastrophic_sl_bps=float(catastrophic_sl_bps),
            exit_reason=exit_reason,
            ret_gross=ret_gross,
            ret_net=ret_gross,  # overwritten below after spread model
            spread_points=entry_spread_points,
            spread_px=entry_spread_points * point_size,
        )

    # 1) simulate all candidate trades first (deterministic)
    candidates = []
    for _, r in operable.iterrows():
        tr = _simulate_trade_from_row(r)
        if tr is not None:
            candidates.append(tr)

    cand_df = pd.DataFrame(candidates)
    if cand_df.empty:
        raise RuntimeError(
            "No candidate trades produced. Possible causes: ts mismatch (decisions ts not matching enriched time) "
            "or sigma missing (for fixed), or filters too strict."
        )

    cand_df = cand_df.sort_values("entry_time").reset_index(drop=True)

    # 2) enforce overlap/stacking rules (conservative by default)
    allow_overlapping_trades = bool(allow_overlapping_trades)
    max_positions = int(max_positions)
    if max_positions < 1:
        max_positions = 1

    accepted = []
    open_positions_exit_times: list[pd.Timestamp] = []

    for _, tr in cand_df.iterrows():
        entry_time = pd.Timestamp(tr["entry_time"])
        exit_time = pd.Timestamp(tr["exit_time"])

        # clean closed positions
        open_positions_exit_times = [et for et in open_positions_exit_times if pd.Timestamp(et) > entry_time]

        if not allow_overlapping_trades:
            # conservative: require zero open positions
            if len(open_positions_exit_times) > 0:
                continue
            accepted.append(tr.to_dict())
            open_positions_exit_times = [exit_time]
        else:
            # stacking allowed up to max_positions
            if len(open_positions_exit_times) >= max_positions:
                continue
            accepted.append(tr.to_dict())
            open_positions_exit_times.append(exit_time)

    trades_df = pd.DataFrame(accepted)
    if trades_df.empty:
        raise RuntimeError(
            "All candidate trades filtered out by overlap/stacking rules. "
            "Try allow_overlapping_trades=True or increase max_positions."
        )

    trades_df = trades_df.sort_values("entry_time").reset_index(drop=True)
    trades_df["ret_gross"] = trades_df["ret_gross"].astype(float)
    trades_df["entry_px"] = trades_df["entry_px"].astype(float)
    if "spread_px" not in trades_df.columns:
        trades_df["spread_px"] = 0.0
    trades_df["spread_px"] = trades_df["spread_px"].astype(float).fillna(0.0)
    trades_df["spread_ret"] = trades_df["spread_px"] / trades_df["entry_px"]

    # one-spread round-trip approximation
    if use_spread and has_spread:
        trades_df["ret_net"] = trades_df["ret_gross"] - trades_df["spread_ret"]
    else:
        trades_df["ret_net"] = trades_df["ret_gross"]

    def apply_perf_gate(trades_df, days, min_trades, ev_min_bps):
        if days <= 0:
            return trades_df

        dfp = trades_df.sort_values("entry_time").reset_index(drop=True).copy()
        dfp["entry_time"] = pd.to_datetime(dfp["entry_time"])
        dfp["ret_net"] = dfp["ret_net"].astype(float)

        ev_min = ev_min_bps / 1e4  # bps -> decimal

        keep = []
        for i, row in dfp.iterrows():
            t = row["entry_time"]
            t0 = t - pd.Timedelta(days=int(days))

            hist = dfp.iloc[:i]
            hist = hist[(hist["entry_time"] >= t0) & (hist["entry_time"] < t)]

            if len(hist) < int(min_trades):
                keep.append(False)
                continue

            ev = hist["ret_net"].mean()
            keep.append(ev >= ev_min)

        return dfp[pd.Series(keep, index=dfp.index)].reset_index(drop=True)

    trades_df = apply_perf_gate(
        trades_df,
        perf_gate_days,
        perf_gate_min_trades,
        perf_gate_ev_min_bps,
    )

    if trades_df.empty:
        raise RuntimeError("All trades filtered out by performance gate.")

    equity = (1.0 + trades_df["ret_net"]).cumprod()
    equity_df = pd.DataFrame(
        {
            "entry_time": trades_df["entry_time"],
            "ret_net": trades_df["ret_net"],
            "equity": equity,
        }
    )

    # Trades/week estimate: use full dataset span (stable even for 1 trade)
    span_days = (pd.to_datetime(df["time"].iloc[-1]) - pd.to_datetime(df["time"].iloc[0])).days
    span_weeks = max(span_days / 7.0, 1e-9)
    trades_per_week = float(len(trades_df) / span_weeks)

    ev_per_trade = float(trades_df["ret_net"].mean())
    winrate = float((trades_df["ret_net"] > 0).mean())
    dd = max_drawdown(equity_df["equity"])

    ev_month = ev_per_trade * trades_per_week * 4.33

    trades_df["year"] = pd.to_datetime(trades_df["entry_time"]).dt.year
    yearly = trades_df.groupby(["year"]).agg(
        trades=("ret_net", "size"),
        ev_trade=("ret_net", "mean"),
        winrate=("ret_net", lambda x: float((x > 0).mean())),
        p5=("ret_net", lambda x: float(np.quantile(x, 0.05))),
        p50=("ret_net", lambda x: float(np.quantile(x, 0.50))),
        p95=("ret_net", lambda x: float(np.quantile(x, 0.95))),
    ).reset_index()

    trades_path = out_dir / "trades.parquet"
    equity_path = out_dir / "equity.csv"
    report_path = out_dir / "report.csv"

    trades_df.to_parquet(trades_path, index=False)
    equity_df.to_csv(equity_path, index=False)

    topline = pd.DataFrame(
        [
            dict(
                symbol=symbol,
                entry_mode=entry_mode,
                mode=mode,
                time_stop_bars=time_stop_bars,
                setup_families=",".join(setup_families),
                side=side,
                trigger_unit=trigger_unit,
                allow_overlapping_trades=bool(allow_overlapping_trades),
                max_positions=int(max_positions),
                use_spread=bool(use_spread and has_spread),
                has_spread_column=bool(has_spread),
                point_size=float(point_size),
                mean_spread_ret=float(trades_df["spread_ret"].mean()) if "spread_ret" in trades_df.columns else 0.0,
                exit_mode=exit_mode,
                arm_state_value=float(arm_state_value),
                catastrophic_sl_bps=float(catastrophic_sl_bps),
                tp_k=float(tp_k),
                sl_k=float(sl_k),
                n_trades=len(trades_df),
                trades_per_week=trades_per_week,
                ev_per_trade=ev_per_trade,
                ev_month_est=ev_month,
                winrate=winrate,
                max_drawdown=dd,
            )
        ]
    )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# TOPLINE\n")
        topline.to_csv(f, index=False)
        f.write("\n# YEARLY\n")
        yearly.to_csv(f, index=False)

    print("[OK] Backtest finished")
    print("  trades:", len(trades_df))
    print("  setup_families:", ",".join(setup_families))
    print("  side:", side)
    print("  trigger_unit:", trigger_unit)
    print("  allow_overlapping_trades:", bool(allow_overlapping_trades), "max_positions:", int(max_positions))
    print("  exit_mode:", exit_mode)
    if exit_mode == "state_change":
        print("  arm_state_value:", float(arm_state_value))
        print("  catastrophic_sl_bps:", float(catastrophic_sl_bps))
    else:
        print(
            "  tp_k:",
            float(tp_k),
            "sl_k:",
            float(sl_k),
            "sigma_source:",
            "ctx_vwap_sigma" if "ctx_vwap_sigma" in df.columns else "bands",
        )
    print("  trades/week:", f"{trades_per_week:.2f}")
    print("  EV/trade:", f"{ev_per_trade:.6f}")
    print("  EV/month(est):", f"{ev_month:.6f}")
    print("  winrate:", f"{winrate:.2%}")
    print("  maxDD:", f"{dd:.2%}")
    if use_spread and has_spread and "spread_ret" in trades_df.columns:
        print("  mean_spread_ret:", f"{float(trades_df['spread_ret'].mean()):.6f}")
    print("  outputs:", str(out_dir))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--enriched_parquet", required=True)
    ap.add_argument("--decisions_csv", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--time_stop_bars", type=int, default=10)
    ap.add_argument("--tp_k", type=float, default=1.5)
    ap.add_argument("--sl_k", type=float, default=1.0)
    ap.add_argument("--entry_mode", default="next_open", choices=["next_open"])
    ap.add_argument("--mode", default="long", choices=["long", "short", "abs_move"])
    ap.add_argument("--use_spread", action="store_true")
    ap.add_argument(
        "--setup_family",
        default="state_reinforcement",
        help="Comma-separated. Default keeps XAU behavior. Example: transition_resolution",
    )
    ap.add_argument("--side", choices=["LONG", "SHORT", "BOTH", "NONE"], default="BOTH")

    # NEW canonical knobs
    ap.add_argument("--trigger_unit", default="episodes", choices=["bars", "episodes"])

    # Backward compatible alias: if you pass --trade_unit it overrides trigger_unit
    ap.add_argument("--trade_unit", default=None, choices=["bars", "episodes"],
                    help="DEPRECATED alias of --trigger_unit (kept for compatibility).")

    ap.add_argument(
        "--exit_mode",
        default="fixed",
        choices=["fixed", "state_change"],
        help="fixed uses TP/SL by sigma; state_change exits on state_hat change after arming.",
    )
    ap.add_argument("--catastrophic_sl_bps", type=float, default=350.0)
    ap.add_argument("--arm_state_value", type=float, default=2.0)

    # NEW: conservative by default
    ap.add_argument("--allow_overlapping_trades", action="store_true",
                    help="If set, allow overlapping trades (stacking) up to --max_positions.")
    ap.add_argument("--max_positions", type=int, default=1)

    ap.add_argument("--perf_gate_days", type=int, default=0)
    ap.add_argument("--perf_gate_min_trades", type=int, default=0)
    ap.add_argument("--perf_gate_ev_min_bps", type=float, default=0.0)
    args = ap.parse_args()

    # alias handling
    trig = args.trigger_unit
    if args.trade_unit is not None:
        trig = args.trade_unit

    main(
        symbol=args.symbol,
        enriched_parquet=args.enriched_parquet,
        decisions_csv=args.decisions_csv,
        out_dir=args.out_dir,
        time_stop_bars=args.time_stop_bars,
        entry_mode=args.entry_mode,
        mode=args.mode,
        use_spread=args.use_spread,
        tp_k=args.tp_k,
        sl_k=args.sl_k,
        setup_family=args.setup_family,
        side=args.side,
        trigger_unit=trig,
        exit_mode=args.exit_mode,
        catastrophic_sl_bps=args.catastrophic_sl_bps,
        arm_state_value=args.arm_state_value,
        perf_gate_days=args.perf_gate_days,
        perf_gate_min_trades=args.perf_gate_min_trades,
        perf_gate_ev_min_bps=args.perf_gate_ev_min_bps,
        allow_overlapping_trades=bool(args.allow_overlapping_trades),
        max_positions=int(args.max_positions),
    )
