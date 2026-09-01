---
name: socratic-intake
description: Establece el entendimiento socrático antes de ejecutar cualquier actividad del PRD. Genera preguntas, las responde citando secciones, separa lo que sabe de lo que supone y obtiene confirmación del usuario. Úsala al abrir cada fase y ante cualquier instrucción ambigua, antes de escribir una línea de código.
---

# Entendimiento socrático

El agente no empieza a trabajar porque haya entendido; empieza a trabajar cuando **puede
demostrar** que ha entendido. La diferencia se demuestra respondiendo preguntas con la cita
de la sección que sostiene cada respuesta.

> **Premisa.** Una respuesta sin cita es una suposición disfrazada. Es exactamente el punto
> por donde entra la alucinación en un proyecto de 1.578 líneas de requisitos.

## Cuándo se invoca

- **Obligatoria** al abrir cada fase F0–F10.
- Ante cualquier instrucción del usuario que admita dos lecturas.
- Cuando una actividad toca una sección del PRD que aún no se ha leído en esta sesión.

## Procedimiento

### 1. Leer solo lo que gobierna la actividad

`memory/PLAN.md` indica en cada actividad las secciones del PRD que la rigen. Se leen
**esas**, no el PRD entero. Leer de más gasta tokens; leer de menos inventa.

### 2. Formular las seis preguntas

Para la fase o instrucción en curso, el agente redacta y responde:

| # | Pregunta | Qué destapa si no se puede responder |
|---|---|---|
| Q1 | **¿Qué** hay que producir exactamente, en qué ficheros? | Alcance difuso: se construirá algo parecido pero no lo pedido |
| Q2 | **¿Por qué** el PRD lo pide así y no de la forma obvia? | Se «mejorará» una decisión deliberada y se romperá el diseño |
| Q3 | **¿Cómo** se verifica que está bien, con qué comando o prueba? | No habrá criterio de salida: la fase se dará por buena sin evidencia |
| Q4 | **¿Qué NO** hay que hacer aquí, aunque parezca natural? | Expansión de alcance por iniciativa propia (§0.3, R-12) |
| Q5 | **¿De qué depende** y qué depende de ello? | Se implementará fuera de orden y habrá que rehacerlo |
| Q6 | **¿Cuánto cuesta** ejecutarlo y qué presupuesto consume? | Se gastará sin aprobación (§9.4) |

**Cada respuesta lleva su cita.** Formato: `respuesta — §X.Y` o `respuesta — D-0N / S-0N / R-NN`.

### 3. Separar las tres categorías

El resultado se clasifica sin piedad:

- **SÉ** — respondido con cita literal del PRD. Se ejecuta.
- **SUPONGO** — deducido con criterio razonable, sin cita directa. **Se declara al usuario
  antes de ejecutar.** El PRD permite suponer, no permite ocultar que se supone.
- **NO SÉ** — ni cita ni deducción segura. **Bloquea la actividad.** Se pregunta.

### 4. Buscar activamente la contradicción

Antes de cerrar, el agente comprueba si dos secciones del PRD se contradicen sobre esta
actividad. La regla de lectura del PRD es explícita: **detenerse y reportar, nunca elegir
una.** Si aparece, se registra un acuerdo `contradiccion` con `memory-ledger` y la fase
queda bloqueada.

### 5. Presentar y esperar

Se presenta al usuario: las seis respuestas, la lista de SUPONGO, la lista de NO SÉ y el
coste estimado. **No se escribe código hasta que el usuario confirma.**

## Contrato de salida

```markdown
## Entendimiento socrático — Fase FN

**Q1 Qué:** …  — §3
**Q2 Por qué:** … — §5.2
**Q3 Cómo lo verifico:** `comando exacto` → resultado esperado — §14
**Q4 Qué no:** … — §0.3
**Q5 Dependencias:** requiere FN-1 · habilita FN+1 — §14
**Q6 Coste:** N consultas ≈ X,XX USD — §9.4

**Supongo (revisable, dime si me equivoco):**
- …

**No sé (bloqueante, necesito tu respuesta):**
- …

**Contradicciones detectadas:** ninguna | ACU-NNN
```

## Criterio de terminado

La lista **NO SÉ** está vacía y el usuario ha confirmado la lista **SUPONGO**. Con una sola
entrada sin resolver en NO SÉ, la fase no arranca.

## Antipatrones

- Responder «lo entiendo» sin las seis preguntas. No es entendimiento, es cortesía.
- Citar una sección que no dice lo que se afirma. **Se verifica abriendo el fichero**, no de memoria.
- Convertir un NO SÉ en un SUPONGO para no tener que preguntar. Es la vía directa a la alucinación.
- Repetir el intake completo dentro de una misma fase. Se hace una vez al abrirla; después
  gobierna `plan-tracker`.
