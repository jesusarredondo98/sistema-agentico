"""Modelos de entrada/salida de las tools (src/tools/schemas.py, PRD §5.4)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.tools.schemas import (
    DatosReservaData,
    EstadoVueloData,
    PasajeroData,
    ToolError,
    ToolResult,
)


def test_toolresult_helpers():
    ok = ToolResult.success({"x": 1})
    assert ok.ok and ok.error is None and ok.data == {"x": 1}
    bad = ToolResult.fail("NOT_FOUND", "no existe")
    assert not bad.ok and bad.data is None
    assert isinstance(bad.error, ToolError) and bad.error.code == "NOT_FOUND"


def test_toolerror_code_restringido():
    with pytest.raises(ValidationError):
        ToolError(code="BOOM", message="x")


def test_estado_vuelo_data_minimo():
    v = EstadoVueloData(
        codigo_vuelo="AN405", estado="A_TIEMPO", origen="MEX", destino="MAD",
        salida_programada="2026-08-27T10:00:00+00:00", fecha_consulta="2026-08-27T08:00:00+00:00",
    )
    assert v.minutos_demora == 0 and v.motivo is None


def test_datos_reserva_rechaza_pasajeros_vacios():
    with pytest.raises(ValidationError):
        DatosReservaData(
            pnr="ABC123", estado="CONFIRMADA", codigo_vuelo="AN405", fecha_vuelo="2026-08-27",
            pasajeros=[], clase_tarifa="FLEX", equipaje_facturado=1, mascota_en_cabina=False,
            reembolsable=True, canal_compra="WEB",
        )


def test_datos_reserva_ignora_fecha_compra():
    r = DatosReservaData(
        pnr="ABC123", estado="CONFIRMADA", codigo_vuelo="AN405", fecha_vuelo="2026-08-27",
        fecha_compra="2026-07-01",  # campo de carga; se ignora
        pasajeros=[PasajeroData(nombre="Ana", tipo="ADULTO")],
        clase_tarifa="FLEX", equipaje_facturado=1, mascota_en_cabina=False,
        reembolsable=True, canal_compra="WEB",
    )
    assert not hasattr(r, "fecha_compra")
