"""``VueloContract``: campos derivados de EstadoVueloData (§5.4.1) y reglas cruzadas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.contracts.flights import VueloContract


def _build(**over):
    base = dict(
        codigo_vuelo="AN405",
        estado="A_TIEMPO",
        origen="MEX",
        destino="MAD",
        salida_programada="2026-08-27T10:00:00+00:00",
        salida_estimada=None,
        minutos_demora=0,
        puerta="B12",
        motivo=None,
        fecha_consulta="2026-08-27T09:00:00+00:00",
    )
    base.update(over)
    return VueloContract(**base)


def test_vuelo_valido(vuelo_valido):
    assert vuelo_valido.codigo_vuelo == "AN405"
    assert vuelo_valido.minutos_demora == 0


@pytest.mark.parametrize("codigo", ["AN40", "AN40555", "BA405", "an405"])
def test_codigo_vuelo_pattern(codigo):
    with pytest.raises(ValidationError):
        _build(codigo_vuelo=codigo)


@pytest.mark.parametrize("iata", ["mex", "MEXX", "M1X", "MX"])
def test_iata_pattern(iata):
    with pytest.raises(ValidationError):
        _build(origen=iata)


def test_fecha_sin_zona_horaria_invalida():
    with pytest.raises(ValidationError, match="ISO 8601 con zona"):
        _build(salida_programada="2026-08-27T10:00:00")


def test_fecha_no_iso_invalida():
    with pytest.raises(ValidationError):
        _build(fecha_consulta="ayer por la tarde")


def test_salida_estimada_none_es_valida():
    assert _build(salida_estimada=None).salida_estimada is None


def test_salida_estimada_con_zona_valida():
    v = _build(
        estado="DEMORADO",
        minutos_demora=30,
        motivo="rotacion",
        salida_estimada="2026-08-27T10:30:00-05:00",
    )
    assert v.salida_estimada.endswith("-05:00")


def test_salida_estimada_sin_zona_invalida():
    with pytest.raises(ValidationError):
        _build(salida_estimada="2026-08-27T10:30:00")


def test_minutos_demora_negativos_invalido():
    with pytest.raises(ValidationError):
        _build(minutos_demora=-1)


# --- reglas cruzadas ---
def test_origen_igual_a_destino():
    with pytest.raises(ValidationError, match="origen y destino"):
        _build(origen="MAD", destino="MAD")


def test_estado_demorado_exige_motivo():
    with pytest.raises(ValidationError, match="exige .motivo."):
        _build(estado="DEMORADO", minutos_demora=15, motivo=None)


def test_estado_cancelado_exige_motivo():
    with pytest.raises(ValidationError, match="exige .motivo."):
        _build(estado="CANCELADO", motivo=None)


def test_motivo_con_estado_a_tiempo_invalido():
    with pytest.raises(ValidationError, match="solo DEMORADO/CANCELADO"):
        _build(estado="A_TIEMPO", motivo="algo")


def test_a_tiempo_con_demora_invalido():
    with pytest.raises(ValidationError, match="A_TIEMPO con minutos_demora"):
        _build(estado="A_TIEMPO", minutos_demora=10)


def test_demorado_sin_minutos_invalido():  # frontera
    with pytest.raises(ValidationError, match="DEMORADO con minutos_demora == 0"):
        _build(estado="DEMORADO", minutos_demora=0, motivo="x")


def test_demorado_valido_completo():
    v = _build(estado="DEMORADO", minutos_demora=45, motivo="meteorologia",
               salida_estimada="2026-08-27T10:45:00+00:00")
    assert v.estado == "DEMORADO" and v.minutos_demora == 45


def test_cancelado_valido():
    v = _build(estado="CANCELADO", motivo="huelga")
    assert v.estado == "CANCELADO"
