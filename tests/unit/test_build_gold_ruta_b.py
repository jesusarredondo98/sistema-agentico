"""Generacion de PNR de ruta B (pipelines/build_gold_dynamo.py, §7.1). Sin red."""
from __future__ import annotations

import re

from pipelines.build_gold_dynamo import ruta_b_pnrs

_PNR_RE = re.compile(r"^[A-Z0-9]{6}$")


def test_pnrs_son_6_alfanumericos_validos():
    pnrs = ruta_b_pnrs(50, exclude=set())
    assert len(pnrs) == 50
    assert all(_PNR_RE.match(p) for p in pnrs), pnrs[:5]


def test_pnrs_son_unicos_y_deterministas():
    a = ruta_b_pnrs(30, exclude=set())
    b = ruta_b_pnrs(30, exclude=set())
    assert a == b
    assert len(set(a)) == 30


def test_pnrs_esquivan_los_excluidos():
    primeros = ruta_b_pnrs(5, exclude=set())
    evitando = ruta_b_pnrs(5, exclude={primeros[0], primeros[2]})
    assert primeros[0] not in evitando and primeros[2] not in evitando
    assert len(set(evitando)) == 5
