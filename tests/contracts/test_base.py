"""Reglas de ``DataContract`` (PRD §6A.3): metadatos obligatorios, SemVer, extra=forbid."""
from __future__ import annotations

from typing import ClassVar

import pytest

from src.contracts.base import DataContract


def test_subclase_sin_metadatos_falla():
    with pytest.raises(TypeError, match="faltan metadatos"):

        class Malo(DataContract):
            CONTRACT_NAME: ClassVar[str] = "x"
            # faltan VERSION, OWNER, SLA_HOURS


def test_version_no_semver_falla():
    with pytest.raises(TypeError, match="SemVer"):

        class Malo(DataContract):
            CONTRACT_NAME: ClassVar[str] = "x"
            CONTRACT_VERSION: ClassVar[str] = "1.0"
            CONTRACT_OWNER: ClassVar[str] = "o@e"
            CONTRACT_SLA_HOURS: ClassVar[int] = 24


def test_sla_hours_no_positivo_falla():
    with pytest.raises(TypeError, match="entero positivo"):

        class Malo(DataContract):
            CONTRACT_NAME: ClassVar[str] = "x"
            CONTRACT_VERSION: ClassVar[str] = "1.0.0"
            CONTRACT_OWNER: ClassVar[str] = "o@e"
            CONTRACT_SLA_HOURS: ClassVar[int] = 0


def test_subclase_intermedia_sin_name_se_permite():
    class Intermedia(DataContract):  # sin CONTRACT_NAME propio: no dispara la comprobacion
        pass

    assert issubclass(Intermedia, DataContract)


def test_contrato_valido_expone_metadatos():
    class Bueno(DataContract):
        CONTRACT_NAME: ClassVar[str] = "x.y"
        CONTRACT_VERSION: ClassVar[str] = "2.3.4"
        CONTRACT_OWNER: ClassVar[str] = "o@e"
        CONTRACT_SLA_HOURS: ClassVar[int] = 48

    assert Bueno.contract_metadata() == {
        "name": "x.y",
        "version": "2.3.4",
        "owner": "o@e",
        "sla_hours": 48,
    }
    assert Bueno.contract_major() == 2


def test_extra_forbid(doc_valido_kwargs):
    from src.contracts.corpus import DocumentoNormativoContract

    with pytest.raises(ValueError):
        DocumentoNormativoContract(**doc_valido_kwargs, campo_inventado=1)


def test_str_strip_whitespace(doc_valido_kwargs):
    from src.contracts.corpus import DocumentoNormativoContract

    doc_valido_kwargs["titulo"] = "  Mascotas en cabina de AeroNova  "
    d = DocumentoNormativoContract(**doc_valido_kwargs)
    assert d.titulo == "Mascotas en cabina de AeroNova"
