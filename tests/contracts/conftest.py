"""Fixtures locales para las pruebas de contrato (PRD §8.1). Sin red."""
from __future__ import annotations

from datetime import date

import pytest

from src.contracts.corpus import DocumentoNormativoContract, sha256_cuerpo
from src.contracts.flights import VueloContract
from src.contracts.reservations import PasajeroContract, ReservaContract

_CUERPO_BASE = (
    "Los animales de compania pequenos pueden viajar en cabina cumpliendo el "
    "peso maximo combinado con su transportin. En vuelos transatlanticos aplica "
    "la excepcion descrita en la normativa de cambios. " * 6
)


def make_cuerpo(*, referencias: list[str] | None = None) -> str:
    cuerpo = _CUERPO_BASE
    for ref in referencias or []:
        cuerpo += f" Ver {ref} para el detalle."
    return cuerpo


@pytest.fixture
def doc_valido_kwargs():
    """kwargs de un DocumentoNormativoContract valido, sin referencias cruzadas."""
    cuerpo = make_cuerpo()
    return dict(
        doc_id="POL-MAS-001",
        titulo="Mascotas en cabina de AeroNova",
        categoria="MASCOTAS",
        vigencia_desde=date(2025, 1, 1),
        vigencia_hasta=None,
        cuerpo=cuerpo,
        referencias=[],
        checksum_cuerpo=sha256_cuerpo(cuerpo),
    )


@pytest.fixture
def doc_valido(doc_valido_kwargs) -> DocumentoNormativoContract:
    return DocumentoNormativoContract(**doc_valido_kwargs)


@pytest.fixture
def vuelo_valido_kwargs():
    return dict(
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


@pytest.fixture
def vuelo_valido(vuelo_valido_kwargs) -> VueloContract:
    return VueloContract(**vuelo_valido_kwargs)


@pytest.fixture
def reserva_valida_kwargs():
    return dict(
        pnr="ABC123",
        estado="CONFIRMADA",
        codigo_vuelo="AN405",
        fecha_vuelo="2026-08-27",
        fecha_compra="2026-07-15",
        pasajeros=[PasajeroContract(nombre="Ana Ruiz", tipo="ADULTO", asiento="12A")],
        clase_tarifa="FLEX",
        equipaje_facturado=1,
        mascota_en_cabina=False,
        reembolsable=True,
        canal_compra="WEB",
    )


@pytest.fixture
def reserva_valida(reserva_valida_kwargs) -> ReservaContract:
    return ReservaContract(**reserva_valida_kwargs)
