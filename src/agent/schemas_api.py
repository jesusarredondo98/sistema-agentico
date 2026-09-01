"""Contratos HTTP del handler (PRD §4.1, §4.2, §4.3).

`ChatRequest` valida la peticion en el handler **antes de tocar el grafo**, con
`extra="forbid"`. `build_response` / `build_error` producen los cuerpos JSON
exactos de §4.2 / §4.3.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.logic.limits import L1_MAX_CHARS, L1_MIN_CHARS


# --------------------------------------------------------------------------- #
# §4.1 Peticion
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    employee_id: str = Field(pattern=r"^EMP_[0-9]{3,6}$")
    message: str = Field(min_length=L1_MIN_CHARS, max_length=L1_MAX_CHARS)

    @field_validator("message")
    @classmethod
    def _no_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("el mensaje no puede ser solo espacios")
        return v


# --------------------------------------------------------------------------- #
# §4.3 Error
# --------------------------------------------------------------------------- #
ErrorCode = Literal[
    "INVALID_REQUEST", "INPUT_TOO_LARGE", "SESSION_TURN_LIMIT", "SESSION_BUDGET_EXCEEDED",
    "SESSION_FORBIDDEN", "LLM_UPSTREAM_ERROR", "LLM_RATE_LIMITED", "INTERNAL_ERROR",
]

# code -> HTTP status
ERROR_STATUS: dict[str, int] = {
    "INVALID_REQUEST": 400,
    "INPUT_TOO_LARGE": 400,
    "SESSION_TURN_LIMIT": 429,
    "SESSION_BUDGET_EXCEEDED": 429,
    "SESSION_FORBIDDEN": 403,
    "LLM_UPSTREAM_ERROR": 502,
    "LLM_RATE_LIMITED": 503,
    "INTERNAL_ERROR": 500,
}


def build_error(code: str, message: str, request_id: str) -> dict:
    return {
        "statusCode": ERROR_STATUS.get(code, 500),
        "body": {"error": {"code": code, "message": message, "request_id": request_id}},
    }


# --------------------------------------------------------------------------- #
# §4.2 Respuesta correcta
# --------------------------------------------------------------------------- #
def build_response(
    *,
    session_id: str,
    reply: str,
    tools_used: list[dict],
    tool_rounds: int,
    finish_reason: str,
    usage: dict,
    cost_usd: float,
    session_turn: int,
    turn_limit: int,
    cost_accumulated: float,
    cost_limit: float,
    truncated: bool,
    messages_dropped: int,
    request_id: str,
    latency_ms: int,
    charts: list | None = None,
) -> dict:
    return {
        "statusCode": 200,
        "body": {
            "session_id": session_id,
            "reply": reply,
            "tools_used": tools_used,
            "charts": charts or [],  # graficas deterministas de campos de tools (§10.6b, cliente)
            "tool_rounds": tool_rounds,
            "finish_reason": finish_reason,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                "cost_usd": round(cost_usd, 6),
            },
            "session": {
                "turn": session_turn,
                "turn_limit": turn_limit,
                "cost_usd_accumulated": round(cost_accumulated, 6),
                "cost_usd_limit": cost_limit,
            },
            "context": {
                "truncated": truncated,
                "messages_dropped": messages_dropped,
            },
            "request_id": request_id,
            "latency_ms": latency_ms,
        },
    }


def to_proxy(resp: dict) -> dict:
    """Adapta ``{statusCode, body: dict}`` al contrato AWS_PROXY de API Gateway REST.

    El handler y sus pruebas trabajan con el cuerpo como dict (§4.2/§4.3); la
    integracion proxy exige ``body`` como cadena JSON y un ``headers`` explicito.

    La respuesta real tambien lleva ``Access-Control-Allow-Origin`` (§2.3, A-105):
    el preflight OPTIONS lo fija API Gateway, pero el navegador exige la cabecera
    tambien en la respuesta del POST o bloquea su lectura. El origen sale de
    ``UI_ORIGIN`` (Terraform); nunca ``*``. Vacio en local -> no se anade.
    """
    from src.config import get_settings

    body = resp["body"]
    headers = {"Content-Type": "application/json"}
    origin = get_settings().ui_origin
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    return {
        "statusCode": resp["statusCode"],
        "headers": headers,
        "body": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False),
        "isBase64Encoded": False,
    }


def synthetic_response(session_id: str, request_id: str, session_turn: int) -> dict:
    """Respuesta de `dry_run` (§8.4): contrato de §4.2 sin invocar al modelo."""
    return build_response(
        session_id=session_id,
        reply="[dry_run] respuesta sintetica: no se invoco al modelo.",
        tools_used=[],
        tool_rounds=0,
        finish_reason="end_turn",
        usage={"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0},
        cost_usd=0.0,
        session_turn=session_turn,
        turn_limit=50,
        cost_accumulated=0.0,
        cost_limit=0.25,
        truncated=False,
        messages_dropped=0,
        request_id=request_id,
        latency_ms=0,
    )
