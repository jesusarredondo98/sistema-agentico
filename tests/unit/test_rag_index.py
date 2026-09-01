"""src/logic/rag_index.py: guard de version de contrato (R-11) y refresco (R-10)."""
from __future__ import annotations

import json

import lancedb
import pytest

from src.logic import rag_index as ri


def _build_local_index(tmp_path, contract_version: str):
    db = lancedb.connect(str(tmp_path))
    db.create_table(ri.TABLE_NAME, data=[{
        "vector": [0.1] * 8, "doc_id": "POL-MAS-001", "titulo": "t",
        "categoria": "MASCOTAS", "vigencia_desde": "2025-01-01",
        "fragmento": "x", "chunk_index": 0,
    }])
    (tmp_path / "_manifest.json").write_text(json.dumps({
        "version": "v=20260828T000000Z", "contract_version": contract_version,
        "counts": {"chunks": 1},
    }))


def test_guard_rechaza_major_inferior(tmp_path, monkeypatch):
    _build_local_index(tmp_path, "0.9.0")
    monkeypatch.setattr(ri, "get_settings", lambda: type("C", (), {"rag_contract_version_min": "1.0.0"})())
    with pytest.raises(ri.RagContractTooOld):
        ri._open_local(tmp_path)


def test_guard_acepta_major_igual_o_superior(tmp_path, monkeypatch):
    _build_local_index(tmp_path, "1.4.2")
    monkeypatch.setattr(ri, "get_settings", lambda: type("C", (), {"rag_contract_version_min": "1.0.0"})())
    idx = ri._open_local(tmp_path)
    assert idx.version == "v=20260828T000000Z"
    assert idx.table.count_rows() == 1


@pytest.fixture(autouse=True)
def _reset():
    ri.reset_cache()
    yield
    ri.reset_cache()


def test_refresh_sin_cache_carga(monkeypatch):
    llamado = {"n": 0}
    monkeypatch.setattr(ri, "load_index", lambda force=False: llamado.__setitem__("n", llamado["n"] + 1))
    assert ri.refresh_if_changed() is True
    assert llamado["n"] == 1


def test_refresh_sin_cambio_no_recarga(monkeypatch):
    idx = ri.LoadedIndex(version="v=AAA", table=None, manifest={"version": "v=AAA"})
    ri._cache = idx
    monkeypatch.setattr(ri, "read_current", lambda: f"gold/rag/{ri.TABLE_NAME}.lance/v=AAA")
    monkeypatch.setattr(ri, "load_index", lambda force=False: pytest.fail("no debe recargar"))
    assert ri.refresh_if_changed() is False


def test_refresh_con_cambio_recarga(monkeypatch):
    ri._cache = ri.LoadedIndex(version="v=AAA", table=None, manifest={"version": "v=AAA"})
    monkeypatch.setattr(ri, "read_current", lambda: f"gold/rag/{ri.TABLE_NAME}.lance/v=BBB")
    recargas = {"n": 0}
    monkeypatch.setattr(ri, "load_index", lambda force=False: recargas.__setitem__("n", recargas["n"] + 1))
    assert ri.refresh_if_changed() is True
    assert recargas["n"] == 1


def test_refresh_indice_no_disponible_no_rompe(monkeypatch):
    ri._cache = ri.LoadedIndex(version="v=AAA", table=None, manifest={"version": "v=AAA"})
    monkeypatch.setattr(ri, "read_current", lambda: (_ for _ in ()).throw(ri.RagUnavailable("sin CURRENT")))
    assert ri.refresh_if_changed() is False
