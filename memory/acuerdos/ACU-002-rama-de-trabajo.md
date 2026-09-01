---
id: ACU-002
titulo: La implementación se hace en la rama feat/aeronova-implementacion
tipo: decision
estado: vigente
fase: F-1
prd_ref: ["S-03", "§13", "§16"]
aprobado_por: usuario
fecha: 2026-08-26
---

**Qué se acordó.** Toda la implementación de F0 a F10 se confirma en la rama
**`feat/aeronova-implementacion`**, creada desde `main` antes de la primera fase. `main`
queda con el PRD original y no recibe commits de implementación hasta que el usuario decida
integrar.

**Por qué.** La skill `git-checkpoint` establece que una rama de trabajo se crea **antes de la
primera fase, no a mitad**: hacerlo después obliga a reescribir historia o a dejar commits de
fase repartidos entre dos ramas. El proyecto tiene un solo operador (S-03), de modo que la
rama no existe para coordinar a varias personas sino para mantener `main` en un estado
conocido mientras se construye.

**Cómo se aplica.**

- Un commit por fase cerrada, con el formato de `skills/git-checkpoint/SKILL.md`.
- El SHA corto se anota en la columna **Commit** del mapa de fases de `memory/PLAN.md`.
- **Nunca `git push`** sin que el usuario lo pida explícitamente.
- La integración a `main` la decide el usuario al terminar, no el agente.

**Qué invalida este acuerdo.** Que el usuario pida trabajar directamente sobre `main`, o que
entre un segundo operador y haga falta un esquema de ramas por fase.
