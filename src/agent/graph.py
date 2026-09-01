"""Definicion y compilacion del grafo ReAct de LangGraph (PRD §5.1, §5.2).

Flujo:  START -> load_memory -> llm_node
                                 |- tool_calls y tool_rounds < MAX_TOOL_ROUNDS -> tool_node -> llm_node
                                 |- tool_calls y tool_rounds == MAX_TOOL_ROUNDS -> finalize
                                 |- texto -> persist_memory -> END

**El limite de negocio (`MAX_TOOL_ROUNDS = 3`) se comprueba en la arista
condicional con `state["tool_rounds"]`.** `recursion_limit = 10` es la red de
seguridad del framework (`2 x MAX_TOOL_ROUNDS + 4`). Con `recursion_limit = 3`
el agente jamas responde (R-07).

Al agotar rondas el grafo **no lanza excepcion**: enruta a `finalize`. Un
`GraphRecursionError` (no deberia ocurrir si el negocio funciona) se captura en
`run_turn` y se traduce a la misma respuesta con exito (HTTP 200 en F6).
"""
from __future__ import annotations

import logging
import time

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from src.agent.llm_node import llm_node
from src.agent.state import AgentState
from src.agent.tool_node import tool_node
from src.config import get_settings
from src.logic.memory import load_session, persist_messages

_log = logging.getLogger("aeronova.graph")

MAX_TOOL_ROUNDS = get_settings().max_tool_rounds          # 3 (regla de negocio)
RECURSION_LIMIT = 2 * MAX_TOOL_ROUNDS + 4                 # 10 (red del framework)
# Reloj de pared del turno. La Lambda y API Gateway cortan a los 29 s (§2.2,
# D-05). Una llamada al modelo puede tardar hasta 15 s (ver llm_node) y luego
# hay que persistir y ensamblar la respuesta (~2 s). Presupuesto: si al ir a
# arrancar otra ronda ya vamos por 12 s, cerramos con lo que haya y devolvemos
# un 200 legible en vez de arriesgar el 504.  12 + 15 + 2 = 29.
TURN_DEADLINE_S = 12.0

_MAX_ROUNDS_MSG = (
    "No pude completar la consulta con la informacion disponible. "
    "¿Puedes darme el codigo de vuelo o el PNR?"
)
_DEADLINE_MSG = (
    "La consulta esta tardando mas de lo normal. Reintentala; si necesitas varias "
    "cosas a la vez, pregunta de una en una."
)


# --------------------------------------------------------------------------- #
# Nodos
# --------------------------------------------------------------------------- #
def load_memory_node(state: AgentState) -> dict:
    """Query a DynamoDB, valida propiedad de sesion, hidrata history y pnr_activo."""
    history, pnr = load_session(state["session_id"], state["employee_id"])
    return {"history": history, "pnr_activo": pnr}


def finalize_node(state: AgentState) -> dict:
    """Cierra el turno sin excepcion (§5.2): se alcanzo MAX_TOOL_ROUNDS o se
    rebaso el reloj de pared del turno.

    Persiste en linea y va directo a END: asi el camino maximo del grafo son 9
    super-pasos y `recursion_limit=10` (`2xMAX_TOOL_ROUNDS+4`, I-03) tiene el
    margen que exige LangGraph. Con `finalize -> persist_memory -> END` serian
    10 nodos y LangGraph necesitaria `recursion_limit>=11`, rompiendo I-03.
    """
    por_deadline = time.monotonic() >= state.get("deadline_mono", float("inf"))
    final_msg = AIMessage(_DEADLINE_MSG if por_deadline else _MAX_ROUNDS_MSG)
    persist_messages(state["session_id"], [*state["messages"], final_msg])
    return {"messages": [final_msg], "finish_reason": "deadline" if por_deadline else "max_rounds"}


def persist_memory_node(state: AgentState) -> dict:
    """Escribe los mensajes del turno. Un fallo se registra pero no rompe el turno (§4.5).

    El item STATE (turno, coste acumulado, pnr_activo) lo escribe el handler
    despues, cuando ya conoce el coste del turno (§4.2, §12A.4).
    """
    persist_messages(state["session_id"], state["messages"])
    return {}


def _route_after_llm(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        if state["tool_rounds"] >= MAX_TOOL_ROUNDS:
            return "finalize"
        if time.monotonic() >= state.get("deadline_mono", float("inf")):
            _log.warning("reloj de pared del turno rebasado (sesion %s); se cierra en finalize",
                         state.get("session_id"))
            return "finalize"
        return "tool_node"
    return "persist_memory"


# --------------------------------------------------------------------------- #
# Compilacion
# --------------------------------------------------------------------------- #
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_memory", load_memory_node)
    g.add_node("llm_node", llm_node)
    g.add_node("tool_node", tool_node)
    g.add_node("finalize", finalize_node)
    g.add_node("persist_memory", persist_memory_node)

    g.add_edge(START, "load_memory")
    g.add_edge("load_memory", "llm_node")
    g.add_conditional_edges("llm_node", _route_after_llm, ["tool_node", "finalize", "persist_memory"])
    g.add_edge("tool_node", "llm_node")
    g.add_edge("finalize", END)          # finalize persiste en linea (ver finalize_node)
    g.add_edge("persist_memory", END)
    return g.compile()


COMPILED = build_graph()


def run_turn(*, session_id: str, employee_id: str, user_message: str) -> AgentState:
    """Ejecuta un turno completo. Captura `GraphRecursionError` -> max_rounds (HTTP 200)."""
    init: AgentState = {
        "messages": [HumanMessage(user_message)],
        "history": [],
        "employee_id": employee_id,
        "session_id": session_id,
        "pnr_activo": None,
        "tool_rounds": 0,
        "finish_reason": None,
        "context_truncated": False,
        "messages_dropped": 0,
        "tools_used": [],
        "deadline_mono": time.monotonic() + TURN_DEADLINE_S,
    }
    try:
        return COMPILED.invoke(init, config={"recursion_limit": RECURSION_LIMIT})
    except GraphRecursionError:
        _log.warning("GraphRecursionError en la sesion %s; se devuelve max_rounds", session_id)
        return {**init, "messages": [*init["messages"], AIMessage(_MAX_ROUNDS_MSG)],
                "finish_reason": "max_rounds"}
