# E2.5 — primera pasada manual sobre familias de transición

## Objetivo
Aplicar por primera vez la grilla E2.5 a dos familias concretas de `TRANSITION`, sin código y sin monetización todavía.

La idea es probar si E2.5 realmente sirve para clasificar capturabilidad de forma honesta.

---

## Familia 1
### Unidad
`(XAUUSD.mg, TRANSITION, LOOK_FOR_transition_chop_near_vwap, TRANSITION_PERSISTENCE)`

### Lectura estructural heredada de E
Contexto de frontera que persiste cerca de VWAP, con lectura de chop / unresolved frontier.
La validación estructural sugiere persistencia de frontera, no resolución limpia hacia uno de los polos.

### Evaluación E2.5

#### 1. Coherencia de mecanismo
Sí.
El baseline `TRANSITION_PERSISTENCE` describe un mecanismo estructural interpretable:
frontera que permanece abierta / ruidosa sin resolver de inmediato.  
**Juicio:** mecanismo interpretable.

#### 2. Compatibilidad con template
Débil o incompleta.
Un contexto de frontera persistente cerca de VWAP no sugiere de forma obvia un template limpio y robusto.
Puede admitir lectura exploratoria, pero no aparece una compatibilidad fuerte y no ambigua con una familia operativa única.  
**Juicio:** compatibilidad insuficientemente clara.

#### 3. Coherencia de horizonte
Parcial.
La persistencia within-K es coherente como objeto estructural, pero no queda claro todavía que esa persistencia se traduzca limpiamente a una ventana operativa capturable sin depender demasiado del timing fino.  
**Juicio:** horizonte estructural válido, pero horizonte operativo todavía no suficientemente certificado.

#### 4. Direccionalidad justificable
No.
La frontera persistente / chop cerca de VWAP no justifica por sí sola una lectura direccional robusta.
La dirección aparece, por ahora, como demasiado ambigua para promoción directa a decisión operativa.  
**Juicio:** direccionalidad `unknown`.

#### 5. Modos de falla identificables
Sí.
Modos plausibles:
- noisy persistence sin expansión útil
- fake resolution
- fallback to balance
- chop prolongado alrededor de VWAP  
**Juicio:** modos de falla identificables.

### Clasificación provisional
`INFO_ONLY`

### Comentario
Familia estructuralmente válida y útil para lectura de contexto, pero todavía sin contrato operativo suficientemente claro.
No se debería promover directamente a template + side + risk solo a partir de este uplift estructural.

---

## Familia 2
### Unidad
`(US500.spot.mg, TRANSITION, LOOK_FOR_transition_repricing_london, TRANSITION_RESOLUTION)`

### Lectura estructural heredada de E
Contexto de frontera que muestra sesgo de resolución hacia trend.

### Evaluación E2.5

#### 1. Coherencia de mecanismo
Pendiente

#### 2. Compatibilidad con template
Pendiente

#### 3. Coherencia de horizonte
Pendiente

#### 4. Direccionalidad justificable
Pendiente

#### 5. Modos de falla identificables
Pendiente

### Clasificación provisional
Pendiente

### Comentario
Pendiente
