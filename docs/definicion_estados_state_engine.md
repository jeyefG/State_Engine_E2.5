# Definición matemática de estados del State Engine

Este documento resume la definición **implementada en código** para los estados:

- `BALANCE`
- `TRANSITION`
- `TREND`

Fuente principal: `state_engine/features.py` y `state_engine/labels.py`.

---

## 1) Variables base (en tiempo \(t\))

Sea una ventana principal de tamaño \(w\) (`window`) y una ventana reciente \(r\) (`recent_window`).

- Precio de cierre: \(C_t\)
- Máximo y mínimo: \(H_t, L_t\)

### ATR

\[
TR_t = \max\{H_t-L_t,\ |H_t-C_{t-1}|,\ |L_t-C_{t-1}|\}
\]
\[
ATR_w(t)=\frac{1}{w}\sum_{i=t-w+1}^{t} TR_i
\]
\[
ATR_r(t)=\frac{1}{r}\sum_{i=t-r+1}^{t} TR_i
\]

### Desplazamiento, Path, Eficiencia

\[
D_t = |C_t - C_{t-w}|
\]
\[
PathRaw_t = \sum_{i=t-w+1}^{t} |C_i - C_{i-1}|
\]
\[
ER_t = \frac{D_t}{PathRaw_t}
\]
\[
NetMove_t = \frac{D_t}{ATR_w(t)}
\]

### Rango previo y métricas auxiliares

Con rango calculado sobre barras previas (hasta \(t-1\)):

\[
R^{high}_t = \max(H_{t-w},\dots,H_{t-1}), \quad R^{low}_t = \min(L_{t-w},\dots,L_{t-1})
\]
\[
BreakMag_t = \frac{|C_t - clamp(C_t, R^{low}_t, R^{high}_t)|}{ATR_r(t)}
\]

`ReentryCount` = cantidad de reingresos en ventana reciente (pasar de fuera del rango a dentro).

`InsideBarsRatio` = proporción de barras inside en ventana reciente.

---

## 2) Umbrales por defecto (`StateLabeler`)

- `trend_er = 0.34`
- `trend_netmove = 1.15`
- `balance_er = 0.30`
- `balance_netmove = 1.20`
- `balance_inside_ratio = 0.16` (confirmación por defecto)

Para transición:

- `transition_breakmag = 0.25`
- `transition_reentry = 1.0`
- `transition_er_low = 0.27`
- `transition_er_high = 0.35`
- `transition_inside_drop = 0.15`

---

## 3) Definición de cada estado

## 3.1 TREND

Con `bootstrap_option = "A"` y `confirmation_feature = "InsideBarsRatio"` (defaults):

\[
TREND_t \iff (ER_t \ge 0.34) \land (NetMove_t \ge 1.15) \land (InsideBarsRatio_t \le 0.16)
\]

Intuición: movimiento eficiente y con desplazamiento neto alto, con baja compresión interna.

## 3.2 BALANCE

\[
BALANCE_t \iff (ER_t \le 0.30) \land (NetMove_t \le 1.20) \land (InsideBarsRatio_t \ge 0.16)
\]

Intuición: baja eficiencia direccional y comportamiento más de rango/rotación.

## 3.3 TRANSITION

En implementación, `TRANSITION` es la etiqueta por defecto y además tiene reglas explícitas, evitando pisar `TREND` y `BALANCE`:

\[
TRANSITION_t \iff TransitionRules_t \land \neg TREND_t \land \neg BALANCE_t
\]

Con reglas:

- **rule_a**:
\[
(BreakMag_t \ge 0.25) \land (ReentryCount_t \ge 1.0)
\]

- **rule_b**: zona intermedia + inestabilidad
\[
(ER_t \in [0.27,0.35]) \land (NetMove_t \in [1.20,1.15]) \land Instability_t
\]

donde `Instability` se activa si hay break, reentry, o caída de `InsideBarsRatio` mayor o igual a `0.15`.

- **rule_c** (si existe `RangeSlope`):
\[
(RangeSlope_t > 0) \land (InsideBarsRatio_{t-1} - InsideBarsRatio_t \ge 0.15)
\]

> Nota: en `rule_b` el intervalo de `NetMove` aparece como `[1.20, 1.15]` según el código actual, por lo que en práctica puede quedar desactivado (límite inferior mayor al superior).

---

## 4) Significado práctico (descriptivo, no señal)

- **Balance**: régimen de equilibrio/rango, poca direccionalidad efectiva.
- **Transition**: régimen inestable de cambio estructural.
- **Trend**: régimen direccional con desplazamiento eficiente.

En línea con la arquitectura del repo, estas etiquetas son de **contextualización estructural** (no equivalen a decisión operativa por sí mismas).
