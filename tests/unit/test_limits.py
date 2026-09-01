"""src/logic/limits.py (PRD §12A.3): L-2, L-3, L-4, L-5."""
from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from src.logic import limits as L


def test_estimate_tokens_es_ceil_len_entre_3_2():
    assert L.estimate_tokens("") == 0
    assert L.estimate_tokens("a" * 32) == 10


# --- L-2: tokens estimados <= 400 ---
def test_l2_mensaje_normal_pasa():
    L.check_message_budget("¿El vuelo AN405 esta demorado?")


def test_l2_mensaje_enorme_rechazado():
    with pytest.raises(L.InputRejected) as e:
        L.check_message_budget("palabra " * 300)  # ~2400 car -> ~750 tok
    assert e.value.rule == "L-2"


# --- L-3: ratio caracteres/tokens >= 1.5 ---
def test_l3_ratio_bajo_rechazado():
    # ratio = len / ceil(len/3.2). len=1 -> tok=1 -> ratio 1.0 < 1.5.
    with pytest.raises(L.InputRejected) as e:
        L.check_message_budget("x")
    assert e.value.rule == "L-3"


# --- L-5: turnos por sesion <= 50 ---
def test_l5_turno_50_pasa():
    L.check_turn_limit(50)


def test_l5_turno_51_rechazado():
    with pytest.raises(L.SessionTurnLimit):
        L.check_turn_limit(51)


# --- L-4: presupuesto del prompt ensamblado ---
def test_l4_sin_truncado_si_cabe():
    hist = [HumanMessage("corto") for _ in range(4)]
    kept, dropped = L.truncate_to_budget(1300, hist, budget=4000)
    assert dropped == 0 and len(kept) == 4


def test_l4_descarta_del_mas_antiguo_al_mas_reciente():
    hist = [HumanMessage("x" * 3200) for _ in range(5)]  # ~1000 tok cada uno
    kept, dropped = L.truncate_to_budget(1300, hist, budget=4000)
    # 1300 + 5*1000 = 6300 > 4000 -> descarta hasta caber: quedan 2 (1300+2000=3300)
    assert dropped == 3 and len(kept) == 2
    assert kept[0] is hist[3] and kept[1] is hist[4]  # se conservan los mas recientes
