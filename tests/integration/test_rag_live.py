"""F4 -- verificacion contra el indice RAG REAL en S3 (PRD §14, §6.3, §6A.5).

Requiere AWS (`AWS_PROFILE=aeronova`) y un indice ya promovido por
`pipelines.build_gold_rag`. Complementa a los unit tests: consulta real contra
LanceDB descargado de S3 y rollback de `CURRENT` de ida y vuelta.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID")),
    reason="sin credenciales AWS; F4 se valida con los unit tests (moto)",
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    from src.logic import rag_index

    rag_index.reset_cache()
    yield
    rag_index.reset_cache()


def test_consulta_real_sobre_umbral():
    from src.tools.rag import buscar_politicas_rag

    r = buscar_politicas_rag("limite de peso del equipaje de mano", "EQUIPAJE")
    assert r.ok, r.error
    assert r.data["resultados"]
    assert all(f["score"] >= 0.35 for f in r.data["resultados"])
    assert r.data["resultados"][0]["categoria"] == "EQUIPAJE"


def test_consulta_sin_sentido_es_not_found():
    from src.tools.rag import buscar_politicas_rag

    r = buscar_politicas_rag("plato volador antigravedad para viajar a marte")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_rollback_ida_y_vuelta():
    from pipelines._lake import lake_bucket, s3
    from scripts.rollback_rag import current, list_versions

    bucket = lake_bucket()
    versiones = list_versions(bucket)
    if len(versiones) < 2:
        pytest.skip("hacen falta >= 2 versiones para probar el rollback")

    original = current(bucket)
    anterior = next(v for v in versiones if v not in original)
    try:
        s3().put_object(Bucket=bucket, Key="gold/rag/CURRENT",
                        Body=f"gold/rag/politicas.lance/{anterior}".encode())
        assert current(bucket).endswith(anterior)
        s3().put_object(Bucket=bucket, Key="gold/rag/CURRENT", Body=original.encode())
        assert current(bucket) == original
    finally:
        s3().put_object(Bucket=bucket, Key="gold/rag/CURRENT", Body=original.encode())
