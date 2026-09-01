"""F1 -- criterio de salida (PRD §14).

Una peticion **real** a ``claude-sonnet-5`` responde **sin 400**, y el cuerpo
HTTP saliente **no lleva** ``temperature`` / ``top_p`` / ``top_k`` /
``budget_tokens`` (§5.3, R-01).

Se ejecuta contra la API real. Requiere ``ANTHROPIC_API_KEY`` en el entorno o en
un ``.env`` en la raiz del repo (gitignored; la clave nunca se hardcodea).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx2
import pytest
from langchain_core.messages import AIMessage, HumanMessage

# --- Cargar .env local si existe, sin exponer el valor ---
_ENV = Path(__file__).resolve().parents[2] / ".env"
if _ENV.is_file():
    for _line in _ENV.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY no disponible; F1 necesita la API real",
)

_SAMPLING_KEYS = ("temperature", "top_p", "top_k", "budget_tokens")


@pytest.fixture
def captured_bodies(monkeypatch):
    """Intercepta el cuerpo JSON de cada POST a /v1/messages sin bloquearlo."""
    bodies: list[dict] = []
    original_send = httpx2.Client.send

    def recording_send(self, request, **kwargs):
        if request.url.path.endswith("/v1/messages"):
            try:
                bodies.append(json.loads(request.read()))
            except Exception:  # pragma: no cover - captura best-effort
                pass
        return original_send(self, request, **kwargs)

    monkeypatch.setattr(httpx2.Client, "send", recording_send)
    return bodies


def test_peticion_real_sin_400_y_sin_parametros_de_sampling(captured_bodies):
    from src.agent.llm_node import llm_node

    out = llm_node(
        {"messages": [HumanMessage("Capital de Francia. Responde en una palabra.")]}
    )

    # 1 - Respondio: un AIMessage con texto (si hubiera sido 400, invoke habria
    #     lanzado anthropic.BadRequestError y el test fallaria aqui).
    msg = out["messages"][-1]
    assert isinstance(msg, AIMessage)
    assert isinstance(msg.content, str) and msg.content.strip()

    # 2 - Se capturo la peticion real saliente.
    assert captured_bodies, "no se intercepto ninguna peticion a /v1/messages"
    body = captured_bodies[-1]

    # 3 - Modelo exacto, sin sufijo de fecha (§5.3, I-02).
    assert body["model"] == "claude-sonnet-5"

    # 4 - NINGUN parametro de sampling en el cuerpo saliente (§5.3, R-01).
    presentes = [k for k in _SAMPLING_KEYS if k in body]
    assert not presentes, f"parametros prohibidos en la peticion: {presentes}"
    #     Cinturon: tampoco anidados en ningun sitio del cuerpo.
    serialized = json.dumps(body)
    for k in _SAMPLING_KEYS:
        assert f'"{k}"' not in serialized, f"{k} aparece anidado: {serialized}"

    # 5 - thinking desactivado explicitamente (§5.3).
    assert body.get("thinking") == {"type": "disabled"}

    # 6 - max_tokens fijado a 1024 (§2.7, §5.3).
    assert body["max_tokens"] == 1024
