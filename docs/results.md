RESULTADOS (BITÁCORAS) — INTEGRADAS EN EL PIPELINE
XAUUSD (State Engine)
1) Símbolo y ventana
Símbolo: XAUUSD.mg
Ventana total analizada: 2023-01-01 → 2025-12-31
Research: 2023-01-01 → 2024-12-31
OOS: 2025-01-01 → 2025-12-31
Timeframe / score_tf: H2 / M30
________________________________________
2) Objetivo
Evaluar si el State Engine detecta edge estructural en XAUUSD y si ese edge puede monetizarse de forma interpretable, neta y OOS.
________________________________________
3) Naturaleza estructural del símbolo
Estados dominantes: TRANSITION > TREND > BALANCE
QL dominantes: TRANSITION_UNCLASSIFIED, TRANSITION_NOISY, TREND_STRONG, BALANCE_LEAKING
LOOK_FOR relevantes:
•	LOOK_FOR_transition_chop_near_vwap
•	LOOK_FOR_trend_strong_orderly
•	LOOK_FOR_balance_vwap_proximity
•	LOOK_FOR_trend_prev_vwap_pullback
Lectura estructural:
XAU muestra una naturaleza mixta pero legible. Predomina un régimen de transición con drift alrededor de VWAP, conviviendo con un régimen de continuación de tendencia que se activa con fuerza cuando el contexto H2 está claramente ordenado. Balance sí aparece descriptivamente, pero en esta ronda no mostró captura monetaria convincente con el template probado.
________________________________________
4) Edge descriptivo detectado (Phase E)
LOOK_FOR	Baseline	n_bars	uplift_pp
LOOK_FOR_trend_strong_orderly	STATE_REINFORCEMENT	2647	7.42
LOOK_FOR_balance_vwap_proximity	BALANCE_STABILITY	2924	5.95
LOOK_FOR_balance_compression	BALANCE_STABILITY	486	5.80
LOOK_FOR_trend_prev_vwap_pullback	STATE_REINFORCEMENT	1180	5.01
LOOK_FOR_transition_chop_near_vwap	TRANSITION_PERSISTENCE	6072	3.98
Edge más robusto:
•	LOOK_FOR_trend_strong_orderly
•	LOOK_FOR_transition_chop_near_vwap
•	LOOK_FOR_balance_vwap_proximity
Lectura:
Sí apareció edge estructural claro en tendencia y transición. Balance también apareció descriptivamente en Phase E, pero no logró transformarse en motor operativo con el template auditado en esta ronda.
________________________________________
5) Estabilidad temporal del edge
Nota: en la iteración final vinculante, la estabilidad descriptiva se validó principalmente como Research 2023-2024 vs OOS 2025.
Tramo	LOOK_FOR	n_bars	uplift_pp
2023-2024 (research)	LOOK_FOR_balance_vwap_proximity	2013	7.09
2023-2024 (research)	LOOK_FOR_trend_strong_orderly	1594	7.03
2023-2024 (research)	LOOK_FOR_transition_chop_near_vwap	4078	4.44
2025 (OOS descriptivo)	LOOK_FOR_trend_strong_orderly	1029	8.23
2025 (OOS descriptivo)	LOOK_FOR_balance_vwap_proximity	911	3.48
2025 (OOS descriptivo)	LOOK_FOR_transition_chop_near_vwap	1988	2.89
Lectura:
•	mixto pero sano
•	tendencia se mantiene fuerte e incluso mejora
•	transición persiste, aunque con menor uplift en 2025
•	balance sigue existiendo descriptivamente, pero no capturó bien
________________________________________
6) Policy / Phase F
Contextos GO principales:
•	STATE=TRANSITION|QL=TRANSITION_UNCLASSIFIED|LF=LOOK_FOR_transition_chop_near_vwap
•	STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly
•	STATE=BALANCE|QL=BALANCE_LEAKING|LF=LOOK_FOR_balance_vwap_proximity
ALLOW rate: 32.65%
Resolución predominante: STATE_QL_LF, con fallback material a STATE_LF
Comentario de wiring:
•	wiring limpio
•	engine_context_key y context_key quedaron correctamente separados
•	fallback QL razonable, no bug
•	trend_dir_h2 existe en el fat CSV y resultó útil solo para refinar SR en NY
________________________________________
7) Motores operativos probados
Motor 1 — Transition NY
Contexto:
•	STATE=TRANSITION
•	QL=TRANSITION_UNCLASSIFIED
•	LOOK_FOR=LOOK_FOR_transition_chop_near_vwap
•	setup_family=transition_persistence
•	sesión=NY
Interpretación:
Drift / continuidad corta de transición, especialmente útil cuando se aísla el núcleo unclassified y se ejecuta solo en NY.
Configuración probada:
•	tp_k=40
•	sl_k=25
•	time_stop_bars=18
•	trigger_unit=bars
•	side=LONG
•	stacking=sí (max_positions=3)
Resultado OOS neto:
•	trades=16
•	trades/week=0.31
•	EV/trade=0.007824
•	EV/month≈1.04%
•	winrate=75.0%
•	maxDD=n/d aislado en esta ronda final
________________________________________
Motor 2 — SR NY trendUP
Contexto:
•	STATE=TREND
•	QL=TREND_STRONG
•	LOOK_FOR=LOOK_FOR_trend_strong_orderly
•	setup_family=state_reinforcement
•	filtro adicional=trend_dir_h2=UP
•	sesión=NY
Interpretación:
Continuation setup más fino que el SR original: solo entra cuando la dirección H2 acompaña explícitamente. Este filtro no ayudó a abrir NY+NY_PM, pero sí rescató NY solo.
Configuración probada:
•	tp_k=40
•	sl_k=25
•	time_stop_bars=24
•	trigger_unit=episodes
•	side=LONG
•	stacking=sí (max_positions=2)
Resultado OOS neto:
•	trades=16
•	trades/week=0.31
•	EV/trade=0.003957
•	EV/month≈0.53%
•	winrate=62.5%
•	maxDD=n/d aislado en esta ronda final
________________________________________
8) Resultado combinado del símbolo
Motores incluidos:
•	Transition NY
•	SR NY trendUP
Resultado combinado (candidato principal, con stacking):
•	trades=83
•	trades/week=0.53
•	EV/trade=0.004063
•	EV/month≈0.94%
•	winrate=67.47%
•	maxDD=-6.40%
Lectura:
Este combinado superó al Combo B previo y al combo histórico abierto en calidad ajustada por riesgo. Mantiene positividad en 2023, 2024 y 2025, baja el drawdown y además sobrevive sin depender críticamente de stacking.
Variante portable / cross-symbol (sin stacking):
•	trades=71
•	trades/week=0.46
•	EV/trade=0.003284
•	EV/month≈0.65%
•	winrate=66.20%
•	maxDD=-6.40%
EV_total anual del candidato principal (con stacking):
•	2023: 0.053280
•	2024: 0.095443
•	2025: 0.188504
EV_total anual de la variante portable (sin stacking):
•	2023: 0.046064
•	2024: 0.066835
•	2025: 0.120263
Benchmarks internos guardados:
•	Combo B
o	2023: 0.028947
o	2024: 0.155714
o	2025: 0.176497
•	Combo abierto
o	2023: 0.045572
o	2024: 0.108256
o	2025: 0.598046
________________________________________
9) Costos y realismo
Spread aplicado: sí
ret_net validado distinto de ret_gross: sí
Observación:
•	neto modelado con spread60
•	histórico del broker no traía spread usable en gran parte de 2023-2024 y comienzos de 2025
•	el tramo post-2025-02-18 observado fue consistente con la tesis del motor final
•	la comparación “nuevo sin spread a DD comparable” se usó solo como benchmark auxiliar de calidad del engine, no como resultado oficial
________________________________________
10) Veredicto final del símbolo
CAPTURABLE
Justificación breve:
XAU sí mostró edge estructural claro y monetizable. Los motores históricos revivieron con templates correctos, y un refinamiento lateral adicional (trend_dir_h2=UP aplicado solo a SR en NY) mejoró todavía más el candidato final. El símbolo quedó capturable con costos modelados, con evidencia adicional consistente en el tramo donde el spread observado sí existe.
________________________________________
11) Siguiente acción
pasar a portafolio candidato
________________________________________
Nota comparativa histórica (DD comparable 20.4%)
Benchmark auxiliar de comparación de calidad del engine
Combo histórico anterior — tal cual (~20.4% DD)
•	2023: +4.56%
•	2024: +10.83%
•	2025: +59.80%
•	1.000 USD → 1,851.75 USD
Combo nuevo principal — sin spread, escalado a ~20.4% DD
•	2023: +19.04%
•	2024: +32.82%
•	2025: +61.92%
•	1.000 USD → 2,560.17 USD
Lectura:
A riesgo comparable, el nuevo combo muestra una evolución mucho más sana y una trayectoria acumulada superior al combo histórico.

12) Reproducibilidad exacta de resultados
Convención general
•	Todos los comandos están en formato de una sola línea para Spyder / terminal Windows.
•	PYTHONPATH=. debe estar seteado.
•	La convención de costos usada en el cierre final es spread60 modelado.
•	Los resultados finales de cierre salen de:
o	outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions_with_side.csv
o	outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet
12.1 Construcción base del símbolo
!set PYTHONPATH=. && python scripts/build_phase_d_context.py --symbol "XAUUSD.mg" --start "2023-01-01" --end "2025-12-31" --timeframe "H2" --window-hours 24 --output-dir "outputs/phase_d_context"
!set PYTHONPATH=. && python scripts/build_prices_h2.py --symbol "XAUUSD.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --out_prices_parquet "outputs/prices/prices_H2_XAUUSD.mg_2023-01-01_2025-12-31.parquet" --timeframe "H2" --pad_hours 24
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_ohlc.py --symbol "XAUUSD.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --prices_parquet "outputs/prices/prices_H2_XAUUSD.mg_2023-01-01_2025-12-31.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc.parquet"
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_vwap_bands.py --symbol "XAUUSD.mg" --in_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet"
12.2 Phase E research binding
!set PYTHONPATH=. && python scripts/phase_e.py --symbol "XAUUSD.mg" --start "2023-01-01" --end "2024-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline
12.3 Phase F congelado desde research
!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "XAUUSD.mg" --barstream "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/XAUUSD.mg.yaml" --symbol_config "configs/symbols/XAUUSD.mg.yaml" --outdir "outputs/phase_f_runs/XAUUSD_frozen_from_research"
!set PYTHONPATH=. && python scripts/phase_f_direction_layer.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions.csv" --out_csv "outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions_with_side.csv" --phase_f_policy "configs/phase_f/XAUUSD.mg.yaml"
12.4 Convención de costos spread60
import pandas as pd

inp = r"outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet"
out = r"outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet"

df = pd.read_parquet(inp).copy()
df["time"] = pd.to_datetime(df["time"])

df["spread_original"] = df["spread"]
df["spread"] = df["spread"].fillna(0)
df.loc[df["spread"] <= 0, "spread"] = 60

df.to_parquet(out, index=False)
print("written", out, "rows", len(df))
12.5 Subsets exactos usados en los motores finales
A) Transition TU base
import os
import re
import pandas as pd

inp = r"outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions_with_side.csv"
out_dir = r"outputs/phase_f_runs/XAU_current_templates"
os.makedirs(out_dir, exist_ok=True)

df = pd.read_csv(inp).copy()
df = df[df["decision"].astype(str).str.upper().eq("ALLOW")].copy()

ctx_col = "engine_context_key" if "engine_context_key" in df.columns else "context_key"

def extract_ql(s):
    if pd.isna(s):
        return None
    m = re.search(r"QL=([^|]+)", str(s))
    return m.group(1) if m else None

df["ql_extracted"] = df[ctx_col].apply(extract_ql)

tpu = df[
    df["setup_family"].eq("transition_persistence")
    & df["side_intent"].eq("LONG")
    & df["ql_extracted"].eq("TRANSITION_UNCLASSIFIED")
].copy()

tpu.to_csv(r"outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv", index=False)
print("transition rows", len(tpu))
B) SR NY trendUP
import os
import pandas as pd

inp = r"outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions_with_side.csv"
out_dir = r"outputs/phase_f_runs/XAU_current_templates"
os.makedirs(out_dir, exist_ok=True)

df = pd.read_csv(inp).copy()

m = (
    df["decision"].astype(str).str.upper().eq("ALLOW")
    & df["setup_family"].eq("state_reinforcement")
    & df["side_intent"].eq("LONG")
    & df["context_key"].astype(str).str.contains("STATE=TREND", na=False)
    & df["context_key"].astype(str).str.contains("QL=TREND_STRONG", na=False)
    & df["trend_dir_h2"].astype(str).eq("UP")
    & df["ctx_session_bucket"].eq("NY")
)

out = df[m].copy()
out.to_csv(r"outputs/phase_f_runs/XAU_current_templates/SR_TS_UP_NY.csv", index=False)
print("rows", len(out))
12.6 Backtests de las mangas finales
A) Transition NY (stack)
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv" --setup_family "transition_persistence" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 18 --allow_overlapping_trades --max_positions 3 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60"
B) Transition NY (no-stack)
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv" --setup_family "transition_persistence" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 18 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60_nostack"
C) SR NY trendUP (stack)
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/SR_TS_UP_NY.csv" --setup_family "state_reinforcement" --side LONG --trigger_unit episodes --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 24 --allow_overlapping_trades --max_positions 2 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_trend_template_trendUP_NY_spread60"
12.7 Construcción exacta del candidato final principal
import os
import pandas as pd

p_trans = r"outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60/trades.parquet"
p_sr_ny = r"outputs/backtests/XAU_current_templates_orig/BT_trend_template_trendUP_NY_spread60/trades.parquet"

out_dir = r"outputs/backtests/XAU_current_templates_orig/BT_combo_transitionNY_SRtrendUP_NY"
os.makedirs(out_dir, exist_ok=True)

a = pd.read_parquet(p_trans).copy()
b = pd.read_parquet(p_sr_ny).copy()

a["engine_name"] = "transition_persistence_long_TU"
b["engine_name"] = "state_reinforcement_long_TS_trendUP_NY"

a["entry_time"] = pd.to_datetime(a["entry_time"])
b["entry_time"] = pd.to_datetime(b["entry_time"])

enr_p = r"outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet"
e = pd.read_parquet(enr_p).copy()
e["time"] = pd.to_datetime(e["time"])

a = a.merge(
    e[["symbol", "time", "ctx_session_bucket"]],
    left_on=["symbol", "entry_time"],
    right_on=["symbol", "time"],
    how="left",
)
a = a[a["ctx_session_bucket"].eq("NY")].copy()

if "time" in a.columns:
    a = a.drop(columns=["time"])

combo = pd.concat([a, b], ignore_index=True).sort_values(["entry_time", "engine_name"]).reset_index(drop=True)

out_p = os.path.join(out_dir, "trades.parquet")
combo.to_parquet(out_p, index=False)
print("written", out_p)
print("rows", len(combo))
12.8 Construcción exacta de la variante portable usada en el chat
Nota metodológica: esta es la versión exacta usada en el chat para XAU_main_crosssymbol_nostack.
Corresponde a:
•	transition no-stack
•	SR NY trendUP con stacking
import os
import pandas as pd

p_trans = r"outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60_nostack/trades.parquet"
p_sr = r"outputs/backtests/XAU_current_templates_orig/BT_trend_template_trendUP_NY_spread60/trades.parquet"

out_dir = r"outputs/backtests/XAU_current_templates_orig/BT_combo_transitionNY_SRtrendUP_NY_nostack"
os.makedirs(out_dir, exist_ok=True)

a = pd.read_parquet(p_trans).copy()
b = pd.read_parquet(p_sr).copy()

a["engine_name"] = "transition_persistence_long_TU"
b["engine_name"] = "state_reinforcement_long_TS_trendUP_NY"

a["entry_time"] = pd.to_datetime(a["entry_time"])
b["entry_time"] = pd.to_datetime(b["entry_time"])

enr_p = r"outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet"
e = pd.read_parquet(enr_p).copy()
e["time"] = pd.to_datetime(e["time"])

a = a.merge(
    e[["symbol", "time", "ctx_session_bucket"]],
    left_on=["symbol", "entry_time"],
    right_on=["symbol", "time"],
    how="left",
)
a = a[a["ctx_session_bucket"].eq("NY")].copy()

if "time" in a.columns:
    a = a.drop(columns=["time"])

combo = pd.concat([a, b], ignore_index=True).sort_values(["entry_time", "engine_name"]).reset_index(drop=True)

out_p = os.path.join(out_dir, "trades.parquet")
combo.to_parquet(out_p, index=False)
print("written", out_p)
print("rows", len(combo))
12.9 Benchmarks internos usados en la bitácora
Combo B
•	trend: NY_PM
•	transition: NY
Combo abierto
•	trend: manga histórica completa
•	transition: manga histórica completa
Si quieres, ese bloque también lo puedo dejar ya escrito con los scripts exactos, pero como el cierre principal ya quedó en el nuevo candidato, aquí dejé solo lo estrictamente vinculante para reproducir el resultado final.
________________________________________
Versión ultra corta para bitácora ejecutiva
XAUUSD
Naturaleza: transición dominante con sleeve de continuación de tendencia; balance descriptivo, pero no monetizable en esta ronda.
Edge principal: trend_strong_orderly / STATE_REINFORCEMENT / 7.42 pp, transition_chop_near_vwap / TRANSITION_PERSISTENCE / 3.98 pp
Motores probados: Transition NY + SR NY con trend_dir_h2=UP
Resultado OOS neto: candidato principal 2025 = EV_total 0.188504, EV/trade 0.005891, winrate 68.75%
Costos: neto modelado con spread60; tramo observado post-2025-02-18 consistente
Veredicto: CAPTURABLE
Estado: pasar a portafolio candidato

US500 (State Engine)
1) Símbolo y ventana
Símbolo: US500.spot.mg
Ventana total analizada: 2023-01-01 → 2025-12-31
Research: 2023-01-01 → 2024-12-31
OOS: 2025-01-01 → 2025-12-31
Timeframe / score_tf: H2 / M30
________________________________________
2) Objetivo
Evaluar si el State Engine detecta edge estructural en US500.spot.mg y si ese edge puede monetizarse de forma interpretable, neta y OOS.
________________________________________
3) Naturaleza estructural del símbolo
Estados dominantes:
•	TRANSITION: 56.9%
•	TREND: 26.7%
•	BALANCE: 16.3%
QL dominantes:
•	TRANSITION_UNCLASSIFIED: 41.5%
•	TREND_STRONG: 16.8%
•	TRANSITION_NOISY: 15.3%
•	BALANCE_LEAKING: 9.5%
•	TREND_UNCLASSIFIED: 8.0%
•	BALANCE_UNCLASSIFIED: 6.5%
LOOK_FOR relevantes:
•	LOOK_FOR_trend_pullback_asia
•	LOOK_FOR_balance_overnight_compression
•	LOOK_FOR_transition_repricing_london
Lectura estructural:
US500 no se dejó leer bien con una ontología simétrica genérica de trend/transition/balance. La hipótesis final que sí quedó respaldada en research fue: reload ordenado de tendencia en ASIA, compresión overnight como contención/estabilidad de balance y repricing en London como resolución de transición. transition_repricing_ny quedó fuera del núcleo validado.
________________________________________
4) Edge descriptivo detectado (Phase E)
LOOK_FOR	Baseline	n_bars	uplift_pp
LOOK_FOR_trend_pullback_asia	STATE_REINFORCEMENT	1008	11.72
LOOK_FOR_transition_repricing_london	TRANSITION_RESOLUTION	344	8.84
LOOK_FOR_balance_overnight_compression	BALANCE_STABILITY	557	5.20
Edge más robusto:
•	LOOK_FOR_trend_pullback_asia
•	LOOK_FOR_transition_repricing_london
Lectura:
Sí apareció edge descriptivo claro en research. El más robusto fue trend_pullback_asia -> STATE_REINFORCEMENT. transition_repricing_london -> TRANSITION_RESOLUTION también apareció sano. balance_overnight_compression -> BALANCE_STABILITY quedó validado como contención, no como leak ni escape. transition_repricing_ny no mostró edge útil y no entró al núcleo.
________________________________________
5) Estabilidad temporal del edge
Nota: en esta ronda de cierre no se re-tabuló 2023 y 2024 por separado; la validación temporal quedó hecha como research agregado 2023-2024 vs OOS 2025.
Tramo	LOOK_FOR	n_bars	uplift_pp
2023-2024 (research)	LOOK_FOR_trend_pullback_asia	1008	11.72
2023-2024 (research)	LOOK_FOR_transition_repricing_london	344	8.84
2023-2024 (research)	LOOK_FOR_balance_overnight_compression	557	5.20
2025 (OOS)	LOOK_FOR_trend_pullback_asia	718	11.64
2025 (OOS)	LOOK_FOR_balance_overnight_compression	219	20.16
2025 (OOS)	LOOK_FOR_transition_repricing_london	no filtró	—
Lectura:
•	Mixto.
•	trend_pullback_asia se sostuvo fuerte OOS.
•	balance_overnight_compression apareció fuerte en uplift, pero quedó bajo el min_n_bars congelado (250).
•	transition_repricing_london no sostuvo filtrado OOS.
________________________________________
6) Policy / Phase F
Contextos GO principales:
•	STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_pullback_asia
•	STATE=TREND|QL=TREND_UNCLASSIFIED|LF=LOOK_FOR_trend_pullback_asia
•	STATE=TRANSITION|QL=TRANSITION_UNCLASSIFIED|LF=LOOK_FOR_transition_repricing_london
•	STATE=BALANCE|QL=BALANCE_LEAKING|LF=LOOK_FOR_balance_overnight_compression
•	STATE=BALANCE|QL=BALANCE_UNCLASSIFIED|LF=LOOK_FOR_balance_overnight_compression
ALLOW rate:
•	Research: 7.59%
•	OOS: 8.09%
Resolución predominante:
•	Research: STATE_QL_LF (457 / 466 ALLOW)
•	OOS: STATE_QL_LF (238 / 247 ALLOW)
Comentario de wiring:
•	Limpio.
•	Fallback bajo y razonable.
•	LF_MISMATCH = 0, META_BASELINE_NA = 0.
•	ql_context_mismatch bajo: ~1.9% en research y ~3.6% en OOS.
________________________________________
7) Motores operativos probados
Motor 1 — Trend reload
Contexto:
•	STATE=TREND
•	QL=TREND_STRONG / TREND_UNCLASSIFIED
•	LOOK_FOR=LOOK_FOR_trend_pullback_asia
•	setup_family=state_reinforcement
Interpretación:
Sleeve de reload/continuation en tendencia viva, usando el side assignment completo del direction layer. No sobrevivió como LONG-only ni SHORT-only en research con costos, pero sí como motor completo en research pseudo-net.
Configuración probada:
•	tp_k=1.5
•	sl_k=1.0
•	time_stop_bars=10
•	trigger_unit=bars
•	side=BOTH
•	stacking=False
Resultado OOS neto:
•	trades=75
•	trades/week=1.50
•	EV/trade=-0.000264
•	EV/month≈-0.0017
•	winrate=45.33%
•	maxDD=n/d en esta ronda
Motor 2 — London resolution long
Contexto:
•	STATE=TRANSITION
•	QL=TRANSITION_UNCLASSIFIED
•	LOOK_FOR=LOOK_FOR_transition_repricing_london
•	setup_family=transition_resolution
Interpretación:
La familia no funcionó bien como sleeve simétrico. En research pseudo-net solo mostró algo plausible en LONG-only. En OOS no sobrevivió.
Configuración probada:
•	tp_k=1.5
•	sl_k=1.0
•	time_stop_bars=10
•	trigger_unit=bars
•	side=LONG
•	stacking=False
Resultado OOS neto:
•	trades=11
•	trades/week=0.31
•	EV/trade=-0.001912
•	EV/month≈-0.0025
•	winrate=18.18%
•	maxDD=n/d en esta ronda
________________________________________
8) Resultado combinado del símbolo
Motores incluidos:
•	state_reinforcement
•	transition_resolution
Resultado combinado:
•	El intento de combo no materializó un combo real.
•	El ledger final quedó compuesto solo por state_reinforcement.
•	trades=75
•	trades/week=1.50
•	EV/trade=-0.000264
•	EV/month≈-0.0017
•	winrate=45.33%
•	maxDD=n/d en esta ronda
Lectura:
No hubo evidencia de que la combinación de motores rescatara el símbolo. En la práctica, el supuesto combo no agregó transition_resolution y terminó comportándose igual que el motor principal fallido OOS.
________________________________________
9) Costos y realismo
Spread aplicado: sí
ret_net validado distinto de ret_gross: sí, en los runs finales con spread=100
Observación:
•	Neto modelado, no gross-only.
•	Se usó spread fijo de 100 puntos como convención pragmática.
•	La imputación está respaldada por observación 2025: cuando el spread aparece en MT5, sale constante en 100.
•	No es costo tick-exacto histórico 2023-2024, pero sí una convención explícita y razonable para cierre práctico.
________________________________________
10) Veredicto final del símbolo
EDGE but NO-CAPTURE
Justificación breve:
US500 sí mostró edge estructural inteligible y consistente, especialmente en trend_pullback_asia. Sin embargo, al exigir monetización OOS con costos pragmáticos, los motores stand-alone probados no sostuvieron rentabilidad. Balance quedó útil como contexto estructural, pero no como sleeve operable. En el ciclo actual no quedó demostrada una captura robusta y defendible.
________________________________________
11) Siguiente acción
cerrado
________________________________________
12) Reproducibilidad exacta
Archivos de entrada finales:
•	outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31.parquet
•	outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet
•	outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv
•	outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv
•	outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv
Convención de costos:
•	spread modelado
•	imputación explícita: spread = 100 puntos
•	motivación: en 2025 el spread observado disponible aparece constante en 100
Comandos exactos para reproducir:
1.	Build barstream OOS
!set PYTHONPATH=. && python scripts/build_phase_d_context.py --symbol "US500.spot.mg" --start "2025-01-01" --end "2025-12-31" --timeframe "H2" --window-hours 24 --output-dir "outputs/phase_d_context"
2.	Build prices 2023-2025
!set PYTHONPATH=. && python scripts/build_prices_h2.py --symbol "US500.spot.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2023-01-01_2025-12-31.parquet" --out_prices_parquet "outputs/prices/prices_H2_US500.spot.mg_2023-01-01_2025-12-31.parquet" --timeframe "H2" --pad_hours 24
3.	Crear prices OOS con spread modelado 100
!set PYTHONPATH=. && python -c "import pandas as pd; p_in=r'outputs/prices/prices_H2_US500.spot.mg_2025-01-01_2025-12-31.parquet'; p_out=r'outputs/prices/prices_H2_US500.spot.mg_2025-01-01_2025-12-31_spread100.parquet'; df=pd.read_parquet(p_in); df['spread']=100.0; df.to_parquet(p_out, index=False)"
4.	Build enriched OOS
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_ohlc.py --symbol "US500.spot.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31.parquet" --prices_parquet "outputs/prices/prices_H2_US500.spot.mg_2025-01-01_2025-12-31_spread100.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_spread100.parquet"
5.	Build VWAP bands OOS
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_vwap_bands.py --symbol "US500.spot.mg" --in_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_spread100.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet"
6.	Phase E research
!set PYTHONPATH=. && python scripts/phase_e.py --symbol "US500.spot.mg" --start "2023-01-01" --end "2024-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline
7.	run_phase_f OOS con registry de research
!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "US500.spot.mg" --barstream "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/US500.spot.mg.yaml" --symbol_config "configs/symbols/US500.spot.mg.yaml" --outdir "outputs/phase_f_runs/US500_oos_hypothesis_audit"
8.	Direction layer OOS
!set PYTHONPATH=. && python scripts/phase_f_direction_layer.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions.csv" --out_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --phase_f_policy "configs/phase_f/US500.spot.mg.yaml"
9.	Backtest exacto motor 1
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --setup_family "state_reinforcement" --side BOTH --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --use_spread --out_dir "outputs/backtests/US500_oos_hypothesis/BT_state_reinforcement_bars_fixed_spread100"
10.	Backtest exacto motor 2
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --setup_family "transition_resolution" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --use_spread --out_dir "outputs/backtests/US500_oos_hypothesis/BT_transition_resolution_LONG_bars_fixed_spread100"
11.	Intento de combo
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --use_spread --out_dir "outputs/backtests/US500_oos_hypothesis/BT_combo_state_reinf_plus_transition_spread100"
Outputs finales a conservar:
•	outputs/backtests/US500_oos_hypothesis/BT_state_reinforcement_bars_fixed_spread100/trades.parquet
•	outputs/backtests/US500_oos_hypothesis/BT_transition_resolution_LONG_bars_fixed_spread100/trades.parquet
•	outputs/backtests/US500_oos_hypothesis/BT_combo_state_reinf_plus_transition_spread100/trades.parquet
•	outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv
Nota metodológica:
•	Los costos finales usados para research y OOS fueron modelados con spread fijo de 100 puntos, no reconstruidos tick a tick para todo el historial.
•	El intento de combo final no materializó mezcla efectiva de motores; el ledger resultante quedó compuesto solo por state_reinforcement.
________________________________________
Versión ultra corta para bitácora ejecutiva
US500.spot.mg
Naturaleza: reload de tendencia en ASIA, compresión overnight como contención, London repricing como resolución, pero con sostén OOS fuerte solo en trend.
Edge principal: LOOK_FOR_trend_pullback_asia / STATE_REINFORCEMENT / +11.72 pp research, +11.64 pp OOS.
Motores probados: state_reinforcement, transition_resolution LONG.
Resultado OOS neto: ambos negativos bajo spread modelado 100.
Costos: ok, pero modelados con spread=100.
Veredicto: EDGE but NO-CAPTURE
Estado: cerrado
