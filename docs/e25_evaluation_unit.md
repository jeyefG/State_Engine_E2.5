# E2.5 — unidad de evaluación

## Objetivo
Definir cuál es la unidad mínima sobre la que E2.5 emite un juicio de:

- `TRADEABLE`
- `INFO_ONLY`
- `NO_GO`

---

## 1. Unidad mínima de evaluación

La unidad mínima de E2.5 no es el símbolo completo.

La unidad mínima es, como regla general:

> `(symbol, base_state, look_for_rule, baseline_id)`

Es decir:
- símbolo,
- contexto estructural base,
- narrativa estructural activa,
- y pregunta estructural validada en E.

---

## 2. Por qué esta es la unidad correcta

Porque:

- el mismo `base_state` puede significar cosas distintas según `LOOK_FOR`,
- el mismo `LOOK_FOR` puede mapear a preguntas distintas si cambia el baseline,
- y un mismo baseline puede ser capturable o no según símbolo.

Por lo tanto, E2.5 no debe clasificar “TRANSITION” en abstracto.
Debe clasificar familias concretas de contexto.

---

## 3. Ejemplos

### Ejemplo 1
`(XAUUSD.mg, TRANSITION, LOOK_FOR_transition_chop_near_vwap, TRANSITION_PERSISTENCE)`

Esto representa una familia estructural concreta.

### Ejemplo 2
`(US500.spot.mg, TRANSITION, LOOK_FOR_transition_repricing_london, TRANSITION_RESOLUTION)`

Esto representa otra familia distinta, aunque ambas vivan dentro de `TRANSITION`.

---

## 4. Qué no es una unidad válida

No son unidades suficientes por sí solas:

- solo `TRANSITION`
- solo `LOOK_FOR_transition_*`
- solo `baseline_id`
- solo el símbolo
- solo `STATE+QL`

Todas esas vistas son demasiado gruesas para E2.5.

---

## 5. Qué evalúa E2.5 sobre esa unidad

Para cada unidad `(symbol, base_state, look_for_rule, baseline_id)`, E2.5 debe emitir juicio sobre:

1. mecanismo estructural interpretable,
2. compatibilidad con template,
3. coherencia de horizonte,
4. direccionalidad justificable,
5. modos de falla identificables.

Solo después de eso puede clasificar la unidad como:

- `TRADEABLE`
- `INFO_ONLY`
- `NO_GO`

---

## 6. Consecuencia metodológica

A partir de esta nota:

- no se evaluarán familias “en abstracto”,
- no se promoverán estados completos a operativa,
- y no se intentará resolver F directamente desde uplift agregado.

La promoción a F deberá hacerse por unidades concretas de contexto estructural.
