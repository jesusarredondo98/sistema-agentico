"""Lectura y escritura del historial conversacional en DynamoDB (PRD §4.5).

Cuatro detalles que fallan en silencio si se descuidan:
- `sk` = ``MSG#`` + contador de **8 digitos con ceros** (orden lexicografico).
- `expires_at` epoch en **segundos** (numero); DynamoDB ignora los TTL en ms.
- carga con ``Query`` + ``ScanIndexForward=False`` + ``Limit`` + invertir; **nunca ``Scan``**.
- la escritura va **despues** de responder; un fallo se registra pero no rompe el turno.

Comprobacion de propiedad de sesion (hallazgo 13): si el item ``STATE`` existe y
su ``employee_id`` no coincide con el de la peticion -> ``SessionForbidden``.
"""
from __future__ import annotations

import functools
import json
import logging
import time
from typing import Iterable

import boto3
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from src.config import get_settings

_log = logging.getLogger("aeronova.memory")

STATE_SK = "STATE"
MSG_PREFIX = "MSG#"


class SessionForbidden(Exception):
    """El `employee_id` de la peticion no coincide con el duenno de la sesion (403)."""


@functools.lru_cache(maxsize=1)
def _table():
    cfg = get_settings()
    return boto3.resource("dynamodb", region_name=cfg.aws_region).Table(cfg.memory_table)


# --------------------------------------------------------------------------- #
# Conversion mensaje <-> item
# --------------------------------------------------------------------------- #
def _msg_to_attrs(m: BaseMessage) -> dict:
    if isinstance(m, HumanMessage):
        return {"role": "human", "content": _text(m.content)}
    if isinstance(m, ToolMessage):
        return {"role": "tool", "content": _text(m.content),
                "tool_call_id": m.tool_call_id, "name": m.name or ""}
    if isinstance(m, AIMessage):
        attrs = {"role": "ai", "content": _text(m.content)}
        if m.tool_calls:
            attrs["tool_calls"] = json.dumps(m.tool_calls, ensure_ascii=False, default=str)
        return attrs
    return {"role": "ai", "content": _text(getattr(m, "content", ""))}


def _attrs_to_msg(item: dict) -> BaseMessage:
    role, content = item.get("role"), item.get("content", "")
    if role == "human":
        return HumanMessage(content)
    if role == "tool":
        return ToolMessage(content=content, tool_call_id=item.get("tool_call_id", ""),
                           name=item.get("name") or None)
    tc = item.get("tool_calls")
    return AIMessage(content=content, tool_calls=json.loads(tc) if tc else [])


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def sanitize_history(msgs: list[BaseMessage]) -> list[BaseMessage]:
    """Deja el historial en un estado que Anthropic acepta (§5.1, R-07).

    La ventana de `history_window_messages` puede empezar a mitad de un
    intercambio de herramienta. Si eso pasa, Anthropic responde **400** (
    "tool_result sin tool_use previo" / "tool_use sin respuesta"), y el handler
    lo mapea a INTERNAL_ERROR. Reglas que se imponen aqui:

    - el historial empieza en un `HumanMessage`;
    - cada `AIMessage` con `tool_calls` va seguido de un `ToolMessage` por cada
      id; si la ventana lo corta, se descarta desde ahi;
    - se descartan `AIMessage` vacios sin `tool_calls` (Anthropic tambien 400).
    """
    i = 0
    while i < len(msgs) and not isinstance(msgs[i], HumanMessage):
        i += 1  # tira de mensajes sueltos al principio (tool_result huerfano, etc.)

    out: list[BaseMessage] = []
    while i < len(msgs):
        m = msgs[i]
        if isinstance(m, HumanMessage):
            out.append(m)
            i += 1
        elif isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            needed = {tc.get("id") for tc in m.tool_calls if tc.get("id")}
            j, respuestas = i + 1, []
            while j < len(msgs) and isinstance(msgs[j], ToolMessage):
                respuestas.append(msgs[j])
                j += 1
            got = {t.tool_call_id for t in respuestas}
            if needed and needed <= got:
                out.append(m)
                out.extend(respuestas)
                i = j
            else:
                break  # intercambio de herramienta incompleto en el borde de la ventana
        elif isinstance(m, AIMessage):
            if _text(m.content).strip():
                out.append(m)
            i += 1
        else:  # ToolMessage huerfano en medio
            i += 1

    # No terminar en un AIMessage con tool_calls sin responder.
    while out and isinstance(out[-1], AIMessage) and getattr(out[-1], "tool_calls", None):
        out.pop()
    return out


# Alias privado por compatibilidad con llamadas y tests previos.
_sanitize_history = sanitize_history


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #
def get_session_meta(session_id: str) -> dict:
    """Turno y coste acumulado del item STATE (§4.2, §12A.4). Ceros si no existe."""
    item = _table().get_item(Key={"session_id": session_id, "sk": STATE_SK}).get("Item") or {}
    return {
        "turn": int(item.get("turn", 0)),
        "cost_usd_acumulado": float(item.get("cost_usd_acumulado", 0) or 0),
        "employee_id": item.get("employee_id"),
    }


def load_session(session_id: str, employee_id: str) -> tuple[list[BaseMessage], str | None]:
    """Devuelve (historial de mensajes en orden cronologico, pnr_activo)."""
    from boto3.dynamodb.conditions import Key

    tbl = _table()
    state = tbl.get_item(Key={"session_id": session_id, "sk": STATE_SK}).get("Item")
    if state and state.get("employee_id") and state["employee_id"] != employee_id:
        raise SessionForbidden(f"la sesion {session_id} pertenece a otro empleado")

    cfg = get_settings()
    resp = tbl.query(
        KeyConditionExpression=Key("session_id").eq(session_id) & Key("sk").begins_with(MSG_PREFIX),
        ScanIndexForward=False,
        Limit=cfg.history_window_messages,
    )
    items = list(reversed(resp.get("Items", [])))  # cronologico
    history = sanitize_history([_attrs_to_msg(it) for it in items])
    pnr = state.get("pnr_activo") if state else None
    return history, pnr


# --------------------------------------------------------------------------- #
# Escritura
# --------------------------------------------------------------------------- #
def _next_counter(session_id: str) -> int:
    from boto3.dynamodb.conditions import Key

    resp = _table().query(
        KeyConditionExpression=Key("session_id").eq(session_id) & Key("sk").begins_with(MSG_PREFIX),
        ScanIndexForward=False,
        Limit=1,
        ProjectionExpression="sk",
    )
    items = resp.get("Items", [])
    if not items:
        return 1
    return int(items[0]["sk"].removeprefix(MSG_PREFIX)) + 1


def _ttl() -> tuple[int, int]:
    now = int(time.time())
    return now, now + get_settings().memory_ttl_hours * 3600  # expires_at en SEGUNDOS


def persist_messages(session_id: str, new_messages: Iterable[BaseMessage]) -> bool:
    """Escribe los mensajes nuevos del turno. Lo usa el grafo. Nunca lanza."""
    now, expires_at = _ttl()
    try:
        tbl = _table()
        counter = _next_counter(session_id)
        with tbl.batch_writer() as bw:
            for m in new_messages:
                bw.put_item(Item={
                    "session_id": session_id,
                    "sk": f"{MSG_PREFIX}{counter:08d}",
                    "created_at": now,
                    "expires_at": expires_at,
                    **_msg_to_attrs(m),
                })
                counter += 1
        return True
    except Exception:  # noqa: BLE001 - un fallo de escritura NO convierte un 200 en 500
        _log.exception("fallo al persistir mensajes de la sesion %s", session_id)
        return False


def write_session_state(
    session_id: str,
    employee_id: str,
    pnr_activo: str | None,
    turn: int,
    cost_usd_acumulado: float,
) -> bool:
    """Escribe el item STATE con turno y coste acumulado. Lo usa el handler. Nunca lanza."""
    from decimal import Decimal

    now, expires_at = _ttl()
    try:
        _table().put_item(Item={
            "session_id": session_id,
            "sk": STATE_SK,
            "employee_id": employee_id,
            "pnr_activo": pnr_activo,
            "turn": turn,
            "cost_usd_acumulado": Decimal(str(round(cost_usd_acumulado, 6))),
            "created_at": now,
            "expires_at": expires_at,
        })
        return True
    except Exception:  # noqa: BLE001
        _log.exception("fallo al escribir STATE de la sesion %s", session_id)
        return False
