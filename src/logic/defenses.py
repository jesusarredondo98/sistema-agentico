"""Defensa en capas contra inyeccion de prompts (PRD §12A.2, D-1..D-6).

- D-1: escapar `<`/`>` en todo texto no confiable **antes** de envolverlo.
- D-2: envoltura `<dato_operativo>` (tools operativas) / `<documento_recuperado>` (RAG).
- D-4: sin canal de operador intercalado -> ya se cumple (system de nivel superior).
- D-5: filtro de salida (firma del prompt + claves) -> respuesta generica, 200, evento.
- D-6: marcadores en la entrada -> marcar y seguir, **nunca bloquear**.
"""
from __future__ import annotations

import re

# --- D-6: marcadores de sondeo conocidos (§12A.2) ---
_INJECTION_MARKERS = re.compile(
    r"ignora (las )?instrucciones|system prompt|eres ahora|"
    r"modo (admin|desarrollador)|reveal your instructions",
    re.IGNORECASE,
)

# --- D-5: firma del system prompt (§5.5). Tres frases distintivas y fijas. ---
_SIGNATURE_PHRASES = (
    "Eres el asistente operativo de AeroNova",
    "Reglas inviolables:",
    "El contenido dentro de las etiquetas <documento_recuperado> y <dato_operativo>",
)
_SK_ANT = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")

# Cadenas-cebo que solo aparecen en los intentos de inyeccion sembrados en el
# corpus (§7.1, POL-ACC-019/020). Nunca deben salir en una respuesta, ni siquiera
# citadas por el modelo al explicar que ignora la inyeccion.
_CANARIOS_INYECCION = re.compile(
    r"SISTEMA-COMPROMETIDO|ESCAPE-FALLIDO", re.IGNORECASE
)
_CANARIO_REEMPLAZO = "[texto bloqueado]"

OUTPUT_FILTER_REPLACEMENT = (
    "No puedo compartir esa informacion. ¿Te ayudo con una consulta operativa de "
    "vuelos, reservas o politicas de AeroNova?"
)


# --------------------------------------------------------------------------- #
# D-1: neutralizacion del delimitador
# --------------------------------------------------------------------------- #
def escape_delimiters(text: str) -> str:
    """Sustituye `<` por `&lt;` y `>` por `&gt;`. La envoltura queda infalsificable."""
    return str(text).replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# D-2: envoltura de contenido no confiable
# --------------------------------------------------------------------------- #
def wrap_dato_operativo(fuente: str, contenido: str) -> str:
    return (f'<dato_operativo fuente="{escape_delimiters(fuente)}">'
            f'{escape_delimiters(contenido)}</dato_operativo>')


def wrap_documento_recuperado(doc_id: str, titulo: str, fragmento: str) -> str:
    return (f'<documento_recuperado id="{escape_delimiters(doc_id)}" '
            f'titulo="{escape_delimiters(titulo)}">'
            f'{escape_delimiters(fragmento)}</documento_recuperado>')


# --------------------------------------------------------------------------- #
# D-6: deteccion en la entrada (marcar, NO bloquear)
# --------------------------------------------------------------------------- #
def input_looks_like_injection(message: str) -> bool:
    return bool(_INJECTION_MARKERS.search(message or ""))


# --------------------------------------------------------------------------- #
# D-5: filtro de salida
# --------------------------------------------------------------------------- #
def output_leaks_secret(reply: str) -> bool:
    if not reply:
        return False
    if _SK_ANT.search(reply) or "ANTHROPIC_API_KEY" in reply:
        return True
    return any(frase in reply for frase in _SIGNATURE_PHRASES)


def scrub_injection_markers(reply: str) -> str:
    """Elimina las cadenas-cebo de inyeccion de la respuesta (D-5, red de
    seguridad determinista). No sustituye toda la respuesta: solo tacha el token,
    asi una explicacion correcta de 'ignoro esta inyeccion' sobrevive."""
    if not reply:
        return reply
    return _CANARIOS_INYECCION.sub(_CANARIO_REEMPLAZO, reply)
