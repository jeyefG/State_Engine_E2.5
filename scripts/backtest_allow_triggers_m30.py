# scripts/backtest_allow_triggers_m30.py
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from state_engine.mt5_connector import MT5Connector


def to_server_naive_datetime(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce", utc=False)
    try:
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
    except Exception:
        pass
    return dt


def build_allow_episodes_from_decisions(dec: pd.DataFrame) -> pd.DataFrame:
    """
    Episodes are contiguous ALLOW regions in H2 grid (by ts).
    We use decisions_with_side.csv rows (same ts grid) and build episodes from decision==ALLOW.
    """
    dec = dec.sort_values(["symbol", "ts"]).reset_index(drop=True)
    is_allow = dec["decision"].astype(str).str.upper().eq("ALLOW")

    prev_allow = is_allow.shift(1, fill_value=False)
    prev_sym = dec["symbol"].shift(1)
    new_sym = dec["symbol"].ne(prev_sym)

    start = is_allow & (~prev_allow | new_sym)
    episode_id = start.cumsum()

    dec["episode_id"] = np.where(is_allow, episode_id, np.nan)
    dec_allow = dec[is_allow].copy()

    ep = dec_allow.groupby(["symbol", "episode_id"], as_index=False).agg(
        t0=("ts", "min"),
        t_last=("ts", "max"),
        n_h2_allow=("ts", "size"),
    )
    ep["episode_id"] = ep["episode_id"].astype(int)
    return ep


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min())


def compute_m30_features(m30: pd.DataFrame, range_window: int = 6):
    """
    Compute chop range position (0..1) using rolling high/low over last range_window bars.
    """
    hi = m30["high"].astype(float).rolling(range_window, min_periods=range_window).max()
    lo = m30["low"].astype(float).rolling(range_window, min_periods=range_window).min()
    denom = (hi - lo).replace(0, np.nan)
    pos = (m30["close"].astype(float) - lo) / denom
    m30["range_pos"] = pos.clip(0, 1)
    m30["range_hi"] = hi
    m30["range_lo"] = lo
    return m30


def find_trigger_trend_continuation(m30: pd.DataFrame, side: str, lookback: int = 3) -> int | None:
    """
    Trigger = BOS: close breaks rolling max/min of previous lookback bars.
    Returns index (row position) of trigger bar in m30 dataframe.
    """
    if len(m30) < lookback + 1:
        return None

    highs = m30["high"].astype(float)
    lows = m30["low"].astype(float)
    closes = m30["close"].astype(float)

    prev_roll_max = highs.shift(1).rolling(lookback, min_periods=lookback).max()
    prev_roll_min = lows.shift(1).rolling(lookback, min_periods=lookback).min()

    if side == "LONG":
        cond = closes > prev_roll_max
    else:
        cond = closes < prev_roll_min

    idxs = np.where(cond.fillna(False).values)[0]
    return int(idxs[0]) if len(idxs) else None


def find_trigger_chop_extreme_reject(m30: pd.DataFrame, side: str, extreme_th: float = 0.2) -> int | None:
    """
    Trigger = at range extreme + rejection candle.
    LONG: range_pos <= 0.2 and close > open
    SHORT: range_pos >= 0.8 and close < open
    """
    if "range_pos" not in m30.columns:
        return None

    rp = m30["range_pos"].astype(float)
    o = m30["open"].astype(float)
    c = m30["close"].astype(float)

    if side == "LONG":
        cond = (rp <= extreme_th) & (c > o)
    else:
        cond = (rp >= (1.0 - extreme_th)) & (c < o)

    idxs = np.where(cond.fillna(False).values)[0]
    return int(idxs[0]) if len(idxs) else None


def simulate_exit(m30: pd.DataFrame, i_entry: int, mode: str, time_stop_bars: int = 6) -> tuple[int, str]:
    """
    Returns (i_exit, exit_reason)
    mode:
      - "trend": exit by time-stop only
      - "chop": exit when range_pos crosses 0.5 or time-stop
    """
    i_last = min(i_entry + time_stop_bars - 1, len(m30) - 1)

    if mode == "trend":
        return i_last, "time_stop"

    # chop
    rp = m30["range_pos"].astype(float).values
    # search from entry to i_last for first cross to center
    for j in range(i_entry, i_last + 1):
        if np.isfinite(rp[j]) and rp[j] >= 0.5 and rp[i_entry] <= 0.5:
            return j, "to_center"
        if np.isfinite(rp[j]) and rp[j] <= 0.5 and rp[i_entry] >= 0.5:
            return j, "to_center"
    return i_last, "time_stop"


def main(
    symbol: str,
    decisions_with_side_csv: str,
    enriched_h2_parquet: str,
    out_dir: str,
    m30_time_stop: int = 6,
    lookback_breakout: int = 3,
    range_window: int = 6,
    extreme_th: float = 0.2,
    use_spread: bool = True,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dec = pd.read_csv(decisions_with_side_csv)
    if "symbol" not in dec.columns:
        dec["symbol"] = symbol
    dec = dec[dec["symbol"] == symbol].copy()
    dec["ts"] = to_server_naive_datetime(dec["ts"])
    dec = dec.sort_values("ts").reset_index(drop=True)

    # Load H2 enriched to locate "next H2" window boundaries
    h2 = pd.read_parquet(enriched_h2_parquet)
    h2 = h2[h2["symbol"] == symbol].copy()
    h2["time"] = to_server_naive_datetime(h2["time"])
    h2 = h2.sort_values("time").reset_index(drop=True)
    h2_time_to_idx = pd.Series(h2.index.values, index=h2["time"].values)

    episodes = build_allow_episodes_from_decisions(dec)
    if episodes.empty:
        raise RuntimeError("No ALLOW episodes found.")

    mt5 = MT5Connector()

    trades = []
    missing_windows = 0
    no_trigger = 0

    for _, ep in episodes.iterrows():
        t0 = ep["t0"]
        # execution window = next H2 bar after t0
        if t0 not in h2_time_to_idx.index:
            missing_windows += 1
            continue
        i0 = int(h2_time_to_idx.loc[t0])
        if i0 + 1 >= len(h2):
            continue
        t_exec_start = h2.loc[i0 + 1, "time"]
        t_exec_end = t_exec_start + pd.Timedelta(hours=2)

        # Determine dominant setup_family + side_intent within episode (use first row at t0)
        row0 = dec.loc[dec["ts"] == t0]
        if row0.empty:
            missing_windows += 1
            continue
        setup_family = str(row0.iloc[0].get("setup_family", "none"))
        side_intent = str(row0.iloc[0].get("side_intent", "NONE"))

        # side candidates
        if side_intent == "NONE":
            continue
        if side_intent == "BOTH":
            sides = ["LONG", "SHORT"]
        else:
            sides = [side_intent]

        # pull M30 bars for execution window
        m30 = mt5.obtener_ohlcv(symbol, "M30", t_exec_start, t_exec_end)
        if isinstance(m30.index, pd.DatetimeIndex):
            m30 = m30.reset_index().rename(columns={m30.index.name or "index": "time"})
        m30["time"] = to_server_naive_datetime(m30["time"])
        m30 = m30.sort_values("time").reset_index(drop=True)

        if m30.empty:
            missing_windows += 1
            continue

        m30 = compute_m30_features(m30, range_window=range_window)

        # Choose trigger function based on setup_family
        # Minimal mapping:
        # - trend_* => trend_continuation trigger
        # - balance_chop / transition_*_chop => chop trigger
        is_trend = setup_family.startswith("trend_")
        is_chop = ("chop" in setup_family) or setup_family.startswith("balance_") or setup_family.startswith("transition_")

        best_trade = None

        for side in sides:
            if is_trend:
                i_trig = find_trigger_trend_continuation(m30, side=side, lookback=lookback_breakout)
                if i_trig is None:
                    continue
                i_entry = i_trig
                i_exit, exit_reason = simulate_exit(m30, i_entry, mode="trend", time_stop_bars=m30_time_stop)
            else:
                # default to chop trigger
                i_trig = find_trigger_chop_extreme_reject(m30, side=side, extreme_th=extreme_th)
                if i_trig is None:
                    continue
                i_entry = i_trig
                i_exit, exit_reason = simulate_exit(m30, i_entry, mode="chop", time_stop_bars=m30_time_stop)

            entry_time = m30.loc[i_entry, "time"]
            exit_time = m30.loc[i_exit, "time"]
            entry_px = float(m30.loc[i_entry, "close"])  # conservative
            exit_px = float(m30.loc[i_exit, "close"])

            if entry_px <= 0 or not np.isfinite(entry_px) or not np.isfinite(exit_px):
                continue

            # returns
            if side == "LONG":
                ret_gross = (exit_px - entry_px) / entry_px
            else:
                ret_gross = (entry_px - exit_px) / entry_px

            # costs
            cost_ret = 0.0
            has_spread = "spread" in m30.columns
            if use_spread and has_spread:
                sp_e = float(m30.loc[i_entry, "spread"])
                sp_x = float(m30.loc[i_exit, "spread"])
                if np.isfinite(sp_e) and np.isfinite(sp_x):
                    # directional half+half
                    cost_ret = ((sp_e / 2.0) + (sp_x / 2.0)) / entry_px

            ret_net = ret_gross - cost_ret

            candidate = dict(
                symbol=symbol,
                episode_id=int(ep["episode_id"]),
                t0=t0,
                exec_start=t_exec_start,
                setup_family=setup_family,
                side=side,
                side_intent=side_intent,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_px=entry_px,
                exit_px=exit_px,
                ret_gross=ret_gross,
                cost_ret=cost_ret,
                ret_net=ret_net,
                exit_reason=exit_reason,
                trig_index=int(i_trig),
            )

            # For BOTH, we must not "pick the best by pnl" (p-hacking).
            # Deterministic tie-break: pick earliest trigger (first in time), and if equal, LONG first.
            if best_trade is None:
                best_trade = candidate
            else:
                if candidate["entry_time"] < best_trade["entry_time"]:
                    best_trade = candidate
                elif candidate["entry_time"] == best_trade["entry_time"]:
                    # deterministic: LONG before SHORT
                    if best_trade["side"] == "SHORT" and candidate["side"] == "LONG":
                        best_trade = candidate

        if best_trade is None:
            no_trigger += 1
            continue

        trades.append(best_trade)

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        raise RuntimeError("No trades produced (no triggers found).")

    trades_df = trades_df.sort_values("entry_time").reset_index(drop=True)

    equity = (1.0 + trades_df["ret_net"]).cumprod()
    equity_df = pd.DataFrame({"entry_time": trades_df["entry_time"], "ret_net": trades_df["ret_net"], "equity": equity})

    span_days = (equity_df["entry_time"].iloc[-1] - equity_df["entry_time"].iloc[0]).days
    span_weeks = max(span_days / 7.0, 1e-9)
    trades_per_week = float(len(trades_df) / span_weeks)

    ev_per_trade = float(trades_df["ret_net"].mean())
    winrate = float((trades_df["ret_net"] > 0).mean())
    dd = max_drawdown(equity_df["equity"])
    ev_month = ev_per_trade * trades_per_week * 4.33

    # year summary
    trades_df["year"] = pd.to_datetime(trades_df["entry_time"]).dt.year
    yearly = trades_df.groupby("year").agg(
        trades=("ret_net", "size"),
        ev_trade=("ret_net", "mean"),
        winrate=("ret_net", lambda x: float((x > 0).mean())),
    ).reset_index()

    # setup summary
    setup_sum = trades_df.groupby(["setup_family", "side"]).agg(
        trades=("ret_net", "size"),
        ev_trade=("ret_net", "mean"),
        winrate=("ret_net", lambda x: float((x > 0).mean())),
    ).reset_index().sort_values("trades", ascending=False)

    out_trades = out_dir / "trades.parquet"
    out_equity = out_dir / "equity.csv"
    out_report = out_dir / "report.csv"

    trades_df.to_parquet(out_trades, index=False)
    equity_df.to_csv(out_equity, index=False)

    topline = pd.DataFrame([dict(
        symbol=symbol,
        n_episodes=int(episodes.shape[0]),
        n_trades=int(trades_df.shape[0]),
        pct_episodes_traded=float(trades_df.shape[0] / episodes.shape[0]),
        trades_per_week=trades_per_week,
        ev_per_trade=ev_per_trade,
        ev_month_est=ev_month,
        winrate=winrate,
        max_drawdown=dd,
        missing_windows=int(missing_windows),
        no_trigger=int(no_trigger),
        m30_time_stop=m30_time_stop,
        lookback_breakout=lookback_breakout,
        range_window=range_window,
        extreme_th=extreme_th,
        use_spread=use_spread and ("spread" in trades_df.columns if not trades_df.empty else False),
    )])

    with open(out_report, "w", encoding="utf-8") as f:
        f.write("# TOPLINE\n")
        topline.to_csv(f, index=False)
        f.write("\n# YEARLY\n")
        yearly.to_csv(f, index=False)
        f.write("\n# SETUP_SUMMARY\n")
        setup_sum.to_csv(f, index=False)

    print("[OK] Backtest triggers M30 finished")
    print("  episodes:", int(episodes.shape[0]))
    print("  trades:", int(trades_df.shape[0]), f"({(trades_df.shape[0]/episodes.shape[0]):.2%} episodes traded)")
    print("  trades/week:", f"{trades_per_week:.2f}")
    print("  EV/trade:", f"{ev_per_trade:.6f}")
    print("  EV/month(est):", f"{ev_month:.6f}")
    print("  winrate:", f"{winrate:.2%}")
    print("  maxDD:", f"{dd:.2%}")
    print("  missing_windows:", missing_windows, " no_trigger:", no_trigger)
    print("  outputs:", str(out_dir))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--decisions_with_side_csv", required=True)
    ap.add_argument("--enriched_h2_parquet", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--m30_time_stop", type=int, default=6)
    ap.add_argument("--lookback_breakout", type=int, default=3)
    ap.add_argument("--range_window", type=int, default=6)
    ap.add_argument("--extreme_th", type=float, default=0.2)
    ap.add_argument("--use_spread", action="store_true")
    args = ap.parse_args()

    main(
        symbol=args.symbol,
        decisions_with_side_csv=args.decisions_with_side_csv,
        enriched_h2_parquet=args.enriched_h2_parquet,
        out_dir=args.out_dir,
        m30_time_stop=args.m30_time_stop,
        lookback_breakout=args.lookback_breakout,
        range_window=args.range_window,
        extreme_th=args.extreme_th,
        use_spread=args.use_spread,
    )
