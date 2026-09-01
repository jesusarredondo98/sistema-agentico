---
name: harness-reentry
description: Reentiende el arnés y el PRD al cerrar cada fase, para evitar la deriva y la alucinación acumuladas. Relee Agents.md, PLAN.md y las secciones que gobiernan la fase siguiente, y somete lo afirmado durante la fase a una declaración de conformidad con evidencia. Úsala inmediatamente después de cada puerta de fase aprobada.
---

# Reentrada al arnés

Un agente que trabaja diez fases seguidas deriva. No porque falle una vez, sino porque cada
fase añade una capa de contexto propio que va desplazando al documento normativo: recuerda
su propia decisión de la fase 3 mejor que la sección del PRD que la contradice.

Esta skill es el mecanismo de corrección: **al cerrar cada fase, el agente vuelve al arnés
como si acabara de llegar**, y comprueba que lo que hizo y lo que va a hacer siguen
gobernados por el documento, no por su recuerdo.

> **Premisa.** El PRD es normativo y no cambia. El recuerdo que el agente tiene del PRD sí
> cambia, y siempre en la misma dirección: hacia lo que le resultó cómodo implementar.

## Cuándo se invoca

- **Obligatoria** tras cada puerta de fase aprobada, antes de abrir la siguiente.
- Tras cualquier truncado o resumen del contexto de la conversación.
- Al retomar el proyecto en una sesión nueva.
- Cuando el usuario señale que algo no coincide con lo que pidió.

## Procedimiento

### 1. Relectura obligatoria, en este orden

| # | Fichero | Qué se busca |
|---|---|---|
| 1 | `memory/PLAN.md` | Estado real: qué está `[x]`, qué falta, en qué fase estamos |
| 2 | `memory/INDEX.md` | Acuerdos vigentes y bloqueantes |
| 3 | `documents/Agents.md` §2 y §4 | Los innegociables y el bucle operativo |
| 4 | Secciones del PRD de la fase **siguiente** | Lo que gobierna lo que viene |

**No se relee el PRD entero.** Se releen los innegociables del arnés y las secciones de la
fase que se abre. Releer todo cuesta tokens y, peor, dilucida la atención.

### 2. Declaración de conformidad de la fase cerrada

Cada afirmación hecha durante la fase se somete a una de tres etiquetas. Sin excepciones:

| Etiqueta | Significado | Qué se exige |
|---|---|---|
| **VERIFICADO** | Se ejecutó y se vio la salida | La salida del comando o la ruta del fichero |
| **INFERIDO** | Se dedujo del PRD sin ejecutar | La cita de la sección, y una nota de que no se ejecutó |
| **NO SOSTENIDO** | Ni ejecutado ni citable | **Se retira la afirmación** y se corrige al usuario |

Una afirmación **NO SOSTENIDA** es una alucinación ya emitida. Retirarla en la reentrada es
barato; descubrirla en la entrega no.

### 3. Las siete preguntas de deriva

| # | Pregunta | Riesgo que ataja |
|---|---|---|
| 1 | ¿Implementé algo que el PRD **no pide**? | R-12, expansión de alcance |
| 2 | ¿Eliminé alguna validación por creerla redundante? | **R-09**: el data contract no sustituye a la validación de §5.4 |
| 3 | ¿Relajé una comprobación del servidor porque el cliente ya la hace? | **R-23**, prohibido por §10.2 |
| 4 | ¿Añadí alguna herramienta con efectos secundarios? | **R-20**: rompe D-3 y obliga a rehacer el análisis de amenazas |
| 5 | ¿Cambié algún valor numérico del PRD «porque tenía más sentido»? | 29 s, 2048 MB, `top_k=4`, umbral 0,35, 1.200 caracteres, cuota MENSUAL |
| 6 | ¿Recorté el system prompt por debajo de 1.024 tokens? | **R-14**: desactiva la caché en silencio y **encarece** el sistema |
| 7 | ¿Di por hecho algo que no verifiqué con un comando? | Alucinación pura |

Cada «sí» abre un acuerdo en `memory/acuerdos/` y, si procede, revierte el cambio.

### 4. Reafirmar los innegociables

Se releen y se confirman uno a uno los innegociables de `Agents.md` §2. Es una lista corta y
deliberadamente repetitiva: son los puntos donde un agente competente se equivoca **por
buen criterio propio**, no por descuido.

### 5. Emitir el informe de reentrada

```markdown
### Reentrada al arnés — cierre de F4, apertura de F5

**Releído:** PLAN.md · INDEX.md · Agents.md §2,§4 · PRD §4.4, §4.5, §5.1, §5.2

**Conformidad de F4**
- VERIFICADO (7): índice promovido, smoke en pass, rollback ida y vuelta, …
- INFERIDO (1): «el índice pesa < 20 MB» — §6.3 lo estima; **no lo medí**. Lo mido en F5.
- NO SOSTENIDO (0)

**Deriva:** ninguna de las 7 preguntas dio positivo.
**Innegociables:** 15 de 15 confirmados.
**Acuerdos nuevos:** ACU-009 (versión real de `lancedb`).

**F5 puede abrirse.**
```

## Antipatrones

- Declarar la reentrada sin abrir los ficheros. La skill **es** la relectura; narrarla no es
  hacerla.
- Etiquetar como VERIFICADO algo cuya salida no se conserva. Si no se puede pegar la
  evidencia, es INFERIDO.
- Saltarse la reentrada «porque la fase fue corta». Las fases cortas son justamente donde se
  cuela un supuesto sin verificar.

## Criterio de terminado

Cero afirmaciones NO SOSTENIDAS en pie, las siete preguntas de deriva respondidas, los
innegociables reconfirmados y el informe presentado al usuario.
