---
name: rag-index
description: Construye, promueve, sirve y revierte el índice LanceDB de políticas con embeddings Titan V2, versionado inmutable, prueba de humo y puntero CURRENT. Úsala en F4 y en cada recarga del corpus.
---

# Índice RAG

Opera sobre `silver/corpus/chunks.parquet`, **nunca sobre la fuente cruda**.

## Construcción (`pipelines/build_gold_rag.py`, ejecución local)

1. **Embeddings**: `amazon.titan-embed-text-v2:0` vía `bedrock-runtime.invoke_model`, con
   `dimensions: 1024` y `normalize: true`. En lotes, con reintento exponencial ante throttling.
2. **Reembebido incremental** (§6A.6): solo se reembeben los fragmentos cuyo documento cambió
   de `checksum_cuerpo`. Evita pagar Bedrock por 150 documentos cuando cambiaron 3.
3. **El índice se reconstruye entero** aunque los embeddings se reutilicen. Un índice
   construido por parches acumula deriva y deja de ser reproducible.
4. **Tabla LanceDB `politicas`** con las columnas: `vector` (1024 float32), `doc_id`,
   `titulo`, `categoria`, `vigencia_desde`, `fragmento`.
5. **Verificación E-07** sobre los vectores: dimensión exacta 1024 y norma ≈ 1,0.

## Promoción, versionado y rollback (§6A.5)

El orden importa y no es negociable:

1. Construir en `gold/rag/politicas.lance/v=<UTC compacto>/`. **Nunca sobrescribir una
   versión existente** — una Lambda en frío podría leer un índice a medio subir.
2. Escribir `_manifest.json` junto al índice.
3. **Prueba de humo obligatoria antes de promover:** 5 consultas fijadas, una por categoría
   mayoritaria. Cada una **debe** devolver al menos un resultado por encima de 0,35. Si alguna
   falla, **no se promueve** y el pipeline termina en error. Un índice que no sabe responder
   nunca llega a producción.
4. **Conmutación atómica:** escribir `gold/rag/CURRENT` con la ruta de la versión nueva. Son
   pocos bytes: la conmutación es instantánea y sin estado intermedio observable.
5. **Rollback:** `scripts/rollback_rag.py --to v=<ts>` reescribe `CURRENT`. Recuperación en
   segundos, sin reconstruir ni redesplegar.

## Recuperación en tiempo de ejecución (§6.3)

- **Inicialización en ámbito de módulo, una sola vez por contenedor:** leer `CURRENT`,
  descargar esa versión a `/tmp`, abrir la tabla, guardar en variable global. **Nunca dentro
  del handler.**
- **Refresco por el ping de calentamiento.** La invocación con `{"warmup": true}` **debe**
  releer `CURRENT` (un `GetObject` de pocos bytes) y, si difiere de lo cargado, descargar y
  recargar. **Sin esto, un contenedor caliente serviría el índice antiguo indefinidamente**,
  que es el efecto perverso del calentamiento (R-10). La ventana de propagación queda acotada
  a 5 minutos.
- Por consulta: embeber la pregunta **con el mismo modelo y la misma dimensión**, buscar por
  coseno con `RAG_TOP_K = 4`, filtrar por `categoria` si viene informada.
- **Umbral 0,35.** Por debajo se descarta. Si no queda ninguno, devolver
  `ToolResult(ok=False, error=ToolError(code="NOT_FOUND", …))`. **Devolver fragmentos
  irrelevantes es la vía principal por la que un RAG induce alucinación.**
- Los fragmentos se entregan envueltos en `<documento_recuperado id="…" titulo="…">…
  </documento_recuperado>`, con el contenido escapado según D-1.
- Tamaño esperado del índice: **< 20 MB** (≈600 fragmentos × 1024 dimensiones).

## Dos trampas silenciosas

| Trampa | Efecto |
|---|---|
| Dimensión distinta en construcción y consulta | Resultados **silenciosamente incorrectos**, sin error |
| `contract_version` del manifiesto con MAJOR < `RAG_CONTRACT_VERSION_MIN` | El runtime **debe negarse a servir**: log crítico y `ToolResult(ok=False, code="UPSTREAM_ERROR")`. Es preferible decir «no puedo consultar políticas» a responder desde un índice incoherente (R-11) |

## Registro obligatorio

El runtime registra `version`, `contract_version` y `counts.chunks` en el log de
inicialización, y emite `contract_version` e `index_version` como dimensiones de la métrica
`RagHits`. Sin eso es imposible correlacionar una caída de calidad con una recarga de datos.

## Carga incremental de documentos nuevos (§6A.6)

- Un documento nuevo que incumpla el contrato **no llega jamás al índice**: queda en
  cuarentena y el operador lo ve en el informe. El corpus vigente sigue sirviéndose intacto.
- Si el lote incumple una expectativa que aborta, **no se promueve nada** y `CURRENT` sigue
  apuntando a la versión anterior.

## Criterio de terminado

Una consulta de política devuelve fragmentos por encima de 0,35, la prueba de humo pasa,
`rollback_rag.py` retrocede y vuelve a avanzar, y el ping de calentamiento recarga tras un
cambio de `CURRENT`.
