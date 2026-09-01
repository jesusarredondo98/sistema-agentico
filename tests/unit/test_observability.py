"""src/logic/observability.py (PRD §11): redaccion de PII, coste, metricas."""
from __future__ import annotations

from src.logic import observability as O


# --- redaccion de PII ---
def test_mask_pnr():
    assert O.mask_pnr("ABC123") == "AB***3"
    assert O.mask_pnr("AB") == "**"
    assert O.mask_pnr("") == ""
    assert O.mask_pnr(None) == ""


def test_redact_message_no_expone_el_texto():
    txt = "PNR ABC123 del pasajero Juan Perez"
    r = O.redact_message(txt)
    assert set(r) == {"len", "sha256_8"}
    assert r["len"] == len(txt)
    assert len(r["sha256_8"]) == 8
    assert "Juan" not in str(r) and "ABC123" not in str(r)


# --- coste por turno (§9.3) ---
def test_compute_cost_solo_entrada_salida():
    # 1000 in * 2/M + 200 out * 10/M = 0.002 + 0.002 = 0.004
    c = O.compute_cost({"input_tokens": 1000, "output_tokens": 200})
    assert c == 0.004


def test_compute_cost_con_lectura_de_cache_es_mas_barato():
    sin_cache = O.compute_cost({"input_tokens": 2000, "output_tokens": 100})
    con_cache = O.compute_cost({"input_tokens": 500, "output_tokens": 100,
                                "cache_read_input_tokens": 1500})
    assert con_cache < sin_cache


def test_compute_cost_escritura_de_cache_1h_es_2x_entrada():
    solo_escritura = O.compute_cost({"cache_creation_input_tokens": 1_000_000})
    assert solo_escritura == 4.0  # 4 USD/MTok


def test_emit_metric_no_lanza():
    O.emit_metric("ToolInvocations", dimensions={"name": "x", "resultado": "ok"})
    O.emit_metric("CostUSD", value=0.01)
