---
name: cost-gate
description: Estima y somete a aprobación el coste de toda decisión de arquitectura y de toda ejecución que gaste dinero, antes de ejecutarla. Presenta coste unitario, coste total, consumo de presupuesto y de cuota. Úsala antes de cualquier llamada al LLM en lote, siembra de datos, apply de Terraform o prueba de carga.
---

# Puerta de coste

Este proyecto tiene un techo de **20 USD/mes** acordado con el sponsor y un gasto previsto
de **9,20 USD/mes** (PRD §9.4). El coste no lo domina el tráfico de producción sino el
desarrollo y las pruebas: **el 60 % del presupuesto no atraviesa la cuota del API Gateway**
y por tanto no tiene tope automático (§9.5, hueco de G-1, riesgo R-13).

> **Regla vinculante.** Ninguna ejecución que gaste dinero se lanza sin haber mostrado antes
> su coste estimado y haber recibido aprobación explícita. «Aprobado antes» no vale para la
> vez siguiente si el importe cambia.

## Qué exige aprobación

| Acción | Aprobación | Por qué |
|---|---|---|
| Corrida completa del golden dataset (42 consultas) | **Sí** | 0,37 USD, la partida mayor del desarrollo |
| Corrida `--smoke` (13 consultas) | Sí, agrupada por fase | 0,11 USD |
| Prueba de carga | **Sí, siempre y una sola vez** | 0,88 USD + 500 peticiones de cuota (25 %) |
| Siembra de DynamoDB con `--profile full` | **Sí** | 0,24 USD y 5–8 minutos |
| `terraform apply` de cualquier stack | **Sí** | Crea coste recurrente y recursos facturables |
| Reconstrucción del índice RAG | Informar | < 0,01 USD |
| Pruebas manuales sueltas (< 10 consultas) | Informar | Salen de la bolsa de 300 consultas de §9.4 |
| Ejecutar con `--profile dev` | No | 20 segundos, coste irrelevante |
| Pruebas unitarias con LLM mockeado | No | Coste cero |
| Familia `abuse_*` del golden dataset | No | Se rechaza antes de llamar al modelo: coste cero |

## Precios de referencia (PRD §9.1, §9.3)

| Concepto | Valor |
|---|---|
| Entrada `claude-sonnet-5` | 2,00 USD / MTok |
| Salida | 10,00 USD / MTok |
| Lectura de caché | ≈ 0,20 USD / MTok |
| Escritura de caché TTL 1 h | ≈ 4,00 USD / MTok |
| **Coste unitario por consulta (con caché 1 h)** | **0,00875 USD** |
| Consulta que necesita un turno extra por falta de datos | 0,0175 USD (**el doble**) |
| Siembra de 190 k items en DynamoDB | 0,24 USD, una sola vez |
| AWS recurrente | ≈ 0,40 USD/mes |

## Procedimiento

### 1. Estimar antes, no después

```
consultas × 0,00875 USD  +  coste AWS de una sola vez  =  coste de la ejecución
```

Si la ejecución tiene turnos multi-mensaje (familia `memory_*`), se cuentan **consultas al
modelo**, no casos. El PRD ya lo hace en §8.3b: 41 casos → 42 consultas.

### 2. Presentar el bloque de aprobación

```markdown
### Aprobación de coste — <actividad>

| Concepto | Valor |
|---|---|
| Consultas al LLM | 42 |
| Coste unitario | 0,00875 USD |
| **Coste de esta ejecución** | **0,37 USD** |
| Gasto acumulado tras ejecutar | 3,91 de 8,80 USD (44 %) |
| Cuota G-1 consumida tras ejecutar | 612 de 2.000 (31 %) |
| Alternativa más barata | `--smoke`: 13 consultas, 0,11 USD, cobertura de 1 caso por familia |

¿Autorizas la ejecución?
```

**La fila «alternativa más barata» es obligatoria.** Si no existe alternativa, se dice por qué.

### 3. Registrar el gasto real

Tras ejecutar, se anota en `memory/costes.md` el **coste real** leído de `usage.cost_usd`
(§4.2), no el estimado. Si el real supera al estimado en más de un 20 %, se investiga antes
de la siguiente ejecución: significa que el perfil de tokens de §9.3 ya no se cumple.

## Decisiones de arquitectura: coste antes que elegancia

Toda propuesta de arquitectura se presenta con su coste mensual y su alternativa descartada.
El PRD ya fijó las comparaciones que no hay que rehacer:

| Opción | Coste | Estado |
|---|---|---|
| LanceDB en `/tmp` | ≈ 0 | **Elegida** (§9.2) |
| OpenSearch Serverless | ~350 USD/mes | Descartada |
| Concurrencia aprovisionada | 20–25 USD/mes | Documentada, **desactivada**: por sí sola supera el techo (§2.2) |
| Lambda fuera de VPC | 0 | **Elegida**: una VPC añade NAT Gateway, ~32 USD/mes (S-06) |
| Glue Data Catalog | > que el resto de la infra junta | **Prohibida** (§0.3) |
| Streamlit en Fargate | 15–40 USD/mes con cero tráfico | Descartada (§10.6) |
| UI estática en S3 + CloudFront | ≈ 0, nivel gratuito | **Elegida** (D-04) |

Proponer cualquiera de las descartadas exige reabrir la decisión con el sponsor, no basta
con que sea técnicamente mejor.

## Los cuatro guardarraíles que deben estar vivos (PRD §9.5)

| # | Control | Verificar antes de la primera llamada real |
|---|---|---|
| G-1 | Cuota de 2.000 peticiones con **`period = MONTH`** | `terraform show` del Usage Plan |
| G-2 | **Límite de gasto del workspace en la consola de Anthropic** | Lo fija el operador a mano. Es el **único** control que cubre el gasto local |
| G-3 | AWS Budgets a 20 USD con alertas al 50/80/100 % | `aws budgets describe-budgets` |
| G-4 | `reserved_concurrent_executions = 20` + alarma `CostUSD` | `terraform show` de la Lambda |

G-1, G-2 y G-3 **deben estar activos antes de la primera llamada real al LLM**. Si G-2 no
está confirmado por el usuario, el agente **no ejecuta** ninguna corrida en lote: es el único
tope del 60 % del presupuesto.

## Criterio de terminado

El usuario ha aprobado el importe exacto, la ejecución se ha realizado y `memory/costes.md`
registra el coste real con su fila fechada.
