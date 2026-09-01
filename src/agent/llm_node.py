"""Nodo LLM del grafo (PRD §5.1, §5.3, §12A.3).

- Modelo ``claude-sonnet-5`` exacto, sin sufijo (I-02, ACU-003).
- **NUNCA** ``temperature`` / ``top_p`` / ``top_k`` / ``budget_tokens``.
- ``thinking`` desactivado explicitamente.
- **Cache de prompt (§5.3):** ``cache_control`` con TTL 1h sobre el ultimo bloque
  del system prompt -> cachea ``tools -> system`` juntos. El prefijo debe superar
  1.024 tokens o la cache no se forma (R-14); se verifica en F6 con ``count_tokens``.
- **L-4 (§12A.3):** el prompt ensamblado no supera 4.000 tokens; se descarta
  historial del mas antiguo al mas reciente y se marca ``context_truncated``.
"""
from __future__ import annotations

import time
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import StructuredTool

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.state import AgentState
from src.config import get_anthropic_api_key, get_settings
from src.logic.limits import estimate_tokens, truncate_to_budget
from src.logic.memory import sanitize_history
from src.tools import TOOL_REGISTRY

# Estimacion del prefijo cacheable (system + 3 tools), §9.3. El valor real se
# verifica con count_tokens en F6 (A-84); aqui solo alimenta la aritmetica de L-4.
_PREFIX_TOKENS_ESTIMATE = 1300

_TOOL_DESCRIPCIONES = {
    "consultar_estado_vuelo": "Estado operativo en vivo de un vuelo de AeroNova por su codigo (AN + 3 o 4 digitos).",
    "obtener_datos_reserva": "Datos de una reserva por su PNR (6 caracteres alfanumericos): estado, vuelo, pasajeros, tarifa.",
    "buscar_politicas_rag": "Recupera fragmentos de la normativa interna de AeroNova relevantes a una pregunta.",
    "vuelos_por_ciudad": "Lista los vuelos de un aeropuerto por su codigo IATA (3 letras) con desglose por estado. `sentido`: salidas, llegadas o ambos.",
    "pasajeros_de_vuelo": "Muestra reproducible de 5 pasajeros de un vuelo (nombre y tipo). Datos sinteticos de demo.",
    "mascotas_por_vuelo": "Recuento de mascotas en cabina de un vuelo por su codigo.",
    "ranking_cabina": "Vuelos de un aeropuerto (IATA) ordenados por mascotas en cabina y por menores de edad a bordo: devuelve el top 5 de cada uno. `sentido`: salidas (por defecto), llegadas o ambos. Usala cuando pidan que vuelos llevan mas mascotas o mas ninos.",
    "resumen_demoras_ciudad": "Demoras de un aeropuerto (IATA): puntualidad, demora media y maxima, motivos mas frecuentes y los 5 vuelos mas retrasados. `sentido`: salidas (por defecto), llegadas o ambos.",
    "ocupacion_vuelo": "Agregados de pasaje de un vuelo por su codigo: numero de pasajeros y reservas, desglose por tipo de pasajero y por clase de tarifa, tamano medio de reserva y equipaje facturado total.",
    "perfil_reservas_vuelo": "Reservas de un vuelo por su codigo, desglosadas por estado, clase de tarifa, canal de compra y cuantas son reembolsables.",
    "buscar_vuelos_ruta": "Vuelos programados en una ruta concreta origen -> destino (dos codigos IATA de 3 letras), con desglose por estado y las proximas salidas.",
    "cobertura_reservas": "Vuelos de un aeropuerto (IATA) con y sin reservas: cuantos tienen pasaje, cuantos estan a cero, y en especial que vuelos estan embarcando/volando/aterrizados/demorados sin ninguna reserva (dato incoherente). Usala cuando pregunten por vuelos sin reservas o por la cobertura de reservas de un aeropuerto.",
    "vuelos_a_continente": "Vuelos que salen de un aeropuerto (IATA) hacia un continente (Norteamerica, Centroamerica, Sudamerica o Europa): si hay o no, cuantos, y a que paises. Usala cuando pregunten si un aeropuerto vuela a un continente.",
    "vuelos_nac_int": "Reparto de vuelos nacionales frente a internacionales de un aeropuerto (IATA), con el desglose de los internacionales por pais. `sentido`: salidas (por defecto), llegadas o ambos.",
    "radar_operativo": "Briefing operativo completo de una ciudad (IATA): salidas y llegadas por estado, cancelaciones, demoras y su impacto en pasajeros y mascotas. Usala cuando pidan un panorama general de un aeropuerto.",
}


def _as_langchain_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(func=fn, name=nombre,
                                     description=_TOOL_DESCRIPCIONES[nombre], args_schema=esquema)
        for nombre, (fn, esquema) in TOOL_REGISTRY.items()
    ]


def _system_message() -> SystemMessage:
    """System prompt con la marca de cache (§5.3). Byte-estable: sin datos volatiles."""
    return SystemMessage(content=[{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }])


@lru_cache(maxsize=1)
def get_llm():
    cfg = get_settings()
    base = ChatAnthropic(
        model=cfg.anthropic_model,          # "claude-sonnet-5", sin sufijo
        api_key=get_anthropic_api_key(),    # de SSM SecureString (§2.7, S-04), cacheada
        max_tokens=cfg.max_output_tokens,   # 1024
        thinking={"type": "disabled"},
        # Techo de 29 s de la Lambda / API Gateway (§2.2, D-05). SIN reintentos
        # (un reintento apilaria otro timeout y se comeria el techo). 15 s por
        # llamada + reloj de pared de 12 s en el grafo (12 + 15 + 2 = 29). Un
        # timeout se traduce a 503 "reintentalo" en el handler, no a 504.
        timeout=15,
        max_retries=0,
    )
    return base.bind_tools(_as_langchain_tools())


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def llm_node(state: AgentState) -> dict:
    """Ensambla system + historial (con L-4) + turno en curso, e invoca el modelo."""
    # Si ya vamos contra el reloj de pared del turno, no arrancamos otra llamada
    # al modelo (que puede tardar ~20 s): devolvemos un mensaje de texto que el
    # router manda directo a cierre. Evita chocar con el techo de 29 s (§2.2).
    if time.monotonic() >= state.get("deadline_mono", float("inf")):
        return {
            "messages": [AIMessage(
                "La consulta esta tardando mas de lo normal; reintentala en un momento."
            )],
            "history": state.get("history", []),
            "finish_reason": "deadline",
        }

    llm = get_llm()
    historial = state.get("history", [])
    turno_tokens = sum(estimate_tokens(_text(getattr(m, "content", ""))) for m in state["messages"])
    historial, dropped = truncate_to_budget(_PREFIX_TOKENS_ESTIMATE + turno_tokens, historial)
    # L-4 recorta por tokens del mas antiguo al mas reciente y puede dejar la
    # ventana empezando a mitad de un intercambio de herramienta (tool_result
    # huerfano) -> Anthropic 400. Re-saneamos el borde y contamos lo que caiga.
    n_antes = len(historial)
    historial = sanitize_history(historial)
    dropped += n_antes - len(historial)

    response = llm.invoke([_system_message(), *historial, *state["messages"]])

    stop = response.response_metadata.get("stop_reason")
    finish = None
    if stop == "end_turn" and not response.tool_calls:
        finish = "end_turn"
    elif stop == "max_tokens":
        finish = "max_tokens"

    return {
        "messages": [response],
        "history": historial,
        "finish_reason": finish,
        "context_truncated": bool(dropped) or state.get("context_truncated", False),
        "messages_dropped": state.get("messages_dropped", 0) + dropped,
    }
