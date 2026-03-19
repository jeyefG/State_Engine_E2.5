# RESULTADOS — US500.spot.mg (State Engine)
## Bitácora unificada legacy + E2.5 nativo + E2.5 geom research-frozen

---

## 1) Símbolo y ventana

**Símbolo:** US500.spot.mg  
**Ventana total analizada:** 2023-01-01 → 2025-12-31  
**Research:** 2023-01-01 → 2024-12-31  
**OOS:** 2025-01-01 → 2025-12-31  
**Timeframe / score_tf:** H2 / M30

---

## 2) Objetivo

Evaluar si el State Engine detecta edge estructural en US500.spot.mg y si ese edge puede monetizarse de forma interpretable, neta y OOS.

En esta bitácora se integran tres lecturas sobre el mismo símbolo:

1. **Legacy**: Phase E → Phase F estándar.
2. **E2.5 nativo**: bridge E2.5 base, sin rediseño geométrico específico.
3. **E2.5 geom research-frozen**: bridge específico para US500, derivado solo desde research pre-F y aislado del wiring de XAU.

---

## 3) Naturaleza estructural del símbolo

### Estados dominantes
- **TRANSITION:** 56.9%
- **TREND:** 26.7%
- **BALANCE:** 16.3%

### QL dominantes
- **TRANSITION_UNCLASSIFIED:** 41.5%
- **TREND_STRONG:** 16.8%
- **TRANSITION_NOISY:** 15.3%
- **BALANCE_LEAKING:** 9.5%
- **TREND_UNCLASSIFIED:** 8.0%
- **BALANCE_UNCLASSIFIED:** 6.5%

### LOOK_FOR relevantes
- `LOOK_FOR_trend_pullback_asia`
- `LOOK_FOR_balance_overnight_compression`
- `LOOK_FOR_transition_repricing_london`

### Lectura estructural

US500 no se dejó leer bien con una ontología simétrica genérica de trend / transition / balance.

La hipótesis final que sí quedó respaldada en research fue:
- reload ordenado de tendencia en **ASIA**
- compresión overnight como **contención / estabilidad de balance**
- repricing en **London** como **resolución de transición**

`transition_repricing_ny` quedó fuera del núcleo validado.

---

## 4) Edge descriptivo detectado (Phase E)

| LOOK_FOR | Baseline | n_bars | uplift_pp |
|---|---:|---:|---:|
| LOOK_FOR_trend_pullback_asia | STATE_REINFORCEMENT | 1008 | 11.72 |
| LOOK_FOR_transition_repricing_london | TRANSITION_RESOLUTION | 344 | 8.84 |
| LOOK_FOR_balance_overnight_compression | BALANCE_STABILITY | 557 | 5.20 |

### Edge más robusto
- `LOOK_FOR_trend_pullback_asia`
- `LOOK_FOR_transition_repricing_london`

### Lectura

Sí apareció edge descriptivo claro en research.

El más robusto fue:
- `trend_pullback_asia -> STATE_REINFORCEMENT`

También apareció sano:
- `transition_repricing_london -> TRANSITION_RESOLUTION`

`balance_overnight_compression -> BALANCE_STABILITY` quedó validado como contención, no como leak ni escape.

`transition_repricing_ny` no mostró edge útil y no entró al núcleo.

---

## 5) Estabilidad temporal del edge

**Nota:** en esta ronda de cierre no se re-tabuló 2023 y 2024 por separado; la validación temporal quedó hecha como research agregado 2023-2024 vs OOS 2025.

| Tramo | LOOK_FOR | n_bars | uplift_pp |
|---|---|---:|---:|
| 2023-2024 (research) | LOOK_FOR_trend_pullback_asia | 1008 | 11.72 |
| 2023-2024 (research) | LOOK_FOR_transition_repricing_london | 344 | 8.84 |
| 2023-2024 (research) | LOOK_FOR_balance_overnight_compression | 557 | 5.20 |
| 2025 (OOS) | LOOK_FOR_trend_pullback_asia | 718 | 11.64 |
| 2025 (OOS) | LOOK_FOR_balance_overnight_compression | 219 | 20.16 |
| 2025 (OOS) | LOOK_FOR_transition_repricing_london | no filtró | — |

### Lectura
- **Mixto**.
- `trend_pullback_asia` se sostuvo fuerte OOS.
- `balance_overnight_compression` apareció fuerte en uplift, pero quedó bajo el `min_n_bars` congelado (250).
- `transition_repricing_london` no sostuvo filtrado OOS.

---

## 6) Legacy — Policy / Phase F

### Contextos GO principales
- `STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_pullback_asia`
- `STATE=TREND|QL=TREND_UNCLASSIFIED|LF=LOOK_FOR_trend_pullback_asia`
- `STATE=TRANSITION|QL=TRANSITION_UNCLASSIFIED|LF=LOOK_FOR_transition_repricing_london`
- `STATE=BALANCE|QL=BALANCE_LEAKING|LF=LOOK_FOR_balance_overnight_compression`
- `STATE=BALANCE|QL=BALANCE_UNCLASSIFIED|LF=LOOK_FOR_balance_overnight_compression`

### ALLOW rate
- **Research:** 7.59%
- **OOS:** 8.09%

### Resolución predominante
- **Research:** `STATE_QL_LF (457 / 466 ALLOW)`
- **OOS:** `STATE_QL_LF (238 / 247 ALLOW)`

### Comentario de wiring
- limpio
- fallback bajo y razonable
- `LF_MISMATCH = 0`
- `META_BASELINE_NA = 0`
- `ql_context_mismatch` bajo: ~1.9% en research y ~3.6% en OOS

---

## 7) Legacy — motores operativos probados

### Motor 1 — Trend reload

**Contexto**
- `STATE=TREND`
- `QL=TREND_STRONG / TREND_UNCLASSIFIED`
- `LOOK_FOR=LOOK_FOR_trend_pullback_asia`
- `setup_family=state_reinforcement`

**Interpretación**
Sleeve de reload / continuation en tendencia viva, usando el side assignment completo del direction layer.

No sobrevivió como LONG-only ni SHORT-only en research con costos, pero sí como motor completo en research pseudo-net.

**Configuración probada**
- `tp_k=1.5`
- `sl_k=1.0`
- `time_stop_bars=10`
- `trigger_unit=bars`
- `side=BOTH`
- `stacking=False`

**Resultado OOS neto**
- `trades=75`
- `trades/week=1.50`
- `EV/trade=-0.000264`
- `EV/month≈-0.0017`
- `winrate=45.33%`
- `maxDD=n/d en esta ronda`

### Motor 2 — London resolution long

**Contexto**
- `STATE=TRANSITION`
- `QL=TRANSITION_UNCLASSIFIED`
- `LOOK_FOR=LOOK_FOR_transition_repricing_london`
- `setup_family=transition_resolution`

**Interpretación**
La familia no funcionó bien como sleeve simétrico. En research pseudo-net solo mostró algo plausible en LONG-only. En OOS no sobrevivió.

**Configuración probada**
- `tp_k=1.5`
- `sl_k=1.0`
- `time_stop_bars=10`
- `trigger_unit=bars`
- `side=LONG`
- `stacking=False`

**Resultado OOS neto**
- `trades=11`
- `trades/week=0.31`
- `EV/trade=-0.001912`
- `EV/month≈-0.0025`
- `winrate=18.18%`
- `maxDD=n/d en esta ronda`

---

## 8) Legacy — resultado combinado del símbolo

### Motores incluidos
- `state_reinforcement`
- `transition_resolution`

### Resultado combinado
- el intento de combo no materializó un combo real
- el ledger final quedó compuesto solo por `state_reinforcement`
- `trades=75`
- `trades/week=1.50`
- `EV/trade=-0.000264`
- `EV/month≈-0.0017`
- `winrate=45.33%`
- `maxDD=n/d en esta ronda`

### Lectura

No hubo evidencia de que la combinación de motores rescatara el símbolo.

En la práctica, el supuesto combo no agregó `transition_resolution` y terminó comportándose igual que el motor principal fallido OOS.

### Veredicto legacy

**EDGE but NO-CAPTURE**

Justificación breve: US500 sí mostró edge estructural inteligible y consistente, especialmente en `trend_pullback_asia`. Sin embargo, al exigir monetización OOS con costos pragmáticos, los motores stand-alone probados no sostuvieron rentabilidad. Balance quedó útil como contexto estructural, pero no como sleeve operable.

---

## 9) E2.5 nativo — barrido agnóstico del universo

Se construyó el universo E2.5 de US500 sin usar winners legacy como prior de screening.

### Universo E2.5 full-window
- `decisions_e25 full-window`: 9201 filas
- `TRADEABLE / core`: 695 filas
- `UNVALIDATED`: 8506 filas

### Source units E2.5 principales
- `TREND / LOOK_FOR_trend_pullback_asia / STATE_REINFORCEMENT / QL=TREND_STRONG` → 253
- `TREND / LOOK_FOR_trend_pullback_asia / STATE_REINFORCEMENT / QL=TREND_UNCLASSIFIED` → 154
- `BALANCE / LOOK_FOR_balance_overnight_compression / BALANCE_STABILITY / QL=BALANCE_LEAKING` → 106
- `TRANSITION / LOOK_FOR_transition_repricing_london / TRANSITION_RESOLUTION / QL=TRANSITION_UNCLASSIFIED` → 96
- `BALANCE / LOOK_FOR_balance_overnight_compression / BALANCE_STABILITY / QL=BALANCE_UNCLASSIFIED` → 86

### Universo operable OOS tras direction layer E2.5 nativo

**Operables candidatos a screening**
- `STATE_REINFORCEMENT / state_reinforcement / LONG` → 106 OOS
- `STATE_REINFORCEMENT / state_reinforcement / SHORT` → 57 OOS
- `TRANSITION_RESOLUTION / transition_resolution / LONG` → 8 OOS
- `TRANSITION_RESOLUTION / transition_resolution / SHORT` → 10 OOS

**No operable nativo**
- `BALANCE_STABILITY` quedó bloqueado por directionality (`blocked_missing_both_side`)

### Screening canónico E2.5 nativo

| Run | n_trades | EV/trade |
|---|---:|---:|
| `tr_long__bars_fixed` | 50 | **+0.000290** |
| `sr_long__bars_fixed` | 118 | -0.000090 |
| `tr_long__episodes_state_change` | 46 | -0.000192 |
| `sr_short__episodes_state_change` | 78 | -0.000246 |
| `sr_short__bars_fixed` | 87 | -0.000416 |
| `sr_long__episodes_state_change` | 111 | -0.000433 |
| `tr_short__bars_fixed` | 41 | -0.001194 |
| `tr_short__episodes_state_change` | 38 | -0.001530 |

### Lectura del único amago de vida nativo

`tr_long__bars_fixed` fue el único sleeve con EV positivo full-window, pero:
- 2023: positivo
- 2024: positivo
- 2025: **negativo**
- masa OOS del sleeve: **8 rows**

**Resultado:** no promovible.

### Bucket test adicional en trend

Corte por QL dentro de `state_reinforcement LONG`:
- `TREND_STRONG` → `EV/trade=+0.000034`
- `TREND_UNCLASSIFIED` → `EV/trade≈0.000000`

Mejora marginal, sin motor pagador defendible.

### Veredicto E2.5 nativo

**NO-CAPTURE**

E2.5 nativo ordenó el universo, pero no rescató capturabilidad OOS defendible.

---

## 10) E2.5 geom research-frozen — motivación

A partir del barrido nativo apareció la pregunta central:

> ¿Está fallando E2.5 porque el edge de Phase E sea falso, o porque el contrato E2.5 → F traduce mal edge estructural a edge ejecutable?

La hipótesis adoptada fue:
- el edge estructural de Phase E **sí existe**
- pero el bridge actual sigue siendo demasiado grueso
- conviene probar un contrato **US500-specific**, aislado de XAU y del contrato genérico

### Restricción metodológica

Las reglas geométricas se derivaron:
- **solo desde research 2023-2024**
- sobre universo **pre-F**
- sin usar OOS para definir el gate
- sin usar PnL para escribir reglas

---

## 11) E2.5 geom research-frozen — diseño

### Policy específica creada
- `configs/phase_f/US500.spot.mg.e25_geom_research_frozen.yaml`

### Reglas congeladas

#### continuation
- `session_bucket = ASIA`
- `required_quality_labels = TREND_STRONG`
- `pass -> TRADEABLE_GEOM`
- `fail -> INFO_ONLY`

#### resolution
- `session_bucket = LONDON`
- `required_state_age_bucket = YOUNG`
- `pass -> TRADEABLE_GEOM`
- `fail -> INFO_ONLY`

#### mean_revert
- siempre `INFO_ONLY`

### Efecto estructural del gate

#### Research pre-F
- `STATE_REINFORCEMENT`: 240 → **152** (`63.3%` sobrevive)
- `TRANSITION_RESOLUTION`: 78 → **48** (`61.5%` sobrevive)
- `BALANCE_STABILITY`: 139 → **0 tradeable`

#### OOS pre-F
- `STATE_REINFORCEMENT`: 167 → **101** (`60.5%` sobrevive)
- `TRANSITION_RESOLUTION`: 18 → **9** (`50.0%` sobrevive)
- `BALANCE_STABILITY`: 53 → **0 tradeable`

### Lectura

El gate research-frozen **sí generalizó estructuralmente a 2025**.

No fue solo relabeling: redujo el universo monetizable OOS de 238 a 110 barras.

---

## 12) Integración E2.5 geom → direction layer

### Problemas encontrados

El direction layer E2.5 original tenía dos cuellos:

1. trataba `INFO_ONLY` como todavía monetizable en la práctica
2. recomputaba `trend_dir_h2` / `range_pos_h2` con heurística legacy, pisando features precomputadas

### Parche metodológico aplicado solo para US500

Se hicieron dos ajustes locales y reversibles:

1. `INFO_ONLY -> NO_GO` para testear correctamente la semántica del gate
2. direction layer US500-specific que respeta PA features precomputadas desde el enriched

### Universo OOS monetizable tras gate research-frozen
- total `TRADEABLE`: **110**
- composición:
  - `STATE_REINFORCEMENT / TREND_STRONG` → **101**
  - `TRANSITION_RESOLUTION / TRANSITION_UNCLASSIFIED / YOUNG` → **9**

### Sleeves OOS resultantes
- `STATE_REINFORCEMENT LONG` → 53
- `STATE_REINFORCEMENT SHORT` → 48
- `TRANSITION_RESOLUTION LONG` → 4
- `TRANSITION_RESOLUTION SHORT` → 5
- `BALANCE_STABILITY` → 0

---

## 13) Screening OOS — E2.5 geom research-frozen

### Bars + fixed

| Sleeve | n_trades | EV/trade | trades/week | winrate | maxDD |
|---|---:|---:|---:|---:|---:|
| `sr_long` | 32 | **-0.000018** | 0.205 | 31.25% | -2.61% |
| `sr_short` | 29 | -0.000393 | 0.186 | 41.38% | -3.96% |
| `tr_short` | 5 | -0.001587 | 0.032 | 20.00% | -1.40% |
| `tr_long` | 4 | -0.001868 | 0.026 | 25.00% | -0.72% |

### Episodes + state_change

Se probó solo el único sleeve que quedó razonablemente cerca de cero:

#### `sr_long`
- `n_trades=32`
- `EV/trade=-0.001455`
- `winrate=50.00%`
- `maxDD=-5.74%`

Lectura: empeora respecto de `bars + fixed`. No rescata el sleeve.

---

## 14) Test adicional — resolver alternativo para transition_resolution

Se probó una política distinta solo para `TRANSITION_RESOLUTION`, resolviendo side por `range_pos_h2`:
- `range_pos >= 0.67 -> LONG`
- `range_pos <= 0.33 -> SHORT`
- resto -> `NONE`

### Resultado
- `tr_short` → **sin cambio material** (`EV/trade=-0.001587`)
- `tr_long` → **empeora** (`EV/trade=-0.003783`)

### Lectura

No apareció una vía nueva real para `TRANSITION_RESOLUTION`.

El sleeve queda descartado.

---

## 15) Qué enseñó US500 sobre E2.5

US500 deja una enseñanza más fina que simplemente “legacy falló”:

1. **Sí había edge estructural real** en Phase E.
2. **El bridge E2.5 original era demasiado grueso** y mezclaba mal `TRADEABLE` con `INFO_ONLY`.
3. **Un contrato geométrico research-frozen sí mejora la descripción operativa del símbolo.**
4. **Pero incluso con ese contrato mejorado, el símbolo sigue sin monetizar neto de forma defendible OOS.**

### Traducción ejecutiva

El problema de US500 no era solo de ontología descriptiva ni solo de direction layer legacy.

Incluso corrigiendo el contrato E2.5 → F de manera causal, aislada por símbolo y sin tocar XAU, **no apareció capture robusto OOS**.

---

## 16) Costos y realismo

### Spread aplicado
- sí

### ret_net validado distinto de ret_gross
- sí, en los runs finales con `spread=100`

### Observación
- neto modelado, no gross-only
- se usó spread fijo de 100 puntos como convención pragmática
- la imputación está respaldada por observación 2025: cuando el spread aparece en MT5, sale constante en 100
- no es costo tick-exacto histórico 2023-2024, pero sí una convención explícita y razonable para cierre práctico

---

## 17) Veredicto final consolidado del símbolo

# **EDGE but NO-CAPTURE**

### Justificación breve

US500 sí mostró edge estructural inteligible y consistente, especialmente en `trend_pullback_asia`.

Sin embargo:
- legacy no capturó de forma robusta OOS
- E2.5 nativo tampoco rescató capturabilidad
- y el bridge E2.5 geom research-frozen, aunque mejoró la traducción estructural y limpió el universo operable, **tampoco logró convertir el edge en PnL neto defendible OOS**

### Lectura final por capa
- **Legacy:** NO-CAPTURE
- **E2.5 nativo:** NO-CAPTURE
- **E2.5 geom research-frozen:** mejor contrato, pero **NO-CAPTURE**

---

## 18) Siguiente acción

**cerrado**

---

## 19) Reproducibilidad exacta

### Legacy — archivos de entrada finales
- `outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31.parquet`
- `outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet`
- `outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv`
- `outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv`
- `outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv`

### Legacy — convención de costos
- `spread modelado`
- imputación explícita: `spread = 100 puntos`
- motivación: en 2025 el spread observado disponible aparece constante en 100

### Legacy — comandos exactos para reproducir
1. Build barstream OOS  
   `python scripts/build_phase_d_context.py --symbol "US500.spot.mg" --start "2025-01-01" --end "2025-12-31" --timeframe "H2" --window-hours 24 --output-dir "outputs/phase_d_context"`
2. Build prices 2023-2025  
   `python scripts/build_prices_h2.py --symbol "US500.spot.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2023-01-01_2025-12-31.parquet" --out_prices_parquet "outputs/prices/prices_H2_US500.spot.mg_2023-01-01_2025-12-31.parquet" --timeframe "H2" --pad_hours 24`
3. Crear prices OOS con spread modelado 100  
   `python -c "import pandas as pd; p_in=r'outputs/prices/prices_H2_US500.spot.mg_2025-01-01_2025-12-31.parquet'; p_out=r'outputs/prices/prices_H2_US500.spot.mg_2025-01-01_2025-12-31_spread100.parquet'; df=pd.read_parquet(p_in); df['spread']=100.0; df.to_parquet(p_out, index=False)"`
4. Build enriched OOS  
   `python scripts/build_phase_f_enriched_ohlc.py --symbol "US500.spot.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31.parquet" --prices_parquet "outputs/prices/prices_H2_US500.spot.mg_2025-01-01_2025-12-31_spread100.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_spread100.parquet"`
5. Build VWAP bands OOS  
   `python scripts/build_phase_f_enriched_vwap_bands.py --symbol "US500.spot.mg" --in_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_spread100.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet"`
6. Phase E research  
   `python scripts/phase_e.py --symbol "US500.spot.mg" --start "2023-01-01" --end "2024-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline`
7. run_phase_f OOS con registry de research  
   `python scripts/run_phase_f.py --symbol "US500.spot.mg" --barstream "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/US500.spot.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/US500.spot.mg.yaml" --symbol_config "configs/symbols/US500.spot.mg.yaml" --outdir "outputs/phase_f_runs/US500_oos_hypothesis_audit"`
8. Direction layer OOS  
   `python scripts/phase_f_direction_layer.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions.csv" --out_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --phase_f_policy "configs/phase_f/US500.spot.mg.yaml"`
9. Backtest exacto motor 1  
   `python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --setup_family "state_reinforcement" --side BOTH --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --use_spread --out_dir "outputs/backtests/US500_oos_hypothesis/BT_state_reinforcement_bars_fixed_spread100"`
10. Backtest exacto motor 2  
   `python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --setup_family "transition_resolution" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --use_spread --out_dir "outputs/backtests/US500_oos_hypothesis/BT_transition_resolution_LONG_bars_fixed_spread100"`
11. Intento de combo  
   `python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2025-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet" --decisions_csv "outputs/phase_f_runs/US500_oos_hypothesis_audit/decisions_with_side.csv" --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --use_spread --out_dir "outputs/backtests/US500_oos_hypothesis/BT_combo_state_reinf_plus_transition_spread100"`

### E2.5 / E2.5 geom — archivos relevantes
- `outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_2023-01-01_2025-12-31.parquet`
- `outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread100.parquet`
- `outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread100_us500geom.parquet`
- `outputs/e25/US500.spot.mg/e25_registry_research.csv`
- `outputs/phase_f_runs/US500_e25_frozen_full_audit/decisions_e25.csv`
- `outputs/phase_f_runs/US500_e25_frozen_full_audit/decisions_e25_geom_oos.csv`
- `outputs/phase_f_runs/US500_e25_frozen_full_audit/decisions_e25_geom_oos_INFO_AS_NOGO.csv`
- `outputs/phase_f_runs/US500_e25_frozen_full_audit/decisions_with_side_e25_geom_oos_INFO_AS_NOGO_us500geom_patched.csv`
- `outputs/phase_f_runs/US500_e25_frozen_full_audit/decisions_with_side_e25_geom_oos_INFO_AS_NOGO_us500tr_range.csv`
- `configs/phase_f/US500.spot.mg.e25_frozen.yaml`
- `configs/phase_f/US500.spot.mg.e25_geom_research_frozen.yaml`

### E2.5 / E2.5 geom — scripts auxiliares creados
- `scripts/phase_f_direction_layer_e25_us500geom.py`
- `scripts/phase_f_direction_layer_e25_us500tr_range.py`

### E2.5 / E2.5 geom — backtests relevantes finales
- `outputs/backtests/US500_e25_screening_v1/...`
- `outputs/backtests/US500_e25_bucket_screening_v1/...`
- `outputs/backtests/US500_e25_geom_oos_bars_fixed_v1/sr_long/report.csv`
- `outputs/backtests/US500_e25_geom_oos_bars_fixed_v1/sr_short/report.csv`
- `outputs/backtests/US500_e25_geom_oos_bars_fixed_v1/tr_long/report.csv`
- `outputs/backtests/US500_e25_geom_oos_bars_fixed_v1/tr_short/report.csv`
- `outputs/backtests/US500_e25_geom_oos_sr_long_episodes_state_change_v1/report.csv`
- `outputs/backtests/US500_e25_geom_oos_tr_range_transition_only_v1/tr_long/report.csv`
- `outputs/backtests/US500_e25_geom_oos_tr_range_transition_only_v1/tr_short/report.csv`

### Nota metodológica
- Los costos finales usados para research y OOS fueron modelados con spread fijo de 100 puntos, no reconstruidos tick a tick para todo el historial.
- El intento de combo legacy no materializó mezcla efectiva de motores; el ledger resultante quedó compuesto solo por `state_reinforcement`.
- El gate geométrico de US500 se derivó **solo desde research pre-F**, sin usar OOS ni PnL para definir reglas.

---

## 20) Versión ultra corta para bitácora ejecutiva

**US500.spot.mg**  
Naturaleza: reload de tendencia en ASIA, compresión overnight como contención, London repricing como resolución.  
Edge principal: `LOOK_FOR_trend_pullback_asia / STATE_REINFORCEMENT / +11.72 pp research`, con sostén descriptivo OOS.  
Legacy: no capturó.  
E2.5 nativo: no capturó.  
E2.5 geom research-frozen: mejoró el contrato y limpió el universo operable, pero tampoco monetizó neto OOS de forma defendible.  
Costos: ok, modelados con `spread=100`.  
Veredicto: **EDGE but NO-CAPTURE**.  
Estado: **cerrado**.
