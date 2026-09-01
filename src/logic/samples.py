"""Muestra de datos de prueba para la UI (§10.3, panel «Datos de prueba»).

Devuelve unos cuantos vuelos y reservas **reales** del Gold, distintos en cada
llamada, para que la demo no se quede siempre con los mismos códigos. Solo
lectura sobre GSIs, sin LLM: es un modo aparte del endpoint (`mode: "sample"`).
"""
from __future__ import annotations

import random

from src.logic.dynamo import query_flights_by_city, query_reservations_by_flight

# Aeropuertos presentes en el conjunto sembrado (§7.2).
_AEROPUERTOS = [
    "MEX", "MAD", "BCN", "BOG", "LIM", "GRU", "JFK", "CDG", "MIA", "LAX",
    "DFW", "GDL", "YYZ", "PTY", "EZE", "CUN", "MTY", "TIJ", "SCL", "ORD",
]
_ESTADO_VUELO = {
    "A_TIEMPO": "A tiempo", "DEMORADO": "Demorado", "CANCELADO": "Cancelado",
    "EMBARCANDO": "Embarcando", "EN_VUELO": "En vuelo", "ATERRIZADO": "Aterrizado",
}
_ESTADO_RES = {
    "CONFIRMADA": "Confirmada", "CANCELADA": "Cancelada", "EN_ESPERA": "En espera",
    "VOLADA": "Volada", "NO_SHOW": "No-show",
}
_TARIFA = {"BASICA": "Básica", "FLEX": "Flex", "PREMIUM": "Premium", "BUSINESS": "Business"}

_N_VUELOS = 8
_N_RESERVAS = 6


def _bonito(mapa: dict, clave) -> str:
    return mapa.get(str(clave), str(clave).replace("_", " ").capitalize())


def sample_datos_prueba(rng: random.Random | None = None) -> dict:
    """`{"vuelos": [...], "reservas": [...]}` con la forma que pinta la UI."""
    rng = rng or random.Random()

    # 1) vuelos: unos aeropuertos al azar, priorizando variedad de estado.
    crudos: dict[str, dict] = {}
    for iata in rng.sample(_AEROPUERTOS, k=min(3, len(_AEROPUERTOS))):
        try:
            for v in query_flights_by_city(iata, "salidas", limit=40):
                cod = v.get("codigo_vuelo")
                if cod and cod not in crudos:
                    crudos[cod] = v
        except Exception:  # noqa: BLE001 - si una GSI falla, seguimos con lo que haya
            continue

    por_estado: dict[str, list[dict]] = {}
    for v in crudos.values():
        por_estado.setdefault(str(v.get("estado", "?")), []).append(v)
    for lst in por_estado.values():
        rng.shuffle(lst)

    elegidos: list[dict] = []
    ronda = 0
    while len(elegidos) < _N_VUELOS and any(por_estado.values()):
        for est in list(por_estado):
            if por_estado[est]:
                elegidos.append(por_estado[est].pop())
                if len(elegidos) >= _N_VUELOS:
                    break
        ronda += 1
        if ronda > 20:
            break

    vuelos = [
        {"codigo": v.get("codigo_vuelo"),
         "ruta": f"{v.get('origen', '?')} → {v.get('destino', '?')}",
         "estado": _bonito(_ESTADO_VUELO, v.get("estado"))}
        for v in elegidos
    ]

    # 2) reservas: PNRs de unos cuantos de esos vuelos.
    reservas: list[dict] = []
    for v in rng.sample(elegidos, k=min(5, len(elegidos))):
        if len(reservas) >= _N_RESERVAS:
            break
        try:
            rs = query_reservations_by_flight(v.get("codigo_vuelo", ""), limit=40)
        except Exception:  # noqa: BLE001
            continue
        rng.shuffle(rs)
        for r in rs[:2]:
            reservas.append({
                "pnr": r.get("pnr"),
                "estado": _bonito(_ESTADO_RES, r.get("estado")),
                "tarifa": _bonito(_TARIFA, r.get("clase_tarifa")),
                "vuelo": r.get("codigo_vuelo"),
            })
            if len(reservas) >= _N_RESERVAS:
                break

    return {"vuelos": vuelos, "reservas": reservas}
