"""Fragmentacion del corpus para Silver (PRD §6.2, capa Silver).

Estrategia (ACU-006): **agrupar articulos consecutivos** hasta ~``GROUP_CHARS``
por fragmento. Partir por articulo suelto (una frase, ~130 car.) hacia que el
RAG recuperara frases sin contexto; el documento entero diluye demasiado la
consulta especifica (la prueba de humo de EQUIPAJE bajaba de 0,35). El punto
medio: 2-3 articulos por fragmento. Si un articulo por si solo supera
``MAX_CHARS`` se trocea, con solape y **sin partir frases**.
"""
from __future__ import annotations

import re

GROUP_CHARS = 500  # objetivo por fragmento: 2-3 articulos juntos
MAX_CHARS = 900    # tope duro; por encima se trocea un articulo largo
OVERLAP = 100

_ARTICULO_RE = re.compile(r"(?m)^\s*Articulo\s+\d+\.")
# Fin de frase: punto (o ?, !) seguido de espacio o fin.
_FIN_FRASE_RE = re.compile(r"[.?!](?:\s|$)")


def split_articulos(cuerpo: str) -> list[str]:
    """Divide el cuerpo en articulos. Si no hay marcadores, es un solo bloque."""
    marcas = [m.start() for m in _ARTICULO_RE.finditer(cuerpo)]
    if not marcas:
        return [cuerpo.strip()] if cuerpo.strip() else []
    marcas.append(len(cuerpo))
    return [cuerpo[marcas[i]:marcas[i + 1]].strip() for i in range(len(marcas) - 1)]


def _corte_en_frase(texto: str, objetivo: int) -> int:
    """Indice de corte <= objetivo que cae en un fin de frase; si no hay, `objetivo`."""
    if len(texto) <= objetivo:
        return len(texto)
    ultimo = 0
    for m in _FIN_FRASE_RE.finditer(texto):
        if m.end() > objetivo:
            break
        ultimo = m.end()
    return ultimo or objetivo


def chunk_articulo(articulo: str) -> list[str]:
    """Trocea un articulo en fragmentos de <= MAX_CHARS con solape, sin partir frases."""
    articulo = articulo.strip()
    if len(articulo) <= MAX_CHARS:
        return [articulo] if articulo else []
    trozos: list[str] = []
    inicio = 0
    while inicio < len(articulo):
        resto = articulo[inicio:]
        corte = _corte_en_frase(resto, MAX_CHARS)
        trozo = resto[:corte].strip()
        if trozo:
            trozos.append(trozo)
        if inicio + corte >= len(articulo):
            break
        # retroceder OVERLAP, pero arrancar en un limite de palabra
        nuevo = inicio + corte - OVERLAP
        espacio = articulo.rfind(" ", inicio, nuevo)
        inicio = espacio + 1 if espacio > inicio else nuevo
    return trozos


def _agrupar_articulos(articulos: list[str], objetivo: int = GROUP_CHARS) -> list[str]:
    """Junta articulos consecutivos en bloques de <= `objetivo` caracteres."""
    grupos: list[str] = []
    actual = ""
    for art in articulos:
        art = art.strip()
        if not art:
            continue
        if actual and len(actual) + len(art) + 2 > objetivo:
            grupos.append(actual)
            actual = art
        else:
            actual = f"{actual}\n\n{art}" if actual else art
    if actual:
        grupos.append(actual)
    return grupos


def chunk_documento(doc: dict) -> list[dict]:
    """Fragmentos de un documento ya validado. Devuelve filas para chunks.parquet.

    Se agrupan articulos consecutivos en bloques de ~GROUP_CHARS. Un articulo que
    por si solo supere MAX_CHARS se trocea (con solape, sin partir frases).
    """
    articulos = split_articulos(doc["cuerpo"])
    bloques = _agrupar_articulos(articulos)
    fragmentos: list[str] = []
    for b in bloques:
        fragmentos.extend(chunk_articulo(b) if len(b) > MAX_CHARS else [b])
    filas = []
    for i, frag in enumerate(fragmentos):
        filas.append(
            {
                "doc_id": doc["doc_id"],
                "titulo": doc["titulo"],
                "categoria": doc["categoria"],
                "vigencia_desde": doc["vigencia_desde"],
                "chunk_index": i,
                "fragmento": frag,
            }
        )
    return filas
