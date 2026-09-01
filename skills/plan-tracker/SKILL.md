---
name: plan-tracker
description: Mantiene y muestra el plan de acción vivo de memory/PLAN.md — qué se hizo, qué falta, en qué fase estamos y cuánto presupuesto queda. Úsala al empezar cada turno, después de cada actividad terminada y siempre que el usuario pregunte por el estado. Es el antídoto contra la pérdida de contexto y el progreso alucinado.
---

# Rastreador del plan de acción

El estado del proyecto **no vive en la conversación**: vive en `memory/PLAN.md`. Una
conversación se resume, se trunca y se pierde; un fichero no. Todo lo que el agente afirme
sobre lo hecho y lo pendiente sale de ahí, y de ningún otro sitio.

> **Regla vinculante.** Si `PLAN.md` no marca una actividad como `[x]`, esa actividad **no
> está hecha**, aunque el agente recuerde haberla hecho. La memoria del modelo no es
> evidencia; el fichero sí.

## Cuándo se invoca

| Momento | Acción |
|---|---|
| **Al empezar cada turno** | Leer `PLAN.md` e `INDEX.md`. Siempre. Antes de cualquier otra cosa |
| **Al terminar cada actividad** | Marcarla `[x]` **con su evidencia**, actualizar contadores |
| **Al cambiar de fase** | Actualizar «Fase actual» y el estado en el mapa de fases |
| **Al final de cada respuesta al usuario** | **Mostrar el plan**: hecho, en curso, siguiente |
| **Si el usuario pregunta «¿por dónde vamos?»** | Releer el fichero y responder desde él, nunca de memoria |

## Los cuatro estados

| Marca | Significado | Requisito para ponerla |
|---|---|---|
| `[ ]` | Pendiente | — |
| `[~]` | En curso | Solo **una** actividad puede estar en curso a la vez |
| `[x]` | Hecha | **Evidencia obligatoria**: ruta de fichero, salida de comando o prueba en verde |
| `[!]` | Bloqueada | Acuerdo abierto en `memory/acuerdos/` que la explica |

**Nunca se marca `[x]` sin evidencia.** Una actividad marcada por optimismo es una
alucinación con formato de checklist, y es peor que no tener plan: da falsa confianza.

## Cómo se actualiza

1. Editar la línea de la actividad: `- [ ] **A-NN** …` → `- [x] **A-NN** … · evidencia: <prueba>`
2. Recalcular «Actividades terminadas: N de 114» en la cabecera.
3. Actualizar «Última actualización» con la fecha real.
4. Si la actividad gastó dinero, anotar la fila correspondiente en `memory/costes.md`.
5. Si se descubre trabajo no previsto, **añadir la actividad al plan** con un ID nuevo y
   subir el denominador. El plan crece; no se ejecuta trabajo que no figure en él.

## Formato de la vista al usuario

Al cerrar cada respuesta, el agente muestra este bloque. Compacto, sin volcar las 78 líneas:

```markdown
### Plan de acción — F2b (34 de 114)

**Recién terminado**
- [x] A-44 Puerta de contrato en `promote_silver.py` · 3 % de cuarentena, E-01..E-09 en pass

**En curso**
- [~] A-46 Siembra de DynamoDB desde Silver

**Siguiente**
- [ ] A-47 Inyección de corrupción de ruta B
- [ ] A-48 Manifiesto de linaje

**Presupuesto:** 0,32 USD de 8,80 · **Fase F2b:** 6 de 10 · **Bloqueos:** ninguno
```

Se muestran como mucho **3 actividades por bloque**. La vista es para orientar, no para
volcar el fichero: el fichero ya está en disco y el usuario puede abrirlo.

## Reglas de integridad

- **Un plan, un fichero.** No se mantienen listas paralelas en la conversación ni en otro
  documento. Dos fuentes de verdad garantizan que una miente.
- **No se borra nada.** Una actividad descartada se marca `[-]` con el motivo, no se elimina.
  El historial de lo descartado evita volver a proponerlo tres fases después.
- **El orden es el de PRD §14.** No se reordenan fases. Dentro de una fase, las actividades
  pueden reordenarse si no hay dependencia.
- **Una actividad `[~]` que lleve dos turnos sin cerrarse** se reporta al usuario: o está
  bloqueada y hay que declararlo, o es demasiado grande y hay que partirla.

## Criterio de terminado

`PLAN.md` refleja el estado real verificable del repositorio. Prueba: un agente nuevo que
lea solo `PLAN.md` y ejecute `ls`/`pytest` encuentra exactamente lo que el plan declara.
