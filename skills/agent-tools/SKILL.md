---
name: agent-tools
description: Implementa las tres herramientas del agente con su sobre uniforme ToolResult, contratos de entrada y salida, timeout, presupuesto de tokens y envoltura de contenido no confiable. Úsala en F3 y F4, y ante cualquier cambio en un campo devuelto por una tool.
---

# Herramientas del agente

Tres herramientas, todas de **solo lectura**: `consultar_estado_vuelo`,
`obtener_datos_reserva`, `buscar_politicas_rag`. Registro en `src/tools/__init__.py`.

> **Ninguna herramienta lanza excepción hacia el LLM.** Un fallo es un dato estructurado que
> el modelo sabe interpretar y explicar al usuario.

## Sobre uniforme

```python
class ToolError(BaseModel):
    code: Literal["NOT_FOUND", "INVALID_INPUT", "UPSTREAM_ERROR", "TIMEOUT"]
    message: str

class ToolResult(BaseModel):
    ok: bool
    data: Any | None = None
    error: ToolError | None = None
```

## Contratos por herramienta (§5.4)

| Tool | Entrada | Patrón | Salida |
|---|---|---|---|
| `consultar_estado_vuelo` | `codigo_vuelo` | `^AN\d{3,4}$` | `EstadoVueloData` |
| `obtener_datos_reserva` | `pnr` | `^[A-Z0-9]{6}$` | `DatosReservaData` |
| `buscar_politicas_rag` | `consulta` (3–500 car.) + `categoria` opcional | 7 categorías del enum | `BusquedaPoliticasData` |

**Los errores de herramienta NO son errores HTTP.** Un PNR inexistente devuelve
`ToolResult(ok=False)` y el HTTP sigue siendo 200 (§4.3).

## Reglas comunes de implementación (§5.4.4)

1. **Fallo de validación del input** → `ToolResult(ok=False, error=ToolError(code="INVALID_INPUT"))`,
   **nunca se propaga la excepción**. Es la ruta que ejercitan las anomalías de §7.
2. **Normalización del PNR** a mayúsculas y sin espacios **antes** de validar. Un agente de
   mostrador escribe `abc 123`.
3. **Timeout duro de 3 s** por herramienta. Al vencer: `code="TIMEOUT"`.
4. **Envoltura obligatoria del retorno.** Todo resultado se entrega al LLM dentro de
   `<dato_operativo fuente="…">`, con el contenido **escapado según D-1** (§12A.2). Los
   campos de texto libre —`nombre` de pasajero, `motivo` de demora, `puerta`— son contenido
   **no confiable aunque procedan de una tabla propia** (R-21).
5. **Cada ejecución emite una métrica EMF** con nombre, resultado y latencia.

## Economía del payload de retorno

El resultado entra íntegro en la ventana de la llamada siguiente y **se paga como tokens de
entrada**. Presupuesto: **≤ 450 tokens por resultado** (L-6).

- Omitir los campos `null` al serializar.
- Limitar `pasajeros` a los **9 primeros** (máximo real de un PNR) e indicar el total aparte.
- No devolver campos que el system prompt no vaya a usar.

Un `DatosReservaData` serializado sin cuidado supera con facilidad los 700 tokens.

## La validación de salida no es opcional (R-09)

El data contract de §6A gobierna la **carga**; esta validación gobierna la **respuesta**. La
corrupción de ruta B (§7.1) se inyecta directamente en DynamoDB precisamente para demostrar
que hace falta: `obtener_datos_reserva` la recupera y su validación Pydantic de salida la
rechaza de forma controlada, produciendo `ToolResult(ok=False, code="UPSTREAM_ERROR")` en
lugar de una traza de excepción.

**Eliminar esta validación por creerla redundante con el data contract hace fallar la familia
`anomalia_*`.** Es el error que §6A.8 prohíbe explícitamente.

## Radio de explosión: la propiedad que hay que preservar (D-3)

Las tres herramientas son consultas de **solo lectura** con entradas tipadas y restringidas
por expresión regular. No hay ejecución de código, ni SQL, ni shell, ni descarga de URL
arbitraria, ni escritura sobre ningún dato.

> Una inyección plenamente exitosa **no puede lograr que el agente haga nada que el empleado
> no pudiera hacer ya**: como mucho, obtiene texto mal redactado.

**Añadir una herramienta con efectos secundarios cambia la clase de riesgo de todo el sistema
y exige rehacer el análisis de amenazas** (R-20, impacto crítico). No se hace sin decisión
explícita del sponsor.

## Criterio de terminado

`pytest tests/unit/` en verde con cobertura ≥ 80 % en `src/tools/`, los registros corruptos
de ruta B producen `ok=False` sin traza, y ningún resultado supera los 450 tokens.
