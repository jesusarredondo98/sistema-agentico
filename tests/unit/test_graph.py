"""src/agent/graph.py: enrutado, limite de rondas, finalize sin excepcion, GraphRecursionError."""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from src.agent import graph as G


# --- enrutado condicional (§5.1, §5.2) ---
def test_route_texto_va_a_persist():
    st = {"messages": [AIMessage(content="respuesta")], "tool_rounds": 0}
    assert G._route_after_llm(st) == "persist_memory"


def test_route_tool_calls_bajo_el_limite_va_a_tool_node():
    ai = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1", "type": "tool_call"}])
    assert G._route_after_llm({"messages": [ai], "tool_rounds": 0}) == "tool_node"
    assert G._route_after_llm({"messages": [ai], "tool_rounds": 2}) == "tool_node"


def test_route_tool_calls_en_el_limite_va_a_finalize():
    ai = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1", "type": "tool_call"}])
    assert G._route_after_llm({"messages": [ai], "tool_rounds": G.MAX_TOOL_ROUNDS}) == "finalize"


def test_finalize_no_lanza_y_marca_max_rounds(monkeypatch):
    guardado = {}
    monkeypatch.setattr(G, "persist_messages",
                        lambda sid, msgs: guardado.update(n=len(msgs)) or True)
    out = G.finalize_node({"messages": [HumanMessage("x")], "session_id": "s", "employee_id": "e"})
    assert out["finish_reason"] == "max_rounds"
    assert "PNR" in out["messages"][0].content
    assert guardado["n"] == 2  # el mensaje original + el de max_rounds, persistidos en linea


def test_route_deadline_rebasado_va_a_finalize():
    ai = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1", "type": "tool_call"}])
    st = {"messages": [ai], "tool_rounds": 0, "session_id": "s",
          "deadline_mono": 0.0}  # ya en el pasado
    assert G._route_after_llm(st) == "finalize"


def test_finalize_por_deadline_marca_deadline(monkeypatch):
    monkeypatch.setattr(G, "persist_messages", lambda *a, **k: True)
    out = G.finalize_node({"messages": [HumanMessage("x")], "session_id": "s",
                           "employee_id": "e", "deadline_mono": 0.0})
    assert out["finish_reason"] == "deadline"
    assert "tardando" in out["messages"][0].content.lower()


def test_recursion_limit_es_2n_mas_4():
    assert G.RECURSION_LIMIT == 2 * G.MAX_TOOL_ROUNDS + 4 == 10


# --- flujo completo con LLM y memoria mockeados ---
@pytest.fixture
def grafo_mock(monkeypatch):
    """Construye el grafo con load_memory/persist/llm falsos."""
    monkeypatch.setattr(G, "load_memory_node", lambda s: {"history": [], "pnr_activo": None})
    persisted = {}
    monkeypatch.setattr(G, "persist_memory_node",
                        lambda s: persisted.update(msgs=list(s["messages"]), pnr=s.get("pnr_activo")) or {})
    monkeypatch.setattr(G, "persist_messages",
                        lambda sid, msgs: persisted.update(msgs=list(msgs)) or True)
    return persisted


def _make_graph(monkeypatch, llm_impl):
    monkeypatch.setattr(G, "llm_node", llm_impl)
    return G.build_graph()


def _init(**over):
    base = {"messages": [], "history": [], "employee_id": "e", "session_id": "s",
            "pnr_activo": None, "tool_rounds": 0, "finish_reason": None,
            "context_truncated": False, "messages_dropped": 0, "tools_used": []}
    base.update(over)
    return base


def test_turno_directo_sin_herramientas(monkeypatch, grafo_mock):
    g = _make_graph(monkeypatch, lambda s: {"messages": [AIMessage(content="Paris")], "finish_reason": "end_turn"})
    final = g.invoke(_init(messages=[HumanMessage("capital de Francia")]),
                     config={"recursion_limit": G.RECURSION_LIMIT})
    assert final["messages"][-1].content == "Paris"
    assert grafo_mock["msgs"][-1].content == "Paris"  # se persistio


def test_una_ronda_de_herramienta_y_luego_texto(monkeypatch, grafo_mock):
    llamadas = {"n": 0}

    def llm(s):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return {"messages": [AIMessage(content="", tool_calls=[
                {"name": "consultar_estado_vuelo", "args": {"codigo_vuelo": "AN405"}, "id": "c1", "type": "tool_call"}])]}
        return {"messages": [AIMessage(content="El vuelo AN405 esta a tiempo.")], "finish_reason": "end_turn"}

    monkeypatch.setattr(G, "tool_node", lambda s: {
        "messages": [ToolMessage(content='{"ok": true}', tool_call_id="c1", name="consultar_estado_vuelo")],
        "tool_rounds": s["tool_rounds"] + 1,
    })
    g = _make_graph(monkeypatch, llm)
    final = g.invoke(_init(messages=[HumanMessage("estado de AN405")]),
                     config={"recursion_limit": G.RECURSION_LIMIT})
    assert "AN405" in final["messages"][-1].content
    assert final["tool_rounds"] == 1


def test_agota_rondas_va_a_finalize_sin_excepcion(monkeypatch, grafo_mock):
    # El LLM siempre pide herramienta -> tras 3 rondas se enruta a finalize.
    def llm(s):
        return {"messages": [AIMessage(content="", tool_calls=[
            {"name": "consultar_estado_vuelo", "args": {"codigo_vuelo": "AN1"}, "id": f"c{s['tool_rounds']}", "type": "tool_call"}])]}

    monkeypatch.setattr(G, "tool_node", lambda s: {
        "messages": [ToolMessage(content='{"ok": false}', tool_call_id=f"c{s['tool_rounds']}", name="consultar_estado_vuelo")],
        "tool_rounds": s["tool_rounds"] + 1,
    })
    g = _make_graph(monkeypatch, llm)
    final = g.invoke(_init(messages=[HumanMessage("bucle")]),
                     config={"recursion_limit": G.RECURSION_LIMIT})
    assert final["finish_reason"] == "max_rounds"
    assert final["tool_rounds"] == G.MAX_TOOL_ROUNDS


def test_run_turn_captura_graph_recursion_error(monkeypatch):
    class _Boom:
        def invoke(self, *a, **k):
            raise GraphRecursionError("limite")

    monkeypatch.setattr(G, "COMPILED", _Boom())
    final = G.run_turn(session_id="s", employee_id="e", user_message="hola")
    assert final["finish_reason"] == "max_rounds"
    assert "PNR" in final["messages"][-1].content
