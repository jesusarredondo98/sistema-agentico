"""src/logic/embeddings.py: Titan V2, dimension 1024, reintento exponencial. Sin red."""
from __future__ import annotations

import json

import pytest
from botocore.exceptions import ClientError

from src.logic import embeddings as em


class _FakeBody:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b


def _throttle():
    return ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "InvokeModel")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("src.logic.embeddings.time.sleep", lambda *_a: None)


def test_embed_text_ok(monkeypatch):
    class C:
        def invoke_model(self, **_k):
            return {"body": _FakeBody({"embedding": [0.1] * em.EMBED_DIM})}

    monkeypatch.setattr(em, "_client", lambda: C())
    v = em.embed_text("hola")
    assert len(v) == em.EMBED_DIM


def test_embed_text_reintenta_ante_throttling(monkeypatch):
    calls = {"n": 0}

    class C:
        def invoke_model(self, **_k):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _throttle()
            return {"body": _FakeBody({"embedding": [0.2] * em.EMBED_DIM})}

    monkeypatch.setattr(em, "_client", lambda: C())
    v = em.embed_text("hola")
    assert calls["n"] == 3 and len(v) == em.EMBED_DIM


def test_embed_text_no_reintenta_errores_no_throttle(monkeypatch):
    class C:
        def invoke_model(self, **_k):
            raise ClientError({"Error": {"Code": "ValidationException", "Message": "bad"}}, "InvokeModel")

    monkeypatch.setattr(em, "_client", lambda: C())
    with pytest.raises(ClientError):
        em.embed_text("hola")


def test_embed_text_rechaza_dimension_incorrecta(monkeypatch):
    class C:
        def invoke_model(self, **_k):
            return {"body": _FakeBody({"embedding": [0.1] * 512})}

    monkeypatch.setattr(em, "_client", lambda: C())
    with pytest.raises(ValueError, match="512 dims"):
        em.embed_text("hola")


def test_embed_batch_conserva_orden(monkeypatch):
    monkeypatch.setattr(em, "embed_text", lambda t: [float(len(t))] * em.EMBED_DIM)
    out = em.embed_batch(["a", "bb", "ccc"])
    assert [v[0] for v in out] == [1.0, 2.0, 3.0]


def test_embed_batch_vacio():
    assert em.embed_batch([]) == []
