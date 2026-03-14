# AGENTS.md — State Engine / Quality / Contextual Layers  
Arquitectura por fases (descriptivo → contextual → validación estructural → ejecución)

---

# Propósito general del repositorio

Este repositorio implementa un **State Engine** cuyo rol es describir la **estructura del mercado** de forma:

- robusta  
- causal (≤ t)  
- generalizable  
- independiente de resultado económico  

El sistema se organiza explícitamente en **fases conceptuales**, donde cada etapa tiene:

- un objetivo propio  
- un tipo de validación permitido  
- límites epistemológicos claros  

El propósito del proyecto es:

> **Contextualizar decisiones de trading antes de intentar generarlas.**

---

# Objetivo operativo del sistema (visión práctica)

El objetivo del sistema es:

> Reducir y concentrar el espacio de interpretación del mercado en tiempo real,  
> acercándolo a un conjunto pequeño, explícito y auditable de narrativas estructurales plausibles.

El sistema no decide qué hacer.  
Decide **cómo entender dónde se está parado**.

---

# Visión general por fases

| Fase | Rol | Naturaleza |
|------|------|------------|
| **A** | Representación temporal | descriptiva |
| **B** | Validación estructural | descriptiva |
| **C** | Calidad del contexto | descriptiva |
| **D** | Contextualización estructural avanzada | descriptiva-contextual |
| **E** | Validación estructural condicionada (lupas) | validación |
| **F** | Arquitectura de decisión operativa | ejecución |

Las fases **no son intercambiables**.

Las métricas económicas:

- no son válidas antes de Fase D  
- no son centrales en Fase D  
- solo aparecen indirectamente después de Fase F  

---

# Fase A — Representación temporal

## Objetivo

Encontrar, por símbolo, una **representación temporal razonable** del mercado.

## Qué se define

- Timeframe base del State Engine (H1, H2, etc.)
- Tamaño de ventana (`window_hours`, `k_bars`)

## Criterios

- coherencia estructural  
- estabilidad temporal  
- interpretabilidad humana  

## Fuera de scope

- edge  
- EV  
- PnL  
- decisiones de trading  

---

# Fase B — Validación estructural

## Objetivo

Validar que el State Engine:

> Clasifica estados de forma estable y no degenerada.

## Qué se valida

- distribución de estados  
- persistencia temporal  
- coherencia lógica  
- estabilidad por splits temporales  

Resultado de Fases A + B:

Cada símbolo queda asociado a un TF + window_hours razonable para describir su estructura,  
sin exigir valor predictivo.

---

# Fase C — Quality Layer (calidad del contexto)

## Objetivo

Describir la **calidad interna** de un estado ya clasificado.

La Fase C no busca edge.  
Busca **reducir incertidumbre contextual**.

## Rol de la Quality Layer

- caracterizar estabilidad  
- medir fricción  
- detectar degradación  
- describir coherencia  

Siempre condicionada al estado base.  
Nunca infiere dirección ni outcome.

## Principios no negociables

Las Quality Labels son:

- descriptivas  
- humanas  
- visualizables  
- independientes de métricas económicas  

Preferencias explícitas:

- falsos negativos > falsos positivos  
- no clasificar > clasificar mal  
- “no clasificado” es válido  

---

# Fase D — LOOK_FORs  
Contextualización estructural avanzada

## Qué es un LOOK_FOR

Un LOOK_FOR es:

> Una descripción contextual más granular definida sobre State + Quality.

Es una etiqueta estructural adicional.

## Qué NO es

- No es señal  
- No es decisión  
- No implica operabilidad  
- No asume edge  

Un LOOK_FOR responde a:

> “¿Se cumple esta configuración estructural específica?”

No responde a:

> “¿Conviene tradear esto?”

## Especialización por símbolo

En Fase D:

- Los LOOK_FOR pueden especializarse por símbolo  
- Siguen siendo descriptivos  
- No reentrenan modelos  
- No optimizan performance  

LOOK_FORs nunca afectan métricas económicas.  
Son tags estructurales.

---

# Fase E — Validación estructural condicionada (Lupas / Baselines)

Estado actual: **estructuralmente activo**

---

## Definición central: Lupa

En Fase E, un baseline no es solo un control estadístico.

Es una:

> Pregunta estructural explícita sobre la evolución futura del régimen.

A esto lo llamamos **lupa**.

Ejemplos:

- ¿Persiste el estado actual?
- ¿Se degrada?
- ¿Escapa de balance hacia trend?
- ¿Transición persiste o se resuelve?
- ¿Reingresa al estado previo?

Una lupa correcta debe:

- Ser coherente con la narrativa del LOOK_FOR  
- Medir evolución estructural (no precio directo)  
- Ser canónica y cerrada  
- No ajustarse post-hoc  
- Aceptar resultado nulo  

---

## Rol de Fase E

Fase E tiene como objetivo:

> Validar si una narrativa estructural anticipa de forma estable la evolución del régimen, medida mediante una lupa canónica.

Fase E:

- No crea narrativas  
- No redefine contexto  
- No optimiza entradas  
- No genera señales  

Solo valida:

> “Cuando ocurre esta configuración estructural, el régimen tiende a evolucionar así.”

---

## Qué significa edge en Fase E

Edge significa:

> Capacidad de un contexto de cambiar la probabilidad de evolución estructural respecto a su baseline comparable.

No significa:

- señal  
- setup  
- rentabilidad inmediata  

Es un sesgo estructural.

---

## Criterios de validez

Fase E es válida si:

- La condicionalidad es estricta  
- La lupa es coherente con la narrativa  
- Existe baseline comparable claro  
- Hay estabilidad temporal  
- Se acepta resultado nulo  

---

## Criterios de invalidez

Fase E es inválida si:

- Se cambia la lupa para rescatar uplift  
- Se redefine contexto tras observar resultados  
- El efecto depende críticamente de tuning fino  
- Se convierte uplift en señal implícita  

---

## Resultado esperado de Fase E

Al finalizar Fase E:

- Sabemos qué narrativas tienen coherencia evolutiva  
- Sabemos cuáles no  
- No hemos generado señales  
- No hemos tomado decisiones operativas  

Fase E valida estructura.  
No ejecuta.

---

# Fase F — Arquitectura de decisión operativa

Estado: diseño explícito posterior a validación estructural.

Fase F es la única fase cuyo objetivo es:

> Traducir contextos estructurales validados en reglas operativas coherentes y rentables.

---

## Qué usa Fase F

- State  
- Quality  
- LOOK_FOR  
- Validación estructural confirmada en Fase E  

---

## Qué hace Fase F

- Define reglas GO / NO-GO  
- Define arquitectura de riesgo por estado  
- Define tipo de estrategia coherente con el régimen  
- Permite validación walk-forward real  

---

## Qué NO hace

- No redefine estados  
- No redefine Quality  
- No redefine LOOK_FOR  
- No cambia lupas  
- No reentrena modelos  
- No crea edge artificial  

Si Fase F modifica contexto para mejorar performance,  
el sistema pierde validez estructural.

---

# Arquitectura del repositorio

configs/
baseline_registry.yaml
symbols/
_template.yaml
XAUUSD.yaml

scripts/
train_state_engine.py
train_event_scorer.py
phase_e.py
run_pipeline_backtest.py
watchdog_state_engine.py

state_engine/
pipeline.py
features.py
labels.py
model.py
gating.py
scoring.py
session.py
mt5_connector.py

tests/
test_features.py
test_events.py
test_config_loader.py


La infraestructura se reutiliza entre fases.  
La validez conceptual no se hereda automáticamente.

---

# Principio rector del repositorio

El sistema avanza en este orden:

> Describir → Contextualizar → Validar evolución → Ejecutar

Nunca:

> Ejecutar → Justificar → Redefinir → Optimizar retroactivamente

---

# Objetivo acumulado del sistema

Construir un sistema que:

- Describa estructura real del mercado  
- Reduzca ambigüedad contextual  
- Valide evolución estructural de narrativas  
- Permita ejecutar solo cuando exista coherencia estructural validada  

El sistema no busca predecir todo.

Busca:

> Operar solo cuando el contexto tenga sentido estructural validado.
