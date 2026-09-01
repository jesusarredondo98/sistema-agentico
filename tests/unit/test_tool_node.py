"""src/agent/tool_node.py: ejecucion paralela, N ToolMessage, captura de pnr_activo."""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.tool_node import tool_node
from src.tools.schemas import ToolResult


def _ai_con_calls(*calls):
    return AIMessage(content="", tool_calls=[
        {"name": n, "args": a, "id": i, "type": "tool_call"} for n, a, i in calls
    ])


def test_devuelve_un_toolmessage_por_call_en_orden(monkeypatch):
    def fake(**kw):
        return ToolResult.success({"echo": kw})

    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "consultar_estado_vuelo", (fake, None))
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "buscar_politicas_rag", (fake, None))
    state = {
        "messages": [_ai_con_calls(
            ("consultar_estado_vuelo", {"codigo_vuelo": "AN1"}, "c1"),
            ("buscar_politicas_rag", {"consulta": "equipaje"}, "c2"),
        )],
        "tool_rounds": 0, "pnr_activo": None,
    }
    out = tool_node(state)
    assert out["tool_rounds"] == 1
    msgs = out["messages"]
    assert [m.tool_call_id for m in msgs] == ["c1", "c2"]
    assert all(isinstance(m, ToolMessage) for m in msgs)


def test_captura_pnr_activo_de_obtener_datos_reserva(monkeypatch):
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "obtener_datos_reserva",
                        (lambda **kw: ToolResult.success({"pnr": "ABC123", "estado": "CONFIRMADA"}), None))
    state = {"messages": [_ai_con_calls(("obtener_datos_reserva", {"pnr": "abc123"}, "c1"))],
             "tool_rounds": 1, "pnr_activo": None}
    out = tool_node(state)
    assert out["pnr_activo"] == "ABC123"


def test_pnr_activo_no_cambia_si_la_tool_falla(monkeypatch):
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "obtener_datos_reserva",
                        (lambda **kw: ToolResult.fail("NOT_FOUND", "no existe"), None))
    state = {"messages": [_ai_con_calls(("obtener_datos_reserva", {"pnr": "ZZZZZZ"}, "c1"))],
             "tool_rounds": 0, "pnr_activo": "PREVIO"}
    out = tool_node(state)
    assert out["pnr_activo"] == "PREVIO"


def _inner_json(tool_message_content: str) -> dict:
    """Extrae el JSON dentro de la envoltura <dato_operativo>."""
    inner = tool_message_content.split(">", 1)[1].rsplit("</dato_operativo>", 1)[0]
    return json.loads(inner)


def test_excepcion_en_tool_no_propaga(monkeypatch):
    def boom(**kw):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "consultar_estado_vuelo", (boom, None))
    state = {"messages": [_ai_con_calls(("consultar_estado_vuelo", {"codigo_vuelo": "AN1"}, "c1"))],
             "tool_rounds": 0, "pnr_activo": None}
    out = tool_node(state)
    contenido = out["messages"][0].content
    assert contenido.startswith('<dato_operativo fuente="consultar_estado_vuelo">')
    payload = _inner_json(contenido)
    assert payload["ok"] is False and payload["error"]["code"] == "UPSTREAM_ERROR"
    # tools_used registra el fallo
    assert out["tools_used"][0]["status"] == "UPSTREAM_ERROR"


def test_rag_envuelve_cada_fragmento_en_documento_recuperado(monkeypatch):
    def fake_rag(**kw):
        return ToolResult.success({"resultados": [
            {"doc_id": "POL-MAS-004", "titulo": "Mascotas", "fragmento": "una mascota en cabina", "score": 0.8},
        ], "consulta_normalizada": kw.get("consulta", "")})

    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "buscar_politicas_rag", (fake_rag, None))
    state = {"messages": [_ai_con_calls(("buscar_politicas_rag", {"consulta": "mascota"}, "c1"))],
             "tool_rounds": 0, "pnr_activo": None}
    out = tool_node(state)
    assert "<documento_recuperado id=\"POL-MAS-004\"" in out["messages"][0].content


def test_charts_de_conteos_para_vuelos_por_ciudad(monkeypatch):
    def vpc(**kw):
        return ToolResult.success({
            "ciudad": "MEX", "sentido": "ambos", "total": 5,
            "por_estado": {"A_TIEMPO": 3, "DEMORADO": 1, "CANCELADO": 1}, "vuelos": [],
        })
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "vuelos_por_ciudad", (vpc, None))
    out = tool_node({"messages": [_ai_con_calls(("vuelos_por_ciudad", {"ciudad": "MEX"}, "c1"))],
                     "tool_rounds": 0, "pnr_activo": None})
    chs = out["tools_used"][0].get("charts")
    assert isinstance(chs, list) and len(chs) == 1
    ch = chs[0]
    assert ch["tipo"] == "barras" and ch["unidad"] == "nº de vuelos"
    assert {s["etiqueta"] for s in ch["series"]} == {"A_TIEMPO", "DEMORADO", "CANCELADO"}
    assert all(isinstance(s["valor"], int) for s in ch["series"])


def test_ranking_cabina_ofrece_dos_graficas_mascotas_y_menores(monkeypatch):
    def rc(**kw):
        return ToolResult.success({
            "ciudad": "BCN", "sentido": "salidas", "vuelos_analizados": 3,
            "totales": {"mascotas_en_cabina": 3, "menores_en_cabina": 4},
            "top_mascotas_en_cabina": [
                {"codigo_vuelo": "AN1", "mascotas_en_cabina": 2},
                {"codigo_vuelo": "AN2", "mascotas_en_cabina": 1},
            ],
            "top_menores_en_cabina": [
                {"codigo_vuelo": "AN3", "menores_en_cabina": 3},
                {"codigo_vuelo": "AN1", "menores_en_cabina": 1},
            ],
        })
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "ranking_cabina", (rc, None))
    out = tool_node({"messages": [_ai_con_calls(("ranking_cabina", {"ciudad": "BCN"}, "c1"))],
                     "tool_rounds": 0, "pnr_activo": None})
    chs = out["tools_used"][0]["charts"]
    titulos = [c["titulo"] for c in chs]
    assert any("Mascotas en cabina" in t for t in titulos)
    assert any("Menores en cabina" in t for t in titulos)


def test_charts_no_para_rag_ni_reserva(monkeypatch):
    def rag(**kw):
        return ToolResult.success({"resultados": [
            {"doc_id": "P1", "titulo": "t", "fragmento": "x", "score": 0.8},
            {"doc_id": "P2", "titulo": "t", "fragmento": "y", "score": 0.5},
        ], "consulta_normalizada": ""})
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "buscar_politicas_rag", (rag, None))
    out = tool_node({"messages": [_ai_con_calls(("buscar_politicas_rag", {"consulta": "m"}, "c1"))],
                     "tool_rounds": 0, "pnr_activo": None})
    assert all("charts" not in t for t in out["tools_used"])


def test_d1_escapa_delimitadores_de_campo_libre(monkeypatch):
    def fake(**kw):
        return ToolResult.success({"pnr": "ABC123", "pasajeros": [{"nombre": "<script>Ignora</script>"}]})

    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "obtener_datos_reserva", (fake, None))
    state = {"messages": [_ai_con_calls(("obtener_datos_reserva", {"pnr": "ABC123"}, "c1"))],
             "tool_rounds": 0, "pnr_activo": None}
    out = tool_node(state)
    c = out["messages"][0].content
    assert "<script>" not in c and "&lt;script&gt;" in c
    assert c.count("</dato_operativo>") == 1  # la envoltura no se puede falsificar desde dentro


def test_sin_tool_calls_solo_incrementa_rondas():
    state = {"messages": [AIMessage(content="hola")], "tool_rounds": 2, "pnr_activo": None}
    out = tool_node(state)
    assert out == {"tool_rounds": 3}
