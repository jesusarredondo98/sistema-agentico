"""src/agent/llm_node.py: ensamblado de mensajes y finish_reason. ChatAnthropic mockeado."""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agent import llm_node as ln


class _FakeLLM:
    def __init__(self, respuesta):
        self._r = respuesta
        self.visto = None

    def invoke(self, mensajes):
        self.visto = mensajes
        return self._r


def test_as_langchain_tools_usa_los_nombres_del_registro():
    from src.tools import TOOL_REGISTRY
    tools = ln._as_langchain_tools()
    assert {t.name for t in tools} == set(TOOL_REGISTRY)
    assert {"consultar_estado_vuelo", "obtener_datos_reserva", "buscar_politicas_rag"} <= {t.name for t in tools}
    assert all(t.description for t in tools)


def test_llm_node_antepone_system_y_history(monkeypatch):
    fake = _FakeLLM(AIMessage(content="hola", response_metadata={"stop_reason": "end_turn"}))
    monkeypatch.setattr(ln, "get_llm", lambda: fake)
    state = {"history": [HumanMessage("antiguo")], "messages": [HumanMessage("nuevo")]}
    out = ln.llm_node(state)
    assert isinstance(fake.visto[0], SystemMessage)
    assert [m.content for m in fake.visto[1:]] == ["antiguo", "nuevo"]
    assert out["finish_reason"] == "end_turn"


def test_llm_node_con_tool_calls_no_marca_end_turn(monkeypatch):
    ai = AIMessage(content="", response_metadata={"stop_reason": "tool_use"},
                   tool_calls=[{"name": "x", "args": {}, "id": "1", "type": "tool_call"}])
    monkeypatch.setattr(ln, "get_llm", lambda: _FakeLLM(ai))
    out = ln.llm_node({"history": [], "messages": [HumanMessage("q")]})
    assert out["finish_reason"] is None


def test_llm_node_detecta_max_tokens(monkeypatch):
    ai = AIMessage(content="respuesta cortada", response_metadata={"stop_reason": "max_tokens"})
    monkeypatch.setattr(ln, "get_llm", lambda: _FakeLLM(ai))
    out = ln.llm_node({"history": [], "messages": [HumanMessage("q")]})
    assert out["finish_reason"] == "max_tokens"


def test_llm_node_no_llama_al_modelo_si_se_rebaso_el_deadline(monkeypatch):
    """Reloj de pared del turno ya en el pasado: se devuelve texto sin invocar."""
    llamado = {"n": 0}
    class _Espia(_FakeLLM):
        def invoke(self, m): llamado["n"] += 1; return super().invoke(m)
    monkeypatch.setattr(ln, "get_llm", lambda: _Espia(AIMessage("no deberia salir")))
    out = ln.llm_node({"history": [], "messages": [HumanMessage("q")], "deadline_mono": 0.0})
    assert llamado["n"] == 0
    assert out["finish_reason"] == "deadline"
    assert not getattr(out["messages"][0], "tool_calls", None)


def test_llm_node_sanea_el_historial_tras_recortar_por_tokens(monkeypatch):
    """L-4 puede dejar el historial empezando en un tool_result huérfano
    (Anthropic 400). El nodo re-sanea el borde antes de invocar."""
    fake = _FakeLLM(AIMessage(content="ok", response_metadata={"stop_reason": "end_turn"}))
    monkeypatch.setattr(ln, "get_llm", lambda: fake)
    monkeypatch.setattr(ln, "truncate_to_budget", lambda *a, **k: (
        [ToolMessage(content="resultado huérfano", tool_call_id="t1"),
         HumanMessage("pregunta buena"),
         AIMessage(content="respuesta buena", response_metadata={"stop_reason": "end_turn"})],
        2,
    ))
    out = ln.llm_node({"history": [HumanMessage("x")], "messages": [HumanMessage("nuevo")]})
    enviados = fake.visto[1:]  # sin el SystemMessage
    assert not isinstance(enviados[0], ToolMessage)
    assert isinstance(enviados[0], HumanMessage) and enviados[0].content == "pregunta buena"
    assert out["messages_dropped"] >= 3  # 2 de L-4 + al menos el huérfano
