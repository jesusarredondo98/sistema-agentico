"""Logs JSON, redaccion de PII, metricas EMF y coste (PRD §11, §12).

La redaccion no es opcional: la conversacion contiene PII y §12 la exige. Es la
misma razon por la que `aeronova-memory` queda fuera del medallion (§6A.0).
"""
from __future__ import annotations

import hashlib

from aws_lambda_powertools import Logger
from aws_lambda_powertools.metrics import MetricUnit, single_metric

NAMESPACE = "AeroNova/Agent"
SERVICE = "aeronova-agent"

logger = Logger(service=SERVICE)

# Precios USD por millon de tokens (§9.1). Escritura de cache TTL 1h = 2x entrada.
_PRICE_IN = 2.00 / 1_000_000
_PRICE_OUT = 10.00 / 1_000_000
_PRICE_CACHE_READ = 0.20 / 1_000_000
_PRICE_CACHE_WRITE_1H = 4.00 / 1_000_000


# --------------------------------------------------------------------------- #
# Redaccion de PII (§11)
# --------------------------------------------------------------------------- #
def mask_pnr(pnr: str | None) -> str:
    """`ABC123` -> `AB***3`. Nunca se registra el PNR completo."""
    if not pnr:
        return ""
    if len(pnr) <= 3:
        return "*" * len(pnr)
    return f"{pnr[:2]}{'*' * (len(pnr) - 3)}{pnr[-1]}"


def redact_message(message: str) -> dict:
    """El `message` integro NO se registra: solo longitud y hash corto."""
    return {
        "len": len(message or ""),
        "sha256_8": hashlib.sha256((message or "").encode("utf-8")).hexdigest()[:8],
    }


# --------------------------------------------------------------------------- #
# Metricas EMF (espacio AeroNova/Agent, §11)
# --------------------------------------------------------------------------- #
def emit_metric(name: str, value: float = 1, unit: MetricUnit = MetricUnit.Count,
                dimensions: dict[str, str] | None = None) -> None:
    """Emite una metrica EMF con sus dimensiones propias (§11)."""
    try:
        with single_metric(name=name, unit=unit, value=value, namespace=NAMESPACE) as m:
            m.add_dimension(name="service", value=SERVICE)
            for k, v in (dimensions or {}).items():
                m.add_dimension(name=k, value=str(v))
    except Exception:  # noqa: BLE001 - la observabilidad nunca rompe el turno
        logger.exception("fallo al emitir la metrica %s", name)


# --------------------------------------------------------------------------- #
# Coste por turno (§4.2, §9.3)
# --------------------------------------------------------------------------- #
def compute_cost(usage: dict) -> float:
    """USD de un turno a partir del `usage` de la respuesta de Anthropic.

    `input_tokens` de la API ya EXCLUYE lo servido/escrito en cache.
    """
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cache_write = usage.get("cache_creation_input_tokens", 0) or 0
    return round(
        inp * _PRICE_IN
        + out * _PRICE_OUT
        + cache_read * _PRICE_CACHE_READ
        + cache_write * _PRICE_CACHE_WRITE_1H,
        6,
    )
