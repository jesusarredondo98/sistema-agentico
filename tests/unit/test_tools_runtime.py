"""Utilidades comunes de las herramientas (src/tools/_runtime.py)."""
from __future__ import annotations

import time

import pytest

from src.tools import _runtime as rt


def test_run_with_timeout_ok():
    assert rt.run_with_timeout(lambda: 21 * 2, seconds=1) == 42


def test_run_with_timeout_vence():
    with pytest.raises(rt.ToolTimeout):
        rt.run_with_timeout(lambda: time.sleep(0.5), seconds=0.1)


def test_drop_nulls_recursivo():
    d = {"a": 1, "b": None, "c": {"d": None, "e": 2}, "f": [{"g": None, "h": 3}]}
    assert rt.drop_nulls(d) == {"a": 1, "c": {"e": 2}, "f": [{"h": 3}]}


def test_estimate_tokens_crece_con_el_tamano():
    assert rt.estimate_tokens("x") < rt.estimate_tokens("x" * 1000)


def test_trim_reservation_capa_y_total():
    data = {"pnr": "ABC123", "pasajeros": [{"n": i} for i in range(12)], "nota": None}
    out = rt.trim_reservation(data)
    assert out["total_pasajeros"] == 12
    assert len(out["pasajeros"]) == rt.MAX_PASAJEROS_EN_RESPUESTA
    assert out["pasajeros_truncados"] is True
    assert "nota" not in out  # drop_nulls


def test_trim_reservation_sin_truncado():
    data = {"pnr": "ABC123", "pasajeros": [{"n": 1}, {"n": 2}]}
    out = rt.trim_reservation(data)
    assert out["total_pasajeros"] == 2
    assert "pasajeros_truncados" not in out


def test_emit_tool_metric_es_noop():
    assert rt.emit_tool_metric("x", True, 1.0) is None


def test_timed_mide_ms():
    with rt.timed() as t:
        time.sleep(0.02)
    assert t.ms >= 15
