"""``DocumentoNormativoContract`` v1.0.0 -- contrato del corpus del RAG (PRD §6A.3).

Es el contrato que el sponsor pidio explicitamente. Gobierna la **carga** de los
documentos normativos a Silver; los modelos de respuesta de la tool RAG (§5.4.3)
son clases distintas.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from typing import ClassVar, Literal

from pydantic import Field, model_validator

from src.contracts.base import DataContract

# Prefijo de doc_id -> categoria (§6A.3, validacion cruzada 1).
_PREFIJO_A_CATEGORIA: dict[str, str] = {
    "EQU": "EQUIPAJE",
    "MAS": "MASCOTAS",
    "CAM": "CAMBIOS",
    "REE": "REEMBOLSOS",
    "MEN": "MENORES",
    "COM": "COMPENSACIONES",
    "ACC": "ACCESIBILIDAD",
}
CATEGORIAS: tuple[str, ...] = tuple(_PREFIJO_A_CATEGORIA.values())

_DOC_ID_RE = re.compile(r"^POL-(EQU|MAS|CAM|REE|MEN|COM|ACC)-\d{3}$")
# doc_id citado dentro del cuerpo (para la validacion cruzada 4).
_REF_EN_CUERPO_RE = re.compile(r"POL-(?:EQU|MAS|CAM|REE|MEN|COM|ACC)-\d{3}")


def normalizar_cuerpo(texto: str) -> str:
    """Normalizacion canonica del cuerpo antes de calcular su sha256.

    Debe ser identica en el generador sintetico (F2b) y en la puerta de
    contrato, o ``checksum_cuerpo`` nunca cuadrara. Reglas:

    - Unicode a forma NFC.
    - Finales de linea a ``\\n`` (CRLF / CR -> LF).
    - Espacios/tabuladores finales de cada linea eliminados.
    - Espacios de borde del texto completo eliminados.
    """
    t = unicodedata.normalize("NFC", texto)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = "\n".join(linea.rstrip(" \t") for linea in t.split("\n"))
    return t.strip()


def sha256_cuerpo(texto: str) -> str:
    """sha256 hex del cuerpo normalizado."""
    return hashlib.sha256(normalizar_cuerpo(texto).encode("utf-8")).hexdigest()


class DocumentoNormativoContract(DataContract):
    """Un documento normativo del corpus. Literal de §6A.3 + 5 validaciones cruzadas."""

    CONTRACT_NAME: ClassVar[str] = "corpus.documento_normativo"
    CONTRACT_VERSION: ClassVar[str] = "1.0.0"
    CONTRACT_OWNER: ClassVar[str] = "operaciones@aeronova.example"
    CONTRACT_SLA_HOURS: ClassVar[int] = 720

    doc_id: str = Field(pattern=r"^POL-(EQU|MAS|CAM|REE|MEN|COM|ACC)-\d{3}$")
    titulo: str = Field(min_length=10, max_length=200)
    categoria: Literal[
        "EQUIPAJE", "MASCOTAS", "CAMBIOS", "REEMBOLSOS",
        "MENORES", "COMPENSACIONES", "ACCESIBILIDAD",
    ]
    vigencia_desde: date
    vigencia_hasta: date | None = None
    cuerpo: str = Field(min_length=400, max_length=12000)
    referencias: list[str] = Field(default_factory=list)  # doc_id citados en el cuerpo
    idioma: Literal["es"] = "es"
    checksum_cuerpo: str = Field(pattern=r"^[a-f0-9]{64}$")  # sha256 del cuerpo normalizado

    # --- Validaciones cruzadas obligatorias (§6A.3) ---

    @model_validator(mode="after")
    def _prefijo_coincide_con_categoria(self) -> "DocumentoNormativoContract":
        m = _DOC_ID_RE.match(self.doc_id)
        if m is None:  # pragma: no cover - lo cubre el pattern del Field
            return self
        esperada = _PREFIJO_A_CATEGORIA[m.group(1)]
        if esperada != self.categoria:
            raise ValueError(
                f"doc_id {self.doc_id} implica categoria {esperada}, no {self.categoria}"
            )
        return self

    @model_validator(mode="after")
    def _vigencia_hasta_posterior(self) -> "DocumentoNormativoContract":
        if self.vigencia_hasta is not None and self.vigencia_hasta <= self.vigencia_desde:
            raise ValueError(
                f"vigencia_hasta ({self.vigencia_hasta}) no es posterior a "
                f"vigencia_desde ({self.vigencia_desde})"
            )
        return self

    @model_validator(mode="after")
    def _vigencia_desde_no_futura(self) -> "DocumentoNormativoContract":
        if self.vigencia_desde > date.today():
            raise ValueError(f"vigencia_desde ({self.vigencia_desde}) es futura")
        return self

    @model_validator(mode="after")
    def _referencias_coinciden_con_cuerpo(self) -> "DocumentoNormativoContract":
        en_cuerpo = set(_REF_EN_CUERPO_RE.findall(self.cuerpo)) - {self.doc_id}
        declaradas = set(self.referencias)
        if declaradas != en_cuerpo:
            faltan = en_cuerpo - declaradas
            sobran = declaradas - en_cuerpo
            raise ValueError(
                f"referencias no coinciden con el cuerpo: sin declarar={sorted(faltan)}, "
                f"declaradas de mas={sorted(sobran)}"
            )
        return self

    @model_validator(mode="after")
    def _checksum_coincide(self) -> "DocumentoNormativoContract":
        recalculado = sha256_cuerpo(self.cuerpo)
        if self.checksum_cuerpo != recalculado:
            raise ValueError(
                "checksum_cuerpo no coincide con el sha256 recalculado del cuerpo normalizado"
            )
        return self
