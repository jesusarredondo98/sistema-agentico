---
name: data-contracts
description: Escribe y prueba los data contracts Pydantic v2 de src/contracts/ y las expectativas de calidad a nivel de lote, que actúan como puerta de admisión Bronze→Silver. Úsala en F2, antes de mover un solo dato, y siempre que se añada o modifique un campo de un dataset.
---

# Data contracts

Fuente única normativa: **modelos Pydantic v2 en `src/contracts/`** (S-09). El YAML y el
JSON Schema de `docs/contracts/` son exportaciones derivadas, generadas por
`scripts/export_contracts.py` y **nunca editadas a mano**.

> **Aviso que el PRD repite y que es el riesgo R-09:** el data contract **NO sustituye** a
> la validación Pydantic de las tools de §5.4. Defienden fallos distintos (§6A.8). Eliminar
> una de las dos hace fallar la familia `anomalia_*`.

## Metadatos obligatorios

Todo contrato hereda de `DataContract` y declara los cuatro `ClassVar`:

```python
class DataContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    CONTRACT_NAME: ClassVar[str]        # "corpus.documento_normativo"
    CONTRACT_VERSION: ClassVar[str]     # SemVer
    CONTRACT_OWNER: ClassVar[str]       # responsable funcional
    CONTRACT_SLA_HOURS: ClassVar[int]   # frescura máxima del lote
```

## Los tres contratos

| Contrato | Fichero | Versión | Deriva de |
|---|---|---|---|
| `DocumentoNormativoContract` | `corpus.py` | 1.0.0 | §6A.3, literal |
| `VueloContract` | `flights.py` | 1.0.0 | Campos de `EstadoVueloData`, **clase separada** |
| `ReservaContract` | `reservations.py` | 1.0.0 | Campos de `DatosReservaData`, **clase separada** |

**No se reutilizan las clases de §5.4.** El contrato gobierna la *carga*; los modelos de
§5.4 gobiernan la *respuesta*. Unificarlos acopla dos ciclos de vida distintos (§6A.3).

## Validaciones cruzadas del corpus (`@model_validator`)

Las cinco son obligatorias y cada una ataja un fallo concreto:

| Regla | Qué evita |
|---|---|
| El prefijo de `doc_id` corresponde a `categoria` (`POL-MAS-*` ⇒ `MASCOTAS`) | Documento irrecuperable cuando la tool filtra por categoría |
| `vigencia_hasta` posterior a `vigencia_desde` si está informada | Política vigente que no lo está |
| `vigencia_desde` **no futura** | El agente promete condiciones que aún no aplican |
| `referencias` coincide **exactamente** con los `POL-XXX-NNN` extraídos del `cuerpo` | Excepción cruzada sin declarar que escapa al control de integridad |
| `checksum_cuerpo` coincide con el sha256 recalculado | Corrupción en tránsito; habilita la carga incremental (§6A.6) |

## Expectativas de lote (`expectations.py`)

Se evalúan **tras** validar registro a registro y **antes** de escribir Silver. La validación
de registro no basta: un lote de registros individualmente válidos puede ser inservible.

| # | Expectativa | Umbral | Si falla |
|---|---|---|---|
| E-01 | Unicidad de `doc_id` / `codigo_vuelo` / `pnr` | 0 duplicados | **Aborta** |
| E-02 | Integridad referencial de las excepciones cruzadas | 100 % | **Aborta** |
| E-03 | Cobertura por categoría | ≥ 15 en cada una de las 7 | **Aborta** |
| E-04 | Tasa de cuarentena del lote | ≤ 2 % | **Aborta** |
| E-05 | `reservations.codigo_vuelo` → `flights` | ≥ 95 % | **Aborta** |
| E-06 | Casi-duplicados entre fragmentos | coseno < 0,98 | Cuarentena del fragmento, el lote sigue |
| E-07 | Dimensión y norma del embedding | 1024, norma ≈ 1,0 | **Aborta** |
| E-08 | Deriva de volumen frente al lote anterior | ≤ 20 % | Aborta salvo `--allow-volume-drift` |
| E-09 | Frescura frente a `CONTRACT_SLA_HOURS` | dentro de SLA | Advertencia |

**E-02 es la más importante.** Una referencia colgante hace que el agente cite una política
inexistente: alucinación por delegación, invisible para la validación de registro.

**E-06 protege el `top_k`.** Cuatro fragmentos casi idénticos ocupando las cuatro plazas
degradan la respuesta sin que nada falle visiblemente.

## Cuarentena: nunca se descarta en silencio

```json
{ "rejected_at": "…Z", "dataset": "corpus.documento_normativo", "contract_version": "1.0.0",
  "rule": "E-02", "record_key": "POL-MAS-004",
  "reason": "referencia colgante: POL-EQU-011 no existe en el lote", "raw": { } }
```

## Versionado SemVer y su efecto sobre Gold (§6A.5)

| Cambio | Versión | Consecuencia |
|---|---|---|
| Campo nuevo opcional, enum ampliado | MINOR | Compatible, no exige reindexar |
| Campo eliminado, tipo restringido, enum reducido, patrón endurecido | **MAJOR** | **Reconstrucción completa del índice** |
| Corrección de regla sin cambio de esquema | PATCH | Compatible |

El runtime rechaza servir un índice cuyo `contract_version` tenga un MAJOR inferior a
`RAG_CONTRACT_VERSION_MIN` (R-11).

## Pruebas (`tests/contracts/`) — cobertura mínima **95 %**

Cada regla y cada expectativa con casos **válido, inválido y de frontera**. Fixtures locales,
sin red. Es la puerta que decide qué datos entran al sistema: una rama sin probar es una vía
de entrada sin vigilar.

## Criterio de terminado

`pytest tests/contracts/` en verde con cobertura ≥ 95 %, un lote con referencia colgante
aborta por E-02, uno válido pasa, y `docs/contracts/` está regenerado desde los modelos.
