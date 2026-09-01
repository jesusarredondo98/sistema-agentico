---
name: synthetic-data
description: Genera el corpus normativo y los datos sintéticos de vuelos y reservas de forma determinista y reproducible, con las anomalías repartidas en dos rutas. Úsala en F2b, antes de la ingesta a Bronze. Sin LLM, con plantilla y Faker.
---

# Datos sintéticos

`scripts/generate_synthetic.py` produce la **fuente**. No valida: de eso se encarga el
pipeline (§6A.3). La generación es determinista y reproducible con la misma semilla.

> **El corpus NO se genera con un LLM** (S-07). Plantillas estructuradas por categoría más
> `Faker` para las variables. Determinista, reproducible y sin coste.

## Volúmenes

| Conjunto | `full` | `dev` | Notas |
|---|---:|---:|---|
| Vuelos | 90.000 | 4.500 | `AN` + 3–4 dígitos, únicos |
| Reservas | 100.000 | 5.000 | PNR de 6 caracteres alfanuméricos, únicos |
| Corpus normativo | 150 | 150 | 7 categorías, 15–30 documentos cada una |

**El perfil `dev` no existe por dinero.** La diferencia de coste es de 0,23 USD, irrelevante.
Existe por **tiempo de iteración**: 5–8 minutos con `full` frente a ~20 segundos con `dev`
(§7.2). `dev` conserva **todas** las proporciones y **todos** los casos borde, incluido el
reparto de anomalías. El entregable **debe** construirse con `full` (R-19).

## Distribución de estados de vuelo

65 % `A_TIEMPO` · 20 % `DEMORADO` · 8 % `EMBARCANDO`/`EN_VUELO`/`ATERRIZADO` · 7 % `CANCELADO`

## Corpus: las excepciones cruzadas son el requisito difícil

- **Al menos 20 documentos** contienen una excepción que remite a otra categoría, de forma
  que responder bien exige recuperar **dos** fragmentos.
- Ejemplo canónico: *«Se permite una mascota en cabina por pasajero (POL-MAS-004), salvo en
  rutas transatlánticas de más de 8 horas, donde aplica lo dispuesto en POL-EQU-011.»*
- **Toda referencia cruzada se declara en el campo `referencias`.** E-02 verifica que
  resuelve; si no, el lote aborta.
- La familia `rag_cruzado_*` del golden dataset las ejercita.

## Anomalías: dos rutas, dos defensas (§7.1)

La contradicción aparente —«si el contrato funciona, las anomalías nunca llegan a DynamoDB»—
se resuelve repartiéndolas según qué defensa demuestran. **No se debilita el contrato.**

**Ruta A — 3 % (≈3.000 registros).** Detectables por contrato. Se generan en la fuente,
llegan a Bronze y **deben** quedar en `quarantine/`. Nunca alcanzan DynamoDB.

- PNR de longitud incorrecta (5 o 7 caracteres)
- PNR con caracteres no alfanuméricos
- `codigo_vuelo` con referencia huérfana
- `fecha_vuelo` anterior a la fecha de compra

Demuestran que **la puerta de carga funciona**. Las verifica la familia `contract_*`.

**Ruta B — 2 % (≈2.000 registros).** Corrupción **posterior** a la carga. Se inyectan
directamente en DynamoDB con `build_gold_dynamo.py --inject-gold-corruption 2000`, saltándose
el pipeline a propósito.

- Lista de pasajeros vacía
- `clase_tarifa` fuera del enum
- Campo obligatorio ausente

Simulan lo que un contrato **estructuralmente no puede evitar**: una escritura fuera del
pipeline, una migración manual, un hueco del propio contrato. Demuestran que la validación en
runtime sigue haciendo falta (§6A.8). Las verifica la familia `anomalia_*`.

La bandera **debe** imprimir una advertencia explícita de que se salta el contrato
deliberadamente, y **debe** estar desactivada por defecto.

## Reglas de reproducibilidad

- Semilla de `Faker` y de `random` fijada por `--seed` (el runbook usa `--seed 42`).
- Misma semilla ⇒ mismo dataset, byte a byte. Si no, la evidencia del entregable no vale.
- El perfil usado queda registrado en el `_manifest.json` (§7.2, R-19).

## Criterio de terminado

Con `--seed 42` se generan los volúmenes exactos del perfil, ≥ 20 documentos llevan
referencia cruzada declarada, el 3 % de ruta A está presente en la fuente y la ruta B queda
disponible pero **desactivada**.
