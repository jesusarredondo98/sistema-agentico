---
name: prd-trace
description: Traza cada requisito DEBE del PRD hasta el artefacto que lo implementa y la prueba que lo verifica, y detecta contradicciones entre secciones. Úsala al planificar una fase, al cerrar el entregable y siempre que sospeches que una sección del PRD choca con otra.
---

# Trazabilidad del PRD

El PRD tiene 16 secciones, 26 riesgos, 54 hallazgos del PMO y decenas de **DEBE**. Un
requisito que nadie implementa no falla ninguna prueba: simplemente no está. Esta skill hace
visible ese hueco.

## Las tres columnas

Todo requisito normativo se traza en tres columnas. **Ninguna puede quedar vacía**:

```
REQUISITO (§ del PRD)  →  ARTEFACTO (fichero:línea)  →  VERIFICACIÓN (prueba o comando)
```

| Columna vacía | Qué significa |
|---|---|
| Sin **artefacto** | El requisito no está implementado. Es un hueco, no una omisión menor |
| Sin **verificación** | Está implementado pero nadie sabe si funciona. Se romperá sin que nadie lo note |
| Sin **requisito** | Se construyó algo que el PRD no pide. Candidato a expansión de alcance (§0.3, R-12) |

## Cómo se extraen los requisitos

```bash
grep -n "DEBE\|NO DEBE" documents/PRD.md | wc -l      # el universo normativo
grep -n "^| R-[0-9]" documents/PRD.md                  # los 26 riesgos con su mitigación
grep -n "^| D-0\|^| S-0" documents/PRD.md              # decisiones cerradas y supuestos
```

Cada **DEBE** es un requisito. Cada **NO DEBE** es una prohibición que también se traza: su
«verificación» es la ausencia comprobada de lo prohibido.

## Detección de contradicciones

La regla de lectura del PRD es taxativa:

> **Si encuentras una contradicción entre dos secciones, detente y repórtala en lugar de
> elegir una.**

Elegir una es lo peligroso: produce un sistema coherente consigo mismo e incoherente con lo
acordado, y el error se descubre en la entrega.

**Contradicciones aparentes que el PRD ya resolvió** — no se reportan, se leen bien:

| Aparente choque | Resolución en el PRD |
|---|---|
| «5 % de anomalías» vs. «el contrato las bloquea» | §7.1: ruta A (3 %, cuarentena) y ruta B (2 %, inyección directa en Gold) |
| Ventana de historial: 12 en §9.2 vs. 8 en §2.7 y §9.3 | §2.7 manda: **8**. §9.2 arrastra el texto de la v2.1 |
| «todo dato atraviesa tres capas» vs. `aeronova-memory` | §6A.0: la memoria queda **fuera** del medallion |
| El data contract «ya valida», ¿sobra §5.4? | §6A.8: **no**. Son dos capas distintas. Eliminar una es R-09 |
| Techo de 20 USD vs. techo duro de 17,90 | 17,90 es el techo del diseño; 20 es el límite acordado con el sponsor |
| §9.2 numera dos veces los puntos 3 y 4 | Error de numeración, no de contenido. Las palancas son las ocho listadas |

Ante una contradicción **nueva**, se registra un acuerdo `contradiccion` con `memory-ledger`,
se marca `[!]` la actividad en `PLAN.md` y **se detiene la fase**.

## Cobertura mínima por fase

Antes de cerrar una fase, todo **DEBE** de las secciones que la gobiernan tiene sus tres
columnas. La matriz vive en el informe de la fase, no en un fichero permanente: el fichero
permanente es `PLAN.md`, y duplicarlo crearía una segunda fuente de verdad.

## Trazas críticas que no pueden faltar

Estas son las que, si se pierden, producen un sistema que parece funcionar y no cumple:

| Requisito | Artefacto | Verificación |
|---|---|---|
| Cuota **MENSUAL**, no diaria (§2.3, hallazgo 38) | `terraform/10-app/main.tf` | `terraform show \| grep period` → `MONTH` |
| Sin `temperature`/`top_p`/`top_k` (§5.3) | nodo LLM | Captura del cuerpo HTTP saliente |
| Prefijo cacheable > 1.024 tokens (§5.3, R-14) | `src/agent/prompts.py` | `cache_read_input_tokens > 0` |
| E-02, integridad referencial cruzada (§6A.4) | `src/contracts/expectations.py` | Lote con referencia colgante aborta |
| Escapado de `<` y `>` antes de envolver (D-1) | `src/logic/` | Familia `injection_escape_*` |
| Validación de §5.4 **conservada** (§6A.8, R-09) | `src/tools/schemas.py` | Familia `anomalia_*` |
| Comprobación de propiedad de sesión (§4.5) | `src/logic/memory.py` | 403 `SESSION_FORBIDDEN` |
| L-1/L-2/L-3 **antes** de llamar al LLM (§12A.3) | `handler.py` | Familia `abuse_*` con coste cero |
| `ui/examples.json` con datos reales (§10.3, R-25) | `ui/examples.json` | Comprobación U-14 |

## Criterio de terminado

Cero requisitos sin artefacto, cero artefactos sin verificación, cero artefactos sin
requisito, y las contradicciones nuevas registradas como acuerdo bloqueante.
