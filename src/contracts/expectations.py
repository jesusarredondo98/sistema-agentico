"""Expectativas de calidad a nivel de lote E-01..E-09 (PRD §6A.4).

Se evaluan **tras** validar registro a registro y **antes** de escribir Silver.
La validacion de registro no basta: un lote de registros individualmente validos
puede ser inservible (duplicados, referencias colgantes, cobertura insuficiente).

Cada ``check_eNN`` es una funcion pura que devuelve un ``ExpectationResult`` con
su ``action``. El pipeline (F2b/F4) las orquesta con ``evaluate``.

E-06 y E-07 operan sobre embeddings: se definen aqui pero solo se ejercitan en
F4, cuando existen los vectores. Sin vectores devuelven ``OK`` con nota.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Sequence

Action = Literal["ABORTA", "CUARENTENA", "ADVERTENCIA", "OK"]

# Umbrales de §6A.4 (no se ajustan sin decision).
UMBRAL_CUARENTENA = 0.02          # E-04: <= 2 %
UMBRAL_INTEGRIDAD_RESERVAS = 0.95  # E-05: >= 95 %
COBERTURA_MIN_POR_CATEGORIA = 15  # E-03
SIMILITUD_MAX_FRAGMENTOS = 0.98   # E-06
DIM_EMBEDDING = 1024              # E-07
NORMA_EMBEDDING_TOL = 1e-3        # E-07: norma ~ 1,0
DERIVA_VOLUMEN_MAX = 0.20         # E-08: <= 20 %


class BatchAborted(RuntimeError):
    """El lote no se promueve: una expectativa con accion ABORTA ha fallado."""


@dataclass(frozen=True)
class ExpectationResult:
    id: str
    passed: bool
    action: Action
    detail: str

    @property
    def aborts(self) -> bool:
        return self.action == "ABORTA" and not self.passed


def _ok(eid: str, action: Action, detail: str) -> ExpectationResult:
    return ExpectationResult(eid, True, action, detail)


def _fail(eid: str, action: Action, detail: str) -> ExpectationResult:
    return ExpectationResult(eid, False, action, detail)


# --------------------------------------------------------------------------- #
# E-01  Unicidad de la clave primaria                                          #
# --------------------------------------------------------------------------- #
def check_e01(keys: Sequence[str], *, dataset: str = "") -> ExpectationResult:
    """0 duplicados en la clave (`doc_id` / `codigo_vuelo` / `pnr`). Falla -> ABORTA."""
    dups = [k for k, n in Counter(keys).items() if n > 1]
    if dups:
        return _fail("E-01", "ABORTA", f"{dataset}: claves duplicadas {sorted(dups)[:10]}")
    return _ok("E-01", "ABORTA", f"{dataset}: {len(keys)} claves unicas")


# --------------------------------------------------------------------------- #
# E-02  Integridad referencial de las excepciones cruzadas (corpus)           #
# --------------------------------------------------------------------------- #
def check_e02(documentos: Sequence[object]) -> ExpectationResult:
    """Todo `doc_id` citado en `referencias` existe en el lote. Falla -> ABORTA.

    Es la mas importante (§6A.4): una referencia colgante hace que el agente
    cite una politica inexistente -- alucinacion por delegacion.
    """
    presentes = {getattr(d, "doc_id") for d in documentos}
    colgantes: list[tuple[str, str]] = []
    for d in documentos:
        for ref in getattr(d, "referencias", []):
            if ref not in presentes:
                colgantes.append((getattr(d, "doc_id"), ref))
    if colgantes:
        muestra = ", ".join(f"{src}->{ref}" for src, ref in colgantes[:10])
        return _fail("E-02", "ABORTA", f"referencias colgantes: {muestra}")
    return _ok("E-02", "ABORTA", f"{len(presentes)} documentos, integridad referencial 100 %")


# --------------------------------------------------------------------------- #
# E-03  Cobertura por categoria (corpus)                                       #
# --------------------------------------------------------------------------- #
def check_e03(documentos: Sequence[object], categorias: Sequence[str]) -> ExpectationResult:
    """>= 15 documentos en cada una de las 7 categorias. Falla -> ABORTA."""
    cuenta = Counter(getattr(d, "categoria") for d in documentos)
    flojas = {c: cuenta.get(c, 0) for c in categorias if cuenta.get(c, 0) < COBERTURA_MIN_POR_CATEGORIA}
    if flojas:
        return _fail("E-03", "ABORTA", f"cobertura insuficiente (< {COBERTURA_MIN_POR_CATEGORIA}): {flojas}")
    return _ok("E-03", "ABORTA", f"cobertura OK en {len(categorias)} categorias")


# --------------------------------------------------------------------------- #
# E-04  Tasa de cuarentena del lote                                            #
# --------------------------------------------------------------------------- #
def check_e04(n_aceptados: int, n_rechazados: int) -> ExpectationResult:
    """Tasa de rechazo <= 2 %. Falla -> ABORTA."""
    total = n_aceptados + n_rechazados
    if total == 0:
        return _fail("E-04", "ABORTA", "lote vacio")
    tasa = n_rechazados / total
    if tasa > UMBRAL_CUARENTENA:
        return _fail("E-04", "ABORTA", f"tasa de cuarentena {tasa:.2%} > {UMBRAL_CUARENTENA:.0%}")
    return _ok("E-04", "ABORTA", f"tasa de cuarentena {tasa:.2%}")


# --------------------------------------------------------------------------- #
# E-05  Integridad referencial reservations.codigo_vuelo -> flights            #
# --------------------------------------------------------------------------- #
def check_e05(codigos_en_reservas: Sequence[str], codigos_de_vuelos: Sequence[str]) -> ExpectationResult:
    """>= 95 % de los `codigo_vuelo` de reservas existen en flights. Falla -> ABORTA.

    El 5 % restante son las anomalias deliberadas de ruta A (§7.1).
    """
    if not codigos_en_reservas:
        return _fail("E-05", "ABORTA", "no hay reservas en el lote")
    universo = set(codigos_de_vuelos)
    casan = sum(1 for c in codigos_en_reservas if c in universo)
    ratio = casan / len(codigos_en_reservas)
    if ratio < UMBRAL_INTEGRIDAD_RESERVAS:
        return _fail("E-05", "ABORTA", f"integridad reservas->flights {ratio:.2%} < {UMBRAL_INTEGRIDAD_RESERVAS:.0%}")
    return _ok("E-05", "ABORTA", f"integridad reservas->flights {ratio:.2%}")


# --------------------------------------------------------------------------- #
# E-10  Cobertura de reservas en vuelos operados                               #
# --------------------------------------------------------------------------- #
# Un vuelo que ya embarca, esta en el aire, aterrizo o va demorado tuvo pasaje:
# debe tener >= 1 reserva. Los A_TIEMPO lejanos pueden ir a 0 sin problema.
ESTADOS_VUELO_OPERADOS = frozenset({"EMBARCANDO", "EN_VUELO", "ATERRIZADO", "DEMORADO"})


def check_e10(
    vuelos: Sequence[dict], codigos_en_reservas: Sequence[str]
) -> ExpectationResult:
    """Todo vuelo en estado operado tiene >= 1 reserva. Falla -> ABORTA."""
    con_reserva = set(codigos_en_reservas)
    operados = [v for v in vuelos if v.get("estado") in ESTADOS_VUELO_OPERADOS]
    sin = [v["codigo_vuelo"] for v in operados if v["codigo_vuelo"] not in con_reserva]
    if sin:
        return _fail("E-10", "ABORTA",
                     f"{len(sin)} vuelos operados sin ninguna reserva (p. ej. {sorted(sin)[:8]})")
    return _ok("E-10", "ABORTA", f"{len(operados)} vuelos operados, todos con >= 1 reserva")


# --------------------------------------------------------------------------- #
# E-06  Casi-duplicados entre fragmentos (embeddings, F4)                       #
# --------------------------------------------------------------------------- #
def _coseno(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return num / (na * nb)


def check_e06(vectores: Sequence[Sequence[float]] | None) -> ExpectationResult:
    """Similitud coseno entre fragmentos < 0,98. Falla -> CUARENTENA del duplicado.

    Protege el `top_k`: 4 fragmentos casi identicos degradan la respuesta sin
    que nada falle visiblemente.
    """
    if not vectores:
        return _ok("E-06", "CUARENTENA", "sin vectores; se ejercita en F4")
    n = len(vectores)
    for i in range(n):
        for j in range(i + 1, n):
            sim = _coseno(vectores[i], vectores[j])
            if sim >= SIMILITUD_MAX_FRAGMENTOS:
                return _fail("E-06", "CUARENTENA", f"fragmentos {i} y {j} con coseno {sim:.4f}")
    return _ok("E-06", "CUARENTENA", f"{n} fragmentos, ningun par >= {SIMILITUD_MAX_FRAGMENTOS}")


# --------------------------------------------------------------------------- #
# E-07  Dimension y norma del embedding (embeddings, F4)                        #
# --------------------------------------------------------------------------- #
def check_e07(vectores: Sequence[Sequence[float]] | None) -> ExpectationResult:
    """Dimension exactamente 1024 y norma ~ 1,0. Falla -> ABORTA."""
    if not vectores:
        return _ok("E-07", "ABORTA", "sin vectores; se ejercita en F4")
    for i, v in enumerate(vectores):
        if len(v) != DIM_EMBEDDING:
            return _fail("E-07", "ABORTA", f"vector {i}: dimension {len(v)} != {DIM_EMBEDDING}")
        norma = math.sqrt(sum(x * x for x in v))
        if abs(norma - 1.0) > NORMA_EMBEDDING_TOL:
            return _fail("E-07", "ABORTA", f"vector {i}: norma {norma:.5f} != 1,0")
    return _ok("E-07", "ABORTA", f"{len(vectores)} vectores, dim {DIM_EMBEDDING}, norma ~ 1,0")


# --------------------------------------------------------------------------- #
# E-08  Deriva de volumen frente al lote anterior                              #
# --------------------------------------------------------------------------- #
def check_e08(n_actual: int, n_anterior: int | None, *, allow_volume_drift: bool = False) -> ExpectationResult:
    """Variacion de volumen <= 20 %. Aborta salvo `--allow-volume-drift`."""
    if n_anterior is None or n_anterior == 0:
        return _ok("E-08", "ABORTA", "sin lote anterior de referencia")
    deriva = abs(n_actual - n_anterior) / n_anterior
    if deriva > DERIVA_VOLUMEN_MAX:
        if allow_volume_drift:
            return _ok("E-08", "ADVERTENCIA", f"deriva de volumen {deriva:.2%} permitida por flag")
        return _fail("E-08", "ABORTA", f"deriva de volumen {deriva:.2%} > {DERIVA_VOLUMEN_MAX:.0%}")
    return _ok("E-08", "ABORTA", f"deriva de volumen {deriva:.2%}")


# --------------------------------------------------------------------------- #
# E-09  Frescura del lote frente a CONTRACT_SLA_HOURS                           #
# --------------------------------------------------------------------------- #
def check_e09(batch_ts: datetime, sla_hours: int, *, now: datetime | None = None) -> ExpectationResult:
    """Edad del lote dentro del SLA del contrato. Falla -> ADVERTENCIA (no aborta)."""
    ahora = now or datetime.now(timezone.utc)
    if batch_ts.tzinfo is None:
        batch_ts = batch_ts.replace(tzinfo=timezone.utc)
    edad_horas = (ahora - batch_ts).total_seconds() / 3600
    if edad_horas > sla_hours:
        return _fail("E-09", "ADVERTENCIA", f"lote de {edad_horas:.1f} h, SLA {sla_hours} h")
    return _ok("E-09", "ADVERTENCIA", f"lote de {edad_horas:.1f} h dentro del SLA {sla_hours} h")


# --------------------------------------------------------------------------- #
# Orquestacion                                                                 #
# --------------------------------------------------------------------------- #
def evaluate(resultados: Sequence[ExpectationResult]) -> list[ExpectationResult]:
    """Devuelve los resultados y lanza ``BatchAborted`` si alguno aborta el lote."""
    aborta = [r for r in resultados if r.aborts]
    if aborta:
        motivos = "; ".join(f"{r.id}: {r.detail}" for r in aborta)
        raise BatchAborted(motivos)
    return list(resultados)
