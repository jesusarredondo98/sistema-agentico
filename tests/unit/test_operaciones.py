"""Tools de operación (ACU-006 y ampliación): vuelos_por_ciudad, pasajeros_de_vuelo,
mascotas_por_vuelo, ranking_cabina, resumen_demoras_ciudad, ocupacion_vuelo,
perfil_reservas_vuelo, buscar_vuelos_ruta, cobertura_reservas, vuelos_a_continente,
vuelos_nac_int, radar_operativo. GSIs mockeados. Sin AWS."""
from __future__ import annotations

import pytest

from src.tools import operaciones as ops

_VUELOS = {
    "MEX": {
        "salidas": [
            {"codigo_vuelo": "AN1001", "origen": "MEX", "destino": "BOG", "estado": "A_TIEMPO",
             "minutos_demora": 0, "salida_programada": "2026-09-01T08:00:00+00:00", "puerta": "A1"},
            {"codigo_vuelo": "AN1002", "origen": "MEX", "destino": "MAD", "estado": "DEMORADO",
             "minutos_demora": 45, "motivo": "meteorologia adversa",
             "salida_programada": "2026-09-01T09:00:00+00:00", "puerta": "B2"},
            {"codigo_vuelo": "AN1003", "origen": "MEX", "destino": "JFK", "estado": "CANCELADO",
             "minutos_demora": 0, "motivo": "huelga de controladores",
             "salida_programada": "2026-09-01T10:00:00+00:00", "puerta": "C3"},
            {"codigo_vuelo": "AN1004", "origen": "MEX", "destino": "MAD", "estado": "A_TIEMPO",
             "minutos_demora": 0, "salida_programada": "2026-09-01T18:00:00+00:00", "puerta": "B7"},
        ],
        "llegadas": [
            {"codigo_vuelo": "AN2001", "origen": "LIM", "destino": "MEX", "estado": "A_TIEMPO",
             "minutos_demora": 0},
        ],
    },
    "GDL": {
        "salidas": [
            {"codigo_vuelo": "AN3001", "origen": "GDL", "destino": "MEX", "estado": "EN_VUELO",
             "minutos_demora": 0},  # operado y SIN reservas -> incoherente
            {"codigo_vuelo": "AN3002", "origen": "GDL", "destino": "LAX", "estado": "A_TIEMPO",
             "minutos_demora": 0},  # sin reservas pero A_TIEMPO -> ok
            {"codigo_vuelo": "AN3003", "origen": "GDL", "destino": "TIJ", "estado": "DEMORADO",
             "minutos_demora": 30, "motivo": "x"},  # con reservas
        ],
    },
}
_RESERVAS = {
    "AN1002": [
        {"pnr": "AAA111", "codigo_vuelo": "AN1002", "estado": "CONFIRMADA", "clase_tarifa": "FLEX",
         "canal_compra": "WEB", "reembolsable": True, "equipaje_facturado": 2, "mascota_en_cabina": True,
         "pasajeros": [{"nombre": "Ana Ruiz", "tipo": "ADULTO"}, {"nombre": "Leo Ruiz", "tipo": "MENOR"}]},
        {"pnr": "BBB222", "codigo_vuelo": "AN1002", "estado": "CANCELADA", "clase_tarifa": "BASICA",
         "canal_compra": "AGENCIA", "reembolsable": False, "equipaje_facturado": 0, "mascota_en_cabina": False,
         "pasajeros": [{"nombre": "Sara Gil", "tipo": "ADULTO"}]},
    ],
    "AN1003": [
        {"pnr": "CCC333", "codigo_vuelo": "AN1003", "estado": "CONFIRMADA", "clase_tarifa": "PREMIUM",
         "canal_compra": "WEB", "reembolsable": True, "equipaje_facturado": 1, "mascota_en_cabina": True,
         "pasajeros": [{"nombre": "Pau Mora", "tipo": "ADULTO"}, {"nombre": "Nil Mora", "tipo": "INFANTE"}]},
    ],
    "AN3003": [
        {"pnr": "DDD444", "codigo_vuelo": "AN3003", "estado": "CONFIRMADA", "clase_tarifa": "FLEX",
         "canal_compra": "WEB", "reembolsable": True, "equipaje_facturado": 0, "mascota_en_cabina": False,
         "pasajeros": [{"nombre": "Eva Sol", "tipo": "ADULTO"}]},
    ],
}


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setattr(ops, "query_flights_by_city",
                        lambda iata, sentido="ambos", limit=60: _VUELOS.get(iata, {}).get(sentido, [])
                        if sentido != "ambos" else
                        _VUELOS.get(iata, {}).get("salidas", []) + _VUELOS.get(iata, {}).get("llegadas", []))
    monkeypatch.setattr(ops, "query_reservations_by_flight",
                        lambda codigo, limit=300: _RESERVAS.get(codigo, []))


def test_vuelos_por_ciudad_desglosa_por_estado():
    r = ops.vuelos_por_ciudad("mex", "salidas")
    assert r.ok
    assert r.data["ciudad"] == "MEX" and r.data["total"] == 4
    assert r.data["por_estado"] == {"A_TIEMPO": 2, "DEMORADO": 1, "CANCELADO": 1}


def test_vuelos_por_ciudad_iata_invalido():
    r = ops.vuelos_por_ciudad("MEXICO")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_vuelos_por_ciudad_sin_resultados_es_not_found():
    r = ops.vuelos_por_ciudad("ZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_pasajeros_de_vuelo_muestra_reproducible():
    r1 = ops.pasajeros_de_vuelo("AN1002")
    r2 = ops.pasajeros_de_vuelo("AN1002")
    assert r1.ok and r1.data["total_pasajeros"] == 3
    assert len(r1.data["muestra"]) == 3  # hay menos de 5
    assert r1.data["muestra"] == r2.data["muestra"]  # determinista por codigo


def test_pasajeros_de_vuelo_codigo_invalido():
    r = ops.pasajeros_de_vuelo("XYZ")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_mascotas_por_vuelo_cuenta():
    r = ops.mascotas_por_vuelo("AN1002")
    assert r.ok and r.data == {"codigo_vuelo": "AN1002", "reservas": 2, "con_mascota_en_cabina": 1}


def test_radar_operativo_briefing_completo():
    r = ops.radar_operativo("MEX")
    assert r.ok
    d = r.data
    assert d["ciudad"] == "MEX"
    assert d["salidas"]["por_estado"] == {"A_TIEMPO": 2, "DEMORADO": 1, "CANCELADO": 1}
    assert d["cancelaciones_salida"]["codigos"] == ["AN1003"]
    assert d["demoras_salida"] == {"vuelos": 1, "media_min": 45, "max_min": 45}
    # AN1002 (demorado, 3 pax) + AN1003 (cancelado, 2 pax) -> 2 mascotas, 5 pasajeros
    assert d["impacto_en_vuelos_criticos"]["mascotas_en_cabina"] == 2
    assert d["impacto_en_vuelos_criticos"]["pasajeros_afectados"] == 5


def test_radar_operativo_ciudad_sin_operacion():
    r = ops.radar_operativo("ZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# Ampliación de tools (ranking_cabina + 4 nuevas)
# --------------------------------------------------------------------------- #
def test_ranking_cabina_ordena_por_mascotas_y_menores():
    r = ops.ranking_cabina("MEX", "salidas")
    assert r.ok
    d = r.data
    assert d["ciudad"] == "MEX" and d["sentido"] == "salidas"
    assert d["totales"]["mascotas_en_cabina"] == 2   # AN1002 (1) + AN1003 (1)
    assert d["totales"]["menores_en_cabina"] == 2    # AN1002 MENOR + AN1003 INFANTE
    top_masc = d["top_mascotas_en_cabina"]
    assert {f["codigo_vuelo"] for f in top_masc[:2]} == {"AN1002", "AN1003"}
    assert top_masc == sorted(top_masc, key=lambda f: f["mascotas_en_cabina"], reverse=True)


def test_ranking_cabina_iata_invalido():
    r = ops.ranking_cabina("MEXICO")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_ranking_cabina_ciudad_sin_vuelos():
    r = ops.ranking_cabina("ZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_resumen_demoras_ciudad():
    r = ops.resumen_demoras_ciudad("MEX", "salidas")
    assert r.ok
    d = r.data
    assert d["total_vuelos"] == 4
    assert d["a_tiempo"] == 2 and d["demorados"] == 1 and d["cancelados"] == 1
    assert d["puntualidad_pct"] == 50
    assert d["demora_media_min"] == 45 and d["demora_max_min"] == 45
    assert d["peores_demoras"][0]["codigo_vuelo"] == "AN1002"
    motivos = {m["motivo"] for m in d["motivos_frecuentes"]}
    assert "meteorologia adversa" in motivos and "huelga de controladores" in motivos


def test_resumen_demoras_ciudad_sin_vuelos():
    r = ops.resumen_demoras_ciudad("ZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_ocupacion_vuelo_agrega_pasaje_y_tarifas():
    r = ops.ocupacion_vuelo("AN1002")
    assert r.ok
    d = r.data
    assert d["reservas"] == 2 and d["pasajeros"] == 3
    assert d["por_tipo_pasajero"] == {"ADULTO": 2, "MENOR": 1}
    assert d["por_clase_tarifa"] == {"FLEX": 1, "BASICA": 1}
    assert d["equipaje_facturado_total"] == 2
    assert d["tamano_medio_reserva"] == 1.5


def test_ocupacion_vuelo_codigo_invalido():
    r = ops.ocupacion_vuelo("XYZ")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_ocupacion_vuelo_sin_reservas():
    r = ops.ocupacion_vuelo("AN9999")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_perfil_reservas_vuelo_desglosa():
    r = ops.perfil_reservas_vuelo("AN1002")
    assert r.ok
    d = r.data
    assert d["reservas"] == 2
    assert d["por_estado"] == {"CONFIRMADA": 1, "CANCELADA": 1}
    assert d["por_canal_compra"] == {"WEB": 1, "AGENCIA": 1}
    assert d["reembolsables"] == 1


def test_buscar_vuelos_ruta_filtra_por_destino():
    r = ops.buscar_vuelos_ruta("mex", "mad")
    assert r.ok
    d = r.data
    assert d["origen"] == "MEX" and d["destino"] == "MAD"
    assert d["total"] == 2  # AN1002 y AN1004
    assert {v["codigo_vuelo"] for v in d["vuelos"]} == {"AN1002", "AN1004"}
    assert d["vuelos"][0]["codigo_vuelo"] == "AN1002"  # ordenado por salida_programada


def test_buscar_vuelos_ruta_sin_vuelos_es_not_found():
    r = ops.buscar_vuelos_ruta("MEX", "BOG")  # AN1001 va a BOG -> sí hay
    assert r.ok and r.data["total"] == 1
    r2 = ops.buscar_vuelos_ruta("MEX", "SCL")  # ninguno
    assert not r2.ok and r2.error.code == "NOT_FOUND"


def test_buscar_vuelos_ruta_origen_igual_destino():
    r = ops.buscar_vuelos_ruta("MEX", "MEX")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_cobertura_reservas_cuenta_con_sin_y_marca_incoherentes():
    r = ops.cobertura_reservas("GDL", "salidas")
    assert r.ok
    d = r.data
    assert d["vuelos_analizados"] == 3
    assert d["con_reservas"] == 1          # AN3003
    assert d["sin_reservas"] == 2          # AN3001, AN3002
    # solo AN3001 (EN_VUELO) es incoherente; AN3002 es A_TIEMPO
    incs = {f["codigo_vuelo"] for f in d["sin_reservas_pero_operando"]}
    assert incs == {"AN3001"}


def test_cobertura_reservas_iata_invalido():
    r = ops.cobertura_reservas("MEXICO")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_cobertura_reservas_ciudad_sin_vuelos():
    r = ops.cobertura_reservas("ZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# vuelos_a_continente / vuelos_nac_int (geografía sobre los 20 aeropuertos)
# --------------------------------------------------------------------------- #
def test_vuelos_a_continente_agrupa_por_pais():
    r = ops.vuelos_a_continente("mex", "Europa")
    assert r.ok
    d = r.data
    assert d["ciudad"] == "MEX" and d["continente"] == "Europa"
    assert d["hay_vuelos"] is True and d["total"] == 2   # AN1002 y AN1004 -> MAD
    assert d["por_pais"] == {"Espana": 2}


def test_vuelos_a_continente_sin_vuelos_a_ese_continente():
    r = ops.vuelos_a_continente("MEX", "Centroamerica")
    assert r.ok
    assert r.data["hay_vuelos"] is False and r.data["total"] == 0


def test_vuelos_a_continente_continente_no_reconocido():
    r = ops.vuelos_a_continente("MEX", "Oceania")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_vuelos_a_continente_iata_invalido():
    r = ops.vuelos_a_continente("MEXICO", "Europa")
    assert not r.ok and r.error.code == "INVALID_INPUT"


def test_vuelos_nac_int_reparte_nacional_e_internacional():
    r = ops.vuelos_nac_int("gdl", "salidas")
    assert r.ok
    d = r.data
    assert d["ciudad"] == "GDL" and d["pais"] == "Mexico"
    assert d["total"] == 3
    assert d["nacionales"] == 2          # AN3001 -> MEX, AN3003 -> TIJ
    assert d["internacionales"] == 1     # AN3002 -> LAX
    assert d["internacionales_por_pais"] == {"Estados Unidos": 1}


def test_vuelos_nac_int_aeropuerto_fuera_de_catalogo():
    r = ops.vuelos_nac_int("ZZZ")
    assert not r.ok and r.error.code == "NOT_FOUND"


def test_vuelos_nac_int_iata_invalido():
    r = ops.vuelos_nac_int("MEXICO")
    assert not r.ok and r.error.code == "INVALID_INPUT"
