# Auditoría conceptual profunda: quiebre entre edge descriptivo (Phase E) y monetización OOS (Phase F)

## Alcance y premisas

- Esta auditoría es **conceptual/matemática/arquitectónica**; no propone scripts ni tuning puntual.
- Se asume el principio rector del repositorio: **Describir → Contextualizar → Validar evolución → Ejecutar**.
- El problema auditado: Phase E parece mostrar edge estructural (uplift sobre baseline), pero la captura monetaria en F y en adaptaciones E.5 no generaliza OOS.

---

## A) Diagnóstico conceptual de fondo

### A.1 Diagnóstico ejecutivo

El sistema actual es sólido para detectar **diferencias estructurales de evolución de régimen**, pero incompleto para detectar **diferencias de capturabilidad económica**.

En otras palabras:

1. **E prueba “evolución condicional del estado”** (probabilidades de trayectorias estructurales dentro de K).
2. **F necesita “mecanismo pagador ejecutable”** (cómo, cuándo y por qué un template extrae PnL neto después de fricciones).
3. El contrato E→F hoy mapea principalmente `context_key + uplift_pp + n_bars (+ wf_score opcional)` hacia decisiones GO/NO-GO, plantilla y política direccional, sin una capa formal que modele la **capturabilidad**.

Resultado: se fuerza a F a monetizar objetos que aún son semánticamente descriptivos.

### A.2 Naturaleza del quiebre

El quiebre no parece ser “falta de ML” sino **mismatch ontológico**:

- Ontología de E: “contexto altera distribución de evolución de estado”.
- Ontología requerida por F: “contexto + microestructura + fricción + timing + dirección alteran distribución de retorno neto ejecutable”.

Si no existe una capa que traduzca explícitamente entre esas ontologías, el sistema queda expuesto a:

- éxitos en research por correlaciones de régimen,
- degradación OOS por cambio de mecanismo pagador real,
- sobreuso de side/template/gate como sustitutos de contrato matemático faltante.

---

## B) Auditoría de la secuencia matemática completa

## B.1 Cadena actual (abstracción funcional)

La cadena práctica observada es:

1. **D** construye `state_hat`, `quality_label`, `LOOK_FOR_*` y aplica gating causal desplazado (`shift(1)`).
2. **E** define lupa estructural canónica (baseline registry) y estima uplift condicional por estrato/contexto.
3. **F** resuelve `context_key`, consulta estadísticas de E y habilita/bloquea con umbrales (`min_n_bars`, `min_uplift_pp`, `min_wf_score`), luego asigna template/risk/direction.
4. **Backtest** evalúa desempeño económico resultante.

La coherencia causal temporal está bien tratada en D/E (evita leakage), pero eso **no alcanza** para garantizar capturabilidad económica.

### B.2 Dónde la matemática es consistente

- Baselines de E son cerrados/canónicos y expresan preguntas estructurales legítimas (persistencia/salida/hit dentro de K).
- Control groups jerárquicos (`PARENT_ESTRATO`) son coherentes para comparar estratos de contexto sin colapsar todo al global.
- Separación descriptiva y ejecución está explicitada y protege de contaminación directa por PnL en fases tempranas.

### B.3 Dónde la cadena destruye o no representa información clave

#### (i) Equivalencia implícita inválida

Hoy se aproxima:

`uplift estructural > 0  =>  contexto monetizable`

Esa equivalencia no está demostrada y, en general, no es cierta.

#### (ii) Pérdida de “información de mecanismo”

El objeto que llega a F (context key + uplift agregado) no retiene explícitamente:

- perfil de trayectoria de precio dentro del episodio,
- asimetría de excursiones (MFE/MAE) relativa al template,
- sensibilidad de edge a spread/sesión/latencia,
- estabilidad de dirección condicionada al mismo contexto,
- estructura de horizon mismatch (K estructural vs holding operativo).

#### (iii) Many-to-one y compresión excesiva

El registry de F conserva una sola fila por `context_key` (privilegia mayor `n_bars` en duplicados). Esa compresión puede mezclar sub-regímenes económicamente heterogéneos bajo una misma llave semántica.

#### (iv) Resolución jerárquica puede degradar especificidad

La jerarquía de `STATE_QL_LF -> STATE_LF -> STATE_QL -> STATE` es útil para cobertura, pero cuando cae a niveles más gruesos puede transformar una narrativa específica en una decisión operativa genérica con menor poder económico.

#### (v) Side como post-procesado sin contrato causal completo

E.5 V2 mejora respecto a V1 (scores y abstain explícito, contrato side-only sobre ALLOW), pero si el gate/template ya no representa un mecanismo pagador robusto, mejorar side no repara la raíz: la unidad monetizable está mal definida.

### B.4 Saltos conceptuales no resueltos

1. **De “probabilidad de transición de estado” a “expectativa de retorno neto por template”**.
2. **De “contexto activo” a “compatibilidad contexto-template”** sin un modelo formal de interacción.
3. **De “dirección recomendada” a “dirección capturable con costos/restricciones reales”**.

---

## C) Auditoría de contratos entre fases

### C.1 Contratos bien planteados

- D→E está bien definido como contrato de contexto canónico, con consumo “as-is” y sin recomputar allow en E.
- E mantiene lupas cerradas y evita tuning post-hoc de narrativa/target.

### C.2 Fricciones de contrato críticas

#### Fricción 1: contrato semántico incompleto E→F

E entrega evidencia de **diferencia estructural**; F necesita evidencia de **diferencia económica capturable**. El contrato actual no distingue formalmente ambos tipos de edge.

#### Fricción 2: baseline esperado vs template ejecutado

F puede exigir `expected_baseline_id`, pero baseline y template no están unidos por un “teorema operativo” explícito (compatibilidad necesaria/suficiente). Se asume correspondencia narrativa, no se certifica mecanismo pagador.

#### Fricción 3: side/template/gate absorben una capa faltante

La arquitectura usa estas piezas como si resolvieran la traducción E→PnL, cuando en rigor sólo parametrizan ejecución.

#### Fricción 4: output de E demasiado grueso para políticas finas

`uplift_pp`, `n_bars`, `wf_score` son insuficientes para decidir robustamente:

- qué plantilla usar,
- en qué condiciones microestructurales,
- con qué horizonte,
- con qué expectativa neta ajustada por fricción.

### C.3 ¿La separación de fases ayuda o estorba?

La separación **sí ayuda** para disciplina científica, pero hoy está incompleta:

- D y E cumplen su rol descriptivo/validación estructural.
- Falta una fase de **transducción semántica** antes de F.

No es que la modularidad sea mala; está **subespecificada** entre E y F.

---

## D) Hipótesis sobre por qué se rompe E → F

### H1 (principal): Edge descriptivo no equivale a edge ejecutable

E detecta cambio en probabilidades de evolución de estado, pero el PnL depende de la geometría de precio y fricción en ventanas operativas. Si esa geometría no está condicionada explícitamente, OOS cae.

### H2: Inestabilidad de mecanismo dentro de la misma etiqueta contextual

Un mismo `STATE+QL+LF` puede pagar por mecanismos distintos según sesión/liquidez/volatilidad. El promedio de uplift no discrimina cuál mecanismo dominó in-sample.

### H3: Desacople de horizontes

- E evalúa within-K estructural.
- F ejecuta con reglas de entrada/salida (time stops, triggers, invalidaciones) que inducen otro horizonte efectivo.

Sin alineación formal de horizontes, el edge puede “existir” estructuralmente pero no dentro de la ventana capturable por template.

### H4: Sobreconfianza por mejoras research en capas de resolución

V1/V2 pueden mejorar métricas internas o comparables, pero si la variable objetivo no está anclada al mecanismo pagador neto, la mejora no transfiere.

---

## E) Qué capa/contrato faltaría entre descripción y monetización

## E.1 Capa faltante: **Phase E.cap (Capturabilidad / Mecanismo pagador)**

Objetivo conceptual:

> Convertir un contexto con edge descriptivo en una hipótesis explícita de capturabilidad económica, verificable y falsable, antes de permitir monetización en F.

### E.2 Qué debe producir (objeto de salida)

No señales, sino un **certificado operativo por contexto** con al menos:

1. **Mechanism class**: tipo de pago esperado (continuación, resolución, mean-revert, compresión/expansión, etc.).
2. **Template compatibility set**: qué familias de template son compatibles/incompatibles.
3. **Directional reliability profile**: estabilidad de sesgo long/short/abstain por régimen operativo.
4. **Friction resilience**: sensibilidad a spread/sesión/ejecución.
5. **Horizon alignment bounds**: rango de holding donde persiste ventaja neta.
6. **Capacity/coverage diagnostics**: frecuencia y clustering temporal para riesgo de sobreexposición.

### E.3 Contrato formal E → E.cap

Entrada: contexto estructural + lupa validada.

Salida: “contexto tradeable” sólo si satisface simultáneamente:

- coherencia de mecanismo,
- robustez de dirección,
- robustez a fricción,
- alineación de horizonte,
- estabilidad temporal OOS en bloques.

Si no cumple, queda como **contexto informativo no tradeable** (resultado válido, no fracaso).

### E.4 Contrato formal E.cap → F

F no debería consumir “uplift desnudo”; debería consumir:

- `tradeability_status` (TRADEABLE / INFO_ONLY / NO_GO),
- `allowed_templates` y `forbidden_templates`,
- `side_policy_type` (si aplica),
- `risk envelope` recomendado,
- `failure modes` esperados.

Así, F deja de inferir mecanismo desde umbrales agregados y pasa a ejecutar políticas sobre un objeto operativo ya tipificado.

---

## F) Propuesta de rediseño conceptual del pipeline

## F.1 Estructura propuesta

1. **D — Ontología descriptiva** (igual).
2. **E — Validación estructural/lupas** (igual, sin contaminar con PnL).
3. **E.cap — Transducción a capturabilidad** (nueva capa puente, obligatoria para monetización).
4. **F — Orquestación operativa** (consumo de contratos operativos, no descubrimiento de edge).
5. **WF/OOS Governance** transversal con criterios de promoción/degradación entre estados de contrato.

### F.2 Reposicionamiento de E.5

E.5 debería dejar de ser “resolver side para mejorar performance” y convertirse en submódulo de E.cap:

- **resolver de ambigüedad dentro de mecanismo ya validado**, o
- **clasificador de régimen de capturabilidad**,

pero no fuente autónoma de edge que reemplace gate semántico.

### F.3 Nuevo contrato de promoción entre fases

- **D→E**: contexto descriptivo válido.
- **E→E.cap**: contexto con evidencia de evolución estructural.
- **E.cap→F**: contexto con evidencia de monetización robusta por mecanismo.

Solo el tercer contrato habilita capital real.

### F.4 Beneficio esperado del rediseño

- Reduce falsos positivos de “contexto interesante pero no tradeable”.
- Evita que F haga ingeniería inversa de edge a partir de proxies débiles.
- Mejora transferibilidad multi-símbolo porque la unidad de generalización pasa de etiqueta a mecanismo.

---

## G) Riesgos, tradeoffs e hipótesis a validar

### G.1 Riesgos / tradeoffs

1. **Menor cobertura inicial**: al exigir capturabilidad, caerá la cantidad de contextos tradeables.
2. **Mayor complejidad de gobernanza**: más contratos y estados de promoción.
3. **Latencia de investigación**: más lento pasar de narrativa a ejecución.

### G.2 Por qué igual conviene

- El objetivo del proyecto no es clasificar todo, sino operar donde hay coherencia validada.
- Menos cobertura con mejor validez suele superar más cobertura con edge ilusorio.

### G.3 Hipótesis críticas a validar después

1. **H-bridge**: contextos con uplift estructural y certificado E.cap superan OOS a contextos con uplift sin certificado.
2. **H-template**: la compatibilidad contexto-template explica más varianza de PnL que uplift_pp aislado.
3. **H-side**: side resolver aporta sólo cuando mecanismo y template ya están validados; fuera de eso degrada.
4. **H-multisymbol**: taxonomía por mecanismo generaliza mejor entre símbolos que taxonomía por etiqueta contextual sola.

---

## Conclusión general

El sistema actual está bien encaminado para describir y validar estructura, pero el salto a monetización falla porque **no existe un contrato explícito de capturabilidad** entre E y F.

La solución de fondo no es tuning ni reemplazar una pieza aislada: es introducir una capa puente que convierta edge descriptivo en edge operativamente certificable, manteniendo la disciplina causal y la separación epistemológica del proyecto.
