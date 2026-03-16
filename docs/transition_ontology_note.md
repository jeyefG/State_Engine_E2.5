# Nota ontológica — interpretación de TRANSITION en State Engine

## Estado
Borrador canónico de contrato conceptual.

## Objetivo
Fijar qué significa `TRANSITION` en el proyecto State Engine, qué no significa, y qué implicancias tiene para las fases D, E y una futura capa E.cap.

---

## 1. Decisión ontológica

`TRANSITION` no debe interpretarse como un tercer régimen puro, simétrico a `BALANCE` y `TREND`.

La interpretación canónica pasa a ser:

> `TRANSITION` es una **frontera estructural** entre `BALANCE` y `TREND`.

Esto implica que:

- `BALANCE` y `TREND` siguen siendo los polos principales.
- `TRANSITION` describe una zona de borde, cambio, tensión, pérdida de equilibrio o direccionalidad aún no consolidada.
- `TRANSITION` puede contener polaridad interna hacia uno u otro polo, sin que eso la convierta automáticamente en señal operativa.

---

## 2. Qué sí significa TRANSITION

Dentro del marco actual del proyecto, `TRANSITION` sí puede significar:

- pérdida parcial de equilibrio,
- inicio o fracaso de expansión,
- repricing en curso,
- reingreso al rango tras intento de escape,
- frontera entre compresión y direccionalidad,
- estado estructuralmente inestable respecto de `BALANCE` y `TREND`.

En consecuencia, `TRANSITION` es una categoría **descriptiva** de borde, no una promesa de continuación, reversión o monetización.

---

## 3. Qué no significa TRANSITION

`TRANSITION` no debe leerse como:

- señal de trade por sí sola,
- estado direccional autónomo,
- tercer polo puro equivalente a `BALANCE` y `TREND`,
- evidencia suficiente de capturabilidad económica,
- justificación para asignar side, template o riesgo sin capa adicional.

---

## 4. Polaridad interna de TRANSITION

Los análisis locales muestran que dentro de `TRANSITION` puede aparecer una polaridad descriptiva interna, del tipo:

- `proto_balance`
- `proto_trend`

Esa polaridad:

- **sí puede existir como metadata descriptiva**,
- **no debe considerarse operativa por defecto**,
- **no debe bajar todavía a F**,
- **no debe usarse todavía como side resolver**,
- requiere evidencia adicional antes de promoción a una capa operativa.

Por ahora, esta polaridad debe entenderse como una propiedad descriptiva de frontera, no como decisión.

---

## 5. Implicancias por fase

### Phase D
Phase D puede usar `TRANSITION` como categoría de frontera estructural.
Quality labels y LOOK_FOR deben interpretarse como refinamientos descriptivos sobre esa frontera.

### Phase E
Phase E puede validar edge estructural sobre `TRANSITION`, pero ese edge debe entenderse como edge de evolución de frontera, no como edge monetizable por sí mismo.

### Futura E.cap
Si parte de `TRANSITION` llegara a ser capturable, eso debe demostrarse en una capa posterior de capturabilidad o mechanism-fit.
No se permite saltar directamente desde frontera descriptiva a decisión operativa.

### Phase F
Phase F no debe consumir la polaridad interna de `TRANSITION` como side o policy input hasta que exista evidencia explícita de capturabilidad.

---

## 6. Afirmaciones permitidas

Sí está permitido afirmar que:

- `TRANSITION` es una frontera estructural,
- puede contener polaridad descriptiva interna,
- esa polaridad puede ayudar a entender el contexto,
- no toda frontera tiene traducción operativa,
- parte de `TRANSITION` puede terminar siendo `INFO_ONLY`.

---

## 7. Afirmaciones prohibidas por ahora

No está permitido afirmar, sin evidencia adicional, que:

- `proto_balance` o `proto_trend` implican dirección futura simple,
- `TRANSITION` debe monetizarse como estado autónomo,
- la polaridad interna ya puede bajar a F,
- LOOK_FOR de transición resuelve por sí solo la ontología interna,
- el edge estructural de `TRANSITION` equivale a edge ejecutable.

---

## 8. Consecuencia metodológica

Hasta nuevo aviso:

1. `TRANSITION` se trata como frontera estructural.
2. Su polaridad interna se considera metadata descriptiva.
3. No se promueve esa metadata a operativa.
4. Cualquier promoción futura requiere validación explícita de capturabilidad.

---

## 9. Estado del proyecto después de esta nota

Con esta reinterpretación:

- la tríada sigue siendo usable,
- pero deja de entenderse como tres polos simétricos,
- `TRANSITION` pasa a ser frontera y no régimen puro,
- y el puente hacia monetización sigue pendiente de contrato explícito.
