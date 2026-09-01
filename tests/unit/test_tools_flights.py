"""consultar_estado_vuelo (PRD §5.4.1): sobre uniforme, sin excepciones al LLM."""
from __future__ import annotations

import pytest

from src.tools._runtime import ToolTimeout
from src.tools.flights import consultar_estado_vuelo


def test_vuelo_valido(monkeypatch, flight_item):
    monkeypatch.setattr("src.tools.flights.get_flight", lambda c: flight_item)
    r = consultar_estado_vuelo("AN405")
    assert r.ok and r.error is None
    assert r.data["codigo_vuelo"] == "AN405"
    assert r.data["estado"] == "DEMORADO"
    assert r.data["minutos_demora"] == 90  # Decimal -> int


def test_vuelo_valido_omite_nulls(monkeypatch, flight_item):
    flight_item["motivo"] = None
    flight_item["salida_estimada"] = None
    monkeypatch.setattr("src.tools.flights.get_flight", lambda c: flight_item)
    r = consultar_estado_vuelo("AN405")
    assert "motivo" not in r.data and "salida_estimada" not in r.data


@pytest.mark.parametrize("codigo", ["AN12", "AN12345", "BA405", "an405", "AN 405", ""])
def test_input_invalido(monkeypatch, codigo):
    monkeypatch.setattr("src.tools.flights.get_flight", lambda c: pytest.fail("no debe leerse"))
    r = consultar_estado_vuelo(codigo)
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_no_encontrado(monkeypatch):
    monkeypatch.setattr("src.tools.flights.get_flight", lambda c: None)
    r = consultar_estado_vuelo("AN9999")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_registro_corrupto_estado_invalido(monkeypatch, flight_item):
    flight_item["estado"] = "DESPEGANDO"  # fuera del enum
    monkeypatch.setattr("src.tools.flights.get_flight", lambda c: flight_item)
    r = consultar_estado_vuelo("AN405")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_registro_corrupto_campo_ausente(monkeypatch, flight_item):
    del flight_item["origen"]
    monkeypatch.setattr("src.tools.flights.get_flight", lambda c: flight_item)
    r = consultar_estado_vuelo("AN405")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_error_de_dynamo_no_propaga(monkeypatch):
    def boom(c):
        raise RuntimeError("throttled")

    monkeypatch.setattr("src.tools.flights.get_flight", boom)
    r = consultar_estado_vuelo("AN405")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_timeout(monkeypatch):
    def _raise():
        raise ToolTimeout("no respondio en 3 s")

    monkeypatch.setattr("src.tools.flights.run_with_timeout", lambda fn, *a, **k: _raise())
    r = consultar_estado_vuelo("AN405")
    assert not r.ok and r.error.code == "TIMEOUT"
