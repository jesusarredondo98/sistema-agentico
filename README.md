# AeroNova — Agente conversacional de mostrador

Asistente **ReAct** (LangGraph) para el personal de mostrador de una aerolínea.
Responde en español sobre estado de vuelos, reservas y normativa interna en
segundos, y **nunca contesta de memoria**: cada dato sale de una herramienta que
consulta un sistema real. Corre sobre AWS serverless con el gasto topado de
fábrica.

- El **qué** y el **porqué** están en [`documents/PRD.md`](documents/PRD.md) (normativo).
- El estado real de la implementación y el mapa de fases, en [`memory/PLAN.md`](memory/PLAN.md).
- Entregables ejecutivos: [`documents/aeronova_entregable.pdf`](documents/aeronova_entregable.pdf)
  y [`documents/aeronova_entregable_tarea2_publico.pdf`](documents/aeronova_entregable_tarea2_publico.pdf).

> **Estado:** F0–F10 completadas y endurecimiento de cierre. Servicio desplegado
> en `us-east-1`. Dataset dorado de **53 casos**, todos los umbrales OK.

---

## Qué hace

| Capacidad | Herramientas |
|---|---|
| Estado de vuelos al momento (demora, puerta, cancelación) por código `AN` | `consultar_estado_vuelo` |
| Datos de una reserva por PNR (pasajeros, tarifa, equipaje, reembolsable) | `obtener_datos_reserva` |
| Normativa interna con cita obligatoria del documento | `buscar_politicas_rag` |
| Operación por aeropuerto (código IATA) | `vuelos_por_ciudad`, `radar_operativo`, `resumen_demoras_ciudad`, `ranking_cabina`, `buscar_vuelos_ruta`, `cobertura_reservas`, `vuelos_a_continente`, `vuelos_nac_int` |
| Operación por vuelo (código `AN`) | `pasajeros_de_vuelo`, `mascotas_por_vuelo`, `ocupacion_vuelo`, `perfil_reservas_vuelo` |

Son **15 herramientas de solo lectura**, todas por índices secundarios de
DynamoDB, con 3 s de presupuesto por llamada. Varias devuelven además datos para
una gráfica de barras que la UI dibuja bajo demanda.

---

## Arquitectura

```
Navegador ──HTTPS──> CloudFront + OAC ──> S3 (UI estática)
    │
    └──POST /v1/chat, x-api-key──> API Gateway REST (Usage Plan: cuota mensual + throttle)
                                        │
                                        v
                          AWS Lambda (imagen de contenedor arm64, 2 GB)
                          Agente ReAct (LangGraph):
                          load_memory → llm_node ⇄ tool_node → finalize → persist_memory
                                        │
              ┌─────────────────────────┼─────────────────────────────┐
              v                         v                             v
     DynamoDB (flights,         LanceDB (índice RAG          Bedrock Titan V2 (embeddings)
     reservations, memory       versionado en /tmp,          Anthropic API (claude-sonnet-5,
     con TTL 24 h)              puntero CURRENT en S3)       sin sampling, thinking off, caché 1 h)
```

- **Grafo:** `MAX_TOOL_ROUNDS=3`, `RECURSION_LIMIT=10`, reloj de pared de turno
  para no chocar con el techo de 29 s de API Gateway / Lambda.
- **Memoria:** historial de sesión en DynamoDB con `expires_at` (TTL 24 h); solo
  se reenvían los últimos mensajes (L-4) para que el coste de entrada no crezca.
- **RAG:** Titan Text Embeddings V2 (1024, coseno), `top_k=4`, umbral 0.35,
  índice inmutable + `gold/rag/CURRENT` + prueba de humo + conmutación atómica y
  recarga en caliente durante el warm-up.
- **Defensas contra inyección (D-1…D-6):** escape de delimitadores, envoltura
  `<dato_operativo>` / `<documento_recuperado>` tratada como dato y no como
  instrucción, marcado de entrada y filtro de salida.
- **Coste topado:** caché de prompt (TTL 1 h, ~−25 %/consulta), tope de vueltas,
  cuota mensual del Usage Plan, cortacircuitos de gasto por sesión (0,75 USD) y
  AWS Budgets a 20 USD con alertas.

### Datos: cadena medallion

`generate_synthetic.py --seed 42` → **Bronze** (crudo) → contrato + expectativas
**E-01…E-10** → **Silver** (limpio y tipado) → **Gold** (DynamoDB + índice RAG).
Si una expectativa crítica aborta, el pipeline sale con código ≠ 0 y el sistema
se queda con los datos anteriores, nunca con datos rotos. Los casos borde
(reservas que rompen el contrato, corrupción post-carga, documentos con
inyección) se inyectan a propósito.

---

## Estructura del repositorio

```
src/          config, agente (grafo + nodos), tools, contratos Pydantic, lógica (memoria, RAG, defensas, geo)
pipelines/    medallion, un módulo por transición de capa
scripts/      generación de datos, orquestación del pipeline, build/push de imagen, deploy de UI, golden
tests/        unit · contracts · integration · golden (dataset de aceptación)
ui/           HTML/JS/CSS estático, sin framework ni build step
terraform/    00-bootstrap (ECR, DynamoDB, S3, SSM) · 10-app (Lambda, API GW, CloudFront, alarmas)
skills/       procedimientos del harness de desarrollo por fases
documents/    PRD (normativo), entregables PDF, estudio comparativo
memory/       PLAN.md (mapa de fases), acuerdos ACU-NNN, guías
```

---

## Desarrollo local

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # ajusta los parámetros SSM y la región
pytest -q                     # suite completa (unit + contracts + golden offline)
```

`make test` corre `pytest` con cobertura. El runner del golden (`python -m
tests.golden.runner --full`) va contra el **endpoint desplegado**; toma las
credenciales de `AERONOVA_API_URL` / `AERONOVA_API_KEY` o de
`terraform -chdir=terraform/10-app output`.

---

## Runbook de despliegue (PRD §13)

Terraform corre en **dos stacks separados**: una Lambda de imagen exige que la
imagen exista en ECR antes del `apply`, así que un stack único sería circular.
Exporta `AWS_PROFILE=aeronova` y trabaja en `us-east-1`.

| Paso | Comando | Qué hace |
|---|---|---|
| 0 · Prerrequisitos | `make preflight` | AWS CLI v2, Terraform ≥ 1.6, Docker `buildx`, acceso a Titan V2 en Bedrock |
| 1 · Bootstrap | `cd terraform/00-bootstrap && terraform init && terraform apply` | ECR, 3 tablas DynamoDB, 2 buckets S3, parámetro SSM |
| 2 · Secreto | `aws ssm put-parameter --name /aeronova/anthropic_api_key --type SecureString --value <clave>` | Manual y deliberado: la clave nunca pasa por un `.tfvars` |
| 3 · Datos | `make data` (dev) · `make data PROFILE=full` (entregable) | `run_pipeline.py`; se detiene en el primer fallo de expectativa |
| 4 · Imagen | `make build` | `docker build --platform linux/arm64` + push a ECR con etiqueta = **SHA corto de Git** (nunca `latest`) |
| 5 · Aplicación | `cd terraform/10-app && terraform init && terraform apply -var="image_tag=<sha>"` | Lambda, API Gateway, CloudFront, EventBridge, alarmas |
| 6 · Verificación | `pytest tests/golden/` · `python -m tests.golden.runner --full` | `outputs.tf` devuelve `api_url`, `api_key` (`sensitive`), `ui_url` |
| 6-bis · Corpus / rollback | `make data-corpus` · `python scripts/rollback_rag.py --to <version>` | Recarga incremental del corpus; vuelta atrás del índice sin redesplegar |
| 7 · Teardown | `terraform destroy` en `10-app` y luego `00-bootstrap` | Los buckets tienen `force_destroy=true`. Además: borrar el usuario IAM `aeronova-terraform` (ACU-004) y revisar las claves de root |

### Objetivos de `make`

| Objetivo | Qué hace |
|---|---|
| `make preflight` | Verifica los cuatro prerrequisitos del paso 0 |
| `make data` | Pipeline medallion completo (`PROFILE=dev` por defecto) |
| `make data-corpus` | Recarga incremental solo del corpus normativo |
| `make test` | `pytest` con cobertura |
| `make build` | `docker build --platform linux/arm64` + push a ECR con etiqueta = SHA |
| `make deploy` | `terraform apply` de `00-bootstrap` y luego `10-app` |

---

## Notas

- **Sin secretos en Git.** Estado de Terraform, `.env`, `.tfvars` y `*.pem`
  están en `.gitignore`. La clave de Anthropic vive solo en SSM SecureString.
- **Modelo:** `claude-sonnet-5` exacto, sin sufijo. Sin `temperature` / `top_p` /
  `top_k`; `thinking` desactivado; `cache_control` con TTL 1 h sobre el system
  prompt.
- **Reproducible:** el servicio se levanta de cero con dos `terraform apply`, el
  pipeline corre de punta a punta con todas las expectativas en `pass` y
  `terraform destroy` deja la cuenta limpia.
