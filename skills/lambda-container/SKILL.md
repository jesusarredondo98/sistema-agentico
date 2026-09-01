---
name: lambda-container
description: Empaqueta la Lambda como imagen de contenedor arm64 y la publica en ECR con etiqueta de SHA de Git. Úsala en F0 para el andamiaje y en F7 para el despliegue.
---

# Empaquetado de la Lambda

## Contrato de construcción (§2.6)

```dockerfile
FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.12
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY handler.py ${LAMBDA_TASK_ROOT}/
CMD [ "handler.lambda_handler" ]
```

## Las cinco reglas

| Regla | Qué pasa si se omite |
|---|---|
| Compilar con `docker build --platform linux/arm64` | En una máquina x86 produce **`exec format error` en tiempo de ejecución, no en el build** — se descubre en producción |
| `.dockerignore` que excluya `terraform/ tests/ .git/ data/ *.md __pycache__/` | Imagen inflada y datos sintéticos dentro del contenedor |
| `requirements.txt` con versiones fijadas con `==`, **no rangos** | Builds no reproducibles; el agente resuelve las versiones **una vez** y las congela |
| Imagen **< 2 GB** | Rechazo de Lambda. Si `pyarrow` la desborda: **eliminar `pandas`** y usar `pyarrow` directamente |
| Etiqueta = **SHA corto de Git**, nunca `latest` | Con `latest`, **Terraform no detecta el cambio** y la Lambda conserva la imagen anterior |

## Dependencias mínimas

`langgraph`, `langchain-core`, `langchain-anthropic`, `anthropic`, `lancedb`, `pyarrow`,
`boto3`, `pydantic>=2`, `aws-lambda-powertools`.

> **Riesgo R-03.** Si alguna rueda no publica `manylinux_aarch64`, se revierte a `x86_64` y
> **se documenta como acuerdo `desviacion`** (S-02). Se detecta en F0, no en F7.

## Variables de entorno (§2.7)

Las 15 variables las inyecta Terraform. **`ANTHROPIC_API_KEY_PARAM` contiene el nombre del
parámetro SSM, no la clave.**

> **La clave de Anthropic NUNCA se declara como variable de entorno en texto plano.** La
> Lambda lee el parámetro SSM **en el ámbito de módulo** —una vez por contenedor, no por
> invocación— y lo cachea en memoria.

Valores que no se cambian sin decisión: `ANTHROPIC_MODEL=claude-sonnet-5`,
`MAX_TOOL_ROUNDS=3`, `MAX_OUTPUT_TOKENS=1024`, **`HISTORY_WINDOW_MESSAGES=8`** (bajado de 12
por coste; §9.2 arrastra el valor antiguo, manda §2.7), `MEMORY_TTL_HOURS=24`, `RAG_TOP_K=4`,
`RAG_CURRENT_POINTER=gold/rag/CURRENT`, `RAG_CONTRACT_VERSION_MIN=1.0.0`.

## Publicación (`scripts/build_and_push.sh`)

Login en ECR → `docker build --platform linux/arm64` → etiquetar con el SHA corto → push →
**imprimir la etiqueta resultante**, que es lo que consume `terraform plan -var="image_tag=…"`.

## Criterio de terminado

`docker build --platform linux/arm64 .` termina con exit 0, la imagen mide menos de 2 GB, y la
etiqueta publicada coincide con el SHA corto del commit desplegado.
