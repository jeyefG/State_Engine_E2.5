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

1. **legacy** como benchmark histórico,
2. **E2.5** como candidato a mejor motor actual,
3. y **híbrido** como política de ejecución combinada cuando tenga sentido.

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

- **Mixto pero sano**.
- **Tendencia** se mantiene fuerte e incluso mejora.
- **Transición** persiste, aunque con menor uplift en 2025.
- **Balance** sigue existiendo descriptivamente, pero no capturó bien.

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

### Motores incluidos

- Transition NY
- SR NY trendUP

### Candidato principal legacy (con stacking)

- trades=83
- trades/week=0.53
- EV/trade=0.004063
- EV/month≈0.94%
- winrate=67.47%
- maxDD=-6.40%

### Variante portable / cross-symbol (sin stacking)

- trades=71
- trades/week=0.46
- EV/trade=0.003284
- winrate=66.20%
- maxDD=-6.40%

### EV_total anual

**Candidato principal (con stacking)**
- 2023: 0.053280
- 2024: 0.095443
- 2025: 0.188504

**Variante portable (sin stacking)**
- 2023: 0.046064
- 2024: 0.066835
- 2025: 0.120263

### Lectura

Este combinado superó al Combo B previo y al combo histórico abierto en calidad ajustada por riesgo. Mantiene positividad en 2023, 2024 y 2025, baja el drawdown y además sobrevive sin depender críticamente de stacking.

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
```

### Activos principales

- **Policy frozen:** `configs/phase_f/XAUUSD.mg.e25_frozen.yaml`
- **Run principal audit:** `outputs/phase_f_runs/XAUUSD_e25_frozen_audit/`
- **Barstream:** `outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet`
- **Enriched usado:** `outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet`

### Lectura metodológica

- legacy se usa como **benchmark**, no como restricción ontológica
- E2.5 se evalúa como **motor actual alternativo**
- todos los runs relevantes se reportan en dos capas:
  - **raw**
  - **legacy-comparable** (`capital inicial = 1000`, `dd_norm = -20.4%`)

---

## 10) E2.5 — TP review

### Metodología

1. Screening canónico:
   - bars + fixed
   - episodes + state_change
2. Luego micro-grid refinado corrigiendo comparabilidad:
   - legacy estaba en puntos
   - el backtester usa sigma-k
   - se hizo traducción bucket por bucket de equivalentes legacy → sigma
3. Luego micro-grid:
   - stacking vs no-stack
   - time_stop 12 / 18 / 24

### Buckets revisados

- ASIA LONG
- ASIA SHORT
- NY_PM LONG
- NY_PM SHORT
- LONDON LONG
- LONDON SHORT
- NY LONG
- NY SHORT

### Resultado

**Todos los buckets murieron con evidencia robusta.**

### Lectura

- EV/trade negativo en todos
- stacking no movió nada relevante
- time_stop no movió nada relevante
- lo que parecía vivo antes se cayó al corregir `pts vs sigma`

**Conclusión práctica:** TP review queda descartado operativamente en XAU.

---

## 11) E2.5 — SR core

### Inventario auditado

- NY_PM LONG = 143
- LONDON LONG = 104
- ASIA LONG = 101
- NY LONG = 89
- NY_PM SHORT = 64
- LONDON SHORT = 50
- NY SHORT = 33
- ASIA SHORT = 30

### Resultado bucket por bucket

#### 11.1) SR | NY_PM LONG

**Screening canónico**
- bars_fixed:
  - n_trades = 92
  - EV/trade = 0.001134
  - winrate = 54.35%
  - maxDD = -1.90%
- episodes_state_change:
  - n_trades = 83
  - EV/trade = 0.001307
  - winrate = 54.22%
  - maxDD = -2.12%

**Micro-grid legacy-equivalent**  
Se probaron equivalentes a 30/20, 40/25, 50/30 en sigma. Todos quedaron negativos.

**Micro-grid sigma-native ganador**
- tp/sl: **1.75 / 1.20**
- time_stop: **18**
- stacking: **no-stack**

**Ganador actual E2.5 para XAU**
- raw:
  - n_trades = 92
  - trades/week = 0.589204
  - EV/trade = 0.001398
  - winrate = 56.52%
  - maxDD = -2.38%
- legacy-comparable:
  - 1000 → 2645.82
  - retorno comparable = **+164.58%**
  - dd_norm = -20.4%

#### 11.2) SR | LONDON LONG
- screening canónico negativo
- comparable legacy aprox: -19.23% / -13.63%
- **muere**

#### 11.3) SR | ASIA LONG
- screening canónico negativo
- comparable legacy aprox: -18.04% / -13.61%
- **muere**

#### 11.4) SR | NY LONG
- bars_fixed sobrevive débil
- n_trades = 76
- EV/trade = 0.000323
- comparable legacy ≈ +10.62%
- **candidato secundario**, muy lejos del líder

#### 11.5) SR | NY_PM SHORT
- bars_fixed negativo
- comparable legacy ≈ -10.23%
- episodes peor aún
- **muere**

#### 11.6) SR | LONDON SHORT
- bars_fixed sobrevive débil
- n_trades = 38
- EV/trade = 0.000369
- comparable legacy ≈ +6.71%
- **no promueve por n_trades < 40**

#### 11.7) SR | NY SHORT
- bars_fixed sobrevive débil
- n_trades = 29
- EV/trade = 0.000447
- comparable legacy ≈ +11.47%
- **no promueve por poca masa**

#### 11.8) SR | ASIA SHORT
- bars_fixed: EV/trade = -0.001152
- episodes_state_change: EV/trade = -0.000246
- **muere**

### Veredicto SR E2.5

SR sí rescata valor en XAU, pero el rescate queda **fuertemente concentrado** en:

**SR | NY_PM LONG | sigma-native | 1.75 / 1.20 | ts18 | nostack**

---

## 12) E2.5 — Balance review

### Nota metodológica importante

En el wiring actual, `balance_stability_center` y `balance_stability_tail` bajan a `NONE`, no a LONG/SHORT. Para hacer la comparación de EV comparable, se construyó una **adaptación explícita de auditoría**:

- `close > ctx_vwap` → `SHORT`
- `close < ctx_vwap` → `LONG`
- `close == ctx_vwap` → drop

Esta conversión **no es el behavior nativo** del direction layer. Se usó solo para cerrar la auditoría de comparabilidad.

### Resultado por bucket

#### ASIA center signed
- bars_fixed: EV/trade = -0.000273
- episodes_state_change: EV/trade = -0.000046
- **muere**

#### LONDON center signed
- bars_fixed: EV/trade = -0.001610
- episodes_state_change: EV/trade = -0.004614
- **muere claramente**

#### NY_PM center signed
- bars_fixed:
  - n_trades = 50
  - EV/trade = 0.000385
  - maxDD = -2.00%
- episodes_state_change:
  - n_trades = 49
  - EV/trade = 0.000221
  - maxDD = -6.15%
- **vive débilmente**, pero no compite con SR

#### NY center signed
- bars_fixed:
  - n_trades = 20
  - EV/trade = 0.000947
  - maxDD = -0.95%
- episodes_state_change:
  - n_trades = 18
  - EV/trade = 0.000476
  - maxDD = -3.00%
- **vive débilmente**, pero no promociona por masa

### Veredicto Balance E2.5

Balance no cambia la decisión del símbolo. Aporta algo de vida táctica en NY_PM y NY, pero **no desplaza al sleeve SR** y no justifica tuning adicional en esta ronda.

---

## 13) Comparación final a DD común (-20.4%)

### Convención de comparabilidad

Todos los motores relevantes se comparan con dos capas:

1. **raw**
   - n_trades
   - EV/trade
   - winrate
   - maxDD
2. **legacy-comparable**
   - capital inicial = USD 1,000
   - reescalado a `maxDD = -20.4%`
   - capital final comparable
   - retorno comparable

### 13.1) Legacy solo

- n_trades = 71
- EV/trade = 0.003284
- winrate = 66.20%
- raw final capital = 1253.95
- raw total return = +25.40%
- raw maxDD = -6.31%
- comparable final capital = 2021.96
- comparable return = **+102.20%**

### 13.2) E2.5 solo

**Motor usado:** `SR | NY_PM LONG | sigma-native | 1.75 / 1.20 | ts18 | nostack`

- n_trades = 92
- EV/trade = 0.001398
- winrate = 56.52%
- raw final capital = 1135.31
- raw total return = +13.53%
- raw maxDD = -2.38%
- comparable final capital = 2645.82
- comparable return = **+164.58%**

### 13.3) Overlap legacy vs E2.5

- legacy trades = 71
- E2.5 trades = 92
- legacy overlapped by E2.5 = 34
- legacy kept for hybrid = 37
- hybrid total trades = 129
- overlap legacy vs E2.5 = **47.89%**

### 13.4) Híbrido

**Regla:** E2.5 manda; si no hay trade E2.5 activo, pasa legacy.

- n_trades = 129
- EV/trade = 0.001775
- winrate = 58.91%
- raw final capital = 1251.82
- raw total return = +25.18%
- raw maxDD = -2.63%
- comparable final capital = 4853.52
- comparable return = **+385.35%**

### Lectura comparativa final

- **Legacy solo** sigue siendo fuerte en raw.
- **E2.5 solo** ya supera a legacy cuando se compara a DD común.
- **Híbrido** es la mejor política total actual para XAU:
  - retiene casi todo el retorno raw del legacy,
  - con drawdown mucho menor,
  - y domina ampliamente en retorno comparable.

---

## 14) Costos y realismo

- **Spread aplicado:** sí
- **ret_net validado distinto de ret_gross:** sí

### Observación

- neto modelado con `spread60`
- el histórico del broker no traía spread usable en gran parte de 2023-2024 y comienzos de 2025
- el tramo post-2025-02-18 observado fue consistente con la tesis del motor final
- la comparación “sin spread a DD comparable” se usó solo como benchmark auxiliar de calidad del engine, no como resultado oficial

---

## 15) Veredicto final del símbolo

## CAPTURABLE

### Lectura final

XAU sí mostró edge estructural claro y monetizable. El legado quedó validado como benchmark fuerte; E2.5 encontró un sleeve superior en eficiencia de riesgo; y la mejor política total actual resultó ser el **híbrido**:

**E2.5 priority + legacy fallback no-overlap**

### Jerarquía final

1. **Mejor política total:** híbrido  
2. **Mejor motor E2.5 puro:** SR NY_PM LONG sigma-native 1.75/1.20 ts18 nostack  
3. **Mejor benchmark legacy:** combo transitionNY + SRtrendUP_NY

---

## 16) Siguiente acción

**Pasar a portafolio candidato**, dejando explícito que para XAU conviven:

- benchmark legacy validado,
- sleeve E2.5 superior por DD comparable,
- y política híbrida como mejor solución operativa actual.

---

## 17) Reproducibilidad exacta — bloque legacy vinculante

### Convención general

- todos los comandos están en formato de una sola línea para Spyder / terminal Windows
- `PYTHONPATH=.` debe estar seteado
- la convención de costos usada en el cierre final es `spread60`

### 17.1 Construcción base del símbolo

```python
!set PYTHONPATH=. && python scripts/build_phase_d_context.py --symbol "XAUUSD.mg" --start "2023-01-01" --end "2025-12-31" --timeframe "H2" --window-hours 24 --output-dir "outputs/phase_d_context"
!set PYTHONPATH=. && python scripts/build_prices_h2.py --symbol "XAUUSD.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --out_prices_parquet "outputs/prices/prices_H2_XAUUSD.mg_2023-01-01_2025-12-31.parquet" --timeframe "H2" --pad_hours 24
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_ohlc.py --symbol "XAUUSD.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --prices_parquet "outputs/prices/prices_H2_XAUUSD.mg_2023-01-01_2025-12-31.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc.parquet"
!set PYTHONPATH=. && python scripts/build_phase_f_enriched_vwap_bands.py --symbol "XAUUSD.mg" --in_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet"
```

### 17.2 Phase E research binding

```python
!set PYTHONPATH=. && python scripts/phase_e.py --symbol "XAUUSD.mg" --start "2023-01-01" --end "2024-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline
```

### 17.3 Phase F congelado desde research

```python
!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "XAUUSD.mg" --barstream "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/XAUUSD.mg.yaml" --symbol_config "configs/symbols/XAUUSD.mg.yaml" --outdir "outputs/phase_f_runs/XAUUSD_frozen_from_research"
!set PYTHONPATH=. && python scripts/phase_f_direction_layer.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions.csv" --out_csv "outputs/phase_f_runs/XAUUSD_frozen_from_research/decisions_with_side.csv" --phase_f_policy "configs/phase_f/XAUUSD.mg.yaml"
```

### 17.4 Convención de costos spread60

```python
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
```

### 17.5 Subsets legacy exactos

**A) Transition TU base**

```python
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
```

**B) SR NY trendUP**

```python
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
```

### 17.6 Backtests legacy exactos

```python
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv" --setup_family "transition_persistence" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 18 --allow_overlapping_trades --max_positions 3 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60"
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/decisions_transition_unclassified_long.csv" --setup_family "transition_persistence" --side LONG --trigger_unit bars --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 18 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_transition_template_current_spread60_nostack"
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAU_current_templates/SR_TS_UP_NY.csv" --setup_family "state_reinforcement" --side LONG --trigger_unit episodes --exit_mode fixed --tp_k 40 --sl_k 25 --time_stop_bars 24 --allow_overlapping_trades --max_positions 2 --use_spread --out_dir "outputs/backtests/XAU_current_templates_orig/BT_trend_template_trendUP_NY_spread60"
```

### 17.7 Construcción del combo legacy final y variante portable

```python
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
```

```python
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
```

---

## 18) Reproducibilidad exacta — bloque E2.5 / híbrido vinculante

### 18.1 Corrida base E2.5

Entradas clave:
- `outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet`
- `outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet`
- `configs/phase_f/XAUUSD.mg.e25_frozen.yaml`
- `outputs/phase_f_runs/XAUUSD_e25_frozen_audit/`

### 18.2 Bridge E2.5

```python
!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "XAUUSD.mg" --barstream "outputs/phase_d_context/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31.parquet" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_edge_baseline/XAUUSD.mg_PhaseE_M30_2023-01-01_2024-12-31_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/XAUUSD.mg.e25_frozen.yaml" --symbol_config "configs/symbols/XAUUSD.mg.yaml" --outdir "outputs/phase_f_runs/XAUUSD_e25_frozen_audit"
!set PYTHONPATH=. && python scripts/annotate_decisions_with_e25.py --symbol "XAUUSD.mg" --decisions_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions.csv" --out_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions_e25.csv"
!set PYTHONPATH=. && python scripts/phase_f_direction_layer_e25.py --symbol "XAUUSD.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_XAUUSD.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands_spread60.parquet" --decisions_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions_e25.csv" --out_csv "outputs/phase_f_runs/XAUUSD_e25_frozen_audit/decisions_with_side_e25_audit.csv" --phase_f_policy "configs/phase_f/XAUUSD.mg.e25_frozen.yaml"
```

### 18.3 Winner E2.5 exacto

Winner auditado:
- `SR | NY_PM LONG | sigma-native | 1.75 / 1.20 | ts18 | nostack`
- trades parquet:
  - `outputs/phase_f_runs/XAUUSD_e25_frozen_audit/microgrid_SR_NYPM_LONG_sigma_native/sigma_1p75_1p20_ts18_nostack/trades.parquet`

### 18.4 Legacy-comparable a DD = -20.4%

La comparación vinculante se hace leyendo `trades.parquet` y reescalando a:
- capital inicial = 1000
- drawdown objetivo = -20.4%

Paths usados:
- legacy comparable:
  - `outputs/backtests/XAU_current_templates_orig/BT_combo_transitionNY_SRtrendUP_NY_nostack/trades.parquet`
- E2.5 comparable:
  - `outputs/phase_f_runs/XAUUSD_e25_frozen_audit/microgrid_SR_NYPM_LONG_sigma_native/sigma_1p75_1p20_ts18_nostack/trades.parquet`

### 18.5 Híbrido exacto

Regla:
- **E2.5 priority**
- **legacy fallback** solo si no hay overlap temporal con trade E2.5 activo

Output final del híbrido:
- `outputs/phase_f_runs/XAUUSD_e25_frozen_audit/HYBRID_e25_priority_legacy_fallback_nooverlap/trades.parquet`

---

## 19) Versión ultra corta para bitácora ejecutiva

**XAUUSD**  
Naturaleza: transición dominante con sleeve de continuación de tendencia; balance descriptivo, pero secundario en monetización.  
Edge principal: `trend_strong_orderly / STATE_REINFORCEMENT / 7.42 pp`, `transition_chop_near_vwap / TRANSITION_PERSISTENCE / 3.98 pp`.  
Legacy validado: combo `Transition NY + SR NY trendUP`.  
E2.5 validado: `SR NY_PM LONG sigma-native 1.75/1.20 ts18 nostack`.  
Resultado comparable a DD común: legacy `+102.20%`, E2.5 `+164.58%`, híbrido `+385.35%`.  
Veredicto: **CAPTURABLE**. Mejor política actual: **híbrido E2.5 priority + legacy fallback no-overlap**.
