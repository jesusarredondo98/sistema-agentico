"""Utilidades comunes a las herramientas (PRD §5.4.4, L-6).

- Timeout duro de 3 s por herramienta -> ``code="TIMEOUT"``.
- Presupuesto de <= 450 tokens por resultado: omitir ``null``, capar pasajeros
  a 9 e indicar el total aparte.
- Seam de metrica EMF (regla 5 de §5.4.4); la emision real es F6 (A-90).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

TOOL_TIMEOUT_S = 3.0
TOKEN_BUDGET = 450
MAX_PASAJEROS_EN_RESPUESTA = 9
# Ratio conservador para espanol (~3,5 car./token). La comprobacion con el
# tokenizador real es de F6 (L-4).
_CHARS_PER_TOKEN = 3.5

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool")


class ToolTimeout(Exception):
    """La herramienta supero TOOL_TIMEOUT_S."""


def run_with_timeout(fn: Callable[[], Any], seconds: float = TOOL_TIMEOUT_S) -> Any:
    """Ejecuta ``fn`` con timeout duro. Al vencer, lanza ``ToolTimeout``."""
    fut = _pool.submit(fn)
    try:
        return fut.result(timeout=seconds)
    except FuturesTimeout as exc:
        fut.cancel()
        raise ToolTimeout(f"la herramienta no respondio en {seconds:.0f} s") from exc


def estimate_tokens(obj: Any) -> int:
    """Estimacion por caracteres del tamano en tokens de un payload serializable."""
    import json

    return int(len(json.dumps(obj, ensure_ascii=False, default=str)) / _CHARS_PER_TOKEN) + 1


def drop_nulls(value: Any) -> Any:
    """Elimina recursivamente las claves con valor ``None`` (economia del payload)."""
    if isinstance(value, dict):
        return {k: drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [drop_nulls(v) for v in value]
    return value


def trim_reservation(data: dict) -> dict:
    """Recorta un ``DatosReservaData`` serializado al presupuesto de tokens (§5.4.4)."""
    out = dict(data)
    pax = out.get("pasajeros") or []
    out["total_pasajeros"] = len(pax)
    if len(pax) > MAX_PASAJEROS_EN_RESPUESTA:
        out["pasajeros"] = pax[:MAX_PASAJEROS_EN_RESPUESTA]
        out["pasajeros_truncados"] = True
    return drop_nulls(out)


def emit_tool_metric(name: str, ok: bool, latency_ms: float) -> None:
    """Seam de la metrica EMF por ejecucion (§5.4.4 regla 5). F6 la implementa."""
    # F0/F3: no-op con firma estable. src/logic/observability.py la conecta en F6.
    _ = (name, ok, latency_ms)


class timed:
    """Context manager que mide latencia en ms."""

    def __enter__(self) -> "timed":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = (time.perf_counter() - self._t0) * 1000
