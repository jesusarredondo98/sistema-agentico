---
name: memory-ledger
description: Registra y consulta los acuerdos del proyecto en la carpeta memory/ — decisiones aprobadas, hallazgos verificados, desviaciones autorizadas y contradicciones del PRD. Úsala cuando el usuario apruebe algo, cuando se verifique un hecho no obvio o cuando dos secciones del PRD se contradigan.
---

# Libro de acuerdos

La memoria del modelo se pierde con el contexto. La memoria del proyecto vive en `memory/`
y sobrevive a cualquier truncado, resumen o sesión nueva. Su propósito no es archivar: es
**impedir que el agente reabra decisiones ya cerradas o invente que algo se decidió**.

## Qué se guarda y qué no

| Se guarda | No se guarda |
|---|---|
| Una decisión que el usuario tomó entre alternativas | Cualquier cosa que ya diga el PRD |
| Un hecho verificado que el PRD no podía saber (versión real de una librería, error concreto) | Resúmenes del PRD — se desincronizan y alucinan |
| Una desviación del PRD autorizada por el usuario | El código escrito — ya está en el repositorio |
| Una contradicción detectada entre secciones del PRD | Explicaciones de lo que hace un fichero — se leen del fichero |
| El resultado de una verificación cara de repetir (R-01, R-03) | Estado del plan — eso es `PLAN.md`, no un acuerdo |

> **Prueba de si algo merece un acuerdo:** ¿un agente nuevo que lea el PRD y el repositorio
> llegaría a la misma conclusión? Si sí, no es un acuerdo. Si no, lo es.

## Consulta: primero el índice, nunca el barrido

```bash
cat memory/INDEX.md          # siempre, al empezar el turno
cat memory/acuerdos/ACU-007-*.md   # solo si el índice dice que toca esta fase
```

**Nunca** `cat memory/acuerdos/*.md`. El índice existe precisamente para no pagar ese barrido
en tokens. Si el índice no basta para decidir si un acuerdo es relevante, su gancho está mal
escrito y hay que corregirlo.

## Registro de un acuerdo

1. Asignar el siguiente `ACU-NNN` correlativo.
2. Escribir `memory/acuerdos/ACU-NNN-<slug>.md` con el formato de `memory/README.md`.
3. Añadir la línea al `INDEX.md`, entre los marcadores.
4. Si es de tipo `contradiccion`, añadirlo también a **Acuerdos bloqueantes activos** y
   marcar `[!]` la actividad afectada en `PLAN.md`.

## Los cuatro tipos, y quién puede crearlos

| Tipo | Quién lo origina | Efecto |
|---|---|---|
| `decision` | **Solo el usuario.** El agente propone, el usuario decide | Cierra una alternativa: no se vuelve a proponer |
| `hallazgo` | El agente, **con evidencia adjunta** | Se da por sabido: no se vuelve a verificar |
| `desviacion` | El agente propone, **el usuario aprueba**. Sin aprobación no existe | Permite apartarse del PRD en un punto concreto |
| `contradiccion` | El agente | **Bloquea la fase.** Solo el usuario la resuelve |

## Ciclo de vida

- Un acuerdo `vigente` obliga. Se aplica sin volver a discutirlo.
- Un acuerdo se marca `superado` cuando otro posterior lo sustituye; se enlazan entre sí.
- Un acuerdo se marca `retirado` cuando resultó equivocado. **Se conserva el fichero** con la
  razón: saber qué se descartó y por qué evita reproponerlo dentro de tres fases.
- **Nunca se edita en silencio un acuerdo vigente.** Se crea uno nuevo que lo supera.

## Acuerdos que el PRD ya anticipa

Estos aparecerán casi con seguridad. Conviene reconocerlos al vuelo:

| Situación | Tipo | PRD |
|---|---|---|
| `langchain-anthropic` inyecta `temperature` → se pasa al SDK `anthropic` directo | `hallazgo` | §5.3, R-01 |
| Una rueda no publica `manylinux_aarch64` → reversión a `x86_64` | `desviacion` | S-02, R-03 |
| Versiones exactas de `requirements.txt` una vez resueltas | `hallazgo` | §2.6 |
| Códigos de vuelo y PNR reales elegidos para `ui/examples.json` | `hallazgo` | §10.3, R-25 |
| Confirmación de que G-2 está activo en la consola de Anthropic | `decision` | §9.5 |
| Reverificación de precios de AWS en la calculadora oficial | `hallazgo` | §9.3 |

## Antipatrones

- Guardar un acuerdo por cada cosa que pasa. El índice deja de ser útil y nadie lo lee.
- Escribir un acuerdo sin evidencia. Un `hallazgo` sin la salida del comando que lo prueba es
  una opinión con número de expediente.
- Tratar una suposición propia como `decision`. Solo el usuario decide.
- Releer el PRD para algo que ya está en un acuerdo. Ese es justamente el gasto que la
  carpeta existe para evitar.

## Criterio de terminado

`INDEX.md` tiene una línea por cada fichero de `acuerdos/`, ningún acuerdo `vigente` se
contradice con otro, y los acuerdos bloqueantes están reflejados en `PLAN.md` como `[!]`.
