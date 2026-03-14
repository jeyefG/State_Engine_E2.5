from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(r"outputs\phase_f_runs\XAUUSD_FINAL\STACKED_COMBO_TP_BARS16_plus_SR_OVERLAY")
OUT.mkdir(parents=True, exist_ok=True)

ENRICHED = r"outputs\phase_f_enriched\phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet"
TRADES   = r"outputs\phase_f_runs\XAUUSD_FINAL\COMBO_TP_BARS16_plus_SR_OVERLAY\trades.parquet"

enr = pd.read_parquet(ENRICHED)[["time", "close"]].copy()
enr["time"] = pd.to_datetime(enr["time"])
enr = enr.sort_values("time").drop_duplicates("time")
enr["r"] = enr["close"].pct_change().fillna(0.0)

tr = pd.read_parquet(TRADES).copy()
tr["entry_time"] = pd.to_datetime(tr["entry_time"])
tr["exit_time"]  = pd.to_datetime(tr["exit_time"])

t_index = pd.Series(np.arange(len(enr)), index=enr["time"])
contrib = np.zeros(len(enr), dtype=float)
r = enr["r"].to_numpy()

for row in tr[["entry_time", "exit_time", "ret_net"]].itertuples(index=False, name=None):
    et, xt, ret = row
    if et not in t_index.index or xt not in t_index.index:
        continue
    a = int(t_index.loc[et])
    b = int(t_index.loc[xt])
    if b <= a:
        continue

    seg = r[a+1:b+1]
    s = float(seg.sum())
    ret = float(ret)

    if abs(s) > 1e-12:
        contrib[a+1:b+1] += (ret / s) * seg
    else:
        contrib[a+1:b+1] += ret / float(b - a)

eq = np.cumprod(1.0 + contrib)
dd = eq / np.maximum.accumulate(eq) - 1.0

pd.DataFrame(
    {"time": enr["time"].values, "contrib": contrib, "equity": eq, "dd": dd}
).to_csv(OUT / "equity_stacked.csv", index=False)

print("saved", OUT)
print("n_trades", len(tr))
print("MaxDD", float(dd.min()))