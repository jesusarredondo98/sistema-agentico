"""Fragmentacion del corpus (PRD §6.2): por articulo, <=800, solape 100, sin partir frases."""
from __future__ import annotations

from pipelines._chunking import (
    MAX_CHARS,
    OVERLAP,
    chunk_articulo,
    chunk_documento,
    split_articulos,
)


def test_split_articulos_por_marcador():
    cuerpo = "Articulo 1. Uno.\n\nArticulo 2. Dos.\n\nArticulo 3. Tres."
    arts = split_articulos(cuerpo)
    assert len(arts) == 3
    assert arts[0].startswith("Articulo 1.")
    assert arts[2].startswith("Articulo 3.")


def test_split_articulos_sin_marcador_es_un_bloque():
    assert split_articulos("Texto sin articulos.") == ["Texto sin articulos."]
    assert split_articulos("   ") == []


def test_articulo_corto_es_un_solo_fragmento():
    art = "Articulo 1. " + "palabra " * 20
    assert len(chunk_articulo(art)) == 1


def test_articulo_largo_se_trocea_por_debajo_del_limite():
    art = "Articulo 1. " + ("Esta es una frase de prueba. " * 80)
    trozos = chunk_articulo(art)
    assert len(trozos) > 1
    assert all(len(t) <= MAX_CHARS for t in trozos)


def test_no_parte_a_mitad_de_frase():
    art = "Articulo 1. " + ("Frase una. Frase dos larga con varias palabras. " * 40)
    trozos = chunk_articulo(art)
    # todos menos quiza el ultimo terminan en signo de puntuacion de fin de frase
    for t in trozos[:-1]:
        assert t.rstrip()[-1] in ".!?"


def test_hay_solape_entre_trozos_consecutivos():
    art = "Articulo 1. " + ("Alfa beta gamma delta. " * 60)
    trozos = chunk_articulo(art)
    if len(trozos) >= 2:
        cola = trozos[0][-OVERLAP:]
        # alguna palabra del final del primero reaparece al inicio del segundo
        assert any(w and w in trozos[1][:OVERLAP + 40] for w in cola.split())


def test_chunk_documento_conserva_metadatos_y_orden():
    doc = {
        "doc_id": "POL-MAS-001",
        "titulo": "Mascotas",
        "categoria": "MASCOTAS",
        "vigencia_desde": "2025-01-01",
        "cuerpo": "Articulo 1. Uno dos tres.\n\nArticulo 2. Cuatro cinco seis.",
    }
    filas = chunk_documento(doc)
    assert [f["chunk_index"] for f in filas] == list(range(len(filas)))
    assert all(f["doc_id"] == "POL-MAS-001" for f in filas)
    assert all(f["categoria"] == "MASCOTAS" for f in filas)


def test_documento_corto_es_un_solo_fragmento():
    doc = {
        "doc_id": "POL-MEN-001", "titulo": "t", "categoria": "MENORES", "vigencia_desde": "2025-01-01",
        "cuerpo": "Articulo 1. Regla uno.\n\nArticulo 2. Regla dos.\n\nArticulo 3. Regla tres.",
    }
    filas = chunk_documento(doc)
    assert len(filas) == 1
    assert "Regla uno" in filas[0]["fragmento"] and "Regla tres" in filas[0]["fragmento"]


def test_documento_muy_largo_se_trocea():
    largo = "\n\n".join(f"Articulo {i}. " + ("frase larga de relleno. " * 20) for i in range(1, 6))
    doc = {"doc_id": "X", "titulo": "t", "categoria": "EQUIPAJE", "vigencia_desde": "2025-01-01", "cuerpo": largo}
    filas = chunk_documento(doc)
    assert len(filas) > 1
    assert all(len(f["fragmento"]) <= MAX_CHARS for f in filas)
