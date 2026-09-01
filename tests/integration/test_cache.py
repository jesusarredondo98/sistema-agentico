"""F6 -- criterio de salida (PRD §14, §5.3): `cache_read_input_tokens > 0` en la 2.a peticion.

Requiere AWS (`AWS_PROFILE=aeronova`) + `ANTHROPIC_API_KEY` en `.env`. Consume LLM.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_ENV = Path(__file__).resolve().parents[2] / ".env"
if _ENV.is_file():
    for _line in _ENV.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="sin ANTHROPIC_API_KEY; F6 se valida con los unit tests",
)


def test_prefijo_cacheable_supera_1024_tokens():
    """A-84: el prefijo `tools + system` debe superar 1.024 tokens o la cache no se forma (R-14)."""
    import anthropic

    from src.agent.llm_node import _as_langchain_tools
    from src.agent.prompts import SYSTEM_PROMPT

    tools = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.args_schema.model_json_schema(),
        }
        for t in _as_langchain_tools()
    ]
    client = anthropic.Anthropic()
    resp = client.messages.count_tokens(
        model="claude-sonnet-5",
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=[{"role": "user", "content": "x"}],
    )
    # count_tokens incluye el mensaje minimo; el prefijo cacheable es el grueso.
    assert resp.input_tokens > 1024, f"prefijo de solo {resp.input_tokens} tokens (< 1024)"
    print(f"prefijo cacheable ~= {resp.input_tokens} tokens")


@pytest.mark.skipif(
    not (os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID")),
    reason="sin credenciales AWS",
)
def test_cache_read_en_la_segunda_peticion():
    import time
    from handler import lambda_handler

    sid = f"usr_cache_{int(time.time())}"
    base = {"session_id": sid, "employee_id": "EMP_001",
            "message": "¿que dice la politica de equipaje de mano de AeroNova?"}

    r1 = lambda_handler(dict(base), None)
    assert r1["statusCode"] == 200, r1

    r2 = lambda_handler({**base, "message": "¿y para el equipaje facturado?"}, None)
    assert r2["statusCode"] == 200, r2

    cache_read = r2["body"]["usage"]["cache_read_input_tokens"]
    print(f"turno 1 cost={r1['body']['usage']['cost_usd']}  "
          f"turno 2 cache_read={cache_read}  cost={r2['body']['usage']['cost_usd']}")
    assert cache_read > 0, "la cache no se leyo en la 2.a peticion (§5.3, R-14)"
