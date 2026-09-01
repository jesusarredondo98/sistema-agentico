"""Limites de entrada y presupuesto de tokens (PRD §12A.3).

L-1 (longitud) la valida Pydantic en el contrato de §4.1 -> 400 INVALID_REQUEST.
L-2 y L-3 aqui -> 400 INPUT_TOO_LARGE, **antes de construir el grafo** (coste 0).
L-4 (presupuesto del prompt ensamblado) se aplica al ensamblar el prompt.
L-5 (turnos por sesion) la comprueba el handler contra el item STATE.
"""
from __future__ import annotations

import math
from typing import Sequence

L1_MIN_CHARS = 1
L1_MAX_CHARS = 1200
L2_MAX_TOKENS = 400
L3_MIN_RATIO = 1.5
L4_PROMPT_BUDGET_TOKENS = 4000
L5_MAX_TURNS = 50

_CHARS_PER_TOKEN = 3.2  # heuristica local de §12A.3 (ceil(len/3.2))


class InputRejected(Exception):
    """Incumple L-2 o L-3. `rule` y `motivo` alimentan la metrica InputRejected."""

    def __init__(self, rule: str, motivo: str) -> None:
        super().__init__(f"{rule}: {motivo}")
        self.rule = rule
        self.motivo = motivo


class SessionTurnLimit(Exception):
    """La sesion supera L-5 (50 turnos) -> 429 SESSION_TURN_LIMIT."""


def estimate_tokens(text: str) -> int:
    """Estimacion local de tokens (§12A.3).

    Base: ``ceil(len / 3.2)`` para texto latino. Correccion por ancho de byte:
    un caracter CJK ocupa 3 bytes UTF-8 y ~1 token real, asi que el texto
    multibyte tokeniza MUCHO mas de lo que sugiere el numero de caracteres. Sin
    esta correccion el ratio de L-3 seria constante (3.2) y L-3 seria codigo
    muerto -- justo el agujero que L-3 debe cerrar (CJK masivo, emoji).
    """
    n = len(text)
    b = len(text.encode("utf-8"))
    base = math.ceil(n / _CHARS_PER_TOKEN)
    multibyte = math.ceil(b / 2.5) if b > n * 1.3 else 0
    return max(1, base, multibyte) if text else 0


def check_message_budget(message: str) -> None:
    """L-2 (tokens estimados) y L-3 (ratio car/tok). Lanza `InputRejected`."""
    tok = estimate_tokens(message)
    if tok > L2_MAX_TOKENS:
        raise InputRejected("L-2", f"~{tok} tokens estimados supera el maximo de {L2_MAX_TOKENS}")
    ratio = len(message) / max(tok, 1)
    if ratio < L3_MIN_RATIO:
        raise InputRejected(
            "L-3", f"ratio caracteres/tokens {ratio:.2f} < {L3_MIN_RATIO} (posible CJK, base64 u ofuscacion)"
        )


def check_turn_limit(turn: int) -> None:
    """L-5: turno actual (1-indexado). Lanza `SessionTurnLimit` si supera 50."""
    if turn > L5_MAX_TURNS:
        raise SessionTurnLimit(f"turno {turn} supera el limite de {L5_MAX_TURNS} por sesion")


def truncate_to_budget(
    fixed_tokens: int, historial: Sequence, budget: int = L4_PROMPT_BUDGET_TOKENS
) -> tuple[list, int]:
    """L-4: descarta mensajes de historial del mas antiguo al mas reciente hasta caber.

    `fixed_tokens` = tokens del system prompt + tools + turno en curso (no se
    descartan). Devuelve (historial conservado, nº de mensajes descartados).
    """
    msgs = list(historial)
    dropped = 0
    total = fixed_tokens + sum(estimate_tokens(_msg_text(m)) for m in msgs)
    while total > budget and msgs:
        quitado = msgs.pop(0)
        total -= estimate_tokens(_msg_text(quitado))
        dropped += 1
    return msgs, dropped


def _msg_text(m) -> str:
    c = getattr(m, "content", m)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict))
    return str(c)
