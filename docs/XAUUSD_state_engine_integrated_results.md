# RESULTADOS — XAUUSD (State Engine)
## Bitácora integrada legacy + E2.5

---

## 1) Símbolo y ventana

- **Símbolo:** XAUUSD.mg
- **Ventana total analizada:** 2023-01-01 → 2025-12-31
- **Research:** 2023-01-01 → 2024-12-31
- **OOS:** 2025-01-01 → 2025-12-31
- **Timeframe / score_tf:** H2 / M30

---

## 2) Objetivo

Evaluar si el State Engine detecta edge estructural en XAUUSD y si ese edge puede monetizarse de forma interpretable, neta y OOS, comparando:

1. **legacy** como benchmark histórico y benchmark refinado actual,
2. **E2.5** como candidato a mejor motor actual,
3. **híbrido** como política de ejecución combinada cuando tenga sentido.

---

## 3) Naturaleza estructural del símbolo

- **Estados dominantes:** TRANSITION > TREND > BALANCE
- **QL dominantes:** TRANSITION_UNCLASSIFIED, TRANSITION_NOISY, TREND_STRONG, BALANCE_LEAKING
- **LOOK_FOR relevantes:**
  - LOOK_FOR_transition_chop_near_vwap
  - LOOK_FOR_trend_strong_orderly
  - LOOK_FOR_balance_vwap_proximity
  - LOOK_FOR_trend_prev_vwap_pullback

### Lectura estructural

XAU muestra una naturaleza mixta pero legible. Predomina un régimen de **transición con drift alrededor de VWAP**, conviviendo con un sleeve de **continuación de tendencia** cuando el contexto H2 está claramente ordenado. **Balance sí aparece descriptivamente**, pero en esta ronda no mostró captura monetaria suficientemente convincente como sleeve principal.

---

## 4) Edge descriptivo detectado (Phase E)

| LOOK_FOR | Baseline | n_bars | uplift_pp |
|---|---:|---:|---:|
| LOOK_FOR_trend_strong_orderly | STATE_REINFORCEMENT | 2647 | 7.42 |
| LOOK_FOR_balance_vwap_proximity | BALANCE_STABILITY | 2924 | 5.95 |
| LOOK_FOR_balance_compression | BALANCE_STABILITY | 486 | 5.80 |
| LOOK_FOR_trend_prev_vwap_pullback | STATE_REINFORCEMENT | 1180 | 5.01 |
| LOOK_FOR_transition_chop_near_vwap | TRANSITION_PERSISTENCE | 6072 | 3.98 |

### Edge más robusto

- LOOK_FOR_trend_strong_orderly
- LOOK_FOR_transition_chop_near_vwap
- LOOK_FOR_balance_vwap_proximity

### Lectura

Sí apareció edge estructural claro en **tendencia** y **transición**. Balance también apareció descriptivamente en Phase E, pero **no logró transformarse en motor operativo dominante** con el template auditado en esta ronda.

---

## 5) Estabilidad temporal del edge

> Nota: en la iteración final vinculante, la estabilidad descriptiva se validó principalmente como **Research 2023-2024 vs OOS 2025**.

| Tramo | LOOK_FOR | n_bars | uplift_pp |
|---|---|---:|---:|
| 2023-2024 (research) | LOOK_FOR_balance_vwap_proximity | 2013 | 7.09 |
| 2023-2024 (research) | LOOK_FOR_trend_strong_orderly | 1594 | 7.03 |
| 2023-2024 (research) | LOOK_FOR_transition_chop_near_vwap | 4078 | 4.44 |
| 2025 (OOS descriptivo) | LOOK_FOR_trend_strong_orderly | 1029 | 8.23 |
| 2025 (OOS descriptivo) | LOOK_FOR_balance_vwap_proximity | 911 | 3.48 |
| 2025 (OOS descriptivo) | LOOK_FOR_transition_chop_near_vwap | 1988 | 2.89 |

### Lectura

- **Mixto pero sano**
- **Tendencia** se mantiene fuerte e incluso mejora
- **Transición** persiste, aunque con menor uplift en 2025
- **Balance** sigue existiendo descriptivamente, pero no capturó bien

---

## 6) Policy / Phase F

### Contextos GO principales

- STATE=TRANSITION|QL=TRANSITION_UNCLASSIFIED|LF=LOOK_FOR_transition_chop_near_vwap
- STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly
- STATE=BALANCE|QL=BALANCE_LEAKING|LF=LOOK_FOR_balance_vwap_proximity

- **ALLOW rate:** 32.65%
- **Resolución predominante:** STATE_QL_LF, con fallback material a STATE_LF

### Comentario de wiring

- wiring limpio
- `engine_context_key` y `context_key` correctamente separados
- fallback QL razonable, no bug
- `trend_dir_h2` existe en el fat CSV y fue útil para refinar SR legacy en NY

---

## 7) Legacy — motores operativos probados

### Motor 1 — Transition NY

**Contexto**
- STATE=TRANSITION
- QL=TRANSITION_UNCLASSIFIED
- LOOK_FOR=LOOK_FOR_transition_chop_near_vwap
- setup_family=transition_persistence
- sesión=NY

**Interpretación**  
Drift / continuidad corta de transición, especialmente útil cuando se aísla el núcleo `TRANSITION_UNCLASSIFIED` y se ejecuta solo en NY.

**Configuración probada**
- tp_k=40
- sl_k=25
- time_stop_bars=18
- trigger_unit=bars
- side=LONG
- stacking=Sí (`max_positions=3`)

**Resultado OOS neto**
- trades=16
- trades/week=0.31
- EV/trade=0.007824
- EV/month≈1.04%
- winrate=75.0%
- maxDD=n/d aislado en la ronda legacy final

### Motor 2 — SR NY trendUP

**Contexto**
- STATE=TREND
- QL=TREND_STRONG
- LOOK_FOR=LOOK_FOR_trend_strong_orderly
- setup_family=state_reinforcement
- filtro adicional=`trend_dir_h2=UP`
- sesión=NY

**Interpretación**  
Continuation setup más fino que el SR original: solo entra cuando la dirección H2 acompaña explícitamente. Este filtro no ayudó a abrir NY+NY_PM, pero sí rescató NY solo.

**Configuración probada**
- tp_k=40
- sl_k=25
- time_stop_bars=24
- trigger_unit=episodes
- side=LONG
- stacking=Sí (`max_positions=2`)

**Resultado OOS neto**
- trades=16
- trades/week=0.31
- EV/trade=0.003957
- EV/month≈0.53%
- winrate=62.5%
- maxDD=n/d aislado en la ronda legacy final

---

## 8) Legacy — resultado combinado del símbolo

### Legacy best refined

Motores incluidos:
- Transition NY
- SR NY trendUP

**Resultado raw**
- trades=83
- trades/week=0.53
- EV/trade=0.004063
- EV/month≈0.94%
- winrate=67.47%
- maxDD=-6.31%

### Variante portable / cross-symbol

**Resultado raw**
- trades=71
- trades/week=0.46
- EV/trade=0.003284
- winrate=66.20%
- maxDD=-6.31%

### EV_total anual raw

**Legacy best refined**
- 2023: 0.053280
- 2024: 0.095443
- 2025: 0.188504

**Variante portable**
- 2023: 0.046064
- 2024: 0.066835
- 2025: 0.120263

### Lectura

El combo legacy refinado `Transition NY + SR NY trendUP` fue el mejor motor legacy actual del símbolo. Superó a la variante portable y quedó como benchmark refinado defendible del cierre actual.  
El **combo histórico amplio** de XAU siguió existiendo como benchmark auxiliar, pero ya no es el benchmark vinculante entre finalistas actuales.

---

## 9) E2.5 — bridge y lógica auditada

### Pipeline auditado E2.5

```text
Phase E
→ run_phase_f.py
→ decisions.csv
→ annotate_decisions_with_e25.py
→ decisions_e25.csv
→ phase_f_direction_layer_e25.py
→ decisions_with_side_e25_*.csv
→ backtest_allow_episodes.py
Activos principales

Policy frozen: configs/phase_f/XAUUSD.mg.e25_frozen.yaml

Run principal audit: outputs/phase_f_runs/XAUUSD_e25_frozen_audit/

Barstream: outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet

Enriched usado: outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet

Lectura metodológica

legacy se usa como benchmark, no como restricción ontológica

E2.5 se evalúa como motor actual alternativo

la comparación histórica auxiliar a DD ~ 20.4% se conserva como benchmark histórico de engine

la comparación final vinculante entre finalistas actuales se hace a DD común defendible = 6.309159%

10) E2.5 — TP review
Metodología

Screening canónico:

bars + fixed

episodes + state_change

Luego micro-grid refinado corrigiendo comparabilidad:

legacy estaba en puntos

el backtester usa sigma-k

se hizo traducción bucket por bucket de equivalentes legacy → sigma

Luego micro-grid:

stacking vs no-stack

time_stop 12 / 18 / 24

Buckets revisados

ASIA LONG

ASIA SHORT

NY_PM LONG

NY_PM SHORT

LONDON LONG

LONDON SHORT

NY LONG

NY SHORT

Resultado

Todos los buckets murieron con evidencia robusta.

Lectura

EV/trade negativo en todos

stacking no movió nada relevante

time_stop no movió nada relevante

lo que parecía vivo antes se cayó al corregir pts vs sigma

Conclusión práctica: TP review queda descartado operativamente en XAU.

11) E2.5 — SR core
Inventario auditado

NY_PM LONG = 143

LONDON LONG = 104

ASIA LONG = 101

NY LONG = 89

NY_PM SHORT = 64

LONDON SHORT = 50

NY SHORT = 33

ASIA SHORT = 30

Resultado bucket por bucket
11.1) SR | NY_PM LONG

Screening canónico

bars_fixed:

n_trades = 92

EV/trade = 0.001134

winrate = 54.35%

maxDD = -1.90%

episodes_state_change:

n_trades = 83

EV/trade = 0.001307

winrate = 54.22%

maxDD = -2.12%

Micro-grid legacy-equivalent
Se probaron equivalentes a 30/20, 40/25, 50/30 en sigma. Todos quedaron negativos.

Micro-grid sigma-native ganador

tp/sl: 1.75 / 1.20

time_stop: 18

stacking: no-stack

Ganador E2.5 puro para XAU

raw:

n_trades = 92

trades/week = 0.589204

EV/trade = 0.001398

winrate = 56.52%

maxDD = -2.38%

11.2) SR | LONDON LONG

screening canónico negativo

muere

11.3) SR | ASIA LONG

screening canónico negativo

muere

11.4) SR | NY LONG

bars_fixed sobrevive débil

n_trades = 76

EV/trade = 0.000323

candidato secundario, muy lejos del líder

11.5) SR | NY_PM SHORT

bars_fixed negativo

episodes peor aún

muere

11.6) SR | LONDON SHORT

bars_fixed sobrevive débil

n_trades = 38

EV/trade = 0.000369

no promueve por n_trades < 40

11.7) SR | NY SHORT

bars_fixed sobrevive débil

n_trades = 29

EV/trade = 0.000447

no promueve por poca masa

11.8) SR | ASIA SHORT

bars_fixed: EV/trade = -0.001152

episodes_state_change: EV/trade = -0.000246

muere

Veredicto SR E2.5

SR sí rescata valor en XAU, pero el rescate queda fuertemente concentrado en:

SR | NY_PM LONG | sigma-native | 1.75 / 1.20 | ts18 | nostack

12) E2.5 — Balance review
Nota metodológica importante

En el wiring actual, balance_stability_center y balance_stability_tail bajan a NONE, no a LONG/SHORT. Para hacer la comparación de EV comparable, se construyó una adaptación explícita de auditoría:

close > ctx_vwap → SHORT

close < ctx_vwap → LONG

close == ctx_vwap → drop

Esta conversión no es el behavior nativo del direction layer. Se usó solo para cerrar la auditoría de comparabilidad.

Resultado por bucket
ASIA center signed

bars_fixed: EV/trade = -0.000273

episodes_state_change: EV/trade = -0.000046

muere

LONDON center signed

bars_fixed: EV/trade = -0.001610

episodes_state_change: EV/trade = -0.004614

muere claramente

NY_PM center signed

bars_fixed:

n_trades = 50

EV/trade = 0.000385

maxDD = -2.00%

episodes_state_change:

n_trades = 49

EV/trade = 0.000221

maxDD = -6.15%

vive débilmente, pero no compite con SR

NY center signed

bars_fixed:

n_trades = 20

EV/trade = 0.000947

maxDD = -0.95%

episodes_state_change:

n_trades = 18

EV/trade = 0.000476

maxDD = -3.00%

vive débilmente, pero no promociona por masa

Veredicto Balance E2.5

Balance no cambia la decisión del símbolo. Aporta algo de vida táctica en NY_PM y NY, pero no desplaza al sleeve SR y no justifica tuning adicional en esta ronda.

13) Benchmark histórico auxiliar
Legacy histórico amplio

Se conserva como benchmark histórico de calidad del engine:

outputs/backtests/XAU_current_templates_orig/BT_combo_transition_trend_spread60/trades.parquet

Resultado raw

trades = 483

EV/trade = 0.001557

winrate = 59.21%

raw final capital = 2041.19

raw total return = +104.12%

raw maxDD = -20.52%

Lectura

Este benchmark sirve como referencia histórica de calidad del engine, pero no es la comparación vinculante entre los finalistas actuales del cierre XAU.

14) Comparación final vinculante entre finalistas actuales
Convención final defendible

Para la comparación final del símbolo se usa un DD común defendible igual al maxDD real del mejor combo legacy refinado actual:

DD común = -6.309159%

Esta es la comparación vinculante entre:

legacy_best_refined

e25_solo

hybrid

14.1) Legacy best refined

Raw

n_trades = 83

EV/trade = 0.004063

winrate = 67.47%

raw final capital = 1389.81

raw total return = +38.98%

raw maxDD = -6.31%

Comparable @ DD 6.31%

comparable final capital = 1389.81

comparable return = +38.98%

14.2) E2.5 solo

Motor usado: SR | NY_PM LONG | sigma-native | 1.75 / 1.20 | ts18 | nostack

Raw

n_trades = 92

EV/trade = 0.001398

winrate = 56.52%

raw final capital = 1135.31

raw total return = +13.53%

raw maxDD = -2.38%

Comparable @ DD 6.31%

comparable final capital = 1388.74

comparable return = +38.87%

14.3) Overlap legacy_best vs E2.5

legacy trades = 83

E2.5 trades = 92

legacy overlapped by E2.5 = 37

legacy kept for hybrid = 46

hybrid total trades = 138

overlap legacy vs E2.5 = 44.58%

14.4) Híbrido final recomendado

Regla

E2.5 tiene prioridad

legacy_best entra como fallback si no hay overlap temporal con E2.5

Resultado raw

n_trades = 138

EV/trade = 0.001933

winrate = 59.42%

raw final capital = 1299.66

raw total return = +29.97%

raw maxDD = -2.63%

Comparable @ DD 6.31%

comparable final capital = 1856.79

comparable return = +85.68%

Lectura comparativa final

legacy_best_refined y E2.5 solo quedan prácticamente empatados a DD común defendible

legacy conserva mejor desempeño raw

E2.5 compensa con mucho menor DD raw

el híbrido domina claramente como mejor política total del símbolo

15) Splits anuales raw de los finalistas actuales

Convención: año asignado por entry_time.

Legacy best refined
Año	Trades	EV/trade	EV total	Winrate	Retorno compuesto
2023	21	0.002537	0.053280	66.67%	5.33%
2024	30	0.003181	0.095443	66.67%	9.81%
2025	32	0.005891	0.188504	68.75%	20.16%
E2.5 solo
Año	Trades	EV/trade	EV total	Winrate	Retorno compuesto
2023	22	-0.000312	-0.006872	50.00%	-0.72%
2024	30	0.000488	0.014628	46.67%	1.43%
2025	40	0.003022	0.120893	67.50%	12.74%
Híbrido
Año	Trades	EV/trade	EV total	Winrate	Retorno compuesto
2023	39	0.001337	0.052135	58.97%	5.20%
2024	45	0.001435	0.064566	53.33%	6.58%
2025	54	0.002778	0.150014	64.81%	15.92%
Lectura

legacy_best_refined es el más limpio y estable en raw

e25_solo aparece de verdad sobre todo en 2025

el híbrido no supera al legacy en cada año raw, pero sí entrega una trayectoria sana y con más masa

16) Splits anuales comparables a DD común = 6.309159%
Legacy best refined

Escala aplicada: 1.000x

Año	Trades	EV/trade comparable	EV total comparable	Winrate	Retorno anual comparable
2023	21	0.002537	0.053280	66.67%	5.33%
2024	30	0.003181	0.095443	66.67%	9.81%
2025	32	0.005891	0.188504	68.75%	20.16%
E2.5 solo

Escala aplicada: 2.647x

Año	Trades	EV/trade comparable	EV total comparable	Winrate	Retorno anual comparable
2023	22	-0.000827	-0.018190	50.00%	-2.02%
2024	30	0.001291	0.038720	46.67%	3.65%
2025	40	0.008000	0.320006	67.50%	36.75%
Híbrido

Escala aplicada: 2.421x

Año	Trades	EV/trade comparable	EV total comparable	Winrate	Retorno anual comparable
2023	39	0.003236	0.126207	58.97%	12.53%
2024	45	0.003473	0.156298	53.33%	16.31%
2025	54	0.006725	0.363145	64.81%	41.86%
Lectura

a DD común, legacy_best_refined sigue siendo el benchmark más estable

E2.5 aporta sobre todo en 2025

el híbrido es el mejor en esta tabla comparable en 2023, 2024 y 2025

17) Validación del scheduler híbrido
Gate 1 — concurrencia real

Legacy best refined

n_trades = 83

max_concurrent = 2

overlap pairs = 13

E2.5 solo

n_trades = 92

max_concurrent = 1

overlap pairs = 0

Híbrido

n_trades = 138

max_concurrent = 2

overlap pairs = 4

Hallazgos

no hubo overlaps entre E2.5 y legacy

los overlaps residuales del híbrido provenían solo del legacy interno

la regla E2.5 manda; legacy fallback quedó operativamente bien planteada

Gate 2 — test de robustez strict

Se auditó adicionalmente una versión estricta max_concurrent = 1 solo como prueba de robustez.

Resultado strict

trades = 134

EV/trade = 0.001923

winrate = 59.70%

raw return = +28.82%

raw maxDD = -2.63%

Splits anuales strict

2023: +3.56%

2024: +7.06%

2025: +16.19%

Conclusión del scheduler

La política híbrida no depende materialmente de imponer max_positions = 1.
La versión recomendada para cierre de XAU no fuerza esa restricción; mantiene la concurrencia interna ya validada del legacy refinado y usa:

E2.5 priority

legacy_best fallback no-overlap

18) Costos y realismo

Spread aplicado: sí

ret_net validado distinto de ret_gross: sí

Observación

neto modelado con spread60

el histórico del broker no traía spread usable en gran parte de 2023-2024 y comienzos de 2025

el tramo post-2025-02-18 observado fue consistente con la tesis del motor final

la comparación histórica a DD ~ 20.4% se usa solo como benchmark auxiliar de calidad del engine, no como comparación final vinculante entre finalistas actuales

19) Nota metodológica de validez y uso operativo
¿Hay look-ahead en estos resultados?

No se observa evidencia de look-ahead duro en legacy_best_refined ni en E2.5 solo.

Razones:

research congelado y luego uso OOS con registry congelado

decisiones generadas desde contexto, no desde resultados futuros

evaluación sobre ledgers cerrados por reglas definidas

Cautela importante:
El híbrido fue validado como arbitraje entre ledgers ya generados, pero luego se auditó su scheduler y su robustez. El resultado ya es suficiente para cierre metodológico del símbolo, aunque una implementación live definitiva idealmente debería vivir en un executor único integrado.

¿Hay p-hacking?

No parece haber p-hacking duro en sentido clásico, pero sí existe riesgo moderado de selección de modelo en monetización.

Lectura práctica:

el edge no se inventó desde PnL puro; Phase E ya lo había detectado antes

sí hubo exploración operativa posterior para encontrar sleeves y configuraciones que sobrevivían

en E2.5 se revisaron múltiples buckets y configuraciones

en Balance se hizo una adaptación signed explícita para volver comparable un sleeve que nativamente salía como NONE

Conclusión

look-ahead duro: no evidente

p-hacking duro: no

riesgo de selección / data-snooping en monetización: sí, moderado

¿Esto ya está en condiciones de generar señales de trading, tal cual está?

Legacy best refined

sí, para paper trading, live-shadow o despliegue muy controlado

E2.5 solo

sí, como sleeve experimental serio, no como reemplazo directo del legacy

Híbrido

sí, para paper trading / live-shadow / generación controlada de señales

para capital real automático, sigue siendo recomendable una implementación integrada única del executor, pero eso ya no bloquea el cierre metodológico del símbolo

20) Veredicto final del símbolo
CAPTURABLE
Lectura final

XAU sí mostró edge estructural claro y monetizable.

El legacy_best_refined quedó como mejor motor legacy puro y benchmark refinado defendible.

E2.5 no reemplaza históricamente al legacy, pero sí aporta una manga nueva con drawdown mucho menor y buen desempeño reciente.

La mejor política total actual del símbolo es el híbrido:

E2.5 priority + legacy_best fallback no-overlap

Jerarquía final

Mejor política total: híbrido

Mejor motor legacy puro: legacy_best_refined

Mejor motor E2.5 puro: SR NY_PM LONG sigma-native 1.75/1.20 ts18 nostack

21) Siguiente acción

Pasar a portafolio candidato, dejando explícito que para XAU conviven:

benchmark legacy refinado validado,

sleeve E2.5 validado,

y política híbrida como mejor solución operativa actual

22) Reproducibilidad exacta — bloque legacy vinculante
Convención general

todos los comandos están en formato de una sola línea para Spyder / terminal Windows

PYTHONPATH=. debe estar seteado

la convención de costos usada en el cierre final es spread60

22.1 Construcción base del símbolo
!set PYTHONPATH=. && python scripts/build_phase_d_context.py --symbol "XAUUSD.mg" --start "2023-01-01" --end "2025-12-31" --timeframe "H2" --window-hours 24 --output-dir "outputs/phase_d_context"
!set PYTHONPATH=. && python scripts/build_prices_h2.py --symbol "XAUUSD.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --out_prices_parquet "outputs/prices/prices_H2_XAUUSD.mg_2023-01-01_2025-12-31.parquet" --timeframe "H2" --pad_hours 24
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_ohlc.py --symbol "XAUUSD.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --prices_parquet "outputs/prices/prices_H2_XAUUSD.mg_2023-01-01_2025-12-31.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc.parquet"
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_vwap_bands.py --symbol "XAUUSD.mg" --in_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet"
22.2 Phase E research binding
!set PYTHONPATH=. && python scripts/phase_e.py --symbol "XAUUSD.mg" --start "2023-01-01" --end "2024-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline
22.3 Phase F congelado desde research
!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "XAUUSD.mg" --barstream "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/XAUUSD.mg.yaml" --symbol_config "configs/symbols/XAUUSD.mg.yaml" --outdir "outputs/phase_f_runs/XAUUSD_frozen_from_research"
!set PYTHONPATH=. && python scripts/phase_f_direction_layer.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions.csv" --out_csv "outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions_with_side.csv" --phase_f_policy "configs/phase_f/XAUUSD.mg.yaml"
22.4 Convención de costos spread60
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
22.5 Subsets legacy exactos

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
22.6 Backtests legacy exactos
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv" --setup_family "transition_persistence" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 18 --allow_overlapping_trades --max_positions 3 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60"
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv" --setup_family "transition_persistence" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 18 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60_nostack"
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/SR_TS_UP_NY.csv" --setup_family "state_reinforcement" --side LONG --trigger_unit episodes --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 24 --allow_overlapping_trades --max_positions 2 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_trend_template_trendUP_NY_spread60"
22.7 Construcción del combo legacy final y variante portable
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
23) Reproducibilidad exacta — bloque E2.5 / híbrido vinculante
23.1 Corrida base E2.5

Entradas clave:

outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet

outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet

configs/phase_f/XAUUSD.mg.e25_frozen.yaml

outputs/phase_f_runs/XAUUSD_e25_frozen_audit/

23.2 Bridge E2.5
!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "XAUUSD.mg" --barstream "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/XAUUSD.mg.e25_frozen.yaml" --symbol_config "configs/symbols/XAUUSD.mg.yaml" --outdir "outputs/phase_f_runs/XAUUSD_e25_frozen_audit"
!set PYTHONPATH=. && python scripts/annotate_decisions_with_e25.py --symbol "XAUUSD.mg" --decisions_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions.csv" --out_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions_e25.csv"
!set PYTHONPATH=. && python scripts/phase_f_direction_layer_e25.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions_e25.csv" --out_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions_with_side_e25_audit.csv" --phase_f_policy "configs/phase_f/XAUUSD.mg.e25_frozen.yaml"
23.3 Winner E2.5 exacto

Winner auditado:

SR | NY_PM LONG | sigma-native | 1.75 / 1.20 | ts18 | nostack

Trades parquet:

outputs/phase_f_runs/XAUUSD_e25_frozen_audit/microgrid_SR_NYPM_LONG_sigma_native/sigma_1p75_1p20_ts18_nostack/trades.parquet

23.4 Híbrido exacto recomendado

Regla:

E2.5 priority

legacy_best fallback solo si no hay overlap temporal con trade E2.5 activo

Output final recomendado:

outputs/phase_f_runs/XAUUSD_e25_frozen_audit/HYBRID_e25_priority_legacyBEST_fallback_nooverlap/trades.parquet

23.5 Test de robustez strict del scheduler

Solo como prueba de robustez, se auditó además:

outputs/phase_f_runs/XAUUSD_e25_frozen_audit/HYBRID_e25_priority_legacyBEST_STRICT_nooverlap_all/trades.parquet

No es la política final recomendada; se usó solo para validar que la concurrencia residual no era material.

24) Versión ultra corta para bitácora ejecutiva

XAUUSD
Naturaleza: transición dominante con sleeve de continuación de tendencia; balance descriptivo, pero secundario en monetización.
Edge principal: trend_strong_orderly / STATE_REINFORCEMENT / 7.42 pp, transition_chop_near_vwap / TRANSITION_PERSISTENCE / 3.98 pp.
Legacy best refined: combo Transition NY + SR NY trendUP, raw +38.98%, maxDD=-6.31%.
E2.5 validado: SR NY_PM LONG sigma-native 1.75/1.20 ts18 nostack, raw +13.53%, maxDD=-2.38%.
Híbrido final recomendado: E2.5 priority + legacy_best fallback no-overlap, raw +29.97%, maxDD=-2.63%, comparable @ DD 6.31% +85.68%.
Veredicto: CAPTURABLE. Mejor política actual: híbrido.
