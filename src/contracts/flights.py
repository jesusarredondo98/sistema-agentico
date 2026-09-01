"""``VueloContract`` v1.0.0 -- contrato de carga del dataset de vuelos (PRD §6A.3).

Deriva sus campos de ``EstadoVueloData`` (§5.4.1) pero es una **clase separada**:
el contrato gobierna la *carga* a Silver, ``EstadoVueloData`` gobierna la
*respuesta* de la tool. Unificarlos acopla dos ciclos de vida (§6A.3, §6A.8).
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from src.contracts.base import DataContract

ESTADOS_VUELO = ("A_TIEMPO", "DEMORADO", "CANCELADO", "EMBARCANDO", "EN_VUELO", "ATERRIZADO")
# Estados en los que §5.4.1 dice que `motivo` va informado y solo en esos.
_ESTADOS_CON_MOTIVO = {"DEMORADO", "CANCELADO"}


def _es_iso8601_con_zona(valor: str) -> bool:
    try:
        dt = datetime.fromisoformat(valor)
    except ValueError:
        return False
    return dt.tzinfo is not None


class VueloContract(DataContract):
    """Un vuelo del dataset sintetico, tal como entra al lago."""

    CONTRACT_NAME: ClassVar[str] = "flights.vuelo"
    CONTRACT_VERSION: ClassVar[str] = "1.0.0"
    CONTRACT_OWNER: ClassVar[str] = "operaciones@aeronova.example"
    CONTRACT_SLA_HOURS: ClassVar[int] = 24

    codigo_vuelo: str = Field(pattern=r"^AN\d{3,4}$")
    estado: Literal["A_TIEMPO", "DEMORADO", "CANCELADO", "EMBARCANDO", "EN_VUELO", "ATERRIZADO"]
    origen: str = Field(pattern=r"^[A-Z]{3}$")   # IATA
    destino: str = Field(pattern=r"^[A-Z]{3}$")  # IATA
    salida_programada: str  # ISO 8601 con zona horaria
    salida_estimada: str | None = None
    minutos_demora: int = Field(default=0, ge=0)
    puerta: str | None = None
    motivo: str | None = None  # solo si estado es DEMORADO o CANCELADO
    fecha_consulta: str  # ISO 8601 con zona horaria

    @field_validator("salida_programada", "fecha_consulta")
    @classmethod
    def _fechas_iso_con_zona(cls, v: str) -> str:
        if not _es_iso8601_con_zona(v):
            raise ValueError(f"{v!r} no es ISO 8601 con zona horaria")
        return v

    @field_validator("salida_estimada")
    @classmethod
    def _estimada_iso_con_zona(cls, v: str | None) -> str | None:
        if v is not None and not _es_iso8601_con_zona(v):
            raise ValueError(f"{v!r} no es ISO 8601 con zona horaria")
        return v

    @model_validator(mode="after")
    def _origen_distinto_de_destino(self) -> "VueloContract":
        if self.origen == self.destino:
            raise ValueError(f"origen y destino coinciden: {self.origen}")
        return self

    @model_validator(mode="after")
    def _motivo_solo_con_demora_o_cancelacion(self) -> "VueloContract":
        tiene_motivo = self.motivo is not None and self.motivo != ""
        if self.estado in _ESTADOS_CON_MOTIVO and not tiene_motivo:
            raise ValueError(f"estado {self.estado} exige `motivo` informado")
        if self.estado not in _ESTADOS_CON_MOTIVO and tiene_motivo:
            raise ValueError(f"`motivo` informado con estado {self.estado} (solo DEMORADO/CANCELADO)")
        return self

    @model_validator(mode="after")
    def _demora_coherente_con_estado(self) -> "VueloContract":
        if self.estado == "A_TIEMPO" and self.minutos_demora != 0:
            raise ValueError("estado A_TIEMPO con minutos_demora > 0")
        if self.estado == "DEMORADO" and self.minutos_demora <= 0:
            raise ValueError("estado DEMORADO con minutos_demora == 0")
        return self
