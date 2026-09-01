---
name: medallion-pipeline
description: Construye la cadena Bronze→Silver→Gold sobre prefijos de S3 con scripts de Python, con cuarentena, expectativas de lote y manifiestos de linaje. Úsala en F2b y cada vez que se recarguen datos. Sin Glue, sin catálogo, sin orquestador.
---

# Pipeline medallion

Prefijos de S3 más scripts de Python (S-08). **Ni Glue, ni Data Catalog, ni Lake Formation,
ni Athena, ni EMR, ni Iceberg, ni Delta Lake, ni dbt, ni Airflow, ni Step Functions** — todo
ello prohibido explícitamente en §0.3, y el riesgo R-12 existe porque es la tentación
natural. Un catálogo de Glue por sí solo cuesta más que el resto de la infraestructura junta.

La cadena se ejecuta con `make data` desde la terminal del operador.

## Semántica de las capas (§6A.1)

| Capa | Contiene | Mutabilidad | Escribe | Lee |
|---|---|---|---|---|
| **Bronze** | El dato tal como llegó, particionado por `ingest_date` | **Inmutable.** Nunca se corrige un fichero; se ingesta una partición nueva | `ingest_bronze.py` | Solo el pipeline |
| **Silver** | Validado contra contrato, tipado, normalizado, deduplicado | Reemplazable, reconstruible desde Bronze | `promote_silver.py` | Pipeline y analista |
| **Gold** | Índice LanceDB versionado en S3 **y** las tablas `aeronova-flights` y `aeronova-reservations` | Versionado inmutable con puntero (S3) / reemplazo idempotente (DynamoDB) | `build_gold_*.py` | **El runtime** |
| **Quarantine** | Rechazados con motivo estructurado | Append-only | `promote_silver.py` | El operador |

**Dos reglas invariables:**

- **Reconstrucción.** Silver y Gold deben poder reconstruirse **por completo desde Bronze**
  sin tocar la fuente original. Si un cambio rompe esa propiedad, es un defecto.
- **Dirección.** Los datos solo fluyen hacia adelante. Nada escribe de Silver a Bronze ni de
  Gold a Silver.

## Qué está y qué no está en el medallion (§6A.0)

| Dataset | ¿Medallion? | Quién escribe |
|---|---|---|
| Corpus → índice LanceDB | **Sí** | El pipeline |
| `aeronova-flights` | **Sí**, Gold | `build_gold_dynamo.py` |
| `aeronova-reservations` | **Sí**, Gold | `build_gold_dynamo.py` |
| `aeronova-memory` | **NO. Fuera del lago** | La propia Lambda, en cada turno |

**Meter `aeronova-memory` en el medallion rompe cuatro propiedades del diseño** (hallazgo 37):
es estado transaccional y no dato de referencia; su TTL de 24 h es incompatible con un Bronze
inmutable; obligaría a dar escritura sobre el lago a la Lambda, que §2.5 le niega; y crearía
retención de PII contraria a §12. Además, la latencia lo impide por sí sola.

**No materializar las tablas de DynamoDB como ficheros en `gold/` de S3.** Su promoción a
Gold *consiste* en la siembra desde Silver (§2.4).

## Disposición de prefijos

```text
s3://aeronova-lake-<sufijo>/
├── bronze/{corpus,flights,reservations}/ingest_date=YYYY-MM-DD/
├── silver/{corpus/{documents,chunks}.parquet, flights/…, reservations/…}
├── quarantine/<dataset>/ingest_date=YYYY-MM-DD/rejects.jsonl
└── gold/rag/{CURRENT, politicas.lance/v=<ts>/}
```

Formato: **Parquet** para tabular, **JSONL + Parquet de fragmentos** para el corpus (S-10).
Ciclo de vida: `bronze/` y `quarantine/` a Glacier IR a los 30 días; `gold/rag/` conserva las
**3 últimas versiones**. Sin esto, cada reconstrucción acumula coste indefinidamente.

## Orden de ejecución (`make data`, §13 paso 3)

Se detiene en el primer fallo:

1. `generate_synthetic.py --seed 42` — produce la fuente
2. `ingest_bronze.py` — copia cruda a `bronze/ingest_date=<hoy>/`
3. `promote_silver.py` — **puerta de contrato** + expectativas; escribe Silver y Quarantine
4. `build_gold_dynamo.py` — siembra las dos tablas desde Silver (5–8 min con `full`)
5. `build_gold_rag.py` — embeddings, índice, manifiesto, prueba de humo, conmutación de `CURRENT`

**Si cualquier expectativa aborta, el pipeline sale con código distinto de cero y `CURRENT`
no se toca.** El sistema degrada a «datos de ayer», nunca a «datos rotos».

Recarga solo del corpus: `make data-corpus`.

## Fragmentación (en `promote_silver.py`, capa Silver)

Por artículo, máximo **800 caracteres**, solape **100**, **nunca partiendo a mitad de frase**.
Se persiste en `silver/corpus/chunks.parquet` con su `doc_id` de origen.

## Siembra a DynamoDB (`build_gold_dynamo.py`)

- Lee de `silver/*.parquet`. **Nunca de la fuente ni de Bronze.**
- `BatchWriteItem` de 25 items, pool de 16 hilos.
- **Reintento obligatorio de los `UnprocessedItems`**; ignorarlos provoca pérdida silenciosa.
- **Idempotente**: re-ejecutar no duplica ni falla. `--reset` vacía antes.

## Manifiesto de linaje (§6A.7)

Todo artefacto Gold lleva `_manifest.json` con: `version`, `built_at`, `contract_name`,
`contract_version`, `source_bronze_partition`, `embedding_model`, `embedding_dimensions`,
`counts` por capa, `quarantine_rate`, resultado de cada expectativa, `smoke_test` y `git_sha`.
Alimenta directamente el entregable §16.5.

## Métricas del pipeline (`AeroNova/Data`, §11)

`RowsBronze`, `RowsSilver`, `RowsQuarantined`, `QuarantineRate`, `ExpectationFailures`,
`ChunksIndexed`, `EmbeddingsComputed`, `SmokeTestResult`. Por dataset.

## Criterio de terminado

`make data` completo sin errores, tasa de cuarentena de reservas ≈ 3 % (ruta A), un
`get_item` recupera un vuelo y un PNR conocidos, y el manifiesto registra todas las
expectativas en `pass` con el perfil usado.
