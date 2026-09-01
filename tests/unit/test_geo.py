"""Mapa geográfico de los 20 aeropuertos sembrados (src/logic/geo.py)."""
from __future__ import annotations

import pytest

from src.logic import geo


def test_cada_aeropuerto_tiene_continente_valido():
    for iata, (ciudad, pais, cont) in geo.AEROPUERTOS.items():
        assert len(iata) == 3
        assert ciudad and pais
        assert cont in geo.CONTINENTES


@pytest.mark.parametrize(
    "iata,pais_esp,cont_esp",
    [
        ("MEX", "Mexico", "Norteamerica"),
        ("mex", "Mexico", "Norteamerica"),
        ("JFK", "Estados Unidos", "Norteamerica"),
        ("PTY", "Panama", "Centroamerica"),
        ("GRU", "Brasil", "Sudamerica"),
        ("MAD", "Espana", "Europa"),
    ],
)
def test_pais_y_continente(iata, pais_esp, cont_esp):
    assert geo.pais(iata) == pais_esp
    assert geo.continente(iata) == cont_esp


def test_iata_desconocido_devuelve_vacio():
    assert geo.pais("ZZZ") == ""
    assert geo.continente("ZZZ") == ""
    assert geo.ciudad("ZZZ") == "ZZZ"


@pytest.mark.parametrize(
    "texto,canon",
    [
        ("Europa", "Europa"),
        ("europa", "Europa"),
        ("EUROPE", "Europa"),
        ("Norteamérica", "Norteamerica"),
        ("america del norte", "Norteamerica"),
        ("Sudamérica", "Sudamerica"),
        ("América del Sur", "Sudamerica"),
        ("Centroamérica", "Centroamerica"),
    ],
)
def test_normaliza_continente_acepta_sinonimos(texto, canon):
    assert geo.normaliza_continente(texto) == canon


def test_normaliza_continente_desconocido_es_none():
    assert geo.normaliza_continente("Oceania") is None
    assert geo.normaliza_continente("") is None
