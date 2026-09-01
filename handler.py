"""Entrypoint de AWS Lambda (PRD §4.1-§4.3, §5.3, §8.4, §11, §12A).

Orquesta: validacion §4.1 -> limites L-1..L-5 (antes del grafo, coste cero) ->
propiedad de sesion -> cortacircuitos de coste §12A.4 -> D-6 (marcar) -> grafo ->
D-5 (filtro de salida) -> contabilidad de coste -> escritura de STATE ->
metricas EMF -> respuesta §4.2. Modos `warmup` y `dry_run` (§2.2, §8.4).
"""
from __future__ import annotations

import time
from uuid import uuid4

from anthropic import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from src.config import configure_langsmith, get_settings
from src.agent.graph import RECURSION_LIMIT, run_turn  # noqa: F401  (RECURSION_LIMIT re-export)
from src.agent.schemas_api import (
    ChatRequest,
    build_error,
    build_response,
    synthetic_response,
    to_proxy,
)
from src.logic.defenses import (
    OUTPUT_FILTER_REPLACEMENT,
    input_looks_like_injection,
    output_leaks_secret,
    scrub_injection_markers,
)
from src.logic.limits import (
    InputRejected,
    L5_MAX_TURNS,
    SessionTurnLimit,
    check_message_budget,
    check_turn_limit,
)
from src.logic.memory import SessionForbidden, get_session_meta, write_session_state
from src.logic.observability import (
    compute_cost,
    emit_metric,
    logger,
    mask_pnr,
    redact_message,
)

SESSION_COST_LIMIT = get_settings().session_cost_limit_usd  # §12A.4 (ACU-006: configurable)

# `configure_langsmith` es idempotente (`lru_cache`): se llama al principio de
# cada camino, no en el ambito de modulo. El import del modulo ya roza el limite
# de 10 s del init de Lambda; sacar de ahi la llamada de red a SSM ayuda (§11).


def _body(event: dict) -> dict:
    """El cuerpo puede venir como dict (invocacion directa) o como str JSON (API GW)."""
    b = event.get("body", event)
    if isinstance(b, str):
        import json
        return json.loads(b or "{}")
    return b or {}


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(x.get("text", "") for x in content if isinstance(x, dict))
    return str(content)


def _turn_usage(final: dict) -> dict:
    """Suma el `usage` de todas las llamadas al LLM del turno."""
    acc = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
           "cache_creation_input_tokens": 0}
    for m in final.get("messages", []):
        if isinstance(m, AIMessage):
            u = m.response_metadata.get("usage") or {}
            for k in acc:
                acc[k] += u.get(k, 0) or 0
    return acc


def _warmup() -> dict:
    """Calienta los tres caminos frios (§2.2, A-106): indice LanceDB, cliente
    Bedrock de embeddings y cliente Anthropic. El tick de EventBridge cada 5 min
    mantiene el contenedor vivo, de modo que las peticiones reales dan en caliente.
    Ningun fallo aqui puede tumbar la Lambda: se registra y se sigue."""
    configure_langsmith()
    warmed: dict[str, object] = {}

    # Consulta RAG real (indice + Bedrock embed + busqueda LanceDB). La primera
    # en un contenedor frio lee los ficheros Lance de /tmp por primera vez y
    # puede agotar su propio timeout de 3 s; el hilo de fondo sigue y llena la
    # cache de paginas, asi que la segunda ya va en caliente. Se hacen las dos
    # aqui para dejar el camino listo antes de que llegue trafico real.
    try:
        # R-10 / §6A.6: si `make data-corpus` promovio un indice nuevo, el tick
        # de EventBridge lo recoge aqui sin necesidad de redesplegar la Lambda.
        from src.logic.rag_index import refresh_if_changed
        warmed["rag_index_swapped"] = refresh_if_changed()
    except Exception:  # noqa: BLE001
        logger.exception("warmup: fallo refresh_if_changed del indice RAG")
        warmed["rag_index_swapped"] = False

    try:
        from src.tools.rag import buscar_politicas_rag
        t = time.perf_counter()
        buscar_politicas_rag("politica general de calentamiento del indice")
        r2 = buscar_politicas_rag("politica general de calentamiento del indice")
        ms = int((time.perf_counter() - t) * 1000)
        codigo = "OK" if r2.ok else (r2.error.code if r2.error else "?")
        warmed["rag_query"] = codigo           # OK / NOT_FOUND => caliente; TIMEOUT => sigue frio
        warmed["rag_query_ms"] = ms
    except Exception:  # noqa: BLE001
        logger.exception("warmup: fallo la consulta RAG de calentamiento")
        warmed["rag_query"] = "ERROR"

    try:
        from src.agent.llm_node import get_llm
        get_llm()  # construye el cliente (lee la clave de SSM); NO llama a la API de Anthropic
        warmed["llm_client"] = True
    except Exception:  # noqa: BLE001
        logger.exception("warmup: fallo al construir el cliente LLM")
        warmed["llm_client"] = False

    return {"statusCode": 200, "body": {"warmed": warmed}}


def lambda_handler(event, context):
    """Entrypoint real. `warmup` se invoca directo (sin API GW); el resto de
    caminos se adaptan al contrato AWS_PROXY antes de devolverse."""
    if isinstance(event, dict) and event.get("warmup") is True:
        return _warmup()
    return to_proxy(_run(event, context))


def _run(event, context) -> dict:  # noqa: C901 - orquestacion lineal, legible
    configure_langsmith()  # idempotente; §11
    request_id = getattr(context, "aws_request_id", None) or str(uuid4())
    t0 = time.perf_counter()
    payload = _body(event) if isinstance(event, dict) else {}

    # Modo «Datos de prueba» de la UI (§10.3): muestra real del Gold, variable en
    # cada llamada. Sin LLM, sin coste, sin validar el contrato de chat.
    if payload.get("mode") == "sample":
        try:
            from src.logic.samples import sample_datos_prueba
            return {"statusCode": 200, "body": sample_datos_prueba()}
        except Exception:  # noqa: BLE001
            logger.exception("fallo generando la muestra de datos de prueba")
            return {"statusCode": 200, "body": {"vuelos": [], "reservas": []}}

    dry_run = bool(payload.pop("dry_run", False))

    # --- 1. Validacion §4.1 (L-1 incluido) ---
    try:
        req = ChatRequest.model_validate(payload)
    except ValidationError as e:
        emit_metric("InputRejected", dimensions={"motivo": "L-1"})
        first = e.errors()[0]
        return build_error("INVALID_REQUEST",
                           f"{'.'.join(map(str, first['loc']))}: {first['msg']}", request_id)

    logger.append_keys(request_id=request_id, session_id=req.session_id,
                       employee_id=req.employee_id, dry_run=dry_run)

    # --- 2. Limites L-2 / L-3 (antes del grafo, coste cero) ---
    try:
        check_message_budget(req.message)
    except InputRejected as e:
        emit_metric("InputRejected", dimensions={"motivo": e.rule})
        return build_error("INPUT_TOO_LARGE", str(e), request_id)

    # --- 3. Meta de sesion: propiedad, L-5, cortacircuitos §12A.4 ---
    try:
        meta = get_session_meta(req.session_id)
    except Exception:  # noqa: BLE001
        logger.exception("no se pudo leer STATE; se asume sesion nueva")
        meta = {"turn": 0, "cost_usd_acumulado": 0.0, "employee_id": None}

    if meta["employee_id"] and meta["employee_id"] != req.employee_id:
        return build_error("SESSION_FORBIDDEN",
                           "El identificador de empleado no coincide con el dueno de la sesion.",
                           request_id)

    turn = meta["turn"] + 1
    try:
        check_turn_limit(turn)
    except SessionTurnLimit as e:
        return build_error("SESSION_TURN_LIMIT", str(e), request_id)

    if meta["cost_usd_acumulado"] > SESSION_COST_LIMIT:
        emit_metric("SessionCostUSD", value=meta["cost_usd_acumulado"])
        return build_error("SESSION_BUDGET_EXCEEDED",
                           f"La sesion supero {SESSION_COST_LIMIT} USD. Abre una sesion nueva.",
                           request_id)

    # --- 4. D-6: marcar posible inyeccion en la entrada, NO bloquear ---
    if input_looks_like_injection(req.message):
        emit_metric("InjectionSuspected")
        logger.warning("posible inyeccion en la entrada", extra={"user_message": redact_message(req.message)})

    # --- 5. dry_run: camino completo sin invocar el modelo (§8.4) ---
    if dry_run:
        write_session_state(req.session_id, req.employee_id, None, turn, meta["cost_usd_acumulado"])
        logger.info("dry_run: respuesta sintetica", extra={"turn": turn})
        resp = synthetic_response(req.session_id, request_id, turn)
        resp["body"]["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return resp

    # --- 6. Grafo ---
    try:
        final = run_turn(session_id=req.session_id, employee_id=req.employee_id,
                         user_message=req.message)
    except SessionForbidden as e:
        return build_error("SESSION_FORBIDDEN", str(e), request_id)
    except RateLimitError:
        return build_error("LLM_RATE_LIMITED", "La API de Anthropic esta limitando el trafico.", request_id)
    except (APITimeoutError, APIConnectionError):
        # Bajo carga, la llamada al modelo puede exceder el timeout (< 29 s del
        # entorno) o cortarse la conexion. Es transitorio: 503 y "reintenta".
        logger.warning("timeout/conexion con la API de Anthropic (probable carga)")
        return build_error("LLM_RATE_LIMITED",
                           "El servicio esta saturado ahora mismo. Espera unos segundos y reintentalo.",
                           request_id)
    except APIStatusError as e:
        status = getattr(e, "status_code", 500)
        logger.error("error de la API de Anthropic", extra={"status": status, "detalle": str(e)[:500]})
        if status >= 500:
            return build_error("LLM_UPSTREAM_ERROR", "Error de la API de Anthropic.", request_id)
        if status == 400:
            # Historial de sesion en estado que el modelo rechaza (par tool cortado,
            # contenido invalido). `_sanitize_history` deberia evitarlo; si aun asi
            # ocurre, la salida limpia es abrir una sesion nueva.
            return build_error("INTERNAL_ERROR",
                               "La conversacion quedo en un estado que el asistente no puede continuar. "
                               "Pulsa «Nueva sesión» para empezar de cero.", request_id)
        return build_error("INTERNAL_ERROR",
                           "El asistente no pudo completar la respuesta. Reinténtalo; si sigue, "
                           "pulsa «Nueva sesión».", request_id)
    except Exception:  # noqa: BLE001
        logger.exception("excepcion no contemplada en el grafo")
        return build_error("INTERNAL_ERROR",
                           "Se produjo un error interno. Reintentalo; si sigue, pulsa «Nueva sesión».",
                           request_id)

    reply = _text(final["messages"][-1].content)

    # --- 7. D-5: filtro de salida ---
    if output_leaks_secret(reply):
        emit_metric("OutputFilterTriggered")
        logger.error("filtro de salida activado: respuesta sustituida")
        reply = OUTPUT_FILTER_REPLACEMENT
    else:
        limpio = scrub_injection_markers(reply)
        if limpio != reply:
            emit_metric("OutputFilterTriggered")
            logger.warning("filtro de salida: cadena-cebo de inyeccion tachada")
            reply = limpio

    # --- 8. Contabilidad de coste del turno (§4.2, §12A.4) ---
    usage = _turn_usage(final)
    turn_cost = compute_cost(usage)
    cost_accumulated = meta["cost_usd_acumulado"] + turn_cost
    pnr = final.get("pnr_activo")

    write_session_state(req.session_id, req.employee_id, pnr, turn, cost_accumulated)

    # --- 9. Metricas EMF (§11) ---
    tools_used = final.get("tools_used", [])
    emit_metric("LLMTokens", value=usage["input_tokens"] + usage["output_tokens"])
    emit_metric("ToolRounds", value=final.get("tool_rounds", 0))
    emit_metric("CostUSD", value=turn_cost)
    emit_metric("SessionCostUSD", value=cost_accumulated)
    for t in tools_used:
        emit_metric("ToolInvocations", dimensions={"name": t["name"], "resultado": t["status"]})
    if final.get("messages_dropped", 0) > 0:
        emit_metric("PromptBudgetTruncations")

    logger.info("turno completado", extra={
        "turn": turn, "tool_rounds": final.get("tool_rounds", 0),
        "finish_reason": final.get("finish_reason"), "cost_usd": turn_cost,
        "pnr": mask_pnr(pnr), "truncated": final.get("context_truncated", False),
    })

    # --- 10. Respuesta §4.2 ---
    latency_ms = int((time.perf_counter() - t0) * 1000)
    # Todas las graficas disponibles de las tools del turno (la UI las ofrece
    # bajo demanda); tope defensivo de 6 para no inflar el payload.
    charts = [c for t in tools_used for c in (t.get("charts") or [])][:6]
    return build_response(
        session_id=req.session_id,
        reply=reply,
        tools_used=tools_used,
        charts=charts,
        tool_rounds=final.get("tool_rounds", 0),
        finish_reason=final.get("finish_reason") or "end_turn",
        usage=usage,
        cost_usd=turn_cost,
        session_turn=turn,
        turn_limit=L5_MAX_TURNS,
        cost_accumulated=cost_accumulated,
        cost_limit=SESSION_COST_LIMIT,
        truncated=final.get("context_truncated", False),
        messages_dropped=final.get("messages_dropped", 0),
        request_id=request_id,
        latency_ms=latency_ms,
    )
