"""Fixtures de F3: items de DynamoDB de ejemplo. Sin red (LLM y AWS mockeados)."""
from __future__ import annotations

from decimal import Decimal

import pytest


@pytest.fixture
def flight_item() -> dict:
    """Item crudo tal como lo devuelve DynamoDB (numeros como Decimal)."""
    return {
        "codigo_vuelo": "AN405",
        "estado": "DEMORADO",
        "origen": "MEX",
        "destino": "MAD",
        "salida_programada": "2026-08-27T10:00:00+00:00",
        "salida_estimada": "2026-08-27T11:30:00+00:00",
        "minutos_demora": Decimal("90"),
        "puerta": "B12",
        "motivo": "meteorologia",
        "fecha_consulta": "2026-08-27T08:00:00+00:00",
    }


@pytest.fixture
def reservation_item() -> dict:
    return {
        "pnr": "ABC123",
        "estado": "CONFIRMADA",
        "codigo_vuelo": "AN405",
        "fecha_vuelo": "2026-08-27",
        "fecha_compra": "2026-07-15",  # campo de carga; el modelo de respuesta lo ignora
        "pasajeros": [
            {"nombre": "Ana Ruiz", "tipo": "ADULTO", "asiento": "12A"},
            {"nombre": "Leo Ruiz", "tipo": "MENOR", "asiento": "12B"},
        ],
        "clase_tarifa": "FLEX",
        "equipaje_facturado": Decimal("1"),
        "mascota_en_cabina": False,
        "reembolsable": True,
        "canal_compra": "WEB",
    }
