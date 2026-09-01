"""src/logic/memory.py (PRD §4.5, §12A.4): sk con ceros, TTL segundos, Query no Scan, 403."""
from __future__ import annotations

import time
from decimal import Decimal

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from moto import mock_aws

from src.config import get_settings
from src.logic import memory as mem


@pytest.fixture
def tabla(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        mem._table.cache_clear()
        cfg = get_settings()
        res = boto3.resource("dynamodb", region_name="us-east-1")
        res.create_table(
            TableName=cfg.memory_table,
            KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"},
                       {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"},
                                  {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield res.Table(cfg.memory_table)
        mem._table.cache_clear()


def _sks(tabla, sid):
    return sorted(i["sk"] for i in tabla.query(KeyConditionExpression=Key("session_id").eq(sid))["Items"]
                 if i["sk"].startswith("MSG#"))


def test_persist_messages_sk_con_8_ceros_y_ttl_en_segundos(tabla):
    assert mem.persist_messages("s1", [HumanMessage("hola"), AIMessage("adios")])
    assert _sks(tabla, "s1") == ["MSG#00000001", "MSG#00000002"]
    msg = tabla.get_item(Key={"session_id": "s1", "sk": "MSG#00000001"})["Item"]
    ahora = int(time.time())
    assert 0 < int(msg["expires_at"]) - ahora <= 24 * 3600 + 5  # segundos, no ms


def test_contador_continua_desde_el_ultimo(tabla):
    mem.persist_messages("s1", [HumanMessage("uno")])
    mem.persist_messages("s1", [HumanMessage("dos"), AIMessage("tres")])
    assert _sks(tabla, "s1") == ["MSG#00000001", "MSG#00000002", "MSG#00000003"]


def test_write_session_state_turno_y_coste(tabla):
    assert mem.write_session_state("s2", "EMP_009", "ABC123", turn=3, cost_usd_acumulado=0.0412)
    state = tabla.get_item(Key={"session_id": "s2", "sk": "STATE"})["Item"]
    assert state["employee_id"] == "EMP_009"
    assert state["pnr_activo"] == "ABC123"
    assert int(state["turn"]) == 3
    assert state["cost_usd_acumulado"] == Decimal("0.0412")


def test_get_session_meta(tabla):
    mem.write_session_state("s2", "EMP_009", "ABC123", turn=5, cost_usd_acumulado=0.2)
    meta = mem.get_session_meta("s2")
    assert meta == {"turn": 5, "cost_usd_acumulado": 0.2, "employee_id": "EMP_009"}


def test_get_session_meta_sesion_nueva(tabla):
    assert mem.get_session_meta("nunca_vista") == {"turn": 0, "cost_usd_acumulado": 0.0, "employee_id": None}


def test_load_devuelve_historial_cronologico_y_pnr(tabla):
    mem.persist_messages("s3", [HumanMessage("PNR ABC123"), AIMessage("ok")])
    mem.write_session_state("s3", "EMP_009", "ABC123", turn=1, cost_usd_acumulado=0.01)
    history, pnr = mem.load_session("s3", "EMP_009")
    assert [type(m).__name__ for m in history] == ["HumanMessage", "AIMessage"]
    assert history[0].content == "PNR ABC123"
    assert pnr == "ABC123"


def test_load_respeta_history_window(tabla, monkeypatch):
    monkeypatch.setattr(mem, "get_settings",
                        lambda: type("C", (), {"aws_region": "us-east-1",
                                               "memory_table": get_settings().memory_table,
                                               "history_window_messages": 2, "memory_ttl_hours": 24})())
    for i in range(5):
        mem.persist_messages("s4", [HumanMessage(f"m{i}")])
    history, _ = mem.load_session("s4", "EMP_001")
    assert [m.content for m in history] == ["m3", "m4"]  # los 2 mas recientes, en orden


def test_propiedad_de_sesion_ajena_lanza_forbidden(tabla):
    mem.write_session_state("s5", "EMP_010", None, turn=1, cost_usd_acumulado=0.0)
    with pytest.raises(mem.SessionForbidden):
        mem.load_session("s5", "EMP_020")


def test_load_sesion_nueva_no_lanza(tabla):
    history, pnr = mem.load_session("nunca_vista", "EMP_099")
    assert history == [] and pnr is None


def test_fallo_de_escritura_no_propaga(tabla, monkeypatch):
    monkeypatch.setattr(mem, "_next_counter", lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    assert mem.persist_messages("s6", [HumanMessage("x")]) is False


def test_sanitize_descarta_tool_result_huerfano_al_inicio():
    # La ventana empieza a mitad de un intercambio de herramienta.
    msgs = [
        ToolMessage(content="{}", tool_call_id="c1", name="t"),
        AIMessage("respuesta final"),
        HumanMessage("siguiente pregunta"),
        AIMessage("otra respuesta"),
    ]
    out = mem._sanitize_history(msgs)
    assert [type(m).__name__ for m in out] == ["HumanMessage", "AIMessage"]


def test_sanitize_corta_par_tool_incompleto_en_el_borde():
    msgs = [
        HumanMessage("pregunta"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "c9", "type": "tool_call"}]),
        # falta el ToolMessage con id c9 (cayo fuera de la ventana por el otro lado)
    ]
    out = mem._sanitize_history(msgs)
    assert [type(m).__name__ for m in out] == ["HumanMessage"]


def test_sanitize_conserva_intercambio_completo():
    msgs = [
        HumanMessage("estado AN405"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "c1", "type": "tool_call"}]),
        ToolMessage(content="{}", tool_call_id="c1", name="t"),
        AIMessage("a tiempo"),
    ]
    out = mem._sanitize_history(msgs)
    assert [type(m).__name__ for m in out] == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]


def test_sanitize_descarta_ai_vacio_sin_tool_calls():
    msgs = [HumanMessage("hola"), AIMessage(content="   "), HumanMessage("sigo aqui")]
    out = mem._sanitize_history(msgs)
    assert [type(m).__name__ for m in out] == ["HumanMessage", "HumanMessage"]


def test_load_sanea_historial_con_par_tool_cortado(tabla):
    # Persistimos un historial donde el primer item es un tool_result huerfano.
    mem.persist_messages("s8", [
        ToolMessage(content="{}", tool_call_id="viejo", name="t"),
        AIMessage("respuesta"),
        HumanMessage("nueva pregunta"),
    ])
    history, _ = mem.load_session("s8", "EMP_001")
    assert history and isinstance(history[0], HumanMessage)


def test_toolmessage_roundtrip(tabla):
    mem.persist_messages("s7", [
        HumanMessage("estado AN405"),
        AIMessage(content="", tool_calls=[{"name": "consultar_estado_vuelo",
                                           "args": {"codigo_vuelo": "AN405"}, "id": "c1", "type": "tool_call"}]),
        ToolMessage(content='<dato_operativo fuente="consultar_estado_vuelo">{}</dato_operativo>',
                    tool_call_id="c1", name="consultar_estado_vuelo"),
        AIMessage("El vuelo esta a tiempo."),
    ])
    history, _ = mem.load_session("s7", "EMP_001")
    assert [type(m).__name__ for m in history] == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert history[1].tool_calls[0]["name"] == "consultar_estado_vuelo"
    assert history[2].tool_call_id == "c1"
