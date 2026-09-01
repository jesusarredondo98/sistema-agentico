"""Acceso de solo lectura a las tablas Gold de DynamoDB (PRD §2.4, §2.5).

Las tools no hablan con boto3 directamente: pasan por aqui. Solo lectura por
clave primaria -- ``GetItem`` / ``BatchGetItem``. Ninguna escritura (§2.5: el
rol de la Lambda solo lee).
"""
from __future__ import annotations

import functools

import boto3

from src.config import get_settings


@functools.lru_cache(maxsize=1)
def _resource():
    cfg = get_settings()
    return boto3.resource("dynamodb", region_name=cfg.aws_region)


def get_flight(codigo_vuelo: str) -> dict | None:
    """Item crudo de ``aeronova-flights`` por ``codigo_vuelo``; ``None`` si no existe."""
    cfg = get_settings()
    tbl = _resource().Table(cfg.flights_table)
    return tbl.get_item(Key={"codigo_vuelo": codigo_vuelo}).get("Item")


def get_reservation(pnr: str) -> dict | None:
    """Item crudo de ``aeronova-reservations`` por ``pnr``; ``None`` si no existe."""
    cfg = get_settings()
    tbl = _resource().Table(cfg.reservations_table)
    return tbl.get_item(Key={"pnr": pnr}).get("Item")


# --- Consultas por GSI (ACU-006). Solo `Query` sobre indice, nunca `Scan`. ---
_MAX_PAGINAS = 6  # tope de paginacion defensivo


def _query_all(tbl, index_name: str, key_expr, limit: int) -> list[dict]:
    items: list[dict] = []
    kwargs = {"IndexName": index_name, "KeyConditionExpression": key_expr, "Limit": limit}
    for _ in range(_MAX_PAGINAS):
        resp = tbl.query(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items[:limit]


def query_flights_by_city(iata: str, sentido: str = "ambos", limit: int = 60) -> list[dict]:
    """Vuelos cuyo ``origen`` y/o ``destino`` es ``iata``. `sentido`: salidas | llegadas | ambos."""
    from boto3.dynamodb.conditions import Key

    cfg = get_settings()
    tbl = _resource().Table(cfg.flights_table)
    out: dict[str, dict] = {}
    if sentido in ("salidas", "ambos"):
        for it in _query_all(tbl, "origen-index", Key("origen").eq(iata), limit):
            out[it["codigo_vuelo"]] = it
    if sentido in ("llegadas", "ambos"):
        for it in _query_all(tbl, "destino-index", Key("destino").eq(iata), limit):
            out.setdefault(it["codigo_vuelo"], it)
    return list(out.values())[:limit]


def query_reservations_by_flight(codigo_vuelo: str, limit: int = 300) -> list[dict]:
    """Reservas de un vuelo (GSI ``codigo_vuelo-index``)."""
    from boto3.dynamodb.conditions import Key

    cfg = get_settings()
    tbl = _resource().Table(cfg.reservations_table)
    return _query_all(tbl, "codigo_vuelo-index", Key("codigo_vuelo").eq(codigo_vuelo), limit)
