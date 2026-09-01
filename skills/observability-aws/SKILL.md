---
name: observability-aws
description: Instrumenta logs JSON con redacción de PII, métricas EMF, trazas en LangSmith y alarmas de CloudWatch. Úsala en F6 y al desplegar en F7. Sin esto no se puede correlacionar una caída de calidad con una recarga de datos.
---

# Observabilidad

## Logs estructurados

JSON con `aws-lambda-powertools`. **Todo registro lleva** `request_id`, `session_id`,
`employee_id` y `duration_ms`.

## Redacción de PII — obligatoria

**Nunca se registran en claro:**

- El **PNR completo** → se enmascara a `AB***3`
- Los **nombres de pasajeros**
- El **`message` íntegro** del usuario → se registra su **longitud y un hash**

Esto no es una buena práctica opcional: la conversación contiene PII y §12 lo exige. La
redacción vive en `src/logic/observability.py`, y es la misma razón por la que
`aeronova-memory` queda fuera del medallion (§6A.0).

## Métricas EMF — espacio `AeroNova/Agent`

`ToolInvocations` (dimensiones: nombre, resultado) · `LLMTokens` (entrada/salida/lectura de
caché) · `ToolRounds` · `RagHits` · `RagBelowThreshold` · `CostUSD` · `InjectionSuspected` ·
`OutputFilterTriggered` · `PromptBudgetTruncations` · `InputRejected` (dimensión: motivo) ·
`SessionCostUSD`.

> **`RagHits` debe llevar `contract_version` e `index_version` como dimensiones** (§6A.7). Sin
> eso es imposible correlacionar una caída de calidad de respuesta con una recarga de datos, y
> se acaba depurando el prompt cuando el problema estaba en el índice.

## Métricas del pipeline — espacio `AeroNova/Data`

Emitidas por `run_pipeline.py`, por dataset: `RowsBronze`, `RowsSilver`, `RowsQuarantined`,
`QuarantineRate`, `ExpectationFailures`, `ChunksIndexed`, `EmbeddingsComputed`,
`SmokeTestResult`. Hacen visible la calidad de la carga **sin abrir un fichero**.

## Trazas

LangSmith vía `LANGCHAIN_TRACING_V2`. **El `session_id` se propaga como metadato de la traza.**

## Alarmas de CloudWatch (definidas en Terraform)

| Alarma | Umbral | Qué señala |
|---|---|---|
| Tasa de error de la Lambda | > 5 % en 5 min | Fallo general |
| Duración p95 | > 20 s | Se acerca al corte de 29 s |
| Throttles | > 0 | La concurrencia de 20 está mordiendo |
| `CostUSD` acumulado diario | > 30 USD | Gasto descontrolado |
| `QuarantineRate` de la última carga | > 2 % | Puerta de contrato rechazando de más (E-04) |
| Antigüedad de `gold/rag/CURRENT` | > `CONTRACT_SLA_HOURS` | Índice rancio |
| `OutputFilterTriggered` | **> 0** | **Evento de seguridad, notificación inmediata** |
| `InjectionSuspected` | > 5 en 1 h | Patrón de sondeo |
| `SessionCostUSD` p99 | > 0,20 USD | Sesiones acercándose al cortacircuitos |
| `PromptBudgetTruncations` | > 10 % de las peticiones | **El perfil de tokens de §9.3 ya no refleja el uso real** (R-22) |

## Contabilidad del gasto — no es opcional

Cada respuesta devuelve `usage.cost_usd` (§4.2). **El runner del golden dataset y
`chat_cli.py` deben acumularlo e imprimir el total al terminar.**

> Sin esa contabilidad, el presupuesto de §9.4 **es una intención, no un control**.

## Criterio de terminado

Un `filter` de Logs Insights recupera un turno completo por `request_id` sin PII en claro, las
métricas aparecen en CloudWatch con sus dimensiones, y las 10 alarmas existen en
`terraform show`.
