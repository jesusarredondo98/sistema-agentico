"""``DocumentoNormativoContract``: las 5 validaciones cruzadas de §6A.3.

Cada regla con caso valido, invalido y de frontera.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from src.contracts.corpus import (
    DocumentoNormativoContract,
    normalizar_cuerpo,
    sha256_cuerpo,
)
from tests.contracts.conftest import make_cuerpo


def _build(**over):
    cuerpo = over.pop("cuerpo", None) or make_cuerpo(referencias=over.get("referencias"))
    base = dict(
        doc_id="POL-MAS-001",
        titulo="Mascotas en cabina de AeroNova",
        categoria="MASCOTAS",
        vigencia_desde=date(2025, 1, 1),
        cuerpo=cuerpo,
        referencias=[],
        checksum_cuerpo=sha256_cuerpo(cuerpo),
    )
    base.update(over)
    if "cuerpo" in over and "checksum_cuerpo" not in over:
        base["checksum_cuerpo"] = sha256_cuerpo(base["cuerpo"])
    return DocumentoNormativoContract(**base)


# --- caso valido base ---
def test_documento_valido(doc_valido):
    assert doc_valido.doc_id == "POL-MAS-001"
    assert doc_valido.idioma == "es"


# --- campo: doc_id / titulo / cuerpo (pattern y longitudes) ---
@pytest.mark.parametrize("doc_id", ["POL-XXX-001", "POL-MAS-1", "pol-mas-001", "POL-MAS-0011"])
def test_doc_id_pattern_invalido(doc_id):
    with pytest.raises(ValidationError):
        _build(doc_id=doc_id, categoria="MASCOTAS")


def test_titulo_demasiado_corto():
    with pytest.raises(ValidationError):
        _build(titulo="corto")


def test_cuerpo_por_debajo_del_minimo():
    with pytest.raises(ValidationError):
        _build(cuerpo="x" * 399)


def test_cuerpo_en_la_frontera_minima():
    cuerpo = "a" * 400
    d = _build(cuerpo=cuerpo, checksum_cuerpo=sha256_cuerpo(cuerpo))
    assert len(d.cuerpo) == 400


def test_checksum_pattern_invalido():
    with pytest.raises(ValidationError):
        _build(checksum_cuerpo="ZZZ")


# --- regla 1: prefijo doc_id <-> categoria ---
def test_regla_prefijo_categoria_ok():
    d = _build(doc_id="POL-EQU-010", categoria="EQUIPAJE")
    assert d.categoria == "EQUIPAJE"


def test_regla_prefijo_categoria_incoherente():
    with pytest.raises(ValidationError, match="implica categoria"):
        _build(doc_id="POL-MAS-002", categoria="EQUIPAJE")


# --- regla 2: vigencia_hasta posterior a vigencia_desde ---
def test_regla_vigencia_hasta_posterior_ok():
    d = _build(vigencia_desde=date(2024, 1, 1), vigencia_hasta=date(2024, 1, 2))
    assert d.vigencia_hasta > d.vigencia_desde


def test_regla_vigencia_hasta_igual_es_invalida():  # frontera
    with pytest.raises(ValidationError, match="posterior"):
        _build(vigencia_desde=date(2024, 1, 1), vigencia_hasta=date(2024, 1, 1))


def test_regla_vigencia_hasta_anterior_es_invalida():
    with pytest.raises(ValidationError, match="posterior"):
        _build(vigencia_desde=date(2024, 6, 1), vigencia_hasta=date(2024, 1, 1))


# --- regla 3: vigencia_desde no futura ---
def test_regla_vigencia_desde_hoy_es_valida():  # frontera
    d = _build(vigencia_desde=date.today())
    assert d.vigencia_desde == date.today()


def test_regla_vigencia_desde_futura_invalida():
    with pytest.raises(ValidationError, match="futura"):
        _build(vigencia_desde=date.today() + timedelta(days=1))


# --- regla 4: referencias == POL-XXX-NNN extraidos del cuerpo ---
def test_regla_referencias_coinciden():
    d = _build(referencias=["POL-CAM-002", "POL-REE-004"])
    assert set(d.referencias) == {"POL-CAM-002", "POL-REE-004"}


def test_regla_referencia_declarada_pero_no_en_cuerpo():
    cuerpo = make_cuerpo(referencias=["POL-CAM-002"])
    with pytest.raises(ValidationError, match="declaradas de mas"):
        _build(cuerpo=cuerpo, referencias=["POL-CAM-002", "POL-REE-009"])


def test_regla_referencia_en_cuerpo_pero_no_declarada():
    cuerpo = make_cuerpo(referencias=["POL-CAM-002", "POL-MEN-003"])
    with pytest.raises(ValidationError, match="sin declarar"):
        _build(cuerpo=cuerpo, referencias=["POL-CAM-002"])


def test_regla_autoreferencia_del_doc_id_no_cuenta():  # frontera
    cuerpo = make_cuerpo() + " Este mismo documento POL-MAS-001 lo regula."
    d = _build(cuerpo=cuerpo, referencias=[])
    assert d.referencias == []


# --- regla 5: checksum ---
def test_regla_checksum_no_coincide():
    with pytest.raises(ValidationError, match="checksum"):
        _build(checksum_cuerpo="a" * 64)


def test_regla_checksum_insensible_a_espacios_de_borde_de_linea():
    cuerpo = make_cuerpo()
    d = _build(cuerpo=cuerpo + "   \n", checksum_cuerpo=sha256_cuerpo(cuerpo))
    assert d.checksum_cuerpo == sha256_cuerpo(cuerpo)


# --- normalizacion ---
def test_normalizar_cuerpo_idempotente():
    t = "linea 1  \r\nlinea 2\t\n\n  borde  "
    once = normalizar_cuerpo(t)
    assert normalizar_cuerpo(once) == once
    assert "\r" not in once
    assert not once.endswith(" ")
