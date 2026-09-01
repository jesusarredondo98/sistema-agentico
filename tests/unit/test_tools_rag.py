"""buscar_politicas_rag (PRD §5.4.3, §6.3): umbral, NOT_FOUND, sin excepciones."""
from __future__ import annotations

import pytest

from src.logic.rag_index import RagContractTooOld, RagUnavailable
from src.tools._runtime import ToolTimeout
from src.tools.rag import buscar_politicas_rag


class _FakeSearch:
    def __init__(self, rows):
        self._rows = rows

    def metric(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def where(self, *_a, **_k):
        return self

    def to_list(self):
        return self._rows


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def search(self, _vec):
        return _FakeSearch(self._rows)


class _FakeIdx:
    def __init__(self, rows):
        self.table = _FakeTable(rows)
        self.version = "v=test"
        self.manifest = {"version": "v=test"}


def _row(doc_id="POL-MAS-004", cat="MASCOTAS", dist=0.2):
    return {
        "doc_id": doc_id, "titulo": f"Politica {doc_id}", "categoria": cat,
        "fragmento": "Se permite una mascota en cabina por pasajero.",
        "vigencia_desde": "2025-01-01", "_distance": dist, "chunk_index": 0,
    }


@pytest.fixture(autouse=True)
def _stub_embed(monkeypatch):
    monkeypatch.setattr("src.tools.rag.embed_text", lambda q: [0.0] * 8)


def test_devuelve_fragmentos_sobre_umbral(monkeypatch):
    # dist 0.1 -> score 0.9 ; dist 0.5 -> score 0.5 ; dist 0.8 -> score 0.2 (descartado)
    monkeypatch.setattr("src.tools.rag.get_index",
                        lambda: _FakeIdx([_row(dist=0.1), _row("POL-MAS-005", dist=0.5),
                                          _row("POL-MAS-006", dist=0.8)]))
    r = buscar_politicas_rag("¿mascota en cabina?")
    assert r.ok
    assert [x["score"] for x in r.data["resultados"]] == [0.9, 0.5]
    assert r.data["resultados"][0]["doc_id"] == "POL-MAS-004"
    assert r.data["consulta_normalizada"] == "¿mascota en cabina?"


def test_filtra_por_umbral(monkeypatch):
    # dist 0.7 -> score 0.3 < 0.35 -> descartado
    monkeypatch.setattr("src.tools.rag.get_index", lambda: _FakeIdx([_row(dist=0.7)]))
    r = buscar_politicas_rag("algo")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_sin_resultados_es_not_found(monkeypatch):
    monkeypatch.setattr("src.tools.rag.get_index", lambda: _FakeIdx([]))
    r = buscar_politicas_rag("consulta sin match")
    assert not r.ok and r.error.code == "NOT_FOUND"


@pytest.mark.parametrize("consulta", ["xy", "  ", "a" * 501])
def test_input_invalido(consulta, monkeypatch):
    monkeypatch.setattr("src.tools.rag.get_index", lambda: pytest.fail("no debe abrir el indice"))
    r = buscar_politicas_rag(consulta)
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_categoria_invalida_es_input_invalido(monkeypatch):
    monkeypatch.setattr("src.tools.rag.get_index", lambda: pytest.fail("no debe abrir"))
    r = buscar_politicas_rag("pregunta valida", categoria="INVENTADA")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_indice_incoherente_es_upstream_error(monkeypatch):
    def boom():
        raise RagContractTooOld("contract_version 0.9.0 < min 1.0.0")

    monkeypatch.setattr("src.tools.rag.get_index", boom)
    r = buscar_politicas_rag("pregunta")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR" and "incoherente" in r.error.message


def test_indice_no_disponible_es_upstream_error(monkeypatch):
    monkeypatch.setattr("src.tools.rag.get_index",
                        lambda: (_ for _ in ()).throw(RagUnavailable("sin CURRENT")))
    r = buscar_politicas_rag("pregunta")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"


def test_timeout_en_la_consulta(monkeypatch):
    monkeypatch.setattr("src.tools.rag.get_index", lambda: _FakeIdx([_row()]))
    monkeypatch.setattr("src.tools.rag.run_with_timeout",
                        lambda fn, *a, **k: (_ for _ in ()).throw(ToolTimeout("3 s")))
    r = buscar_politicas_rag("pregunta")
    assert not r.ok and r.error.code == "TIMEOUT"


def test_error_inesperado_no_propaga(monkeypatch):
    monkeypatch.setattr("src.tools.rag.get_index", lambda: _FakeIdx([_row()]))
    monkeypatch.setattr("src.tools.rag.embed_text",
                        lambda q: (_ for _ in ()).throw(RuntimeError("bedrock down")))
    r = buscar_politicas_rag("pregunta")
    assert not r.ok and r.error.code == "UPSTREAM_ERROR"
