"""``consultar_estado_vuelo`` (PRD §5.4.1).

Solo lectura. Nunca lanza excepcion al LLM: todo fallo es un ``ToolResult``.
"""
from __future__ import annotations

from pydantic import ValidationError

from src.logic.dynamo import get_flight
from src.tools._runtime import ToolTimeout, drop_nulls, emit_tool_metric, run_with_timeout, timed
from src.tools.schemas import (
    ConsultarEstadoVueloInput,
    EstadoVueloData,
    ToolResult,
)

NOMBRE = "consultar_estado_vuelo"


def consultar_estado_vuelo(codigo_vuelo: str) -> ToolResult:
    """Devuelve el estado operativo de un vuelo de AeroNova."""
    with timed() as t:
        result = _consultar(codigo_vuelo)
    emit_tool_metric(NOMBRE, result.ok, t.ms)
    return result


def _consultar(codigo_vuelo: str) -> ToolResult:
    # 1) validacion de entrada -> INVALID_INPUT, nunca excepcion (§5.4.4)
    try:
        entrada = ConsultarEstadoVueloInput(codigo_vuelo=codigo_vuelo)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    # 2) lectura con timeout duro de 3 s -> TIMEOUT
    try:
        item = run_with_timeout(lambda: get_flight(entrada.codigo_vuelo))
    except ToolTimeout as e:
        return ToolResult.fail("TIMEOUT", str(e))
    except Exception as e:  # noqa: BLE001 - la tool no propaga nada al LLM
        return ToolResult.fail("UPSTREAM_ERROR", f"error al consultar el vuelo: {e}")

    if item is None:
        return ToolResult.fail("NOT_FOUND", f"no existe el vuelo {entrada.codigo_vuelo}")

    # 3) validacion de SALIDA (R-09): la corrupcion de ruta B se rechaza aqui de
    #    forma controlada, no con una traza.
    try:
        vuelo = EstadoVueloData.model_validate(item)
    except ValidationError as e:
        return ToolResult.fail("UPSTREAM_ERROR", f"registro de vuelo invalido: {_first_msg(e)}")

    return ToolResult.success(drop_nulls(vuelo.model_dump()))


def _first_msg(e: ValidationError) -> str:
    err = e.errors()[0]
    loc = ".".join(str(x) for x in err["loc"])
    return f"{loc}: {err['msg']}"
