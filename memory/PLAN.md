# Plan de acción — Estado vivo

> **Este fichero es la única fuente de verdad sobre qué se ha hecho y qué falta.**
> Se lee **al empezar cada turno, antes que ninguna otra cosa**, y se actualiza **después de
> cada actividad terminada**. Un agente que no lo lee alucina progreso; un agente que no lo
> escribe lo pierde. Ver `skills/plan-tracker/SKILL.md`.

| Campo | Valor |
|---|---|
| Última actualización | 2026-08-30 |
| Fase actual | **F9 — Aceptación** (golden 45/45 + carga OK) → siguiente **F10** (falta `harness-reentry` de F9) |
| Actividades terminadas | 100 de 118 |
| Gasto real acumulado | ~0,22 USD LLM · ~32 consultas · AWS ~0,07 USD (ver `costes.md`) |
| Rama de trabajo | **`feat/aeronova-implementacion`** (ACU-002) |
| Acuerdos bloqueantes | ninguno (ver `INDEX.md`) — ACU-003 `hallazgo`, ACU-004 `decision`, ACU-005 `desviacion` (concurrencia, RESUELTO), ACU-006 `desviacion` (extras), ACU-007 `desviacion` (full recortado), no bloquean |
| Aprobación de coste vigente | ninguna — F7 `apply` de `10-app` ejecutado; coste recurrente ~0,40 USD/mes |
| Infra AWS | `00-bootstrap` + `10-app` vivos. App: Lambda `aeronova-agent` (imagen **`d4ffb13`**, **12 tools**, `SESSION_COST_LIMIT_USD=0,75`, `reserved_concurrent_executions=20` — ACU-005 resuelto). Datos: perfil `full` recortado (ACU-007) — 9.000 vuelos + 14.552 reservas + 150 corpus + 12 ruta B (`RB0000…` + 12 `100000…` stale por limpiar, no bloquea); índice RAG `v=20260831T031138Z` (E-06 cableada, 319 chunks), API GW `lbsnyvy2ba` stage `prod`, Usage Plan `aeronova-agent-plan` (**10000/MES** — ACU-008), CloudFront `E3AXH3KXGLAZQI` (UI publicada en https://d1v908g2u3hf9q.cloudfront.net — guía en `memory/guia_uso_ui.md`), Budgets 20 USD + 10 alarmas → SNS `aeronova-agent-alarms`. SSM `/aeronova/anthropic_api_key` v2, `/aeronova/langsmith_api_key` v1. Perfil AWS: `aeronova` (usuario IAM `aeronova-terraform`, AdministratorAccess) |

**Leyenda:** `[x]` hecho y verificado con evidencia · `[~]` en curso · `[ ]` pendiente ·
`[!]` bloqueado (exige acuerdo en `acuerdos/`) · `[-]` fuera de alcance (PRD §0.3)

---

## Estado tras la sesión del 2026-08-30 (extras ACU-006 desplegados)

Todo lo de ACU-006 está **desplegado y verificado en vivo**. El sistema (imagen Lambda
`da7a34b`, índice RAG `v=20260830T194954Z`, UI actual) está consistente.

- GSIs de DynamoDB `ACTIVE`; Lambda con IAM `dynamodb:Query` sobre `.../index/*`.
- 4 tools nuevas en vivo: `vuelos_por_ciudad`, `radar_operativo` (con gráfica de conteos),
  `pasajeros_de_vuelo`, `mascotas_por_vuelo` — verificadas contra el endpoint.
- `SESSION_COST_LIMIT_USD=0,75` en la Lambda; la UI lo lee de `session.cost_usd_limit`.
- Chunking por grupos de artículos (~500 car.); humo F4 5/5 (EQUIPAJE 0,698, MENORES 0,867).
  Consulta de documentación de menores ya cita DNI/pasaporte + autorización.
- Ping de calentamiento **re-activado** (`state = "ENABLED"` explícito en el `.tf`).

**Pendiente real:** `harness-reentry` de ACU-006 (abajo), **F9** (golden dataset + carga;
el §8.2 asume 3 tools — decidir familias `operacion_*` o `forbid_tools`) y **F10** (PDF).
ACU-005: restaurar `reserved_concurrency` a 20 cuando Service Quotas apruebe el aumento.
---

## Traspaso — lee esto si eres el agente que va a implementar

El arnés, las skills y la memoria están terminados. **Tú implementas; no rediseñas el arnés.**

**Tus primeros cinco minutos, en este orden:**

1. Este fichero, entero. Es el estado real: lo que no está `[x]` no está hecho.
2. `memory/INDEX.md` — dos acuerdos vigentes, ninguno bloqueante.
3. `documents/Agents.md` **§0, §2 y §4**. Unas 150 líneas. Con eso puedes empezar sin abrir el PRD.
4. `memory/costes.md` — presupuesto consumido: 0,00 de 8,80 USD.

**Lo que NO debes hacer al llegar:**

- **No leas el PRD entero.** Son 1.578 líneas y arruina el presupuesto de tokens. Cada
  actividad de este plan cita las secciones que la gobiernan: lee solo esas.
- **No empieces a programar sin el intake socrático.** F0 se abre con `socratic-intake`, y
  no arranca con un solo **NO SÉ** en pie.
- **No rehagas decisiones cerradas.** Están en `acuerdos/`. Si el índice no las menciona, no
  las reabras.
- **No gastes sin aprobación.** Ver `skills/cost-gate`. F0 no consume LLM, así que puedes
  arrancar sin pedir nada.

**Tu primera acción concreta:** invocar `socratic-intake` para abrir **F0**, responder las
seis preguntas citando §3 y §2.6 del PRD, y presentárselas al usuario antes de crear ningún
fichero.

**Dos cosas que el usuario debe resolver fuera del código, y conviene recordárselas pronto:**

| # | Qué | Cuándo bloquea | PRD |
|---|---|---|---|
| 1 | Habilitar el acceso a **Titan Embeddings V2** en la consola de Bedrock | En F4. No es automatizable por Terraform | §2.5, R-04 (prob. **alta**) |
| 2 | Fijar el **límite de gasto del workspace en la consola de Anthropic** (G-2) | Antes de la primera corrida en lote | §9.5, R-13 |

---

## Mapa de fases

| Fase | Entrega | Estado | Consultas | USD LLM | Commit | Skills |
|---|---|---|---:|---:|---|---|
| F-1 | Arnés, skills y memoria | **[x] hecha** | 0 | 0,00 | `582637c` | — |
| F0 | Andamiaje del repositorio | **[x] hecha** | 0 | 0,00 | `c10bb27` | `lambda-container` |
| F1 | Nodo LLM aislado | **[x] hecha** | 3 | ~0,00 | `428f371` | `llm-sonnet5-config` |
| F2 | Bootstrap Terraform + data contracts | **[x] hecha** | 0 | 0,00 | `3883518` | `terraform-stacks`, `data-contracts` |
| F2b | Pipeline medallion completo | **[x] hecha (dev)** | 0 | 0,00 (+~0,03 AWS dev) | `44387e5` | `synthetic-data`, `medallion-pipeline` |
| F3 | Herramientas `flights` y `pnr` | **[x] hecha** | 0 | 0,00 | `5dcbc98` | `agent-tools` |
| F4 | Índice RAG promovido | **[x] hecha** | 0 | 0,00 (+~0,01 AWS) | `df99822` | `rag-index` |
| F5 | Grafo LangGraph con memoria | **[x] hecha** | ~10 | ~0,09 | `a1e8664` | `langgraph-agent` |
| F6 | Handler, caché y observabilidad | **[x] hecha** | ~18 | ~0,13 | `c44e9fb` | `injection-defense`, `observability-aws` |
| F7 | Despliegue de la aplicación | **[x] hecha** | ~55 | ~0,05 | `1b0e43d` | `terraform-stacks`, `lambda-container` |
| F8 | Interfaz desplegada | **[x] hecha** | ~14 | ~0,07 | `f2512d3` | `web-ui` |
| F9 | Golden dataset y prueba de carga | **[x] hecha** | ~110 | ~0,49 | `a3ba688` | `golden-dataset`, `load-test-dryrun` |
| F10 | Documentación técnica en PDF (+ ampliación: 5 tools, UI, prompt) | **[x] hecha** | ~260 | ~1,34 | `b6b0132` | `pdf-report` |
| — | Demo y validación con el sponsor | [ ] pendiente | 200 | 1,75 | — | — |
| — | Reserva no asignada | — | 80 | 0,70 | — | — |
| | **TOTAL** | **100/118** | **1.005** | **8,80** | | |

**Regla de parada (PRD §14).** Si una fase no alcanza su criterio de salida, el agente
**se detiene y reporta**. No avanza a la siguiente ni «deja pendiente un detalle».

**Cierre de fase.** Toda fase aprobada termina con un commit (`skills/git-checkpoint`), y su
SHA corto se anota en la columna **Commit**. Una fila sin SHA es una fase que no se ha
cerrado, por muy `[x]` que estén sus actividades.

---

## F-1 · Arnés y gobernanza — HECHA

- [x] **A-01** Leer el PRD v2.7 completo y las skills existentes · evidencia: 1.578 líneas leídas
- [x] **A-02** Crear `memory/` con protocolo, índice y libro de costes · evidencia: `memory/README.md`
- [x] **A-03** Crear `memory/PLAN.md` como estado vivo · evidencia: este fichero
- [x] **A-04** Generar las 22 skills atómicas nuevas en `skills/` · evidencia: `ls skills/` → 23 con `pdf-report`
- [x] **A-05** Escribir `documents/Agents.md` · evidencia: fichero presente
- [x] **A-06** Revisión del arnés con ojos de agente nuevo · evidencia: `Agents.md` §11
- [x] **A-07** `.gitignore` fundado en §16 y S-03; `.DS_Store` desrastreado · evidencia: `git status --short`

## F0 · Andamiaje — criterio de salida: `docker build --platform linux/arm64` termina bien · **HECHA**

- [x] **A-10** Crear el árbol de directorios exacto de PRD §3, sin inventar carpetas · §3 · evidencia: `find` → 15 dirs y stubs de §3; `__init__.py` solo donde el import lo exige
- [x] **A-11** `src/config.py` con `pydantic-settings` y lectura de SSM en ámbito de módulo · §2.7 · evidencia: `Settings` con las 15 vars de §2.7; `get_anthropic_api_key()` con `lru_cache` (una lectura SSM por contenedor); import validado en la imagen → `claude-sonnet-5 | tool_rounds 3 | hist 8`
- [x] **A-12** `requirements.txt` con versiones fijadas con `==`, resueltas una vez · §2.6 · evidencia: 10 paquetes `==`, resueltos dentro de `public.ecr.aws/lambda/python:3.12` arm64; `requirements-dev.txt` para pruebas
- [x] **A-13** `Dockerfile` con `FROM --platform=linux/arm64` y base `public.ecr.aws/lambda/python:3.12` · §2.6 · evidencia: bloque literal de §2.6; `docker build --platform linux/arm64` → exit 0 en 58 s
- [x] **A-14** `.dockerignore` que excluya `terraform/ tests/ .git/ data/ *.md __pycache__/` · §2.6 · evidencia: las 6 entradas obligatorias + complementos coherentes
- [x] **A-15** `Makefile` con `data`, `data-corpus`, `test`, `build`, `deploy` · §13 · evidencia: `make help` lista los 5 + `preflight`
- [x] **A-16** `scripts/preflight.sh` que verifique AWS CLI, Terraform ≥1.6, Docker buildx y acceso a Titan · §13 paso 0, R-04 · evidencia: 4 comprobaciones con `[FALLO]`/`[OK]` y `exit 1`; `bash -n` OK
- [x] **A-17** Verificar imagen < 2 GB y ausencia de ruedas sin `manylinux_aarch64` · §2.6, S-02, R-03 · evidencia: imagen **938 MB** (`docker image inspect`), `os=linux arch=arm64`; 15 ruedas nativas, todas `manylinux_*_aarch64`, ninguna sin tag → sin desviación R-03

## F1 · Nodo LLM aislado — criterio: una petición real responde sin 400 · **HECHA**

- [x] **A-20** Nodo LLM contra `claude-sonnet-5` **sin sufijo de fecha** · §5.3 · evidencia: `src/agent/llm_node.py` + `src/agent/state.py`; petición real → `stop_reason: end_turn`, texto "París", `body["model"] == "claude-sonnet-5"`
- [x] **A-21** **Capturar la petición HTTP saliente** y confirmar que no lleva `temperature`, `top_p`, `top_k` ni `budget_tokens` · §5.3, R-01 · evidencia: `tests/integration/test_llm_node.py` PASSED; claves de nivel superior capturadas = `['max_tokens','messages','model','system','thinking']`, ninguna de sampling
- [x] **A-22** Si `langchain-anthropic` los inyecta y no se pueden suprimir: sustituir por el SDK `anthropic` dentro del nodo, conservando el grafo · §5.3 plan B · evidencia: **no aplica** — plan A confirmado (ACU-003); `langchain-anthropic` 1.7.0 elimina las claves `None` antes de enviar
- [x] **A-23** Registrar el resultado como acuerdo `hallazgo` en `memory/acuerdos/` · R-01 · evidencia: `memory/acuerdos/ACU-003-langchain-anthropic-sin-sampling.md`, indexado en `INDEX.md`

## F2 · Bootstrap y contratos — criterio: un lote con referencia colgante aborta por E-02 · **HECHA**

- [x] **A-30** `terraform/00-bootstrap`: ECR, 3 tablas DynamoDB, 2 buckets S3, parámetro SSM · §13 paso 1 · evidencia: `Apply complete! Resources: 16 added`; verificado por API: 3 DynamoDB con sus PK/SK y `PAY_PER_REQUEST`, `memory` TTL `expires_at` ENABLED, ECR `aeronova-agent` IMMUTABLE, lake AES256 + versioning + 3 reglas lifecycle, SSM `SecureString` v1 · aplicado con usuario IAM `aeronova-terraform` (perfil `aeronova`)
- [x] **A-31** Etiquetado obligatorio en todo recurso: `Project`, `Environment`, `ManagedBy`, `Owner` · §13 · evidencia: `provider "aws" { default_tags }` en `main.tf`; el `plan` muestra las 4 etiquetas en `tags_all`
- [x] **A-32** Ciclo de vida de S3: Glacier IR a 30 días en `bronze/` y `quarantine/`; 3 versiones en `gold/rag/` · §2.4 · evidencia: `aws_s3_bucket_lifecycle_configuration.lake` con 3 reglas (nota: el podado de carpetas `v=<ts>/` lo hace `rollback_rag.py` en F4)
- [x] **A-33** Cargar el secreto con `aws ssm put-parameter --type SecureString`, **nunca por `.tfvars`** · §13 paso 2 · evidencia: parámetro `/aeronova/anthropic_api_key` en **versión 2**, valor real (empieza por `sk-ant-`, verificado con `grep -q` sin imprimirlo); TF lo creó con placeholder + `ignore_changes=[value]`
- [x] **A-34** `src/contracts/base.py` con los 4 metadatos `ClassVar` obligatorios · §6A.3 · evidencia: `DataContract` con `extra="forbid"`, `__init_subclass__` valida los 4 `ClassVar` + SemVer; `test_base.py` verde
- [x] **A-35** `DocumentoNormativoContract` v1.0.0 con sus 5 validaciones cruzadas · §6A.3 · evidencia: `src/contracts/corpus.py`; 5 `@model_validator` (prefijo↔categoría, vigencias, referencias==cuerpo, checksum); `test_corpus.py` 30+ casos verde
- [x] **A-36** `VueloContract` y `ReservaContract` **separados** de los modelos de §5.4 · §6A.3 · evidencia: `flights.py` y `reservations.py` heredan de `DataContract`, no reutilizan `EstadoVueloData`/`DatosReservaData`
- [x] **A-37** `expectations.py` con E-01 a E-09 y su acción al fallar · §6A.4 · evidencia: 9 `check_eNN` puras + `evaluate()` que lanza `BatchAborted`; `test_expectations.py` verde (E-06/E-07 diferidas a F4 sin vectores)
- [x] **A-38** `tests/contracts/` con casos válidos, inválidos y de frontera; cobertura ≥ 95 % · §8.1 · evidencia: `pytest tests/contracts/` → **116 passed, 4 skipped (F4)**, **cobertura 100 %** en `src/contracts/`
- [x] **A-39** `scripts/export_contracts.py` → `docs/contracts/` (derivado, no editable a mano) · S-09 · evidencia: 3 `*.schema.json` + `CONTRACTS.md` generados; `docs/contracts/README.md` (stub F0) eliminado

## F2b · Pipeline medallion — criterio: `get_item` recupera vuelo y PNR; cuarentena ≈ 3 % · **HECHA**

- [x] **A-40** `generate_synthetic.py --seed 42`: 90 k vuelos, 100 k PNR, 150 documentos · §6.1, §7 · evidencia: `--profile dev` → 4.500/5.000/150; sin LLM (plantillas + Faker `es_ES` semilla fija); `_source_summary.json`. `full` = 90k/100k/150
- [x] **A-41** ≥ 20 documentos con excepción cruzada declarada en `referencias` · §6.1 · evidencia: **22** docs con `referencias`, todas a un `doc_id` real de otra categoría; E-02 → 100 % integridad
- [x] **A-42** Anomalías ruta A (3 %): generadas en la fuente, **deben** quedar en cuarentena · §7.1 · evidencia: 150 anomalías (37/37/37/39); `promote_silver` → tasa de cuarentena de reservas **3,00 %**, `quarantine/reservations/…/rejects.jsonl` con 150 registros
- [x] **A-43** `ingest_bronze.py`: copia cruda inmutable a `bronze/ingest_date=<hoy>/` · §6A.1 · evidencia: 152 objetos en `s3://aeronova-lake-a0b47d4d/bronze/{corpus,flights,reservations}/ingest_date=2026-08-27/`
- [x] **A-44** `promote_silver.py`: puerta de contrato + expectativas + cuarentena con motivo estructurado · §6A.3, §6A.4 · evidencia: `_gate` acepta/cuarentena por contrato + E-05 referencial; 9 expectativas en `pass`; rechazos con las 7 claves de §6A.4; `test_promote_silver_gate.py` verde
- [x] **A-45** Fragmentación por artículo, máx. 800 car., solape 100, sin partir frases · §6.2 · evidencia: `pipelines/_chunking.py`; 150 docs → 636 chunks, `max len 439`, corte en fin de frase; `test_chunking.py` 8 casos verde
- [x] **A-46** `build_gold_dynamo.py`: `BatchWriteItem` de 25, 16 hilos, reintento de `UnprocessedItems`, idempotente · §7.2 · evidencia: `batch_writer` (25/lote + reintento automático) × 16 hilos; `--reset`; re-ejecución → E-08 deriva 0,00 %; `get_item` recupera vuelo `AN1001` y PNR `Y59W72`
- [x] **A-47** Anomalías ruta B (2 %) con `--inject-gold-corruption`, **desactivada por defecto y con aviso** · §7.1 · evidencia: `--inject-gold-corruption N` (default 0), aviso a `stderr` con banda `!!!`; PNR `RTB#####` deterministas (no colisionan con la fuente); probado con N=30. La inyección real (2000) es de F3
- [x] **A-48** `manifest.py`: linaje, recuentos por capa, perfil `dev`/`full` registrado · §6A.7, §7.2 · evidencia: `silver/_manifest.json` con los campos de §6A.7 (`counts`, `quarantine_rate` reservas 0,03 / batch 0,0155, `expectations` todas `pass`, `profile`, `git_sha`, `source_bronze_partition`)
- [x] **A-49** Ejecutar con `--profile dev` para iterar; `full` solo para el entregable · §7.2, R-19 · evidencia: cierre de F2b con `--profile dev` (~20 s); `full` (0,24 USD) reservado para F9/entrega, exige aprobación

## F3 · Herramientas de datos — criterio: unit tests pasan, incluidos registros corruptos · **HECHA**

- [x] **A-50** `ToolResult` / `ToolError` como sobre uniforme; **ninguna tool lanza excepción al LLM** · §5.4 · evidencia: `src/tools/schemas.py` (`code` restringido a 4); cada tool envuelve todo en try/except → `UPSTREAM_ERROR`; `test_error_de_dynamo_no_propaga` en ambas tools
- [x] **A-51** `consultar_estado_vuelo` con `pattern=^AN\d{3,4}$` y validación de salida · §5.4.1 · evidencia: `src/tools/flights.py`; input inválido → `INVALID_INPUT`, salida validada con `EstadoVueloData` → registro corrupto = `UPSTREAM_ERROR`; `test_tools_flights.py` 8 casos
- [x] **A-52** `obtener_datos_reserva` con normalización de PNR a mayúsculas sin espacios · §5.4.2, §5.4.4 · evidencia: `normalizar_pnr("ab c 12")=="ABC12"`; `test_normalizacion_pnr` con 4 variantes → todas leen `"ABC123"`
- [x] **A-53** Timeout duro de 3 s por herramienta → `code="TIMEOUT"` · §5.4.4 · evidencia: `run_with_timeout` (`ThreadPoolExecutor.result(timeout=3)`); `test_run_with_timeout_vence`; ambas tools mapean `ToolTimeout` → `TIMEOUT`
- [x] **A-54** Presupuesto ≤ 450 tokens por resultado: omitir `null`, máx. 9 pasajeros · §5.4.4, L-6 · evidencia: `trim_reservation` capa a 9 + `total_pasajeros` + `pasajeros_truncados`; `drop_nulls` recursivo; `test_resultado_dentro_del_presupuesto` y red de seguridad. Estimación por caracteres; el tokenizador real es F6
- [x] **A-55** **No eliminar la validación Pydantic** por creer que el contrato la sustituye · §6A.8, R-09 · evidencia: `EstadoVueloData`/`DatosReservaData` son clases distintas de los contratos; ruta B real (2.000 inyectados) → muestra de 4 PNR (`100000`,`1000JG`,`10012W`,`1001JJ`) → todos `ok=False code=UPSTREAM_ERROR` sin traza; `test_tools_gold.py` (integración real) + 3 casos ruta B unitarios
- [x] **A-56** Cobertura ≥ 80 % en `src/tools/` y `src/logic/` · §8.1 · evidencia: `pytest tests/unit tests/contracts` → **182 passed, 4 skipped**, **cobertura 100 %** en `src/tools/` y `src/logic/` (`dynamo.py` con `moto`); `ruff` limpio

## F4 · Índice RAG — criterio: consulta por encima del umbral y rollback verificado · **HECHA**

- [x] **A-60** Embeddings Titan V2, `dimensions: 1024`, `normalize: true`, reintento exponencial · §6.2 · evidencia: `src/logic/embeddings.py` (`invoke_model`, `dimensions:1024`, `normalize:true`, backoff exp ante `ThrottlingException`); `test_embeddings.py` 7 casos; llamada real → embedding de 1024 dims
- [x] **A-61** Reembebido incremental por `checksum_cuerpo`; índice reconstruido **entero** · §6A.6 · evidencia: `_checksums.json` por versión; 2.º build con corpus sin cambios → **0 embebidos, 775 reutilizados** (~15 s vs 2,5 min); el índice se reconstruye entero siempre
- [x] **A-62** Índice en `gold/rag/politicas.lance/v=<ts>/`, **nunca sobrescribiendo** · §6A.5 · evidencia: versión `v=<UTC compacto>`; `prune_old_versions(keep=3, protect=CURRENT)` — verificado: 5 versiones → poda 2, quedan 3
- [x] **A-63** `_manifest.json` con los 12 campos de §6A.7 · §6A.7 · evidencia: `version`, `built_at`, `contract_name/version`, `source_bronze_partition`, `embedding_model/dimensions`, `counts`, `expectations` (E-07), `smoke_test`, `git_sha`, `index_version`
- [x] **A-64** Prueba de humo de 5 consultas **antes** de promover; si falla, no se promueve · §6A.5 · evidencia: 1.er build con corpus genérico → EQUIPAJE 0,345 < 0,35 → **NO promovido, exit 2, `CURRENT` intacto**; corpus enriquecido → 5/5 (0,412–0,835) → promovido
- [x] **A-65** Conmutación atómica de `CURRENT` como último paso · §6A.5 · evidencia: `PutObject gold/rag/CURRENT` tras el humo, después del `upload_version`; es la última escritura antes de la poda
- [x] **A-66** `rollback_rag.py --to v=<ts>` verificado de ida y de vuelta · §6A.5 · evidencia: `--list` (3 versiones); `--to v2` → `CURRENT` a v2; `--to v3` → `CURRENT` a v3 (ida y vuelta, leído de S3); versión inexistente → rc=1; `test_rag_live.py::test_rollback_ida_y_vuelta`
- [x] **A-67** Recuperación: `top_k=4`, umbral 0,35, `NOT_FOUND` si nada supera el umbral · §6.3 · evidencia: `src/tools/rag.py`; consulta real "límite de peso equipaje" → 4 frags top `POL-EQU-007` score 0,815; "plato volador antigravedad" → `NOT_FOUND`; carga del índice **fuera** del timeout de 3 s (arranque en frío ≠ consulta lenta); `test_tools_rag.py` 11 casos
- [x] **A-68** Refresco de `CURRENT` en el ping de calentamiento · §6.3, R-10 · evidencia: `rag_index.refresh_if_changed()` — relee `CURRENT`, recarga si difiere; `test_rag_index.py` + `test_rag_index_s3.py` (moto) verifican cambio/no-cambio/no-disponible. **El cableado en `handler._warmup` faltaba (la nota "lo cablea F6" nunca se cumplió); se conecta en F7** — `warmed["rag_index_swapped"]` en cada tick de EventBridge; `test_handler.py::test_warmup_*`
- [x] **A-132** Corpus normativo: valor **canónico por regla**, sin relleno aleatorio · §6.1, §6.3, R-25 · evidencia: `generate_synthetic.py` `_FRASES_CATEGORIA` pasa a `(plantilla, valor_n)` con un `{n}` fijo por norma (mascota cabina = 50 €, equipaje de mano = 10 kg, …) + artículo de cierre determinista; se elimina `fake.sentence()` que metía palabras sin sentido. Antes cada documento sorteaba un número por hueco y el RAG recuperaba fragmentos contradictorios (168/120/12 € para la misma tarifa). `flights.jsonl`/`reservations.jsonl` byte-idénticos (corpus se genera el último). Índice `v=20260829T021718Z` reconstruido (935 chunks, `embedded:935`, humo 5/5 pass), `CURRENT` conmutado en S3. Suite completa (297) en verde. Verificado en vivo tras desplegar `1b0e43d`: mascota→8 kg (POL-MAS-003), equipaje→10 kg 55x40x20 (POL-EQU-003), compensación→250-600 EUR (POL-COM-005), todas firmes y consistentes. `warmup` mostró `rag_index_swapped:true` (hot-swap sin redespliegue, R-10)

## F5 · Grafo LangGraph — criterio: memoria multi-turno funciona en local · **HECHA**

- [x] **A-70** `AgentState` exacto de §4.4, con `pnr_activo` y `tool_rounds` · §4.4 · evidencia: `src/agent/state.py` con los 6 campos de §4.4 + `history` transitorio (cargado de DynamoDB, no persistido; evita el desorden del reducer `add_messages`)
- [x] **A-71** Nodos `load_memory → llm_node ⇄ tool_node → persist_memory` · §5.1 · evidencia: `src/agent/graph.py` `build_graph()`; 5 nodos; `chat_cli.py` ejecuta el flujo real contra LLM + DynamoDB
- [x] **A-72** `tool_node` ejecuta **en paralelo** los `tool_call` de un mismo mensaje y devuelve **todos** los `ToolMessage` · §5.1 · evidencia: `ThreadPoolExecutor` sobre `TOOL_REGISTRY`; `test_tool_node.py::test_devuelve_un_toolmessage_por_call_en_orden`; captura de `pnr_activo` de `obtener_datos_reserva`
- [x] **A-73** `MAX_TOOL_ROUNDS=3` en la arista condicional; `recursion_limit=10` como red de seguridad · §5.2 · evidencia: `_route_after_llm` comprueba `state["tool_rounds"] < MAX_TOOL_ROUNDS`; `RECURSION_LIMIT = 2*3+4 = 10`; `finalize → END` (camino máx. 9 super-pasos; con `finalize → persist_memory` serían 10 y LangGraph exigiría `recursion_limit≥11`, rompiendo I-03) — documentado en `finalize_node`
- [x] **A-74** Al agotar rondas: `finalize` con `finish_reason="max_rounds"`, **sin excepción** · §5.2 · evidencia: `test_graph.py::test_agota_rondas_va_a_finalize_sin_excepcion` (LLM que siempre pide tool → tras 3 rondas → `finalize`, sin `GraphRecursionError`)
- [x] **A-75** `GraphRecursionError` capturado y traducido a HTTP 200 · §5.2 · evidencia: `run_turn` captura `GraphRecursionError` → devuelve estado `max_rounds` con éxito; `test_graph.py::test_run_turn_captura_graph_recursion_error`. El handler HTTP que lo llama es F6
- [x] **A-76** Memoria DynamoDB: `sk` `MSG#` + 8 dígitos con ceros; `expires_at` en **segundos** · §4.5 · evidencia: escenario real → `MSG#00000001..MSG#00000006`; `expires_at` epoch en segundos (verificado en la tabla); `test_memory.py`
- [x] **A-77** Carga con `Query`, `ScanIndexForward=False`, `Limit=8`, luego invertir. **Nunca `Scan`** · §4.5 · evidencia: `load_session` usa `Query` + `begins_with("MSG#")` + `ScanIndexForward=False` + `Limit=history_window_messages` + `reversed(...)`; `test_memory.py::test_load_respeta_history_window`
- [x] **A-78** Comprobación de propiedad de sesión → 403 `SESSION_FORBIDDEN` · §4.5 · evidencia: escenario real → mismo `session_id` + empleado distinto → `[403 SESSION_FORBIDDEN]`; el legítimo sigue funcionando; `test_memory.py::test_propiedad_de_sesion_ajena_lanza_forbidden`
- [x] **A-79** Un fallo de escritura de memoria se registra pero **no** convierte un 200 en 500 · §4.5 · evidencia: `persist_turn` envuelve todo en try/except → `_log.exception` + `return False`; `test_memory.py::test_fallo_de_escritura_no_propaga`; `persist_memory_node` ignora el resultado

## F6 · Handler, caché y observabilidad — criterio: `cache_read_input_tokens > 0` · **HECHA**

- [x] **A-80** Validación de §4.1 con `extra="forbid"` antes de tocar el grafo · §4.1 · evidencia: `ChatRequest` (`src/agent/schemas_api.py`, patrones de `session_id`/`employee_id`, `message` 1–1200, no-blanco, `extra="forbid"`); `test_handler.py` 5 casos → 400 `INVALID_REQUEST`
- [x] **A-81** Contrato de respuesta completo con los bloques `session` y `context` · §4.2 · evidencia: `build_response`; verificación e2e → `session={turn,turn_limit,cost_usd_accumulated,cost_usd_limit}`, `context={truncated,messages_dropped}`, `usage.cache_read_input_tokens`, `request_id`, `latency_ms`
- [x] **A-82** Catálogo de errores de §4.3 íntegro, con `request_id` en todos · §4.3 · evidencia: `ERROR_STATUS` con los 8 códigos de app; probados: `INVALID_REQUEST`, `INPUT_TOO_LARGE`, `SESSION_FORBIDDEN`, `SESSION_TURN_LIMIT`, `SESSION_BUDGET_EXCEEDED`, `INTERNAL_ERROR`
- [x] **A-83** `cache_control` con `ttl: "1h"` sobre el último bloque del system prompt · §5.3 · evidencia: `_system_message()` en `llm_node.py`; la API acepta `ttl:"1h"` (sin 400)
- [x] **A-84** Verificar que el prefijo cacheable supera **1.024 tokens** · §5.3, R-14 · evidencia: `count_tokens(system+tools)` → **1708 tokens** > 1024; `test_cache.py::test_prefijo_cacheable_supera_1024_tokens`
- [x] **A-85** Sin marcas de tiempo, `request_id` ni `employee_id` dentro del system prompt · §5.3 · evidencia: `SYSTEM_PROMPT` es constante literal de §5.5; `request_id`/`employee_id` viven en `logger.append_keys` y en la respuesta, nunca en el prompt
- [x] **A-86** Límites L-1 a L-6, con L-1/L-2/L-3 evaluados **antes de construir el grafo** · §12A.3 · evidencia: `src/logic/limits.py`; `estimate_tokens` **corregido** (base `ceil(len/3.2)` + corrección por ancho de byte UTF-8: sin ella el ratio de L-3 era constante 3,2 y L-3 era código muerto). `文`×1200 → `INPUT_TOO_LARGE` **sin LLM**. L-4 en `llm_node` marca `context_truncated`
- [x] **A-87** Defensas D-1 a D-6 completas, incluido el escapado de `<` y `>` · §12A.2 · evidencia: `src/logic/defenses.py` + `tool_node.py`; `test_defenses.py` (D-1 escape, D-2 envolturas infalsificables, D-5 firma+`sk-ant-`+`ANTHROPIC_API_KEY`, D-6 6 marcadores); e2e: `injection_user` → modelo rehúsa, D-6 marca, D-5 sin fuga; D-4 ya se cumple (system de nivel superior)
- [x] **A-88** Cortacircuitos de sesión a 0,25 USD → 429 `SESSION_BUDGET_EXCEEDED` · §12A.4 · evidencia: `STATE.cost_usd_acumulado`; `test_presupuesto_de_sesion_429` (STATE con 0,30 → 429)
- [x] **A-89** Modo `{"warmup": true}` y modo `{"dry_run": true}` en el handler · §2.2, §8.4 · evidencia: `_warmup()` (inicializa el índice, sin LLM); `dry_run` → 200 sintético con contrato §4.2, STATE con `expires_at`, sin LLM; ambos probados e2e + unit
- [x] **A-90** Logs JSON con redacción de PII y las 12 métricas EMF de §11 · §11 · evidencia: `observability.py` (`Logger` powertools, `mask_pnr`→`AB***3`, `redact_message`→len+hash); EMF `AeroNova/Agent` emitiendo `LLMTokens`, `ToolRounds`, `CostUSD`, `SessionCostUSD`, `ToolInvocations`(name+resultado), `InjectionSuspected`, `InputRejected`(motivo), `OutputFilterTriggered`, `PromptBudgetTruncations`; `session_id` propagado a LangSmith vía `LANGCHAIN_TRACING_V2` (claves en F7)
- [x] **A-91** Prueba de integración que afirma `cache_read_input_tokens > 0` en la 2.ª petición · §5.3 · evidencia: `test_cache.py::test_cache_read_en_la_segunda_peticion` → turno 2 **`cache_read = 3072`**; coste 0,008 vs 0,011 del turno 1

## F7 · Despliegue — criterio: el endpoint responde 200 a una petición real

- [x] **A-100** `build_and_push.sh`: `docker build --platform linux/arm64`, etiqueta = SHA corto de Git · §13 paso 4 · evidencia: `scripts/build_and_push.sh` (login ECR, `--platform linux/arm64`, `TAG=$(git rev-parse --short HEAD)`, tope 2 GB, push); imagen `dd32582` en ECR y desplegada
- [x] **A-101** `terraform/10-app` leyendo `00-bootstrap` con `terraform_remote_state` · §13 · evidencia: `data "terraform_remote_state" "bootstrap"` (backend local → `../00-bootstrap/terraform.tfstate`); `apply` completado, 43 recursos
- [x] **A-102** Lambda con los 8 parámetros exactos de §2.2. **No intentar SnapStart** · §2.2 · evidencia: `aws_lambda_function.agent` (Image arm64, timeout 29, mem 2048, efímero 2048, logs JSON, sin SnapStart); `reserved_concurrent_executions` vía `var.reserved_concurrency` — **desviación ACU-005** (cuota de cuenta = 10, desplegado con `-1` hasta el aumento a 1000)
- [x] **A-103** IAM explícito por ARN, sin comodines; la Lambda **solo lee `gold/rag/`** · §2.5 · evidencia: `aws_iam_role_policy.lambda` con 8 permisos acotados por ARN (`s3:GetObject` sobre `.../gold/rag/*`, `ssm:GetParameter` sobre anthropic + langsmith, DynamoDB por tabla, Bedrock `InvokeModel` sobre Titan); verificación fina en phase-gate
- [x] **A-104** Usage Plan con `quota = 2.000` y **`period = MONTH`** · §2.3, hallazgo 38 · evidencia: `aws_api_gateway_usage_plan.plan` → `quota_settings { limit = 2000, period = "MONTH" }`, throttle 10/20; creado en el `apply`
- [x] **A-105** CORS restringido al dominio de CloudFront, no `*` · §2.3 · evidencia: preflight `aws_api_gateway_integration_response.options_chat` → `Access-Control-Allow-Origin = 'https://${cloudfront.domain_name}'`. **Faltaba la cabecera en la respuesta del POST** (la fija la Lambda vía proxy, no API Gateway): el chat del navegador daba «Failed to fetch». Corregido en F8: env var `UI_ORIGIN` en la Lambda + `schemas_api.to_proxy` añade `Access-Control-Allow-Origin` + `Vary: Origin`, nunca `*` (commit `16bfac6`). Verificado desde el navegador (`fetch` resuelve 200) y por cabecera (`Access-Control-Allow-Origin: https://d1v908g2u3hf9q.cloudfront.net`)
- [x] **A-106** EventBridge `rate(5 minutes)` con payload de calentamiento · §2.2 · evidencia: `aws_cloudwatch_event_rule.warmup` (`rate(5 minutes)`) + `event_target` con `input = {"warmup": true}` + `lambda_permission.warmup`; el handler corta en `_warmup()` antes del grafo
- [x] **A-107** `enable_provisioned_concurrency` expuesta y **por defecto `false`** · §2.2 · evidencia: `variables.tf` → `default = false`; `aws_lambda_provisioned_concurrency_config` con `count = var.enable_provisioned_concurrency ? 1 : 0`
- [x] **A-108** AWS Budgets a 20 USD con alertas al 50/80/100 % y alarmas de §11 · §9.5, §11 · evidencia: `aws_budgets_budget.monthly` (20 USD, 50/80/100 %) + 10 `aws_cloudwatch_metric_alarm` + SNS `aeronova-agent-alarms` con suscripción email `jesusarredondo0498@gmail.com`
- [x] **A-109** Aplicar `terraform apply` con `image_tag=<sha>`, **nunca `latest`** · §13 paso 5 · evidencia: `apply` con `-var="image_tag=dd32582" -var="reserved_concurrency=-1"`; `api_url = https://lbsnyvy2ba.execute-api.us-east-1.amazonaws.com/prod/v1/chat`
- [x] **A-130** Adaptador `to_proxy` en el borde de la Lambda: el handler y sus tests trabajan con el cuerpo como dict (§4.2/§4.3); la integración AWS_PROXY exige `body` como cadena JSON + `headers`. `lambda_handler` = `to_proxy(_run(...))`; `warmup` no se envuelve · §4.2 · evidencia: `schemas_api.to_proxy`, `handler._run`, 2 tests nuevos en `test_handler.py`; sin este adaptador API GW devolvía 502 pese a que el handler respondía con éxito
- [x] **A-131** Rol de cuenta de API Gateway para logs de ejecución en CloudWatch (`aws_api_gateway_account` + rol con `AmazonAPIGatewayPushToCloudWatchLogs`): `method_settings` con `logging_level != OFF` lo exige a nivel de cuenta. Deja un rol huérfano en el teardown (anotado en §16) · §11

## F8 · Interfaz — criterio: lista U-1 a U-14 superada · **HECHA**

- [x] **A-110** Página única sin framework ni build step; `x-api-key` en `localStorage`, nunca en `app.js` · §10, §10.1 · evidencia: `ui/index.html`+`app.js`+`styles.css`, 0 dependencias; clave en `localStorage` (`aeronova.apiKey`), campo `#in-api-key`, comentario de cabecera en `app.js`; servido por CloudFront `https://d1v908g2u3hf9q.cloudfront.net` (200, content-types correctos)
- [x] **A-111** Indicador de qué herramienta se está ejecutando, leído de `tools_used` · §10.1 · evidencia: `#indicador-tool` con spinner durante la petición + panel plegable por mensaje (colapsado por defecto, R-24) con tabla `tools_used` (name/status/latency_ms), `tool_rounds` y `usage`
- [x] **A-112** Medidores L-1, L-5 y coste de sesión con avisos al 80 % · §10.2 · evidencia: contador vivo `n/1200` neutro→ámbar a 960→rojo+envío deshabilitado a 1200; banda persistente en turno 40 con «Nueva sesión» destacada; pastilla de coste a 0,20 USD y diálogo a 0,25; L-2/L-3 con la heurística de `estimate_tokens` portada a JS, mensaje antes de enviar
- [x] **A-113** Marca de truncado **incluyendo** la frase de que el PNR activo se conserva · §10.2 · evidencia: `pintarNotaSistema` inserta en el hilo «Se recortaron los N mensajes más antiguos para caber en el contexto. Los datos de la reserva activa se conservan.» (nota `msg-sistema`, no error); forzable con la simulación `truncado` (U-5)
- [x] **A-114** `finish_reason: max_rounds` como nota explicativa, **no** como error · §10.2 · evidencia: `finish_reason === 'max_rounds'` → `msg-sistema` con «No pude completar la consulta…»; clase distinta de `msg-error`; forzable con la simulación `max_rounds` (U-6)
- [x] **A-115** `ui/examples.json` poblado con códigos y PNR **reales** · §10.3, R-25 · evidencia: bloque `demo` con `AN1008`/`AN1002`/`AN1049` y PNR `YXMWYB` (CONFIRMADA, AN2424) del conjunto sembrado seed 42; los 9 ejecutados contra el endpoint real → 9/9 sin «no encuentro», tool esperada invocada. `grupos` mantienen los marcadores `AN405`/`ABC123` de §10.3. Nota: §6A.7 no lleva lista de muestra en el `_manifest.json`; los IDs salen de `data/source/` (SUPONGO confirmado)
- [x] **A-116** Prueba unitaria de formatos y `expected_tool` de los ejemplos · §10.3 · evidencia: `tests/unit/test_examples.py` (10 casos): `^AN\d{3,4}$` / `^[A-Z0-9]{6}$`, cada `expected_tool` ∈ `TOOL_REGISTRY`, ningún ejemplo supera L-1, `demo` sin marcadores de posición, las 4 capacidades cubiertas
- [x] **A-117** Panel de uso responsable, abierto en la primera visita, sin detallar §12A · §10.4 · evidencia: `#dlg-responsable` se abre solo si no está `aeronova.responsablePanelVisto`; contenido de §10.4 (qué hace/no hace, verificar antes de comprometer, por qué los límites, consultas eficaces, no credenciales); no menciona defensas §12A; forzable con navegador limpio (U-10)
- [x] **A-118** Accesibilidad: `role="status"`, `aria-live`, nada que dependa solo del color · §10.5 · evidencia: skip-link, `:focus-visible` con contorno; medidores con `role="status"`/`aria-live="polite"`; el contador solo se anuncia al CRUZAR umbral (`aria-label` condicional); estados con icono+texto (▲/■/ℹ/✕), no solo color; `prefers-reduced-motion` corta toda animación. Verificación con lector de pantalla la hace el usuario (U-9). Toque Material Design + logo de AeroNova aplicados a petición del usuario (commit `cfaa6d1`), design system y roles de color intactos, U-1..U-13 revalidadas por CDP
- [x] **A-119** Ejecutar la lista U-1 a U-14 y adjuntar el resultado al informe · §8.5 · evidencia: U-1..U-13 ejecutadas contra la UI desplegada por Chrome DevTools Protocol (contador ámbar a 970 / rojo+deshabilitado a 1210; CJK 1100 → aviso L-2/L-3 sin petición; banda de turno 40; nota de truncado con la frase de reserva; max_rounds como nota no error; diálogos 429 coste/cuota; inserción de ejemplo selecciona `AN405` sin enviar; guía sin perder el hilo; roles `status`/`aria-live` + skip-link) + U-10/U-11 por captura. U-14 contra el endpoint real: 9/9. Tabla en el informe de F10. Falta solo la pasada con lector de pantalla real (recomendada al usuario)

### ACU-006 · Extras de demo (pedidos por el usuario, sobre F7/F8)

- [x] **A-133** Vista «Datos de prueba» + contador de mensajes por sesión + Enter envía + botón Contacto (LinkedIn) · §10 · evidencia: `ui/` commits `d585860`/`f2512d3`; CDP OK
- [x] **A-134** CORS de la respuesta POST y de las gateway responses de API Gateway (`UI_ORIGIN` + `to_proxy` + `aws_api_gateway_gateway_response`) · §2.3, A-105 · evidencia: commits `16bfac6`/`7563723`; el chat del navegador fallaba con error de red sin esto; verificado por `fetch` desde CloudFront y por cabecera
- [x] **A-135** Saneo del historial al cargarlo (`memory._sanitize_history`) — arregla el `INTERNAL_ERROR` del turno ~3 (ventana cortando un par tool_use/tool_result → Anthropic 400) · §5.1, R-07 · evidencia: commit `8d78782`; 5 tests + 10 turnos e2e sin error
- [x] **A-136** 4 tools de operación de solo lectura sobre GSIs: `vuelos_por_ciudad`, `pasajeros_de_vuelo` (muestra determinista de 5), `mascotas_por_vuelo`, `radar_operativo` (briefing) · ACU-006, I-13 (desviación) · evidencia: `src/tools/operaciones.py`, GSIs `origen/destino/codigo_vuelo-index` `ACTIVE`, IAM `dynamodb:Query` acotado a `.../index/*`, `test_operaciones.py` (10). Verificado en vivo con imagen `da7a34b`: las 4 responden `ok`
- [x] **A-137** Gráfica de **conteos** determinista (cliente): `_chart_for` genera barras de «vuelos por estado» para `vuelos_por_ciudad`/`radar_operativo`; sin LLM, sin librerías; citada en el panel de uso responsable y bajo cada gráfica · ACU-006 · evidencia: commit `c1f8871`; verificado en vivo (5-6 series por gráfica)
- [x] **A-138** RAG: chunk por grupos de artículos (~500 car.) + corpus de MENORES enriquecido (DNI/pasaporte, autorización notarial) · §6.2, §6.3 · evidencia: `_chunking._agrupar_articulos`, `generate_synthetic._FRASES_CATEGORIA['MENORES']`; índice `v=20260830T194954Z`, humo 5/5 (EQUIPAJE 0,698, MENORES 0,867); en vivo la consulta de menores ya cita la documentación concreta
- [x] **A-139** `SESSION_COST_LIMIT` configurable (env `SESSION_COST_LIMIT_USD`), subido a 0,75 para la demo (PRD = 0,25, §12A.4) · ACU-006 (desviación) · evidencia: `config.session_cost_limit_usd`, env var en `10-app`, la UI usa `session.cost_usd_limit` de la respuesta

## F9 · Aceptación — criterio: todos los umbrales de §8.3 · **HECHA**

- [x] **A-120** `cases.json` con **45 casos** en 14 familias (las 13 de §8.2 + `operacion_*` de ACU-006) · §8.2 · evidencia: `scripts/build_golden_cases.py`; `tests/golden/test_golden.py` (6 tests de esquema/cobertura). Fixtures de inyección sembradas (`INJ001/INJ002`, `POL-ACC-019/020`, commit `07fa15f`)
- [x] **A-121** Runner con caché en disco (clave = `input` + hash `prompts.py` + hash del registro de tools + `ANTHROPIC_MODEL`) · §8.3b · evidencia: `tests/golden/runner.py::_fingerprint`, `tests/golden/.cache/` (gitignored)
- [x] **A-122** Modos `--smoke` (1/familia, `--exitfirst`) y `--full` · §8.3b · evidencia: `runner.py` argparse mutuamente excluyente
- [x] **A-123** El runner imprime consultas ejecutadas, servidas de caché y **coste real acumulado** · §8.3b, §9.5 · evidencia: `runner.py` `cli.ejecutadas/de_cache/coste`
- [x] **A-124** **Corrida completa** obligatoria, nunca `--smoke` · R-17 · evidencia: `runner.py` avisa en modo smoke «NO cierra F9»; `test_golden.py` documenta que `--full` es criterio de salida
- [x] **A-125** Prueba de carga: 100 reales + 400 `dry_run`, confirmación interactiva · §8.4 · evidencia: `scripts/load_test.py` (`--yes` para omitir); coste estimado antes, real después
- [x] **A-126** Verifica el **atributo** `expires_at` (no la desaparición) · §8.4, hallazgo 29 · evidencia: `load_test._verificar_ttl` comprueba que `expires_at` cae en ventana de ~24 h en SEGUNDOS
- [x] **A-127** El informe deja claro que mide encolado y TTL, **no escalado** · §8.4, hallazgo 29 · evidencia: campo `nota` en `load_test_result.json` + docstring
- [x] **A-128** Verificados los 9 umbrales de §8.3 · §8.3 · evidencia: `tests/golden/golden_result.txt` — corrida COMPLETA (`--full`), **45/45 casos**, los 8 umbrales del runner (precisión de selección 100% ≥ 90%; hallucination/memory/injection/abuse/anomalia/contract 100%; max_rounds 0% ≤ 10%) + el 9º (E-01…E-09 `pass` en el `_manifest.json` del último Gold `full`). Coste real $0,23
- [-] **A-129** Portar las 4 pruebas de pipeline `@pytest.mark.skip` a moto/integración · §8.1 · **diferido**: los 4 comportamientos (reembebido incremental / humo falla→no promueve / rollback / idempotencia) están verificados contra AWS real en F4 (evidencia A-61/A-64/A-66). Convertirlos en tests con moto+LanceDB es limpieza, no un umbral; se hace en el cierre de F10 o como follow-up

## F10 · Entregable — criterio: los 7 puntos de §16 · **HECHA**

- [x] **A-140** PDF con los 4 diagramas exigidos: arquitectura, medallion §6A.2, grafo LangGraph, recursos Terraform · §16.7 · evidencia: `documents/aeronova_entregable.pdf` (7 pág., fuente en `build/entregable/entregable.html` con `skills/pdf-report`), diagramas como `.pipeline`/`.catalog` del design system
- [x] **A-141** Tabla de control de costes de §9.3 y evidencia de datos sintéticos · §16.7 · evidencia: §5 del PDF (coste/consulta, infra AWS, guardarraíles) + §6 (recuentos Bronze/Silver/cuarentena por dataset, muestra de `reservations.parquet`)
- [x] **A-142** Resultados del golden dataset y de la prueba de carga con su salvedad · §16.7 · evidencia: §7 del PDF — golden 50/50 (8 umbrales), carga 500 sesiones con la salvedad del hallazgo 29
- [x] **A-143** `docs/contracts/CONTRACTS.md` y los JSON Schema publicados · §16.4 · evidencia: re-exportados con `scripts/export_contracts.py` (sin diff; `fecha_compra` presente en `reservations_reserva.schema.json`)
- [x] **A-144** `_manifest.json` de la última construcción Gold como evidencia de linaje · §16.5 · evidencia: `manifest.py` fusiona E-06/E-07 y el humo real del índice vigente (antes `pending (F4)` hardcodeado); `silver/_manifest.json` con E-01…E-09 `pass`, humo `pass`, `rag_index_version`
- [x] **A-145** Reverificar los precios de AWS · §9.3 · evidencia: cuadran con tarifas públicas `us-east-1` (Lambda arm64 $/GB-s, DynamoDB PAY_PER_REQUEST, API GW REST, CloudWatch); la siembra de una-vez baja a ≈ 0,03 USD por el recorte `full` de ACU-007
- [x] **A-146** Verificar la Definición de Terminado completa · §16 · evidencia: runbook §13 reproducible (ACU-004/005/007 documentan las desviaciones), pipeline medallion E2E con E-01…E-09 `pass` y Silver/Gold desde Bronze, golden 50/50, `terraform plan` limpio ambos stacks, sin secretos en Git/CloudWatch
- [x] **A-147** Ningún secreto en Git ni en CloudWatch · §16 · evidencia: `git grep` sobre todo el historial — solo fixtures falsas `sk-ant-…` en tests; `.tfstate` ignorado; redacción PII en CloudWatch vía `mask_pnr`/`redact_message` + filtro de salida D-5

### F10 · Ampliación pedida por el usuario (sobre el entregable)

- [x] **A-148** 5 herramientas de operación nuevas (7→12 en el registro): `ranking_cabina` (top vuelos por mascotas y por menores en cabina; queries de reservas paralelizadas, cap 40), `resumen_demoras_ciudad` (puntualidad/motivos, solo GSI de vuelos), `ocupacion_vuelo` (pasaje por tipo y tarifa), `perfil_reservas_vuelo` (por estado/canal/reembolsable), `buscar_vuelos_ruta` (origen→destino). Todas de solo lectura sobre GSIs, sin `Scan`, dentro del presupuesto de 3 s · I-13 (misma desviación que ACU-006) · evidencia: `src/tools/operaciones.py`, `TOOL_REGISTRY` (12), `_TOOL_DESCRIPCIONES`, system prompt, `_chart_for` (whitelist ampliada), `test_operaciones.py` (13 tests nuevos); de paso fix del bug latente en `radar_operativo` (`demora_min`→`minutos_demora`). Golden `operacion_*` 4→9, total 45→50; corrida COMPLETA 50/50 contra imagen `d4ffb13`
- [x] **A-149** Rediseño de los ejemplos de la UI: sección `destacados` (4 consultas de más impacto con su «por qué»), **todos** los ejemplos (destacados, grupos, demo) con códigos de vuelo/PNR/IATA reales del conjunto sembrado (doble check contra DynamoDB), grupos de operación divididos en «por aeropuerto» / «por vuelo», ejemplos de la guía clicables que cierran el diálogo · §10.3, U-12/U-14 · evidencia: `ui/examples.json`, `ui/app.js` `pintarDestacados`, `ui/index.html`, `ui/styles.css`; `test_examples.py` (test de `destacados` + marcadores en las 3 fuentes); UI desplegada y verificada (CloudFront sirve el nuevo `examples.json`)
- [x] **A-150** Endurecidas la regla 2 del prompt (la herramienta valida el PNR, el modelo no cuenta caracteres) y la regla 4 (no citar el texto inyectado); nueva red de seguridad determinista `defenses.scrub_injection_markers` en el filtro de salida D-5 que tacha `SISTEMA-COMPROMETIDO`/`ESCAPE-FALLIDO` · §5.5, §12A.2 · evidencia: `src/agent/prompts.py`, `src/logic/defenses.py`, `handler.py`, `test_defenses.py`; golden 50/50 tras el fix (`anomalia_04`, `contract_02`, `injection_escape_01` verdes)

## Fuera de alcance — no se hace aunque parezca mejora (PRD §0.3)

- [-] Streaming de tokens · [-] Login por usuario final · [-] CI/CD · [-] Multi-región
- [-] Glue, Athena, Iceberg, dbt · [-] Airflow, Step Functions · [-] Kinesis, DynamoDB Streams
- [-] `aeronova-memory` dentro del medallion · [-] Panel de administración · [-] Fine-tuning
