"""ui/examples.json (PRD §10.3, R-25, comprobacion U-14).

Verifica que la fuente unica de la guia de uso cumple los formatos de §5.4, que
cada grupo declara una `expected_tool` real, y que ningun ejemplo supera L-1.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.logic.limits import L1_MAX_CHARS
from src.tools import TOOL_REGISTRY

_EXAMPLES = Path(__file__).resolve().parents[2] / "ui" / "examples.json"

CODIGO_VUELO = re.compile(r"\bAN\d+\b")
CODIGO_VUELO_OK = re.compile(r"^AN\d{3,4}$")
# Token que "parece PNR": 6 caracteres, mayusculas y digitos, con al menos una letra
# (para no confundir con numeros sueltos como "4 horas").
POSIBLE_PNR = re.compile(r"\b(?=[A-Z0-9]{6}\b)(?=.*[A-Z])[A-Z0-9]{6}\b")
PNR_OK = re.compile(r"^[A-Z0-9]{6}$")


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(_EXAMPLES.read_text(encoding="utf-8"))


def _tools(valor) -> list[str]:
    return valor if isinstance(valor, list) else [valor]


def _textos_de_grupos(data: dict) -> list[str]:
    return [ej for g in data["grupos"] for ej in g["ejemplos"]]


def _textos_de_demo(data: dict) -> list[str]:
    return [d["texto"] for d in data["demo"]]


def test_estructura_minima(data):
    assert data["grupos"] and data["demo"]
    assert data["no_puedo"] and data["consejos"]
    for g in data["grupos"]:
        assert g["capacidad"] and g["ejemplos"]


def test_cada_grupo_declara_expected_tool_real(data):
    for g in data["grupos"]:
        for t in _tools(g["expected_tool"]):
            assert t in TOOL_REGISTRY, f"{g['capacidad']}: tool desconocida {t!r}"


def test_cada_demo_declara_expected_tool_real(data):
    for d in data["demo"]:
        for t in _tools(d["expected_tool"]):
            assert t in TOOL_REGISTRY, f"demo {d['texto']!r}: tool desconocida {t!r}"


@pytest.mark.parametrize("fuente", ["grupos", "demo"])
def test_codigos_de_vuelo_bien_formados(data, fuente):
    textos = _textos_de_grupos(data) if fuente == "grupos" else _textos_de_demo(data)
    for txt in textos:
        for cod in CODIGO_VUELO.findall(txt):
            assert CODIGO_VUELO_OK.match(cod), f"{txt!r}: codigo mal formado {cod!r}"


@pytest.mark.parametrize("fuente", ["grupos", "demo"])
def test_pnr_bien_formados(data, fuente):
    textos = _textos_de_grupos(data) if fuente == "grupos" else _textos_de_demo(data)
    for txt in textos:
        for pnr in POSIBLE_PNR.findall(txt):
            assert PNR_OK.match(pnr), f"{txt!r}: PNR mal formado {pnr!r}"


def test_ningun_ejemplo_supera_l1(data):
    for txt in _textos_de_grupos(data) + _textos_de_demo(data):
        assert len(txt) <= L1_MAX_CHARS, f"{txt!r} supera L-1 ({L1_MAX_CHARS})"


def test_ningun_ejemplo_usa_marcadores_de_posicion(data):
    """R-25, U-14: los ejemplos que la app inserta se pueden enviar tal cual, asi
    que NINGUNO (destacados, grupos ni demo) puede usar un marcador de posicion."""
    prohibidos = {"AN405", "AN1220", "AN882", "ABC123", "AN400"}
    textos = (
        _textos_de_grupos(data)
        + _textos_de_demo(data)
        + [d["texto"] for d in (data.get("destacados") or [])]
    )
    for txt in textos:
        assert not (prohibidos & set(txt.split())), f"{txt!r} usa un marcador de posicion"


def test_grupos_cubren_las_capacidades_base(data):
    caps = {g["capacidad"] for g in data["grupos"]}
    assert {
        "Estado de vuelos", "Reservas (PNR)", "Políticas internas", "Consultas combinadas",
    } <= caps


def test_destacados_bien_formados(data):
    """'destacados' se muestra en primer plano: tools reales, identificadores
    reales (como 'demo', no marcadores) y con una explicacion de por que."""
    destacados = data.get("destacados") or []
    assert len(destacados) >= 3
    prohibidos = {"AN405", "AN1220", "AN882", "ABC123"}
    for d in destacados:
        assert d["texto"] and d["por_que"]
        assert len(d["texto"]) <= L1_MAX_CHARS
        assert not (prohibidos & set(d["texto"].split())), f"destacado {d['texto']!r} usa un marcador"
        for t in _tools(d["expected_tool"]):
            assert t in TOOL_REGISTRY, f"destacado {d['texto']!r}: tool desconocida {t!r}"
        for cod in CODIGO_VUELO.findall(d["texto"]):
            assert CODIGO_VUELO_OK.match(cod), f"{d['texto']!r}: codigo mal formado {cod!r}"
        for pnr in POSIBLE_PNR.findall(d["texto"]):
            assert PNR_OK.match(pnr), f"{d['texto']!r}: PNR mal formado {pnr!r}"
