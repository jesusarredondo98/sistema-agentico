"""Geografia de los aeropuertos del conjunto sembrado (§7.2).

El dato de vuelos solo trae codigos IATA. Este modulo mapea cada codigo a su
ciudad, pais y continente para las tools `vuelos_a_continente` y
`vuelos_nacionales_internacionales`. Estatico: son 20 aeropuertos fijos.
"""
from __future__ import annotations

import unicodedata

# IATA -> (ciudad, pais, continente)
AEROPUERTOS: dict[str, tuple[str, str, str]] = {
    "MEX": ("Ciudad de Mexico", "Mexico", "Norteamerica"),
    "CUN": ("Cancun", "Mexico", "Norteamerica"),
    "GDL": ("Guadalajara", "Mexico", "Norteamerica"),
    "MTY": ("Monterrey", "Mexico", "Norteamerica"),
    "TIJ": ("Tijuana", "Mexico", "Norteamerica"),
    "JFK": ("Nueva York", "Estados Unidos", "Norteamerica"),
    "LAX": ("Los Angeles", "Estados Unidos", "Norteamerica"),
    "MIA": ("Miami", "Estados Unidos", "Norteamerica"),
    "ORD": ("Chicago", "Estados Unidos", "Norteamerica"),
    "DFW": ("Dallas", "Estados Unidos", "Norteamerica"),
    "YYZ": ("Toronto", "Canada", "Norteamerica"),
    "PTY": ("Ciudad de Panama", "Panama", "Centroamerica"),
    "BOG": ("Bogota", "Colombia", "Sudamerica"),
    "LIM": ("Lima", "Peru", "Sudamerica"),
    "SCL": ("Santiago", "Chile", "Sudamerica"),
    "EZE": ("Buenos Aires", "Argentina", "Sudamerica"),
    "GRU": ("Sao Paulo", "Brasil", "Sudamerica"),
    "MAD": ("Madrid", "Espana", "Europa"),
    "BCN": ("Barcelona", "Espana", "Europa"),
    "CDG": ("Paris", "Francia", "Europa"),
}

CONTINENTES = ("Norteamerica", "Centroamerica", "Sudamerica", "Europa")

# Sinonimos aceptados -> forma canonica.
_ALIAS_CONTINENTE = {
    "norteamerica": "Norteamerica", "america del norte": "Norteamerica",
    "north america": "Norteamerica", "na": "Norteamerica",
    "centroamerica": "Centroamerica", "america central": "Centroamerica",
    "central america": "Centroamerica",
    "sudamerica": "Sudamerica", "suramerica": "Sudamerica",
    "america del sur": "Sudamerica", "south america": "Sudamerica",
    "latinoamerica": "Sudamerica",
    "europa": "Europa", "europe": "Europa", "eu": "Europa",
}


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


def ciudad(iata: str) -> str:
    return AEROPUERTOS.get(iata.upper(), (iata.upper(), "", ""))[0]


def pais(iata: str) -> str:
    return AEROPUERTOS.get(iata.upper(), ("", "", ""))[1]


def continente(iata: str) -> str:
    return AEROPUERTOS.get(iata.upper(), ("", "", ""))[2]


def normaliza_continente(txt: str) -> str | None:
    """Devuelve la forma canonica del continente o None si no se reconoce."""
    return _ALIAS_CONTINENTE.get(_slug(txt))
