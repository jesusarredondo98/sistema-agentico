# Memoria del proyecto AeroNova

Esta carpeta es la **memoria persistente y externa** del agente de código. Existe por dos
razones: evitar la alucinación por olvido y evitar el gasto de tokens que supone releer el
PRD entero en cada turno.

> **Regla de oro.** Si algo no está en `PLAN.md`, en `INDEX.md` o en un acuerdo de
> `acuerdos/`, **no ha ocurrido**. El agente no puede afirmar que hizo algo que la memoria
> no registra, ni puede dar por decidido lo que no consta como acuerdo.

## Qué hay aquí

| Fichero | Qué es | Cuándo se lee | Cuándo se escribe |
|---|---|---|---|
| `PLAN.md` | **Estado vivo** del plan de acción: qué está hecho, qué falta, en qué fase estamos, cuánto presupuesto queda | **Al empezar cada turno, siempre. Es lo primero que se lee** | Tras **cada** actividad terminada, sin excepción |
| `INDEX.md` | Índice de una línea por acuerdo. Es el mapa que evita abrir ficheros innecesarios | Al empezar cada turno, junto con `PLAN.md` | Al crear o retirar un acuerdo |
| `acuerdos/ACU-NNN-<slug>.md` | Un acuerdo por fichero: una decisión cerrada con el usuario, un hallazgo o una desviación autorizada | Solo cuando `INDEX.md` indica que es relevante para la tarea en curso | Cuando el usuario aprueba algo o el agente detecta una contradicción |
| `costes.md` | Libro de gasto real: consultas al LLM y USD consumidos por fase | Antes de cualquier ejecución que gaste | Tras cada ejecución que gaste |

## Disciplina de tokens

1. **`PLAN.md` + `INDEX.md` siempre.** Juntos ocupan poco y dan el estado completo.
2. **`acuerdos/*` bajo demanda.** Se abre un acuerdo solo si su línea de `INDEX.md` toca
   la fase o el artefacto en curso.
3. **El PRD nunca se lee entero.** Se leen las secciones que la actividad cita, y solo esas.
   `PLAN.md` guarda en cada actividad las secciones del PRD que la gobiernan, precisamente
   para no tener que buscarlas.
4. **Nada de resúmenes del PRD en memoria.** Un resumen se desincroniza y se convierte en
   fuente de alucinación. La memoria guarda **decisiones y estado**, no copias del PRD.

## Formato de un acuerdo

```markdown
---
id: ACU-007
titulo: Reversión a x86_64 por rueda no disponible
tipo: decision | hallazgo | desviacion | contradiccion
estado: vigente | superado | retirado
fase: F0
prd_ref: ["S-02", "§2.6", "R-03"]
aprobado_por: usuario
fecha: 2026-08-27
---

**Qué se acordó.** Una frase, sin ambigüedad.

**Por qué.** La razón, con la evidencia que la sostiene (salida de comando, error real).

**Cómo se aplica.** Qué cambia en el código, en qué ficheros, y qué prueba lo verifica.

**Qué invalida este acuerdo.** La condición bajo la cual habría que revisarlo.
```

## Tipos de acuerdo

- **`decision`** — el usuario eligió entre alternativas. Solo el usuario crea decisiones.
- **`hallazgo`** — el agente descubrió un hecho verificado (una versión, un límite real, una
  incompatibilidad). Lleva siempre la evidencia que lo prueba.
- **`desviacion`** — se hace algo distinto de lo que dice el PRD. **Requiere aprobación
  explícita del usuario.** Sin ella no existe; el PRD manda.
- **`contradiccion`** — dos secciones del PRD se contradicen. El PRD ordena **detenerse y
  reportar** (regla de lectura, encabezado del PRD). El acuerdo queda `estado: vigente` y
  bloqueante hasta que el usuario lo resuelva.
