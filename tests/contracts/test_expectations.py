"""Expectativas de lote E-01..E-09 (§6A.4): caso que pasa, que falla y de frontera."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.contracts import expectations as ex
from src.contracts.corpus import CATEGORIAS


class _Doc:
    def __init__(self, doc_id, categoria="MASCOTAS", referencias=None):
        self.doc_id = doc_id
        self.categoria = categoria
        self.referencias = referencias or []


# --- E-01 unicidad ---
def test_e01_sin_duplicados():
    r = ex.check_e01(["A", "B", "C"], dataset="flights")
    assert r.passed and r.action == "ABORTA"


def test_e01_con_duplicados():
    r = ex.check_e01(["A", "B", "A"])
    assert not r.passed and r.aborts


# --- E-02 integridad referencial cruzada ---
def test_e02_todas_las_referencias_presentes():
    docs = [_Doc("POL-MAS-001", referencias=["POL-CAM-002"]), _Doc("POL-CAM-002", "CAMBIOS")]
    assert ex.check_e02(docs).passed


def test_e02_referencia_colgante_aborta():
    docs = [_Doc("POL-MAS-001", referencias=["POL-EQU-099"])]
    r = ex.check_e02(docs)
    assert r.aborts and "POL-EQU-099" in r.detail


# --- E-03 cobertura por categoria ---
def test_e03_cobertura_suficiente():
    docs = [_Doc(f"POL-MAS-{i:03d}", cat) for cat in CATEGORIAS for i in range(ex.COBERTURA_MIN_POR_CATEGORIA)]
    assert ex.check_e03(docs, CATEGORIAS).passed


def test_e03_una_categoria_floja_aborta():
    docs = [_Doc(f"POL-MAS-{i:03d}", cat) for cat in CATEGORIAS for i in range(ex.COBERTURA_MIN_POR_CATEGORIA)]
    docs = [d for d in docs if not (d.categoria == "MENORES")][:-1] + [_Doc("POL-MEN-001", "MENORES")]
    r = ex.check_e03(docs, CATEGORIAS)
    assert r.aborts and "MENORES" in r.detail


# --- E-04 tasa de cuarentena ---
def test_e04_dentro_del_umbral():
    assert ex.check_e04(n_aceptados=98, n_rechazados=2).passed  # 2 % exacto, frontera


def test_e04_por_encima_del_umbral_aborta():
    r = ex.check_e04(n_aceptados=97, n_rechazados=3)
    assert r.aborts


def test_e04_lote_vacio_aborta():
    assert ex.check_e04(0, 0).aborts


# --- E-05 integridad reservas -> flights ---
def test_e05_por_encima_del_95():
    reservas = ["AN1"] * 96 + ["AN9"] * 4
    r = ex.check_e05(reservas, ["AN1"])
    assert r.passed


def test_e05_por_debajo_del_95_aborta():
    reservas = ["AN1"] * 90 + ["AN9"] * 10
    assert ex.check_e05(reservas, ["AN1"]).aborts


def test_e05_sin_reservas_aborta():
    assert ex.check_e05([], ["AN1"]).aborts


# --- E-10 cobertura de reservas en vuelos operados ---
def test_e10_todos_los_operados_con_reserva_ok():
    vuelos = [
        {"codigo_vuelo": "AN1", "estado": "EN_VUELO"},
        {"codigo_vuelo": "AN2", "estado": "DEMORADO"},
        {"codigo_vuelo": "AN3", "estado": "A_TIEMPO"},  # lejano, puede ir a 0
    ]
    r = ex.check_e10(vuelos, ["AN1", "AN2"])  # AN3 sin reserva no importa
    assert r.passed


def test_e10_vuelo_operado_sin_reserva_aborta():
    vuelos = [
        {"codigo_vuelo": "AN1", "estado": "EMBARCANDO"},
        {"codigo_vuelo": "AN2", "estado": "ATERRIZADO"},
    ]
    r = ex.check_e10(vuelos, ["AN1"])  # AN2 aterrizado y sin reserva -> incoherente
    assert r.aborts and "AN2" in r.detail


# --- E-06 casi-duplicados (embeddings) ---
def test_e06_sin_vectores_es_ok_diferido():
    r = ex.check_e06(None)
    assert r.passed and "F4" in r.detail


def test_e06_par_casi_identico_cuarentena():
    v = [1.0, 0.0, 0.0]
    r = ex.check_e06([v, [1.0, 0.001, 0.0], [0.0, 1.0, 0.0]])
    assert not r.passed and r.action == "CUARENTENA"


def test_e06_vectores_distintos_ok():
    assert ex.check_e06([[1.0, 0.0], [0.0, 1.0]]).passed


# --- E-07 dimension y norma ---
def _unit(dim=ex.DIM_EMBEDDING):
    v = [0.0] * dim
    v[0] = 1.0
    return v


def test_e07_vector_unitario_1024_ok():
    assert ex.check_e07([_unit()]).passed


def test_e07_dimension_incorrecta_aborta():
    assert ex.check_e07([_unit(dim=512)]).aborts


def test_e07_norma_lejos_de_uno_aborta():
    v = [0.9, 0.9] + [0.0] * (ex.DIM_EMBEDDING - 2)
    assert ex.check_e07([v]).aborts


def test_e07_sin_vectores_diferido():
    assert ex.check_e07([]).passed


# --- E-08 deriva de volumen ---
def test_e08_sin_lote_anterior():
    assert ex.check_e08(100, None).passed


def test_e08_dentro_del_20():
    assert ex.check_e08(115, 100).passed


def test_e08_deriva_excesiva_aborta():
    assert ex.check_e08(130, 100).aborts


def test_e08_deriva_excesiva_con_flag_es_advertencia():
    r = ex.check_e08(130, 100, allow_volume_drift=True)
    assert r.passed and r.action == "ADVERTENCIA"


# --- E-09 frescura ---
def test_e09_dentro_del_sla():
    ts = datetime.now(timezone.utc) - timedelta(hours=2)
    assert ex.check_e09(ts, sla_hours=24).passed


def test_e09_fuera_del_sla_es_advertencia_no_aborta():
    ts = datetime.now(timezone.utc) - timedelta(hours=48)
    r = ex.check_e09(ts, sla_hours=24)
    assert not r.passed and r.action == "ADVERTENCIA" and not r.aborts


def test_e09_naive_datetime_se_asume_utc():
    ts = datetime.utcnow() - timedelta(hours=1)
    assert ex.check_e09(ts, sla_hours=24, now=datetime.now(timezone.utc)).passed


# --- evaluate ---
def test_evaluate_sin_abortos_devuelve_lista():
    res = [ex.check_e01(["A"]), ex.check_e04(100, 0)]
    assert ex.evaluate(res) == res


def test_evaluate_con_aborto_lanza():
    res = [ex.check_e02([_Doc("POL-MAS-001", referencias=["POL-X-999"])])]
    with pytest.raises(ex.BatchAborted, match="E-02"):
        ex.evaluate(res)


def test_coseno_vector_cero():
    assert ex._coseno([0.0, 0.0], [1.0, 1.0]) == 0.0
