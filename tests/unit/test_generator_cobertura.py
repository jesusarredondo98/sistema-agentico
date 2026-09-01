"""generate_synthetic.gen_reservations: cobertura E-10 (vuelos operados con reserva)."""
from __future__ import annotations

import importlib
import random

from faker import Faker

gs = importlib.import_module("scripts.generate_synthetic")


def test_todo_vuelo_operado_recibe_al_menos_una_reserva():
    rng = random.Random(7)
    fake = Faker("es_ES")
    fake.seed_instance(7)
    # 60 vuelos: fuerza estados variados por la distribución del generador
    vuelos = gs.gen_flights(60, rng, fake)
    # pocas reservas a propósito -> sin la cobertura, varios operados quedarían a 0
    reservas, reparto = gs.gen_reservations(25, vuelos, rng, fake)

    con_reserva = {r["codigo_vuelo"] for r in reservas}
    operados = [v for v in vuelos if v["estado"] in gs.ESTADOS_VUELO_OPERADOS]
    sin = [v["codigo_vuelo"] for v in operados if v["codigo_vuelo"] not in con_reserva]
    assert sin == [], f"vuelos operados sin reserva: {sin}"
    # con 25 reservas aleatorias sobre 60 vuelos, la cobertura tuvo que añadir varias
    assert reparto["cobertura_e10"] >= 1
    # la misma expectativa E-10 del pipeline debe pasar con estos datos
    from src.contracts import expectations as ex
    assert ex.check_e10(vuelos, [r["codigo_vuelo"] for r in reservas]).passed
