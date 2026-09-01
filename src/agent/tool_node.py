"""Nodo de herramientas del grafo (PRD §5.1, §12A.2 D-1/D-2).

Ejecuta **en paralelo** los ``tool_call`` de un mismo ``AIMessage`` y devuelve
**TODOS** los ``ToolMessage``, en el orden de las llamadas.

Envoltura obligatoria del retorno (D-2), con el contenido escapado (D-1):
- ``consultar_estado_vuelo`` / ``obtener_datos_reserva`` -> ``<dato_operativo fuente="...">``
- ``buscar_politicas_rag`` -> cada fragmento en ``<documento_recuperado id titulo>``

El system prompt (§5.5 regla 4) declara ambas como zonas de datos, nunca de
instrucciones.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.state import AgentState
from src.logic.defenses import wrap_dato_operativo, wrap_documento_recuperado
from src.tools import TOOL_REGISTRY
from src.tools.schemas import ToolResult


def _run_one(call: dict) -> tuple[ToolResult, float]:
    fn, _schema = TOOL_REGISTRY[call["name"]]
    t0 = time.perf_counter()
    try:
        res = fn(**call.get("args", {}))
    except Exception as exc:  # noqa: BLE001 - defensa extra; las tools ya no lanzan
        res = ToolResult.fail("UPSTREAM_ERROR", f"error inesperado en {call['name']}: {exc}")
    return res, (time.perf_counter() - t0) * 1000


def _envolver(nombre: str, res: ToolResult) -> str:
    """Aplica D-1 + D-2 al resultado de la tool antes de entregarlo al LLM."""
    if nombre == "buscar_politicas_rag" and res.ok and isinstance(res.data, dict):
        frags = res.data.get("resultados", [])
        if not frags:
            return wrap_dato_operativo(nombre, json.dumps(res.model_dump(), ensure_ascii=False, default=str))
        cuerpos = [
            wrap_documento_recuperado(f.get("doc_id", ""), f.get("titulo", ""),
                                      f"[{f.get('score')}] {f.get('fragmento', '')}")
            for f in frags
        ]
        return "\n".join(cuerpos)
    payload = json.dumps(res.model_dump(), ensure_ascii=False, default=str)
    return wrap_dato_operativo(nombre, payload)


def _barras(titulo: str, unidad: str, pares) -> dict | None:
    """Un grafico de barras si hay >= 2 series con algun valor > 0."""
    series = [{"etiqueta": str(k), "valor": int(v)} for k, v in pares]
    series = [s for s in series if s["valor"] >= 0]
    if len(series) < 2 or not any(s["valor"] > 0 for s in series):
        return None
    return {"tipo": "barras", "titulo": titulo, "unidad": unidad, "series": series[:8]}


def _charts_for(nombre: str, res: ToolResult) -> list[dict]:
    """Graficas de CONTEOS disponibles para el resultado de una tool (0..N).
    Deterministas, sin LLM ni librerias. La UI las ofrece BAJO DEMANDA: el
    usuario pulsa el boton de la que quiera ver. Cubre toda tool cuyos campos
    sean conteos."""
    if not res.ok or not isinstance(res.data, dict):
        return []
    d = res.data
    ciudad = d.get("ciudad", "")
    vuelo = d.get("codigo_vuelo", "")
    out: list[dict] = []

    if nombre == "vuelos_por_ciudad":
        out.append(_barras(f"Vuelos de {ciudad} por estado", "nº de vuelos",
                           sorted((d.get("por_estado") or {}).items())))
    elif nombre == "radar_operativo":
        out.append(_barras(f"Salidas de {ciudad} por estado", "nº de vuelos",
                           sorted(((d.get("salidas") or {}).get("por_estado") or {}).items())))
        out.append(_barras(f"Llegadas de {ciudad} por estado", "nº de vuelos",
                           sorted(((d.get("llegadas") or {}).get("por_estado") or {}).items())))
    elif nombre == "resumen_demoras_ciudad":
        out.append(_barras(f"Estado de vuelos de {ciudad}", "nº de vuelos", [
            ("A tiempo", d.get("a_tiempo", 0)),
            ("Demorados", d.get("demorados", 0)),
            ("Cancelados", d.get("cancelados", 0)),
        ]))
        out.append(_barras(f"Motivos de demora en {ciudad}", "nº de vuelos",
                           [(m.get("motivo", "?"), m.get("vuelos", 0)) for m in (d.get("motivos_frecuentes") or [])]))
    elif nombre == "ranking_cabina":
        out.append(_barras(f"Mascotas en cabina — top vuelos de {ciudad}", "nº de mascotas",
                           [(f.get("codigo_vuelo", "?"), f.get("mascotas_en_cabina", 0))
                            for f in (d.get("top_mascotas_en_cabina") or [])]))
        out.append(_barras(f"Menores en cabina — top vuelos de {ciudad}", "nº de menores",
                           [(f.get("codigo_vuelo", "?"), f.get("menores_en_cabina", 0))
                            for f in (d.get("top_menores_en_cabina") or [])]))
    elif nombre == "buscar_vuelos_ruta":
        out.append(_barras(f"Vuelos {d.get('origen', '')} → {d.get('destino', '')} por estado",
                           "nº de vuelos", sorted((d.get("por_estado") or {}).items())))
    elif nombre == "perfil_reservas_vuelo":
        out.append(_barras(f"Reservas del {vuelo} por estado", "nº de reservas",
                           sorted((d.get("por_estado") or {}).items())))
        out.append(_barras(f"Reservas del {vuelo} por canal de compra", "nº de reservas",
                           sorted((d.get("por_canal_compra") or {}).items())))
    elif nombre == "ocupacion_vuelo":
        out.append(_barras(f"Pasaje del {vuelo} por tipo", "nº de pasajeros",
                           sorted((d.get("por_tipo_pasajero") or {}).items())))
        out.append(_barras(f"Pasaje del {vuelo} por clase de tarifa", "nº de pasajeros",
                           sorted((d.get("por_clase_tarifa") or {}).items())))
    elif nombre == "cobertura_reservas":
        out.append(_barras(f"Cobertura de reservas en {ciudad}", "nº de vuelos", [
            ("Con reservas", d.get("con_reservas", 0)),
            ("Sin reservas", d.get("sin_reservas", 0)),
        ]))
    elif nombre == "vuelos_a_continente":
        out.append(_barras(
            f"Vuelos {ciudad} → {d.get('continente', '')} por país", "nº de vuelos",
            sorted((d.get("por_pais") or {}).items())))
    elif nombre == "vuelos_nac_int":
        out.append(_barras(f"Vuelos de {ciudad}: nacionales vs internacionales", "nº de vuelos", [
            ("Nacionales", d.get("nacionales", 0)),
            ("Internacionales", d.get("internacionales", 0)),
        ]))

    return [c for c in out if c]


def tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    calls: list[dict] = list(getattr(last, "tool_calls", []) or []) if isinstance(last, AIMessage) else []
    if not calls:
        return {"tool_rounds": state["tool_rounds"] + 1}

    with ThreadPoolExecutor(max_workers=min(len(calls), 8)) as pool:
        resultados = list(pool.map(_run_one, calls))

    mensajes: list[ToolMessage] = []
    tools_used: list[dict] = []
    pnr_activo = state.get("pnr_activo")
    for call, (res, latency_ms) in zip(calls, resultados):
        mensajes.append(ToolMessage(
            content=_envolver(call["name"], res),
            tool_call_id=call["id"],
            name=call["name"],
        ))
        entrada = {
            "name": call["name"],
            "input": call.get("args", {}),
            "status": "ok" if res.ok else (res.error.code if res.error else "error"),
            "latency_ms": round(latency_ms),
        }
        graficas = _charts_for(call["name"], res)
        if graficas:
            entrada["charts"] = graficas
        tools_used.append(entrada)
        if call["name"] == "obtener_datos_reserva" and res.ok and isinstance(res.data, dict):
            pnr_activo = res.data.get("pnr", pnr_activo)

    return {
        "messages": mensajes,
        "tool_rounds": state["tool_rounds"] + 1,
        "pnr_activo": pnr_activo,
        "tools_used": tools_used,
    }
