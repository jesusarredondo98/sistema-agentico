---
name: terraform-stacks
description: Despliega la topología AWS en dos stacks de Terraform separados, con IAM acotado por ARN, Usage Plan de cuota mensual y guardarraíles de presupuesto. Úsala en F2 (bootstrap) y F7 (aplicación). Ningún recurso se crea a mano por consola.
---

# Stacks de Terraform

**Toda la topología se despliega con Terraform. Ningún recurso se crea a mano por consola.**

## Por qué dos stacks, y no uno

Una Lambda de tipo imagen exige que la imagen **ya exista en ECR** en el momento del `apply`.
Un stack único que cree el repositorio ECR y la función a la vez **es circular y falla
siempre** (hallazgo 9).

| Stack | Crea | Cuándo |
|---|---|---|
| `terraform/00-bootstrap` | ECR, 3 tablas DynamoDB, 2 buckets S3, parámetro SSM | Apply #1, en F2 |
| `terraform/10-app` | Lambda, API Gateway, IAM, CloudFront, EventBridge, alarmas, Budgets | Apply #2, en F7 |

`10-app` lee las salidas de `00-bootstrap` mediante `terraform_remote_state`.

Estado **local** (S-03): un solo operador. Se documenta la migración a backend S3+DynamoDB
para multi-operador, pero no se implementa.

## Parámetros exactos de la Lambda (§2.2) — no se ajustan «a ojo»

| Parámetro | Valor | Justificación |
|---|---|---|
| `timeout` | **29 s** | API Gateway REST corta a los 29 s. Un valor mayor solo desplaza quién emite el error |
| `memory_size` | **2048 MB** | La CPU escala con la memoria: reduce carga del índice y serialización |
| `ephemeral_storage` | **2048 MB** | `/tmp` por defecto son 512 MB; el índice los desborda |
| `architectures` | `["arm64"]` | ~20 % más barato (S-02) |
| `package_type` | `Image` | §2.5 |
| `reserved_concurrent_executions` | **20** | Techo de gasto: impide que un bucle dispare el coste del LLM |
| `logging_config.log_format` | `JSON` | Consultable con Logs Insights |
| Retención de logs | **14 días** | Coste |

> **SnapStart no está disponible para funciones empaquetadas como imagen** (solo ZIP). No se
> intenta activar: el `apply` fallará.

## API Gateway y el control de coste primario (§2.3)

- Recurso `POST /v1/chat`, stage `prod`, tipo **REST** (no HTTP API: el Usage Plan con
  `x-api-key` es nativo de REST).
- `api_key_required = true`. La ausencia de la cabecera devuelve **403** (nativo, no
  configurable a 401).
- **Usage Plan: `throttle` 10 req/s, `burst` 20, `quota` 2.000 con `period = MONTH`.**

> **La cuota es MENSUAL, y esa diferencia es el guardarraíl del presupuesto** (hallazgo 38,
> severidad bloqueante). Con `period = DAY`, 2.000 peticiones/día permiten ~525 USD/mes: **26
> veces el techo acordado**. **No se cambia el periodo a `DAY` ni se eleva la cuota sin
> decisión explícita del sponsor.**

- **CORS** restringido al dominio de CloudFront (salida de Terraform), **nunca `*`**.
  `Access-Control-Allow-Headers: content-type,x-api-key`.

## IAM: explícito y acotado por ARN (§2.5)

**Prohibido usar comodines de servicio.** Ocho permisos, cada uno con su recurso:
logs del propio log group · DynamoDB `memory` (lectura y escritura) · DynamoDB `flights` y
`reservations` (solo `GetItem`/`BatchGetItem`) · `s3:GetObject` sobre
`gold/rag/*` · `s3:ListBucket` condicionado a `s3:prefix = gold/rag/*` · `bedrock:InvokeModel`
sobre el ARN exacto de Titan V2 · `ssm:GetParameter` del parámetro · `kms:Decrypt`.

> **Separación de roles sobre el lago, obligatoria.** El rol de la Lambda **solo lee
> `gold/rag/`**: sin acceso a Bronze, Silver ni Quarantine, y **sin ningún permiso de
> escritura sobre el lago**. El medallion lo construye el operador con sus propias
> credenciales desde la terminal. Esto impide que un fallo del runtime contamine las capas de
> origen.

## Recursos de datos (§2.4)

Las tres tablas en `PAY_PER_REQUEST`, **PITR desactivado** por coste. TTL sobre `expires_at`
solo en `aeronova-memory`. Buckets privados con `block_public_access` completo, SSE-S3 y
versionado; el de UI servido **exclusivamente vía CloudFront con OAC**. CloudFront con
`redirect-to-https` y `PriceClass_100`.

`<sufijo>` derivado de `random_id` o del ID de cuenta, para unicidad global del nombre.

**Ciclo de vida de S3:** `bronze/` y `quarantine/` a Glacier IR a 30 días; `gold/rag/`
conserva **3 versiones**. Sin esto, cada reconstrucción acumula coste indefinidamente.

## Calentamiento (§2.2)

EventBridge con `rate(5 minutes)` invocando `{"warmup": true}`. El handler detecta el payload,
ejecuta la inicialización y **retorna de inmediato sin llamar al LLM**. Coste ≈ 0,05 USD/mes.

`enable_provisioned_concurrency` se expone como variable **con valor por defecto `false`**.

> **Está documentada pero es incompatible con el presupuesto acordado:** por sí sola consume
> 20–25 USD/mes, más que el techo completo. Activarla exige **renegociar el presupuesto**, no
> es una optimización libre.

## Guardarraíles y alarmas

`aws_budgets_budget` a **20 USD** con alertas al 50/80/100 % del real y del previsto (G-3), y
las 10 alarmas de CloudWatch de §11.

## Etiquetado obligatorio en todos los recursos

`Project=aeronova-agent` · `Environment=eval` · `ManagedBy=terraform` · `Owner=<email>`

## Runbook (§13)

Paso 0 preflight · 1 bootstrap · 2 secreto por `aws ssm put-parameter` (**nunca por
`.tfvars`**) · 3 `make data` · 4 imagen · 5 `apply` con `image_tag=<sha>` · 6 verificación ·
6-bis recarga y rollback · 7 teardown.

> **Prerrequisito no automatizable:** el acceso al modelo Titan V2 se habilita **una vez por
> cuenta y región desde la consola de Bedrock**. Sin ello, `bedrock:InvokeModel` falla con
> `AccessDeniedException` **pese a tener el permiso IAM**. Es el paso 0 y el riesgo R-04
> (probabilidad alta).

## Criterio de terminado

`terraform plan` limpio en ambos stacks, `curl` con `x-api-key` devuelve 200 contra `api_url`,
el Usage Plan muestra `period = MONTH`, y `terraform destroy` deja la cuenta limpia.
