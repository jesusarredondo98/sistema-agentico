"""``ReservaContract`` / ``PasajeroContract``: campos de DatosReservaData (§5.4.2) y reglas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.contracts.reservations import MAX_PASAJEROS, PasajeroContract, ReservaContract


def _pax(nombre="Ana Ruiz", tipo="ADULTO", asiento="12A"):
    return PasajeroContract(nombre=nombre, tipo=tipo, asiento=asiento)


def _build(**over):
    base = dict(
        pnr="ABC123",
        estado="CONFIRMADA",
        codigo_vuelo="AN405",
        fecha_vuelo="2026-08-27",
        fecha_compra="2026-07-15",
        pasajeros=[_pax()],
        clase_tarifa="FLEX",
        equipaje_facturado=1,
        mascota_en_cabina=False,
        reembolsable=True,
        canal_compra="WEB",
    )
    base.update(over)
    return ReservaContract(**base)


def test_reserva_valida(reserva_valida):
    assert reserva_valida.pnr == "ABC123"
    assert len(reserva_valida.pasajeros) == 1


@pytest.mark.parametrize("pnr", ["abc123", "ABC12", "ABC1234", "AB C12", "ABC-12"])
def test_pnr_pattern(pnr):
    with pytest.raises(ValidationError):
        _build(pnr=pnr)


def test_codigo_vuelo_pattern():
    with pytest.raises(ValidationError):
        _build(codigo_vuelo="XY1")


def test_fecha_vuelo_no_iso():
    with pytest.raises(ValidationError, match="no es una fecha ISO 8601"):
        _build(fecha_vuelo="27/08/2026")


def test_fecha_compra_no_iso():
    with pytest.raises(ValidationError, match="fecha_compra .* no es una fecha ISO 8601"):
        _build(fecha_compra="ayer")


def test_fecha_vuelo_anterior_a_compra_invalida():  # anomalia ruta A tipo 4 (§7.1)
    with pytest.raises(ValidationError, match="anterior a fecha_compra"):
        _build(fecha_vuelo="2026-07-01", fecha_compra="2026-07-15")


def test_fecha_vuelo_igual_a_compra_valida():  # frontera
    r = _build(fecha_vuelo="2026-07-15", fecha_compra="2026-07-15")
    assert r.fecha_vuelo == r.fecha_compra


def test_sin_pasajeros_invalido():
    with pytest.raises(ValidationError):
        _build(pasajeros=[])


def test_pasajeros_por_encima_del_maximo():
    with pytest.raises(ValidationError):
        _build(pasajeros=[_pax(nombre=f"P{i}") for i in range(MAX_PASAJEROS + 1)])


def test_pasajeros_en_la_frontera():  # 9 exactos
    r = _build(pasajeros=[_pax(nombre=f"P{i}", tipo="ADULTO") for i in range(MAX_PASAJEROS)])
    assert len(r.pasajeros) == MAX_PASAJEROS


def test_equipaje_negativo_invalido():
    with pytest.raises(ValidationError):
        _build(equipaje_facturado=-1)


def test_equipaje_por_encima_del_tope():
    with pytest.raises(ValidationError):
        _build(equipaje_facturado=21)


def test_pasajero_nombre_vacio_invalido():
    with pytest.raises(ValidationError):
        _pax(nombre="")


def test_pasajero_tipo_invalido():
    with pytest.raises(ValidationError):
        _pax(tipo="BEBE")


def test_pasajero_asiento_opcional():
    assert _pax(asiento=None).asiento is None


def test_pasajero_extra_forbid():
    with pytest.raises(ValidationError):
        PasajeroContract(nombre="Ana", tipo="ADULTO", asiento=None, fumador=False)


# --- regla cruzada: menor/infante requiere adulto ---
def test_menor_con_adulto_ok():
    r = _build(pasajeros=[_pax(tipo="ADULTO"), _pax(nombre="Leo", tipo="MENOR", asiento="12B")])
    assert {p.tipo for p in r.pasajeros} == {"ADULTO", "MENOR"}


def test_infante_sin_adulto_invalido():
    with pytest.raises(ValidationError, match="sin ningun ADULTO"):
        _build(pasajeros=[_pax(nombre="Bebe", tipo="INFANTE", asiento=None)])


def test_menor_sin_adulto_invalido():
    with pytest.raises(ValidationError, match="sin ningun ADULTO"):
        _build(pasajeros=[_pax(nombre="Leo", tipo="MENOR", asiento="1A")])


@pytest.mark.parametrize("estado", ["CONFIRMADA", "CANCELADA", "EN_ESPERA", "VOLADA", "NO_SHOW"])
def test_estados_validos(estado):
    assert _build(estado=estado).estado == estado


@pytest.mark.parametrize("canal", ["WEB", "MOSTRADOR", "AGENCIA", "CALL_CENTER"])
def test_canales_validos(canal):
    assert _build(canal_compra=canal).canal_compra == canal
