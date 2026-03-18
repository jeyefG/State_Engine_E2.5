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
