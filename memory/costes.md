# Libro de gasto real

Fuente única del consumo. El presupuesto vive en `documents/Agents.md` §5; **aquí solo se
registra lo realmente gastado**, tomado de `usage.cost_usd` de cada respuesta (PRD §4.2,
§9.5), nunca estimado a ojo.

## Resumen

| Concepto | Valor |
|---|---|
| Consultas LLM consumidas | **~430** de 1.005 previstas |
| Gasto LLM real | **~2,6 USD** de 8,80 previstos |
| Gasto AWS recurrente | **~0,40 USD/mes** previstos (`10-app` desplegado: Lambda + warmup 5 min + API GW + CloudFront + alarmas) |
| Gasto AWS de una sola vez | **~0,20 USD** (siembra `dev` + `full` recortado + ruta B + índice RAG xN + `apply` de `10-app` x muchas) |
| **Total real** | **~3 USD** — previsto 8,80, techo duro 17,90 USD/mes |
| Cuota G-1 consumida (API Gateway) | **~3.100** — agotó las 2.000; elevada a 10.000 (ACU-008) |

## Registro por ejecución

Se añade una fila **después** de cada ejecución que gaste. Sin fila, la ejecución no ocurrió.

| Fecha | Fase | Actividad | Modo | Consultas | USD real | Acumulado |
|---|---|---|---|---:|---:|---:|
| 2026-08-27 | F1 | A-20/A-21 verificación de la API (test + captura) | real | 3 | ~0,0005 | ~0,0005 |
| 2026-08-27 | F1 | prueba de integración re-ejecutada en F2b | real | 1 | ~0,0002 | ~0,0007 |
| 2026-08-27 | F2 | `terraform apply` de `00-bootstrap` (16 recursos, sin coste al crear) | AWS | 0 | ~0,00/mes | ~0,0007 |
| 2026-08-27 | F2b | siembra medallion `--profile dev`: 9.350 escrituras DynamoDB + PUT S3 | AWS | 0 | ~0,03 | ~0,03 |
| 2026-08-27 | F3 | verificación ruta B (2.000 inyectados + reset + reseed) | AWS | 0 | ~0,01 | ~0,04 |

## Alertas

| Umbral | Acción obligatoria |
|---|---|
| Acumulado > 4,40 USD (50 % del previsto) | Avisar al usuario en la respuesta |
| Acumulado > 7,04 USD (80 % del previsto) | **Detenerse** y pedir aprobación para continuar |
| Acumulado > 8,80 USD | **Detenerse.** Solo el usuario puede autorizar entrar en el margen hasta el techo de 17,90 |
| Cuota G-1 > 1.600 peticiones (80 %) | Detenerse: el resto del mes hay riesgo de 429 en la demo (R-15) |
| 2026-08-28 | F4 | índice RAG: ~2 builds reales (embebido 636+775 chunks Titan V2) + humo + pruebas + PUT S3 | AWS | 0 | ~0,01 | ~0,05 |
| 2026-08-28 | F5 | escenario multi-turno de memoria + comprobacion de propiedad de sesion (grafo real, LLM + DynamoDB) | real | ~10 | ~0,09 | ~0,09 |
| 2026-08-28 | F6 | prueba de cache (2 turnos) + verificacion e2e del handler (inyeccion, dry_run, abuse, turno normal) | real | ~18 | ~0,13 | ~0,22 |
| 2026-08-29 | F7 | `terraform apply` de `10-app` (43 recursos) + humo de verificacion del endpoint (dry_run, sin/ con api-key) | AWS | 0 | ~0,02 | ~0,24 |
| 2026-08-29 | F7 | depuracion del despliegue: ~4 rebuilds de imagen + reverificacion e2e (vuelo, PNR, RAG) contra el endpoint real | real | ~15 | ~0,08 | ~0,32 |
| 2026-08-29 | F4 rework | corpus con valor canonico: `make data-corpus` reembebe 935 chunks Titan V2 + humo 5/5 + reverificacion de politicas en vivo | real+AWS | ~5 | ~0,03 | ~0,35 |
| 2026-08-29 | F8 | U-14: 9 ejemplos de demo de `examples.json` contra el endpoint real (2 pasadas por el cambio de PNR) | real | ~12 | ~0,06 | ~0,41 |
| 2026-08-29 | F7 fix | INTERNAL_ERROR del turno ~3 (ventana de historial cortando pares tool): saneo + rebuild + 10 turnos de verificación e2e | real | ~25 | ~0,12 | ~0,55 |
| 2026-08-30 | ACU-006 desplegado | rebuild índice RAG x2 (chunking) + 4 tools nuevas + verificación en vivo (5 consultas) | real+AWS | ~10 | ~0,05 | ~0,60 |
| 2026-08-30 | F9 golden | resiembra full (recortado) + smoke x2 + corrida COMPLETA (45 casos, 49 consultas) | real+AWS | ~64 | ~0,31 | ~0,91 |
| 2026-08-30 | F9 carga | prueba de carga §8.4: 100 reales + 400 dry_run | real | ~100 | ~0,26 | ~1,17 |
| 2026-08-29 | F7 fix | rebuild + apply por CORS de la respuesta POST + verificación e2e desde el navegador (rediseño Material, sin coste LLM salvo 3-4 sondeos) | real+AWS | ~4 | ~0,02 | ~0,43 |
| 2026-08-31 | F10 DoD | barrido de pendientes: cableado de E-06 (reconstrucción índice, coste ~0 por reúso), fix corpus, `terraform plan` limpio; golden `--full` x2 (fix prompt PNR) | real+AWS | ~100 | ~0,49 | ~1,66 |
| 2026-08-31 | F10 carga | reintento prueba de carga §8.4 x2 (una reventó en verificación TTL por falta de perfil) | real | ~1000 | ~0,34 | ~2,00 |
| 2026-08-31 | F10 tools | 5 tools de operación nuevas (7→12) + rediseño UI de ejemplos; golden `--full` x3 (fix prompt formato PNR + tachado D-5 de cebos de inyección) | real+AWS | ~160 | ~0,85 | ~2,85 |
