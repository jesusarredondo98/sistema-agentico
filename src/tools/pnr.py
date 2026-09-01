"""``obtener_datos_reserva`` (PRD §5.4.2, §5.4.4).

Solo lectura. Normaliza el PNR (mayusculas, sin espacios) **antes** de validar:
un agente de mostrador escribe `abc 123`. Nunca lanza excepcion al LLM.
"""
from __future__ import annotations

from pydantic import ValidationError

from src.logic.dynamo import get_reservation
from src.tools._runtime import (
    ToolTimeout,
    emit_tool_metric,
    estimate_tokens,
    run_with_timeout,
    timed,
    trim_reservation,
    TOKEN_BUDGET,
)
from src.tools.schemas import DatosReservaData, ObtenerDatosReservaInput, ToolResult

NOMBRE = "obtener_datos_reserva"


def normalizar_pnr(pnr: str) -> str:
    """Mayusculas y sin espacios (§5.4.4 regla 2)."""
    return "".join(str(pnr).split()).upper()


def obtener_datos_reserva(pnr: str) -> ToolResult:
    """Devuelve los datos de una reserva (PNR) de AeroNova."""
    with timed() as t:
        result = _obtener(pnr)
    emit_tool_metric(NOMBRE, result.ok, t.ms)
    return result


def _obtener(pnr: str) -> ToolResult:
    pnr_norm = normalizar_pnr(pnr)
    try:
        entrada = ObtenerDatosReservaInput(pnr=pnr_norm)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    try:
        item = run_with_timeout(lambda: get_reservation(entrada.pnr))
    except ToolTimeout as e:
        return ToolResult.fail("TIMEOUT", str(e))
    except Exception as e:  # noqa: BLE001 - la tool no propaga nada al LLM
        return ToolResult.fail("UPSTREAM_ERROR", f"error al consultar la reserva: {e}")

    if item is None:
        return ToolResult.fail("NOT_FOUND", f"no existe la reserva {entrada.pnr}")

    # Validacion de SALIDA (R-09): ruta B (pasajeros vacios / enum invalido /
    # campo ausente) -> ok=False code=UPSTREAM_ERROR, sin traza.
    try:
        reserva = DatosReservaData.model_validate(item)
    except ValidationError as e:
        return ToolResult.fail("UPSTREAM_ERROR", f"registro de reserva invalido: {_first_msg(e)}")

    data = trim_reservation(reserva.model_dump())
    if estimate_tokens(data) > TOKEN_BUDGET:  # red de seguridad; no deberia dispararse con <=9 pax
        data.pop("pasajeros", None)
        data["pasajeros_omitidos_por_presupuesto"] = True
    return ToolResult.success(data)


def _first_msg(e: ValidationError) -> str:
    err = e.errors()[0]
    loc = ".".join(str(x) for x in err["loc"])
    return f"{loc}: {err['msg']}"
