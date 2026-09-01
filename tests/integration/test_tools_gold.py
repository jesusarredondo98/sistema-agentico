"""F3 -- verificacion contra DynamoDB REAL (PRD §14, §7.1 ruta B).

Requiere AWS (`AWS_PROFILE=aeronova`) y las tablas sembradas por F2b. Complementa
a los unit tests: comprueba el camino boto3 real (Decimal, GetItem) y que un
registro de **ruta B** inyectado en Gold produce `ok=False code=UPSTREAM_ERROR`,
no una traza.

Ejecutar:  AWS_PROFILE=aeronova AWS_REGION=us-east-1 pytest tests/integration/test_tools_gold.py
"""
from __future__ import annotations

import os

import boto3
import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID")),
    reason="sin credenciales AWS; F3 se valida con los unit tests (moto)",
)

REGION = os.environ.get("AWS_REGION", "us-east-1")
_RB_PNR = "ZZZ001"  # 6 alfanumericos: pasa la validacion de entrada de la tool


@pytest.fixture(scope="module")
def ruta_b_item():
    """Inyecta una reserva corrupta (pasajeros vacios) directamente en Gold y la retira."""
    tbl = boto3.resource("dynamodb", region_name=REGION).Table("aeronova-reservations")
    tbl.put_item(Item={
        "pnr": _RB_PNR, "estado": "CONFIRMADA", "codigo_vuelo": "AN400",
        "fecha_vuelo": "2026-09-01", "fecha_compra": "2026-08-01", "pasajeros": [],
        "clase_tarifa": "FLEX", "equipaje_facturado": 1, "mascota_en_cabina": False,
        "reembolsable": True, "canal_compra": "WEB",
    })
    yield _RB_PNR
    tbl.delete_item(Key={"pnr": _RB_PNR})


def test_vuelo_real_ok():
    from src.tools.flights import consultar_estado_vuelo

    # AN1001 existe en el conjunto sembrado (perfil dev, seed 42)
    r = consultar_estado_vuelo("AN1001")
    assert r.ok and r.data["codigo_vuelo"] == "AN1001"
    assert r.data["minutos_demora"] == int(r.data["minutos_demora"])  # Decimal -> int


def test_pnr_inexistente_not_found():
    from src.tools.pnr import obtener_datos_reserva

    r = obtener_datos_reserva("ZZZZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_ruta_b_real_upstream_error(ruta_b_item):
    from src.tools.pnr import obtener_datos_reserva

    r = obtener_datos_reserva(ruta_b_item)
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"
    assert "invalido" in r.error.message
