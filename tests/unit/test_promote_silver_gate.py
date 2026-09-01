"""Puerta de contrato de promote_silver (PRD §6A.3, §6A.4, §7.1): sin red.

Verifica que ``_gate`` acepta lo valido, cuarentena lo invalido con el motivo
estructurado de §6A.4, y que las 4 anomalias de ruta A acaban en cuarentena.
"""
from __future__ import annotations

from pipelines.promote_silver import _gate, _quarantine_row
from src.contracts.reservations import ReservaContract


def _reserva(**over) -> dict:
    base = dict(
        pnr="ABC123",
        estado="CONFIRMADA",
        codigo_vuelo="AN405",
        fecha_vuelo="2026-08-27",
        fecha_compra="2026-07-15",
        pasajeros=[{"nombre": "Ana Ruiz", "tipo": "ADULTO", "asiento": "12A"}],
        clase_tarifa="FLEX",
        equipaje_facturado=1,
        mascota_en_cabina=False,
        reembolsable=True,
        canal_compra="WEB",
    )
    base.update(over)
    return base


def test_gate_acepta_validos_y_cuarentena_invalidos():
    records = [_reserva(pnr="AAA111"), _reserva(pnr="short"), _reserva(pnr="BBB222")]
    accepted, rejects = _gate(records, ReservaContract, "reservations.reserva", "pnr")
    assert [r["pnr"] for r in accepted] == ["AAA111", "BBB222"]
    assert len(rejects) == 1
    rej = rejects[0]
    assert rej["dataset"] == "reservations.reserva"
    assert rej["contract_version"] == "1.0.0"
    assert rej["rule"] == "CONTRACT"
    assert rej["record_key"] == "short"
    assert "pnr" in rej["reason"]
    assert rej["raw"]["pnr"] == "short"
    assert set(rej) == {"rejected_at", "dataset", "contract_version", "rule", "record_key", "reason", "raw"}


def test_ruta_a_tipo1_pnr_longitud():
    _, rej = _gate([_reserva(pnr="ABCDE"), _reserva(pnr="ABCDEFG")], ReservaContract, "d", "pnr")
    assert len(rej) == 2


def test_ruta_a_tipo2_pnr_no_alfanumerico():
    _, rej = _gate([_reserva(pnr="ABC-23")], ReservaContract, "d", "pnr")
    assert len(rej) == 1


def test_ruta_a_tipo4_fecha_vuelo_anterior_a_compra():
    r = _reserva(fecha_vuelo="2026-07-01", fecha_compra="2026-07-15")
    _, rej = _gate([r], ReservaContract, "d", "pnr")
    assert rej and "anterior a fecha_compra" in rej[0]["reason"]


def test_ruta_a_tipo3_orfano_pasa_el_contrato_pero_no_e05():
    # un codigo_vuelo con formato valido pero inexistente PASA el contrato:
    # lo detecta la comprobacion referencial E-05 en promote_silver, no _gate.
    r = _reserva(codigo_vuelo="AN9999")
    accepted, rej = _gate([r], ReservaContract, "d", "pnr")
    assert accepted and not rej


def test_quarantine_row_forma_exacta():
    row = _quarantine_row("x", "1.0.0", "E-02", "POL-MAS-004", "referencia colgante", {"a": 1})
    assert list(row) == ["rejected_at", "dataset", "contract_version", "rule", "record_key", "reason", "raw"]
    assert row["raw"] == {"a": 1}
