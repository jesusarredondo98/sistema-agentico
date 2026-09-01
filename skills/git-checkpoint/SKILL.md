---
name: git-checkpoint
description: Confirma en git el trabajo de una fase, y solo cuando esa fase ha superado su criterio de salida con evidencia. Incluye la revisión de higiene que impide subir un secreto. Úsala como último paso del cierre de cada fase, después de phase-gate y harness-reentry, nunca antes.
---

# Checkpoint de fase en git

Un commit por fase. Ni más ni menos.

> **El commit no es un guardado: es una afirmación.** Dice «esta fase superó su criterio de
> salida y aquí está la prueba». Confirmar una fase que no pasó su puerta convierte el
> historial en una mentira ordenada cronológicamente, y destruye justo lo que hace útil un
> historial: poder volver a un punto que se sabe bueno.

## Precondiciones — las tres, sin excepción

| # | Precondición | Cómo se comprueba |
|---|---|---|
| 1 | `phase-gate` emitió veredicto **APROBADA**, con la comprobación **ejecutada** | El veredicto y la salida del comando |
| 2 | `harness-reentry` terminó sin afirmaciones **NO SOSTENIDAS** en pie | El informe de reentrada |
| 3 | Todas las actividades de la fase están `[x]` con evidencia, `[-]` justificadas o `[!]` con acuerdo | `memory/PLAN.md` |

**Si falla cualquiera de las tres, no hay commit.** El trabajo se queda en el árbol y se
reporta al usuario. Nunca se confirma «para no perderlo»: perder trabajo no confirmado es
recuperable; un historial que miente sobre qué funcionaba, no.

## Paso 1 · Higiene: la revisión que impide subir un secreto

La Definición de Terminado del PRD §16 exige que **ningún secreto aparezca en Git**. Un
secreto confirmado no se borra reescribiendo el fichero: queda en el historial para siempre y
hay que rotar la credencial. Por eso la revisión va **antes** del `add`, no después.

```bash
# 1 · Qué se va a confirmar exactamente. Míralo, no lo asumas.
git status --short
git diff --stat

# 2 · Barrido de secretos sobre lo que se va a confirmar.
# Se excluye este propio fichero: contiene los patrones y se marcaría a sí mismo.
git diff --cached -- . ':!skills/git-checkpoint/SKILL.md' \
  | grep -nE 'sk-ant-[A-Za-z0-9_-]{20,}|ANTHROPIC_API_KEY *=|aws_secret_access_key|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY'

# 3 · Ficheros que nunca deben entrar, por si el .gitignore se quedó corto
git diff --cached --name-only | grep -E '\.tfstate|\.tfvars$|^\.env$|\.pem$|\.key$'

# 4 · Ficheros grandes que delatan datos sintéticos colados
git diff --cached --name-only | xargs -I{} sh -c 'test -f "{}" && du -k "{}"' 2>/dev/null | awk '$1>1024'
```

**Cualquier coincidencia en 2, 3 o 4 aborta el commit.** Se corrige y se vuelve a empezar.

> **Antes de abortar, identifica el fichero.** Un patrón como `sk-ant-` aparece legítimamente
> en documentación, en pruebas del filtro de salida (D-5, §12A.2) y en `.env.example`. La
> comprobación que separa el falso positivo del real es buscar el **valor**, no el patrón:
> `git diff --cached | grep -oE 'sk-ant-[A-Za-z0-9_-]{20,}'`. Si no devuelve nada, era la
> definición del patrón y no una credencial. **Documenta la exclusión; no la asumas.**

## Paso 2 · Confirmar

```bash
git add -A
git commit
```

Se usa `git add -A` **después** de la revisión, no antes: el `.gitignore` hace el trabajo
grueso y la revisión atrapa lo que se le escape.

## Formato del mensaje

El asunto identifica la fase; el cuerpo carga la evidencia. Un mensaje que solo diga «F4
terminada» obliga a abrir el diff para saber qué se demostró.

```
F4: índice RAG promovido con manifiesto, prueba de humo y rollback

Criterio de salida (PRD §14): una consulta de política devuelve fragmentos por
encima del umbral 0,35; rollback_rag.py retrocede y vuelve a avanzar.

Evidencia:
- Prueba de humo 5/5 en pass, score mínimo 0,58
- CURRENT: v=20260826T140311Z -> v=20260825T091802Z -> v=20260826T140311Z
- pytest tests/contracts/ -> 47 passed
- _manifest.json: 150 bronze / 148 silver / 2 cuarentena / 612 fragmentos

Actividades: A-60 a A-68 (9 de 9)
Gasto de la fase: 0,00 USD LLM + <0,01 USD Bedrock
Acuerdos nuevos: ACU-009

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

**Reglas del mensaje:**

- Asunto: `F<N>: <qué quedó demostrado>`, sin punto final.
- El bloque **Evidencia** lleva salidas reales, no descripciones. «Las pruebas pasan» no es
  evidencia; `47 passed` sí.
- Se declara el **gasto de la fase**, coherente con `memory/costes.md`.
- Si la fase abrió acuerdos, se nombran por su identificador.

## Paso 3 · Registrar el SHA en el plan

El commit se anota en la columna **Commit** del mapa de fases de `memory/PLAN.md`:

```bash
git rev-parse --short HEAD
```

Ese SHA es lo que convierte el plan en algo auditable: cualquiera puede hacer
`git show <sha>` y ver exactamente qué se afirmó y qué se entregó.

## Reglas de operación

| Regla | Motivo |
|---|---|
| **Un commit por fase**, no uno por actividad | El historial debe leerse como el plan de §14, no como un registro de teclas |
| **Nunca `git push` sin que el usuario lo pida** | Publicar es una acción hacia fuera y no la decide el agente |
| **Nunca `--amend` sobre una fase ya confirmada** | Reescribe una afirmación que ya se dio por buena |
| **Nunca `--no-verify`** | Si un hook bloquea, es que hay algo que mirar |
| **Nunca `git add` de un fichero que no se ha leído** | Es como se confirman secretos sin darse cuenta |
| Trabajo intermedio que se quiera salvar | `git stash`, no un commit de fase |

**Sobre la rama.** El PRD asume un solo operador (S-03), así que confirmar sobre la rama de
trabajo es coherente. Si esa rama es `main` y el usuario prefiere una rama dedicada, se crea
**antes de la primera fase**, no a mitad: `git switch -c feat/aeronova-implementacion`.

## Qué hacer si una fase se retoma tras el commit

Una fase confirmada está cerrada. Si después aparece un defecto en ella:

1. **No se reescribe** el commit de la fase.
2. Se abre una actividad nueva en `PLAN.md`, con su identificador.
3. Se corrige y se confirma aparte: `fix(F4): <qué se corrigió>`, citando el SHA original.

El historial debe conservar que la fase se dio por buena y que después se descubrió algo. Esa
secuencia es información, no un error que ocultar.

## Criterio de terminado

Existe un commit por cada fase cerrada, su mensaje contiene evidencia ejecutada, el barrido
de secretos no dio coincidencias, y el SHA corto está anotado en el mapa de fases de
`memory/PLAN.md`.
