# Pipeline multi-símbolo — State Engine
**Versión integrada y ordenada**  
**Base:** PRE NEW E2.5 LAYER

---

## 0) Principio rector (inviolable)

### 0.1 Qué es el State Engine y qué no es
El pipeline se sostiene sobre una separación conceptual estricta:

- **Phase D** describe estructura (ontología): `STATE / QL / LOOK_FOR`.
- **Phase E** mide edge estadístico: `uplift vs baselines canónicos`.
- **Phase F** monetiza solo lo que **Phase E** validó, usando `policy + templates canónicos` o explícitamente justificados.

Separación obligatoria:

- **Phase D** describe la naturaleza del instrumento.
- **Phase E** valida si existe edge estructural.
- **Phase F** intenta capturar ese edge con la menor cantidad posible de supuestos extra.
- **El backtest no redefine ontología**. El backtest prueba captura, no existencia.

### 0.2 Objetivo económico real del proyecto
El objetivo del proyecto **no** es maximizar research abierto ni “entender por entender”.

El objetivo es transformar el State Engine en una fuente de ingresos lo antes posible.

Eso implica una metodología distinta:

- no queremos investigación infinita;
- no queremos ontologías bonitas pero imposibles de monetizar;
- no queremos prolongar símbolos ambiguos por apego al trabajo ya hecho.

Queremos:

- motores netos;
- OOS;
- simples;
- comparables;
- combinables en portafolio.

### 0.3 Prohibido
Sigue prohibido:

- diseñar monetización antes de entender edge;
- tocar **Phase D** por PnL;
- inventar LFs por “faltó plata”;
- ajustar YAML solo para subir `ALLOW`;
- usar el backtest para redefinir ontología;
- confundir un fallback jerárquico con bug si el contexto fino no pasa thresholds;
- usar `abs_move + side NONE` como prueba final de monetización económica;
- aceptar resultados “netos” sin verificar que `ret_net != ret_gross` cuando se pidió spread/costos.

### 0.4 Permitido (sin p-hack)
Sigue permitido:

- iterar ontología por símbolo solo como hipótesis estructural escrita;
- corregir wiring / trazabilidad / coverage si el sistema pierde descripción contextual;
- cambiar policy para que aguante contextos finos y agregados, siempre que eso refleje lo que **Phase E** realmente validó;
- explorar monetización de un edge ya validado, mientras el barrido sea corto, estructural y justificado *ex ante*;
- usar una ronda final de due diligence si todavía quedan hipótesis razonables sobre la naturaleza del símbolo.

---

## 1) Cálculo de `state_hat` y lectura correcta del estado

Antes de cualquier YAML o monetización, hay que entender bien qué representa `state_hat`, porque de eso depende toda la ontología.

### 1.1 Qué describe `state_hat`
El sistema clasifica cada barra en estados estructurales, típicamente:

- `BALANCE`
- `TRANSITION`
- `TREND`

El objetivo no es “predecir precio” en esta etapa, sino **describir la naturaleza estructural del instrumento**.

### 1.2 Qué debe responder la lectura de estados
La lectura de `state_hat` debe permitir responder preguntas como:

- ¿el instrumento vive más en balance, en transición o en tendencia?
- ¿el cambio de estado es frecuente o persistente?
- ¿hay degradación a ruido o resolución limpia?
- ¿qué sesión construye balance, cuál lo degrada y cuál lo resuelve?
- ¿el instrumento repricia alrededor de un centro o deriva direccionalmente?

### 1.3 Regla metodológica
No basta con mirar que existan activaciones.  
Hay que entender si el símbolo es **legible estructuralmente**.

La lectura correcta debe responder:

- qué estado domina;
- qué `QL` domina;
- si la ontología parece viva o muerta;
- si la mezcla conversa con la intuición del símbolo;
- si la hipótesis estructural es coherente antes de correr **Phase E**.

---

## 2) Baselines canónicas: qué son y cómo se usan

### 2.1 Qué es realmente un baseline en el runner actual
En el runner actual, los baselines de **Phase E** son lentes canónicos `state-only within-K`.

Eso significa:

- se toma la fila en `t`,
- se mira la trayectoria de `base_state` en `t+1 ... t+k`,
- y se marca una propiedad binaria `y = 1/0`,
- dejando los últimos `k` bars en `NaN`.

No es un target de precio.  
No es una trayectoria económica completa.  
No es un trade simulation.  
Es una **propiedad estructural de la trayectoria de estados dentro de una ventana futura**.

### 2.2 Qué sí mide bien Phase E
**Phase E** hoy sí puede medir de forma útil:

- persistencia del estado;
- fragilidad del estado;
- escape de balance;
- degradación de balance a transición;
- resolución de transición a trend;
- fallback de transición a balance;
- permanencia de transición dentro de `K`.

Eso es útil para construir hipótesis ontológicas.

### 2.3 Qué no debe inferirse erróneamente
Los baselines actuales **no describen trayectorias exclusivas ni ordenadas**.

Ejemplo:
Una transición puede ser simultáneamente:

- `TRANSITION_RESOLUTION = 1` porque toca `TREND` dentro de `K`,
- y también `TRANSITION_FALLBACK_TO_BALANCE = 1` porque toca `BALANCE` dentro de `K`.

Eso no es bug.  
Significa que la ventana dentro de `K` visitó ambos estados.

Por lo tanto:

- estos baselines no son escenarios mutuamente excluyentes;
- no deben leerse como “clasificación final de la trayectoria”;
- no equivalen directamente a una historia económica completa.

Lo correcto es leerlos como:

> esta narrativa tiene uplift respecto de cierta propiedad estructural dentro de una ventana futura.

### 2.4 Baselines confiables
#### `STATE_REINFORCEMENT`
`y=1` si el estado actual permanece igual toda la ventana `K`.

#### `STATE_FRAGILITY`
`y=1` si el estado actual sale al menos una vez dentro de `K`.

#### `BALANCE_ESCAPE`
`y=1` si, estando en `BALANCE`, la trayectoria toca `TREND` dentro de `K`.

#### `BALANCE_CONTAINMENT`
`y=1` si, estando en `BALANCE`, la trayectoria no toca `TREND` dentro de `K`.

#### `BALANCE_DEGRADATION` / `BALANCE_LEAK_TO_TRANSITION`
`y=1` si, estando en `BALANCE`, la trayectoria toca `TRANSITION` dentro de `K`.

#### `BALANCE_STABILITY` / `BALANCE_NOT_LEAK_TO_TRANSITION`
`y=1` si, estando en `BALANCE`, la trayectoria no toca `TRANSITION` dentro de `K`.

#### `TRANSITION_RESOLUTION` / `TRANSITION_BREAKOUT`
`y=1` si, estando en `TRANSITION`, la trayectoria toca `TREND` dentro de `K`.

#### `TRANSITION_NOISE`
`y=1` si, estando en `TRANSITION`, la trayectoria no toca `TREND` dentro de `K`.

#### `TRANSITION_FALLBACK_TO_BALANCE` / `TRANSITION_MEAN_REVERT`
`y=1` si, estando en `TRANSITION`, la trayectoria toca `BALANCE` dentro de `K`.

#### `TRANSITION_NOT_FALLBACK_TO_BALANCE`
`y=1` si, estando en `TRANSITION`, la trayectoria no toca `BALANCE` dentro de `K`.

#### `TRANSITION_PERSISTENCE`
`y=1` si, estando en `TRANSITION`, la trayectoria permanece en `TRANSITION` toda la ventana `K`.

### 2.5 Aliases equivalentes
Hay aliases semánticos que en implementación son iguales. Deben leerse como sinónimos narrativos, no como outcomes distintos:

- `BALANCE_STABILITY = BALANCE_NOT_LEAK_TO_TRANSITION`
- `BALANCE_DEGRADATION = BALANCE_LEAK_TO_TRANSITION`
- `TRANSITION_RESOLUTION = TRANSITION_BREAKOUT`
- `TRANSITION_FALLBACK_TO_BALANCE = TRANSITION_MEAN_REVERT`

### 2.6 Baselines a tratar con cautela
#### `TRANSITION_POLARITY_BIAS`
Tal como está implementado, usa `PREVIOUS_STATE` como el estado de `t-1`, no como “el estado previo estructural a la transición”.

Eso puede degenerar en una métrica poco limpia, especialmente cuando `t-1` ya era `TRANSITION`.

Por ahora debe tratarse como:

- baseline experimental;
- no baseline central para diseñar ontología;
- no base fuerte para monetización.

#### `FALSE_SIGNAL_RETURN`
Tal como está implementado, no exige correctamente el orden “salir y luego reingresar”.

Puede marcar positivo aun cuando hubo permanencia previa y salida posterior, sin reingreso real después de la salida.

Por lo tanto hoy debe considerarse:

- semánticamente defectuoso;
- no confiable como baseline principal;
- no apto para fundamentar **Phase F** sin corrección.

### 2.7 Regla de asignación de baseline
El baseline **no se elige por conveniencia estadística**.

Se elige por la pregunta ontológica que el `LF` intenta responder.

Regla:

> cada LF debe compararse contra la normalidad estructural del mismo dominio que pretende describir.

Ejemplos:

- si el LF describe `BALANCE`, su baseline debe ser una lente natural de `BALANCE`;
- si el LF describe `TRANSITION`, su baseline debe ser una lente natural de `TRANSITION`;
- si el LF describe `TREND`, debe compararse con la normalidad de `TREND`.

Frase obligatoria para cada LF:

> Quiero saber si esta narrativa supera a la normalidad estructural X.

Si esa frase no sale clara, el baseline todavía no está bien pensado.

---

## 3) Hipótesis previa del símbolo (antes de YAML y antes de Phase E research)

### 3.1 Regla general
No se parte desde los nombres del YAML heredado.

La pregunta inicial no es:

> qué LOOK_FORs le ponemos a este símbolo

sino:

> cómo se comporta este instrumento cuando está en balance, transición y tendencia, y qué edge estructural sería razonable esperar en cada caso.

### 3.2 Ejes de hipótesis
La hipótesis previa debe construirse al menos en 4 ejes.

#### Eje A — modo dominante de desplazamiento
Responder si el instrumento tiende más a:

- reversionar después de extensiones;
- repriciarse en transiciones cortas;
- continuar cuando ya tomó dirección;
- degradarse a ruido;
- o quedarse contenido sin resolver.

#### Eje B — dependencia por sesión
Preguntas:

- qué sesión construye balance;
- cuál lo degrada;
- cuál resuelve transición;
- cuál confirma tendencia;
- cuál ensucia o agota lo anterior.

#### Eje C — valor real del `QL`
Preguntas:

- ¿el `QL` agrega información estructural real?
- ¿o es mayormente ruido descriptivo?

Ejemplos:

- `TRANSITION_NOISY` puede ser ruido puro o antesala de una resolución importante;
- `TREND_FRAGILE` puede ser agotamiento o pullback sano.

La semántica no debe heredarse automáticamente desde otro símbolo.

#### Eje D — relación entre movimiento y referencia
Entender si el instrumento usa referencias tipo centro / VWAP / valor justo como:

- imán;
- frontera de repricing;
- pivote de continuación;
- o simple ruido alrededor del centro.

### 3.3 Plantilla de hipótesis previa
Antes de tocar YAML, conviene escribir:

1. Estado dominante esperado: `<BALANCE / TRANSITION / TREND / mezcla>`
2. Mecánica esperada por sesión.
3. Rol esperado del `QL`.
4. Tipo de edge esperable:
   - continuidad,
   - repricing,
   - reversión,
   - contención,
   - degradación,
   - compresión útil,
   - etc.
5. Qué probablemente no debería funcionar.

La hipótesis no tiene que estar correcta al inicio.  
Tiene que ser **clara, falsable y útil** para diseñar ontología.

### 3.4 Regla para iterar hipótesis con Phase E
La secuencia correcta es:

1. formular hipótesis previa;
2. correr **Phase E research**;
3. validar o refinar la hipótesis;
4. iterar si hace falta;
5. agregar / modificar / fusionar / borrar `LF` si es necesario;
6. solo cuando la hipótesis sea representativa del símbolo, pasar a **Phase F**.

### 3.5 Filtro por default de Phase E research
En esta etapa, **Phase E** usa por defecto:

- `min-events = 200`
- `min_days = 20`

Eso forma parte del filtro disciplinario para evitar pockets anecdóticos.

---

## 4) Metodología temporal estándar: research, freeze y OOS

### 4.1 Filosofía general
La metodología ya no debe ser “research-first” en sentido abierto.  
Debe ser **monetization-first con disciplina estructural**.

Eso significa:

- **Phase D** y **Phase E** siguen siendo obligatorias;
- el símbolo debe pasar rápido a una decisión práctica;
- toda iteración adicional debe estar justificada *ex ante*.

### 4.2 Ventana estándar
La ventana estándar por símbolo será:

- **3 años totales**
- **2 años research**
- **1 año OOS**

Ejemplo estándar:

- `2023-01-01` a `2024-12-31` = research
- `2025-01-01` a `2025-12-31` = OOS

### 4.3 Por qué este estándar
Porque da un equilibrio razonable entre:

- suficiente muestra;
- cercanía temporal;
- no diluir edge vigente con regímenes muy viejos.

No usar “todos los años posibles” por defecto.

### 4.4 Cuándo usar más historia
Solo si:

- el símbolo tiene muy poca frecuencia;
- el edge es raro y necesita más `n_bars`;
- el instrumento parece extremadamente estable.

No usar 5–10 años por inercia.

### 4.5 Qué cuenta como research
En research se puede:

- construir ontología;
- hacer mini-labs descriptivos;
- barrer una grilla corta de monetización plausible;
- decidir qué contextos entran a `policy`.

### 4.6 Qué cuenta como validación OOS
En OOS no se rediseña dentro del mismo ciclo.

En OOS solo se responde:

- ¿el edge se sostiene?
- ¿la policy resuelve coherentemente?
- ¿el template captura neto real?

Si OOS falla y todavía quedan hipótesis razonables, eso ya no es “mismo ciclo”; es una nueva iteración ontológica o un nuevo ciclo del símbolo.

### 4.7 Freeze obligatorio
Después de **Phase E research**, se congela:

- YAML de símbolo;
- `narrative_to_baseline`;
- `lf_synth.priority`;
- `go_contexts`;
- grilla corta de templates a probar.

Sin freeze, no existe OOS real.

### 4.8 Research selecciona, OOS valida
Regla operativa:

- **Research selecciona**
- **OOS valida**
- **Phase E OOS informa**, pero no re-selecciona

Eso implica:

- `min_n_bars` pertenece a research;
- en OOS no debe reinterpretarse como gate de existencia;
- en OOS se usa el **registry de research**, no uno nuevo.

---

## 5) Cambios estructurales ya aplicados al sistema

### 5.1 LF synthesis correcto
El `lf` ya no debe depender del resolver ni de normalizaciones tardías.

Se sintetiza desde flags binarios `LOOK_FOR_*` presentes en el barstream, usando:

- `lf_synth.priority`
- `none_token`

Regla correcta en `run_phase_f.py`:

1. extrae flags `LOOK_FOR_*`
2. sintetiza `lf`
3. construye `ContextRow(state, ql, lf)`
4. recién después llama al resolver / policy

Resultado esperado:

- `lf_context_mismatch = 0` o casi 0
- no más colapso artificial a `LF=NONE` cuando sí había `LOOK_FOR` activo

### 5.2 Separación explícita entre contexto descriptivo y monetizado
Ahora se exportan ambos:

#### `engine_context_key`
Siempre representa el contexto real del bar:

`STATE={state real}|QL={ql real}|LF={lf real}`

#### `context_key`
Representa el contexto finalmente seleccionado por `policy` tras fallback jerárquico.

Nueva metadata de auditoría:

- `ql_context_mismatch`
- `lf_context_mismatch`

Interpretación correcta:

Si ves:

- `engine_context_key = STATE=TRANSITION|QL=TRANSITION_NOISY|LF=LOOK_FOR_transition_chop_near_vwap`
- `context_key = STATE=TRANSITION|QL=NONE|LF=LOOK_FOR_transition_chop_near_vwap`

eso **no** significa que `QL` no llegó.  
Significa:

- el `QL` sí llegó a Phase F;
- el resolver / policy hizo fallback a `STATE_LF`.

Eso es correcto si el contexto fino no pasó thresholds o no estaba cubierto por `policy`.

### 5.3 Direction layer estable
El `direction layer`:

- usa `meta_baseline_id`;
- no redefine el edge;
- no retroalimenta `Phase E`;
- solo agrega `side_intent`, `setup_family`, columnas `fat` de enriched y trazabilidad para auditoría / backtest.

Resultado esperado:

- `meta_baseline_id` coherente con `Phase E`;
- `close hit-rate ~1.0`;
- `ctx_vwap`, `ctx_vwap_sigma`, `ctx_session_bucket` presentes;
- `setup_family` y `side_intent` poblados.

### 5.4 Merge robusto
Se normalizó el merge entre:

- `decisions.csv`
- `enriched parquet`

Sanity esperado:

- `hit_rate close ~ 1.0`
- sin `NaN`s estructurales;
- sin pérdida masiva de filas por mismatch temporal;
- `ts` y `time` ya no deben romper direction layer ni backtest.

### 5.5 Registry Phase E correcto
`PhaseECSVRegistry` debe cargar ambos niveles si quieres que `Phase F` pueda resolver fino:

- `*_lookfor_state_filtered.csv`
- `*_lookfor_state_ql_filtered.csv`

Regla:

`run_phase_f.py` debe recibir ambos `--registry_csv` cuando existan.

Si cargas solo `state_filtered`, todo tenderá a resolverse a:

- `STATE_LF`

aunque el `QL` haya llegado correctamente.

### 5.6 Metadata de auditoría de resolución
Se mantiene:

- `meta_candidate_rank`
- `meta_context_resolution_level`
- `meta_candidates_n`

Niveles:

- `STATE_QL_LF`
- `STATE_LF`
- `STATE_QL`
- `STATE`

Interpretación correcta de `STATE_LF`:

No es bug. Significa:

- el candidato fino `STATE_QL_LF` existió;
- pero no fue seleccionado por `policy`;
- el resolver cayó a agregado jerárquico.

### 5.7 Corrección metodológica en costos
Se confirmó un bug importante en backtesting:

- al menos una variante del backtester dejaba `ret_net = ret_gross` y reportaba `use_spread=True` sin descontar costo real.

Consecuencia:

- cualquier resultado que haya usado `--use_spread` en un script bugueado debe tratarse como sospechoso;
- cualquier resultado sin `--use_spread` es `gross-only` por diseño.

Directiva nueva:

Ningún símbolo se considera capturable sin verificar explícitamente costos.

Mínimo requerido:

- spread aplicado de verdad;
- `ret_net` distinto de `ret_gross` cuando corresponde;
- sanity check del costo medio.

### 5.8 Cautela con `abs_move`
Un motor `abs_move` con `side NONE` puede ser útil como:

- screening de capturabilidad de expansión;
- detector de movimiento posterior al contexto;
- evidencia de que el setup “produce algo”.

Pero **no** equivale automáticamente a monetización económica direccional real.

Interpretación correcta:

- `abs_move + side NONE` = prueba de “hay movimiento”
- `LONG/SHORT` con neto y costos = prueba de “hay estrategia monetizable”

---

## 6) Pipeline cronológico genérico

---

## 6.0 Fase 0 — Exploración ontológica previa a YAML

### Objetivo
Antes de tocar YAML, `Phase F` o monetización, responder:

> ¿Qué naturaleza estructural parece tener este instrumento, y cómo se debería traducir esa naturaleza en LOOK_FORs y baselines coherentes?

### Regla
No partir desde los nombres heredados del YAML.  
No asumir que el YAML viejo está bien.  
No definir `Phase F` antes de entender qué mide realmente `Phase E`.

### Método genérico
#### Capa 1 — Retrato bruto del símbolo
Mirar:

- mezcla de `state_hat`;
- mezcla de `quality_label`;
- distribución por sesión;
- concentración de `LF` heredados;
- riqueza o pobreza de la ontología actual;
- persistencia / cambio de estado;
- run lengths;
- flip rates.

Objetivo: salir con una impresión estructural gruesa del instrumento.

#### Capa 2 — Lectura causal tentativa
Preguntas:

- qué sesión parece construir;
- cuál resuelve;
- cuál degrada;
- qué `QL` parece separar contextos útiles;
- qué tipos de transición son plausibles;
- qué balance parece útil o inútil.

Objetivo: escribir 3–5 frases fuertes sobre la naturaleza probable del símbolo.

#### Capa 3 — Ontología explícita
Recién aquí se define:

- qué `LF` merecen existir;
- cuáles sobran;
- cuáles hay que fusionar;
- cuáles renombrar;
- qué baseline corresponde a cada uno;
- cuáles no deben heredarse del YAML viejo.

### Familias de LOOK_FOR recomendadas
Empezar con 3 o 4 familias ontológicas.

#### Familia BALANCE
Preguntar qué hace este instrumento con el balance:

- compresión útil;
- equilibrio centrado;
- balance estable descriptivo pero poco monetizable;
- balance que se degrada antes de resolver.

#### Familia TRANSITION
Preguntar si la transición es:

- repricing real;
- ruido;
- resolución;
- vuelta a balance;
- persistencia sin resolver.

#### Familia TREND
No asumir que toda tendencia es útil:

- tendencia ordenada;
- continuación por pullback;
- tendencia frágil;
- extensión tardía;
- tendencia agotada.

#### Familia MIXTA o DE PUENTE
Usar con moderación:

- balance que se degrada y libera;
- transición que confirma trend;
- trend que pierde orden y vuelve a transición.

### Regla para crear / reasignar / borrar LF
#### Crear LF nuevo
Cuando la hipótesis detecta una mecánica real que el set actual no representa bien.

#### Reasignar baseline
Cuando el `LF` sí es real, pero está siendo comparado contra la normalidad equivocada.

#### Borrar o fusionar LF
Cuando:

- duplica otro;
- no tiene identidad ontológica real;
- existe solo porque alguna vez dio uplift.

### Test de honestidad intelectual
Antes de tocar YAML, preguntar:

1. ¿Este LF describe una mecánica real o solo un patrón estadístico?
2. ¿Su baseline representa la normalidad correcta?
3. ¿Seguiría existiendo aunque todavía no fuera monetizable?
4. ¿Podríamos explicarlo como comportamiento de mercado sin jerga?
5. ¿Estamos describiendo naturaleza o tuneando relato para pasar thresholds?

---

## 6.1 Preparación mínima por símbolo (contratos YAML)

### Regla temporal estándar
Antes de correr nada, definir explícitamente:

- ventana total;
- research window;
- OOS window.

Estándar recomendado:

- 3 años total
- 2 años research
- 1 año OOS

Ejemplo:

- total: `2023-01-01 → 2025-12-31`
- research: `2023-01-01 → 2024-12-31`
- OOS: `2025-01-01 → 2025-12-31`

### YAML symbol (Phase D/E)
Ruta:

`configs/symbols/<SYMBOL>.yaml`

Checklist:

- símbolo exacto;
- timeframe soportado;
- `window-hours` coherente;
- mapping `narrative_to_baseline`;
- nombres de `LOOK_FOR_*` consistentes entre `Phase D`, `Phase E` y `Phase F`.

Regla:

El YAML de símbolo debe ser la salida natural de la **Fase 0**, no heredarse por inercia.

### YAML Phase F policy
Ruta:

`configs/phase_f/<SYMBOL>.yaml`

Checklist:

- `go_thresholds` consistentes;
- `lf_synth.priority` solo con LFs existentes;
- `go_contexts[*].expected_baseline_id` correctos;
- `context_key` exacto;
- `none_token = NONE`;
- incluir contextos finos (`STATE_QL_LF`) y fallbacks `QL=NONE`.

Regla:

El YAML debe aguantar el contexto fino.  
No debe depender de que el resolver lo “adivine”.

### Freeze del ciclo
Una vez cerrada la ontología research del símbolo:

- no se toca YAML dentro del mismo ciclo OOS;
- no se agrega LF mirando OOS;
- no se cambia policy mirando OOS;
- no se reabre el ciclo salvo que explícitamente se declare `v2` del símbolo.

---

## 6.2 Phase D — Build barstream (ontología)

### Build Phase D context
CLI:

```bash
!set PYTHONPATH=. && python scripts/build_phase_d_context.py --symbol "US500.spot.mg" --start "YYYY-MM-DD" --end "YYYY-MM-DD" --timeframe "H2" --window-hours 24 --output-dir "outputs/phase_d_context"

Output esperado:

outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_<start>_<end>.parquet

Pre-check barstream

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD.parquet'; df=pd.read_parquet(p); lfs=[c for c in df.columns if c.startswith('LOOK_FOR_')]; print('rows:',len(df)); print('n_LF_cols:',len(lfs)); print('top_LFs:'); print(df[lfs].sum().sort_values(ascending=False).head(30).to_string()); print('state_hat top share:'); print(df['state_hat'].value_counts(normalize=True).to_string() if 'state_hat' in df.columns else None); print('quality_label top share:'); q='quality_label_full' if 'quality_label_full' in df.columns else ('quality_label' if 'quality_label' in df.columns else None); print(df[q].value_counts(normalize=True).to_string() if q else None)"

Qué mirar:

concentración excesiva en 1 LF;

QLs razonables;

mezcla de estados;

no “sopa random”;

no ontología muerta.

Regla:

Este pre-check no reemplaza la Fase 0, pero sí la alimenta.

6.3 Prices H2 (infra) — requerido para Phase F enriched + backtests
Build prices parquet

CLI:

!set PYTHONPATH=. && python scripts/build_prices_h2.py --symbol "US500.spot.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD.parquet" --out_prices_parquet "outputs/prices/prices_H2_US500.spot.mg_YYYY-MM-DD_YYYY-MM-DD.parquet" --timeframe "H2" --pad_hours 24
Sanity básico

Esperamos:

cobertura completa de close;

rango temporal coherente;

sin huecos absurdos.

6.4 Phase F Enriched (OHLC + VWAP bands)
Merge OHLC sobre barstream

CLI:

!set PYTHONPATH=. && python scripts/build_phase_f_enriched_ohlc.py --symbol "US500.spot.mg" --context_parquet "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD.parquet" --prices_parquet "outputs/prices/prices_H2_US500.spot.mg_YYYY-MM-DD_YYYY-MM-DD.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc.parquet"
VWAP + bands

CLI:

!set PYTHONPATH=. && python scripts/build_phase_f_enriched_vwap_bands.py --symbol "US500.spot.mg" --in_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc.parquet" --out_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet"
Contract check

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet'; df=pd.read_parquet(p); need=['symbol','time','open','high','low','close','ctx_vwap','ctx_vwap_sigma','ctx_vwap_hi','ctx_vwap_lo','ctx_session_bucket']; print('rows:',len(df)); print('missing:',[c for c in need if c not in df.columns]); print('close_coverage:',float(df['close'].notna().mean()) if 'close' in df.columns else None); print('sigma_coverage:',float(df['ctx_vwap_sigma'].notna().mean()) if 'ctx_vwap_sigma' in df.columns else None); print('time_min:',df['time'].min() if 'time' in df.columns else None,'time_max:',df['time'].max() if 'time' in df.columns else None)"
Regla de costos preliminar

Si el símbolo eventualmente va a monetizarse, este enriched debe traer spread usable o debe dejarse explícito que el backtest es gross-only.

6.5 Auditoría ontológica D1–D4

Objetivo: amplitud y coherencia descriptiva antes de los gates de Phase E.

CLI:

!set PYTHONPATH=. && python scripts/audit_symbol_description.py --symbol "US500.spot.mg" --phase_e_dir "outputs/phase_e/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_edge_baseline" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --out_dir "outputs/audits/US500.spot.mg_full"

Guidelines GO ontológico:

top1_share < ~0.60

ideal >= 4–5 LFs activos si aplica

jaccard bajo

coherencia por sesión y por QL

distribución entendible del instrumento

Lectura obligatoria:

Si la ontología se ve muy cargada a una sola narrativa pero el símbolo empíricamente parece más rico, eso no es éxito; puede ser pobreza ontológica.

6.6 Phase E — Edge vs baseline (no monetización)
Run Phase E baseline mode

CLI:

!set PYTHONPATH=. && python scripts/phase_e.py --symbol "US500.spot.mg" --start "YYYY-MM-DD" --end "YYYY-MM-DD" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline

Outputs esperables:

*_lookfor_state_filtered.csv

*_lookfor_state_ql_filtered.csv

*_baseline_state.csv

*_baseline_state_ql.csv

*_baseline_state_ql_uplift.csv

Split por año

CLI:

!set PYTHONPATH=. && python scripts/phase_e.py --symbol "US500.spot.mg" --start "2024-01-01" --end "2024-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline
!set PYTHONPATH=. && python scripts/phase_e.py --symbol "US500.spot.mg" --start "2025-01-01" --end "2025-12-31" --timeframe "H2" --score-tf "M30" --window-hours 24 --phase-e --edge-mode baseline
Regla temporal

Además del split anual, el estándar operativo es:

research = 2 años

OOS = 1 año

GO edge (regla de research)

n_bars >= min_n_bars

uplift_pp >= min_uplift_pp

estabilidad interanual

Importante:

Esto pertenece a research como regla de admisión.
No debe reinterpretarse como filtro OOS.

Regla de lectura

Un edge fuerte no es solo el que tiene más uplift, sino el que combina:

uplift;

n_bars;

estabilidad;

legibilidad estructural.

6.7 Construir eligible_rules / eligible_baselines

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/phase_e/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_edge_baseline/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_lookfor_state_filtered.csv'; df=pd.read_csv(p); print('rows:',len(df)); print(df[['look_for_rule','baseline_id','n_bars','uplift_pp']].sort_values('uplift_pp',ascending=False).head(30).to_string(index=False)); print('eligible_baselines:',sorted(df['baseline_id'].dropna().unique().tolist()))"

Mapa fino QL:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/phase_e/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_edge_baseline/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_lookfor_state_ql_filtered.csv'; df=pd.read_csv(p); print(df[['quality_label_full','look_for_rule','baseline_id','n_bars','uplift_pp']].sort_values(['look_for_rule','uplift_pp'],ascending=[True,False]).to_string(index=False))"

Esto permite distinguir:

edge agregado STATE_LF

edge fino STATE_QL_LF

Regla:

Phase F no debería monetizar más de 1–3 motores por símbolo.

La admisión a esta lista se hace con base en research, no en OOS.

6.8 Phase F Runner — decisions only
Run Phase F

Muy importante: pasar ambos registry_csv.

CLI:

!set PYTHONPATH=. && python scripts/run_phase_f.py --symbol "US500.spot.mg" --barstream "outputs/phase_d_context/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD.parquet" --registry_csv "outputs/phase_e/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_edge_baseline/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_lookfor_state_filtered.csv" --registry_csv "outputs/phase_e/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_edge_baseline/US500.spot.mg_PhaseE_M30_YYYY-MM-DD_YYYY-MM-DD_lookfor_state_ql_filtered.csv" --policy "configs/phase_f/US500.spot.mg.yaml" --symbol_config "configs/symbols/US500.spot.mg.yaml" --outdir "outputs/phase_f_runs/US500_audit"
Chequeos obligatorios

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/phase_f_runs/US500_audit/decisions.csv'; df=pd.read_csv(p); a=df[df.decision.astype(str).str.upper().eq('ALLOW')]; print('n',len(df),'ALLOW',len(a),'rate',len(a)/max(len(df),1)); print('nan_meta_baseline_in_allow', float(a['meta_baseline_id'].isna().mean()) if 'meta_baseline_id' in a.columns else None); print('top_contexts'); print(a['context_key'].value_counts().head(10).to_string()); print('top_engine_contexts'); print(a['engine_context_key'].value_counts().head(10).to_string() if 'engine_context_key' in a.columns else 'NO engine_context_key')"
Chequeo crítico de fallback QL

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd; d=pd.read_csv(r'outputs/phase_f_runs/US500_audit/decisions.csv'); a=d[d['decision'].astype(str).str.upper().eq('ALLOW')].copy(); print(a[['ql','engine_context_key','context_key','ql_context_mismatch']].head(20).to_string(index=False)); print('ql_context_mismatch rate:', float(a['ql_context_mismatch'].mean()) if 'ql_context_mismatch' in a.columns else None); print('resolution:'); print(a['meta_context_resolution_level'].value_counts().to_string() if 'meta_context_resolution_level' in a.columns else 'NO COL')"

Interpretación:

engine_context_key correcto = el QL llegó;

ql_context_mismatch alto = mucho fallback;

eso no es bug por sí mismo; puede ser coverage o thresholds.

Coverage fino vs YAML

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd, yaml; d=pd.read_csv(r'outputs/phase_f_runs/US500_audit/decisions.csv'); a=d[d['decision'].astype(str).str.upper().eq('ALLOW')].copy(); go=yaml.safe_load(open(r'configs/phase_f/US500.spot.mg.yaml','r',encoding='utf-8')) or {}; go_keys=set([x['context_key'] for x in go.get('go_contexts',[])]); g=a.groupby(['engine_context_key','context_key']).size().reset_index(name='n').sort_values('n',ascending=False); g['engine_in_go']=g['engine_context_key'].isin(go_keys); print(g.head(40).to_string(index=False)); print('\\nTop engine_context_key NOT in go_map:'); print(g[~g['engine_in_go']].head(20).to_string(index=False))"

Uso:

Esto permite distinguir si el fallback se debe a:

policy coverage insuficiente;

thresholds;

baseline mismatch.

Regla OOS crítica

Cuando Phase F se corre en OOS:

debe usarse el barstream OOS;

pero el registry sigue siendo el de research.

Eso evita convertir OOS en una nueva ronda de selección.

6.9 Direction Layer — parte del template, no accesorio
Run direction layer

CLI:

!set PYTHONPATH=. && python scripts/phase_f_direction_layer.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_audit/decisions.csv" --out_csv "outputs/phase_f_runs/US500_audit/decisions_with_side.csv" --phase_f_policy "configs/phase_f/US500.spot.mg.yaml"
Chequeos wiring

CLI:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/phase_f_runs/US500_audit/decisions_with_side.csv'; df=pd.read_csv(p); need=['close','ctx_vwap','ctx_vwap_sigma','ctx_session_bucket']; print('missing:',[c for c in need if c not in df.columns]); print('hit_close:', float(df['close'].notna().mean()) if 'close' in df.columns else None); print(df[['setup_family','side_intent']].value_counts().head(20).to_string())"
Lectura metodológica

Si aparece mucho side_intent = NONE, eso no es automáticamente malo.

Pero abre la pregunta:

¿esto es un motor económico?

¿o solo una señal de “hay movimiento posterior”?

Si es lo segundo, no se puede cerrar como monetización final sin convertirlo a una hipótesis económica explícita y reauditarlo.

6.10 Auditoría MFE/MAE (antes del backtest)

CLI:

!set PYTHONPATH=. && python scripts/audit_phase_f_mfe_mae.py --decisions_with_side_csv "outputs/phase_f_runs/US500_audit/decisions_with_side.csv" --enriched_ohlc_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --out_dir "outputs/analysis/US500_mfe_mae_audit"

Outputs:

episodes.csv

trade_intents.csv

mfe_mae_by_intent.csv

mfe_mae_summary_go_nogo.csv

Lectura rápida:

!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/analysis/US500_mfe_mae_audit/mfe_mae_summary_go_nogo.csv'; df=pd.read_csv(p); print(df.to_string(index=False))"

Recordatorio:

El audit MFE/MAE puede tener hardcodes por setup raíz / aliases / horizontes.
No asumir que reemplaza el backtest. Sirve como screening, no como verdad final.

6.11 Backtest — catálogo canónico

Script:

scripts/backtest_allow_episodes.py

Por qué existe el fix EP blocks

Problema real:

se backtesteaba con CSV ALLOW-only;

el backtester antiguo asumía BLOCKs;

allow_block_id colapsaba episodios inválidos.

Fix:

si hay BLOCKs → episodios por corridas contiguas;

si no hay BLOCKs → reconstrucción por gaps;

si no se puede → fallback conservador.

Audit impreso siempre:

ALLOW/BLOCK

hit_rate

allow_block_id unique

top block sizes

warnings EP

Parámetros conceptuales nuevos
trigger_unit

Es el parámetro real:

bars

episodes

trade_unit queda como alias deprecated.
Usar trigger_unit.

allow_overlapping_trades + max_positions

Ahora forman parte explícita del motor.

allow_overlapping_trades=False = no stacking

True + max_positions=N = stacking controlado

Regla sobre TP/SL

En algunos motores, TP/SL puede quedar tan lejos que el motor realmente funcione como:

ENTER → HOLD N BARS → EXIT

No asumir que fixed siempre implica TP/SL activos. Revisar exit_reason.

Costo obligatorio

Antes de aceptar cualquier resultado neto, verificar:

ret_gross != ret_net cuando se pidió --use_spread

costo medio razonable

no aceptar reporte por metadata sola

Cautela con abs_move

abs_move es válido como test de capturabilidad de expansión.
No es automáticamente prueba final de monetización.

CLIs canónicas
A) bars + fixed
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_audit/decisions_with_side.csv" --setup_family "SETUP_FAMILY" --side BOTH --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --out_dir "outputs/backtests/US500_audit/BT_SETUP_bars_fixed"
B) episodes + state_change
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_audit/decisions_with_side.csv" --setup_family "SETUP_FAMILY" --side BOTH --trigger_unit episodes --exit_mode state_change --arm_state_value 2.0 --catastrophic_sl_bps 350.0 --out_dir "outputs/backtests/US500_audit/BT_SETUP_ep_statechange"
C) abs_move directionless balance
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_audit/decisions_with_side.csv" --setup_family "balance_stability_center" --side BOTH --mode abs_move --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --out_dir "outputs/backtests/US500_audit/BT_balance_center_abs"
D) stacking controlado
!set PYTHONPATH=. && python scripts/backtest_allow_episodes.py --symbol "US500.spot.mg" --enriched_parquet "outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet" --decisions_csv "outputs/phase_f_runs/US500_audit/decisions_with_side.csv" --setup_family "SETUP_FAMILY" --side BOTH --trigger_unit bars --exit_mode fixed --tp_k 1.5 --sl_k 1.0 --allow_overlapping_trades --max_positions 2 --out_dir "outputs/backtests/US500_audit/BT_SETUP_stack2"
Scorecard obligatorio

Por baseline / setup_family, revisar:

trades/week

EV/trade

EV/month

maxDD

winrate

split por año

split por sesión

idealmente por exit_reason

duración de trades

si TP/SL realmente disparan o si todo sale por timeout

overlap y stacking efectivo

costos reales

Split anual
!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/backtests/US500_audit/BT_SETUP_bars_fixed/trades.parquet'; df=pd.read_parquet(p); df['entry_time']=pd.to_datetime(df['entry_time']); df['year']=df['entry_time'].dt.year; y=df.groupby('year').agg(trades=('ret_net','count'), ev_trade=('ret_net','mean'), ev_total=('ret_net','sum'), winrate=('ret_net',lambda s:(s>0).mean())); print(y.to_string())"
Split por sesión
!set PYTHONPATH=. && python -c "import pandas as pd; t=pd.read_parquet(r'outputs/backtests/US500_audit/BT_SETUP_bars_fixed/trades.parquet'); e=pd.read_parquet(r'outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_YYYY-MM-DD_YYYY-MM-DD_with_ohlc_vwapbands.parquet'); t['entry_time']=pd.to_datetime(t['entry_time']); e['time']=pd.to_datetime(e['time']); m=t.merge(e[['symbol','time','ctx_session_bucket']], left_on=['symbol','entry_time'], right_on=['symbol','time'], how='left'); s=m.groupby('ctx_session_bucket').agg(trades=('ret_net','size'), ev_trade=('ret_net','mean'), ev_total=('ret_net','sum'), winrate=('ret_net',lambda x:(x>0).mean())); print(s.to_string())"
Exit reasons
!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/backtests/US500_audit/BT_SETUP_bars_fixed/trades.parquet'; df=pd.read_parquet(p); print(df['exit_reason'].value_counts(normalize=True).to_string())"
Duración de trades
!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/backtests/US500_audit/BT_SETUP_bars_fixed/trades.parquet'; df=pd.read_parquet(p); df['entry_time']=pd.to_datetime(df['entry_time']); df['exit_time']=pd.to_datetime(df['exit_time']); df['dur_h']=(df['exit_time']-df['entry_time']).dt.total_seconds()/3600; print(df['dur_h'].describe().to_string())"
Sanity de costos
!set PYTHONPATH=. && python -c "import pandas as pd; p=r'outputs/backtests/US500_audit/BT_SETUP_bars_fixed/trades.parquet'; df=pd.read_parquet(p); print('has_cols', {'ret_gross','ret_net'}.issubset(df.columns)); print((df['ret_gross']-df['ret_net']).describe().to_string() if {'ret_gross','ret_net'}.issubset(df.columns) else 'missing gross/net')"

Interpretación:

Si ret_gross - ret_net = 0 en todos los trades, no aceptar el resultado como neto.

6.12 Criterio formal de cierre
A) NO-EDGE

no pasa Phase E;

o pasa solo en un año y colapsa en otro;

o el edge fino desaparece al segmentar por QL y no queda agregado sano.

B) EDGE pero NO-CAPTURE

Phase E sí valida edge;

backtests canónicos netos no lo capturan razonablemente;

exit_reason muestra que el template no conversa con la microestructura;

el motor depende de supuestos demasiado arbitrarios;

o el combo produce DD/costos inaceptables.

C) EDGE CAPTURABLE

Phase E valida;

Phase F lo resuelve fino o agregado de forma coherente;

el backtest lo monetiza con lógica interpretable;

hay estabilidad por año y por sesión;

hay costos reales;

no se necesita tuning fino para que aparezca.

D) PENDING COST RE-AUDIT

la historia gross parece buena;

pero costos no están verificados;

o el plumbing de spread está defectuoso.

Qué significa “cerrado” en sentido fuerte

Un símbolo queda cerrado solo si:

ya no queda ontología razonable dentro del universo actual;

la captura fue probada o descartada con costos reales;

no quedan templates plausibles cortos por barrer;

no hay bugs pendientes que afecten el veredicto.

Si falta auditoría de costos, no hay cierre fuerte.

7) Flujo real LF → Phase F (bitácora estructural anti-fantasmas)

Separación estricta:

Phase D describe

Phase E mide uplift vs baseline

Phase F monetiza edge validado

Flujo real:

Phase D emite

state_hat

quality_label / quality_label_full

columnas binarias LOOK_FOR_*

run_phase_f.py

extrae flags activos

sintetiza lf

construye ContextRow(state, ql, lf)

exporta además engine_context_key

ContextResolver

Genera candidatos:

STATE_QL_LF

STATE_LF

STATE_QL

STATE

Registry

Entrega stats de Phase E por context_key.

PolicyEngine.decide()

aplica thresholds

aplica expected_baseline_id

elige contexto

puede hacer fallback

decisions.csv

Exporta:

engine_context_key

context_key

meta_context_resolution_level

ql_context_mismatch

lf_context_mismatch

Direction layer

Agrega:

side_intent

setup_family

columnas enriched

sin alterar Phase E.

Backtester

simula captura

aplica reglas de episodio / barras

debe cobrar costos reales si se pide neto

Nota operativa crucial

Si ves ql_context_mismatch alto:

verificar coverage fino del YAML;

verificar uplift fino en Phase E;

verificar registry;

solo después discutir thresholds.

No asumir bug.

8) Directiva operativa ante cuellos de botella

Si aparece un cuello en:

wiring;

merge;

coverage;

thresholds;

policy ahorcada;

backtest inconsistente;

abs_move ambiguo;

costos no cobrados;

entonces:

no abrir ramas paralelas;

no optimizar por reacción;

resolver el cuello primero;

recién después seguir.

9) Arranque recomendado en nuevo chat para cualquier símbolo

definir ventana total y split 2Y research / 1Y OOS

construir hipótesis previa del instrumento en 4 ejes

clasificar YAML viejo: mantener / renombrar / fusionar / borrar / reemplazar

revisar distribución Phase D (LOOK_FOR / STATE / QL)

revisar edge agregado y edge fino en Phase E research

freeze ontológico

correr run_phase_f con ambos registry CSV

auditar engine_context_key vs context_key

revisar coverage fino vs go_contexts

direction layer

MFE/MAE

backtests canónicos netos

costos

decisión final del símbolo

10) Clave final

Las ontologías no están a firme.
Lo que manda es la naturaleza de cada instrumento.

Pero el proceso sí debe estar a firme:

ventana estándar;

freeze;

OOS;

costos;

decisión final.

Si empíricamente un instrumento muestra una naturaleza distinta a la hipótesis escrita en YAML:

se corrige ontología;

se corrige policy;

se corrige coverage;

pero no para “mejorar EV”, sino para describir correctamente el instrumento y luego monetizar lo que realmente existe.

Clave práctica

Los CLIs siguen siendo de una sola línea para Spyder sin ^.

Pero el criterio final de aceptación ya no es solo:

salió positivo

sino:

salió positivo, OOS, neto, interpretable y con costos reales.
