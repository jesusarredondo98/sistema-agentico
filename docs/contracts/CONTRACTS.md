# Data contracts de AeroNova

> Generado por `scripts/export_contracts.py` desde `src/contracts/`. **No editar a mano** (S-09).

| Contrato | Version | Responsable | SLA (h) | Campos |
|---|---|---|---:|---|
| `corpus.documento_normativo` | 1.0.0 | operaciones@aeronova.example | 720 | `doc_id`, `titulo`, `categoria`, `vigencia_desde`, `vigencia_hasta`, `cuerpo`, `referencias`, `idioma`, `checksum_cuerpo` |
| `flights.vuelo` | 1.0.0 | operaciones@aeronova.example | 24 | `codigo_vuelo`, `estado`, `origen`, `destino`, `salida_programada`, `salida_estimada`, `minutos_demora`, `puerta`, `motivo`, `fecha_consulta` |
| `reservations.reserva` | 1.0.0 | atencion_cliente@aeronova.example | 24 | `pnr`, `estado`, `codigo_vuelo`, `fecha_vuelo`, `fecha_compra`, `pasajeros`, `clase_tarifa`, `equipaje_facturado`, `mascota_en_cabina`, `reembolsable`, `canal_compra` |

## Detalle por contrato

### `corpus.documento_normativo` v1.0.0

- **Responsable:** operaciones@aeronova.example
- **SLA de frescura:** 720 h
- **JSON Schema:** [`corpus_documento_normativo.schema.json`](corpus_documento_normativo.schema.json)

| Campo | Tipo | Requerido |
|---|---|---|
| `doc_id` | `str` | si |
| `titulo` | `str` | si |
| `categoria` | `Literal` | si |
| `vigencia_desde` | `date` | si |
| `vigencia_hasta` | `datetime.date | None` | no |
| `cuerpo` | `str` | si |
| `referencias` | `list` | no |
| `idioma` | `Literal` | no |
| `checksum_cuerpo` | `str` | si |

### `flights.vuelo` v1.0.0

- **Responsable:** operaciones@aeronova.example
- **SLA de frescura:** 24 h
- **JSON Schema:** [`flights_vuelo.schema.json`](flights_vuelo.schema.json)

| Campo | Tipo | Requerido |
|---|---|---|
| `codigo_vuelo` | `str` | si |
| `estado` | `Literal` | si |
| `origen` | `str` | si |
| `destino` | `str` | si |
| `salida_programada` | `str` | si |
| `salida_estimada` | `str | None` | no |
| `minutos_demora` | `int` | no |
| `puerta` | `str | None` | no |
| `motivo` | `str | None` | no |
| `fecha_consulta` | `str` | si |

### `reservations.reserva` v1.0.0

- **Responsable:** atencion_cliente@aeronova.example
- **SLA de frescura:** 24 h
- **JSON Schema:** [`reservations_reserva.schema.json`](reservations_reserva.schema.json)

| Campo | Tipo | Requerido |
|---|---|---|
| `pnr` | `str` | si |
| `estado` | `Literal` | si |
| `codigo_vuelo` | `str` | si |
| `fecha_vuelo` | `str` | si |
| `fecha_compra` | `str` | si |
| `pasajeros` | `list` | si |
| `clase_tarifa` | `Literal` | si |
| `equipaje_facturado` | `int` | si |
| `mascota_en_cabina` | `bool` | si |
| `reembolsable` | `bool` | si |
| `canal_compra` | `Literal` | si |
