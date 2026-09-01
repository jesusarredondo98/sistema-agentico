"""Estado del grafo LangGraph (PRD §4.4).

`messages` acumula los mensajes del **turno en curso** (humano + ai + tool + ...).
`history` es transitorio: lo carga `load_memory` desde DynamoDB una sola vez por
turno y `llm_node` lo antepone; NO se persiste (se persiste `messages`). Separar
historia de mensajes evita el desorden que produciria el reducer `add_messages`
al anteponer, y mantiene `load once`.

`pnr_activo` vive en el item `STATE` de la tabla de memoria (§4.5), no se deduce
del historial: truncar mensajes por el presupuesto L-4 no hace que el agente
olvide el PNR.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

FinishReason = Literal["end_turn", "max_rounds", "max_tokens", "deadline"]


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # turno en curso
    history: list[BaseMessage]        # transitorio: cargado de DynamoDB por load_memory
    employee_id: str
    session_id: str
    pnr_activo: str | None            # se persiste en el item STATE (§4.5)
    tool_rounds: int                  # rondas de herramienta ejecutadas
    finish_reason: FinishReason | None
    # Reloj de pared del turno: si se rebasa antes de otra ronda de herramienta,
    # el grafo cierra en `finalize` para no chocar con el timeout de 29 s de la
    # Lambda / API Gateway (§2.2, D-05). Lo fija `run_turn`.
    deadline_mono: float
    # Transitorios de L-4 (§12A.3): los fija llm_node al ensamblar el prompt y el
    # handler los expone en el bloque `context` de la respuesta (§4.2).
    context_truncated: bool
    messages_dropped: int
    # Invocaciones de herramienta del turno, para el bloque `tools_used` de §4.2.
    tools_used: Annotated[list[dict[str, Any]], operator.add]
