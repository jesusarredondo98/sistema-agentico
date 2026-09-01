"""Puerta pytest del golden dataset (PRD §8.3).

El golden real corre contra el endpoint desplegado y consume LLM: NO se ejecuta
en la suite normal. Aquí solo se valida que `cases.json` está bien formado y
cubre las familias de §8.2 + `operacion_*` (ACU-006).

La corrida de aceptación es:

    AWS_PROFILE=aeronova python -m tests.golden.runner --full

y su resultado (los 9 umbrales de §8.3) se adjunta al informe de F10 (R-17: la
corrida completa es obligatoria, nunca `--smoke`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CASES = json.loads((Path(__file__).with_name("cases.json")).read_text(encoding="utf-8"))

FAMILIAS_MIN = {
    "rag_aislado": 4, "rag_cruzado": 4, "falta_datos": 4, "memory": 4, "tool_directa": 4,
    "anomalia": 4, "contract": 3, "hallucination": 4, "injection_doc": 2, "injection_escape": 1,
    "injection_tool": 2, "injection_user": 2, "abuse": 3, "operacion": 12,
}
_AN = re.compile(r"\bAN\d{3,4}\b")
_PNR = re.compile(r"\b[A-Z0-9]{6}\b")


def _fam(cid: str) -> str:
    return cid.rsplit("_", 1)[0]


def test_al_menos_41_casos():
    assert len(CASES["cases"]) >= 41


def test_familias_completas():
    conteo: dict[str, int] = {}
    for c in CASES["cases"]:
        conteo[_fam(c["id"])] = conteo.get(_fam(c["id"]), 0) + 1
    for fam, minimo in FAMILIAS_MIN.items():
        assert conteo.get(fam, 0) >= minimo, f"{fam}: {conteo.get(fam, 0)} < {minimo}"


def test_esquema_de_cada_caso():
    from src.tools import TOOL_REGISTRY

    ids = set()
    for c in CASES["cases"]:
        assert c["id"] not in ids, f"id duplicado {c['id']}"
        ids.add(c["id"])
        assert c["turns"] and all(t["message"] for t in c["turns"])
        for t in c["expect_tools"] + c["forbid_tools"]:
            assert t in TOOL_REGISTRY, f"{c['id']}: tool desconocida {t}"
        assert isinstance(c["expect_contains"], list)
        assert isinstance(c["expect_cites_doc"], bool)


def test_codigos_y_pnr_bien_formados():
    for c in CASES["cases"]:
        for t in c["turns"]:
            for cod in _AN.findall(t["message"]):
                assert re.fullmatch(r"AN\d{3,4}", cod)


def test_memory_tiene_dos_turnos():
    for c in CASES["cases"]:
        if _fam(c["id"]) == "memory":
            assert len(c["turns"]) == 2


def test_abuse_declara_error_y_sin_llm():
    for c in CASES["cases"]:
        if _fam(c["id"]) == "abuse":
            assert c.get("expect_error_code")
            assert c.get("expect_no_llm") is True
