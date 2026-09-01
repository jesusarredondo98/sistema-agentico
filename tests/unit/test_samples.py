"""src/logic/samples.py: muestra de «Datos de prueba» (GSIs mockeados)."""
from __future__ import annotations

import random

from src.logic import samples as S

_VUELOS = {
    "MEX": {"salidas": [
        {"codigo_vuelo": "AN1001", "origen": "MEX", "destino": "BOG", "estado": "A_TIEMPO"},
        {"codigo_vuelo": "AN1002", "origen": "MEX", "destino": "MAD", "estado": "DEMORADO"},
        {"codigo_vuelo": "AN1003", "origen": "MEX", "destino": "JFK", "estado": "CANCELADO"},
        {"codigo_vuelo": "AN1004", "origen": "MEX", "destino": "CUN", "estado": "EMBARCANDO"},
    ]},
}
_RES = {
    "AN1002": [
        {"pnr": "AAA111", "codigo_vuelo": "AN1002", "estado": "CONFIRMADA", "clase_tarifa": "FLEX"},
        {"pnr": "BBB222", "codigo_vuelo": "AN1002", "estado": "NO_SHOW", "clase_tarifa": "BASICA"},
    ],
}


def _stub(monkeypatch):
    monkeypatch.setattr(S, "query_flights_by_city",
                        lambda iata, sentido="ambos", limit=60: _VUELOS.get(iata, {}).get(sentido, []))
    monkeypatch.setattr(S, "query_reservations_by_flight",
                        lambda cod, limit=300: _RES.get(cod, []))


def test_muestra_forma_y_campos(monkeypatch):
    _stub(monkeypatch)
    monkeypatch.setattr(S, "_AEROPUERTOS", ["MEX"])
    out = S.sample_datos_prueba(random.Random(1))
    assert set(out) == {"vuelos", "reservas"}
    for v in out["vuelos"]:
        assert set(v) == {"codigo", "ruta", "estado"}
        assert "→" in v["ruta"]
        assert v["estado"] in {"A tiempo", "Demorado", "Cancelado", "Embarcando", "En vuelo", "Aterrizado"}
    for r in out["reservas"]:
        assert set(r) == {"pnr", "estado", "tarifa", "vuelo"}
    # con 4 vuelos MEX salen los 4; hay reservas del AN1002
    assert len(out["vuelos"]) == 4
    assert any(r["vuelo"] == "AN1002" for r in out["reservas"])


def test_muestra_varia_entre_llamadas(monkeypatch):
    _stub(monkeypatch)
    monkeypatch.setattr(S, "_AEROPUERTOS", ["MEX"])
    a = S.sample_datos_prueba(random.Random(1))
    b = S.sample_datos_prueba(random.Random(2))
    # mismo conjunto de vuelos pero el orden/selección de reservas cambia con la semilla
    assert [v["codigo"] for v in a["vuelos"]] != [] and [v["codigo"] for v in b["vuelos"]] != []


def test_gsi_que_falla_no_rompe(monkeypatch):
    def boom(*a, **k): raise RuntimeError("dynamo caído")
    monkeypatch.setattr(S, "query_flights_by_city", boom)
    monkeypatch.setattr(S, "query_reservations_by_flight", boom)
    out = S.sample_datos_prueba(random.Random(1))
    assert out == {"vuelos": [], "reservas": []}
