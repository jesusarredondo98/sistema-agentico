"""obtener_datos_reserva (PRD §5.4.2, §5.4.4): normalizacion, ruta B, presupuesto."""
from __future__ import annotations

import pytest

from src.tools._runtime import ToolTimeout, estimate_tokens
from src.tools.pnr import normalizar_pnr, obtener_datos_reserva


def test_reserva_valida(monkeypatch, reservation_item):
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert r.ok
    assert r.data["pnr"] == "ABC123"
    assert r.data["total_pasajeros"] == 2
    assert "fecha_compra" not in r.data  # el modelo de respuesta lo ignora


@pytest.mark.parametrize("entrada", ["abc123", "ABC 123", "  abc 123 ", "aBc123"])
def test_normalizacion_pnr(monkeypatch, reservation_item, entrada):
    visto = {}

    def fake(pnr):
        visto["pnr"] = pnr
        return reservation_item

    monkeypatch.setattr("src.tools.pnr.get_reservation", fake)
    r = obtener_datos_reserva(entrada)
    assert r.ok and visto["pnr"] == "ABC123"


def test_normalizar_pnr_unitario():
    assert normalizar_pnr("ab c 12") == "ABC12"


@pytest.mark.parametrize("pnr", ["ABC12", "ABC1234", "abc-12", "AB@123"])
def test_input_invalido(monkeypatch, pnr):
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: pytest.fail("no debe leerse"))
    r = obtener_datos_reserva(pnr)
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_no_encontrada(monkeypatch):
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: None)
    r = obtener_datos_reserva("ZZZZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


# --- ruta B (§7.1): corrupcion inyectada en Gold -> UPSTREAM_ERROR, sin traza ---
def test_ruta_b_pasajeros_vacios(monkeypatch, reservation_item):
    reservation_item["pasajeros"] = []
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_ruta_b_clase_tarifa_fuera_del_enum(monkeypatch, reservation_item):
    reservation_item["clase_tarifa"] = "GOLD"
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_ruta_b_campo_obligatorio_ausente(monkeypatch, reservation_item):
    del reservation_item["canal_compra"]
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_error_de_dynamo_no_propaga(monkeypatch):
    monkeypatch.setattr("src.tools.pnr.get_reservation",
                        lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    r = obtener_datos_reserva("ABC123")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_timeout(monkeypatch):
    monkeypatch.setattr("src.tools.pnr.run_with_timeout",
                        lambda fn, *a, **k: (_ for _ in ()).throw(ToolTimeout("3 s")))
    r = obtener_datos_reserva("ABC123")
    assert not r.ok and r.error.code == "TIMEOUT"


# --- presupuesto de <= 450 tokens (§5.4.4, L-6) ---
def _pax(i: int) -> dict:
    return {"nombre": f"Pasajero Numero {i} De Prueba", "tipo": "ADULTO", "asiento": f"{i}A"}


def test_capa_pasajeros_a_9(monkeypatch, reservation_item):
    reservation_item["pasajeros"] = [_pax(i) for i in range(15)]
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert r.ok
    assert len(r.data["pasajeros"]) == 9
    assert r.data["total_pasajeros"] == 15
    assert r.data["pasajeros_truncados"] is True


def test_resultado_dentro_del_presupuesto(monkeypatch, reservation_item):
    reservation_item["pasajeros"] = [_pax(i) for i in range(9)]
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert r.ok and estimate_tokens(r.data) <= 450


def test_red_de_seguridad_de_presupuesto(monkeypatch, reservation_item):
    # 9 pasajeros con nombres desmesurados: aun capado, desborda 450 tokens ->
    # la red de seguridad omite `pasajeros` en vez de devolver algo enorme.
    reservation_item["pasajeros"] = [
        {"nombre": "Nombre Larguisimo " * 20, "tipo": "ADULTO", "asiento": f"{i}A"}
        for i in range(9)
    ]
    monkeypatch.setattr("src.tools.pnr.get_reservation", lambda p: reservation_item)
    r = obtener_datos_reserva("ABC123")
    assert r.ok
    assert "pasajeros" not in r.data
    assert r.data["pasajeros_omitidos_por_presupuesto"] is True
