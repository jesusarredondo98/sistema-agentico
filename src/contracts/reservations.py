"""``ReservaContract`` v1.0.0 -- contrato de carga del dataset de reservas (PRD §6A.3).

Deriva sus campos de ``DatosReservaData`` / ``PasajeroData`` (§5.4.2) pero es una
**clase separada**: contrato = carga, modelo de §5.4 = respuesta (§6A.3, §6A.8).

Lleva ademas ``fecha_compra``, que **no** existe en ``DatosReservaData``: es un
campo solo de carga necesario para que la anomalia de ruta A tipo 4 de §7.1
("fecha_vuelo anterior a la fecha de compra") sea detectable por contrato. La
version se mantiene en 1.0.0 porque aun no se ha cargado ningun dato.
"""
from __future__ import annotations

from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.contracts.base import DataContract

ESTADOS_RESERVA = ("CONFIRMADA", "CANCELADA", "EN_ESPERA", "VOLADA", "NO_SHOW")
CLASES_TARIFA = ("BASICA", "FLEX", "PREMIUM", "BUSINESS")
CANALES_COMPRA = ("WEB", "MOSTRADOR", "AGENCIA", "CALL_CENTER")
TIPOS_PASAJERO = ("ADULTO", "MENOR", "INFANTE")

# Maximo real de un PNR (§5.4.4): la tool trunca a 9; el contrato lo exige en carga.
MAX_PASAJEROS = 9


class PasajeroContract(BaseModel):
    """Un pasajero dentro de una reserva."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=120)
    tipo: Literal["ADULTO", "MENOR", "INFANTE"]
    asiento: str | None = None


class ReservaContract(DataContract):
    """Una reserva (PNR) del dataset sintetico, tal como entra al lago."""

    CONTRACT_NAME: ClassVar[str] = "reservations.reserva"
    CONTRACT_VERSION: ClassVar[str] = "1.0.0"
    CONTRACT_OWNER: ClassVar[str] = "atencion_cliente@aeronova.example"
    CONTRACT_SLA_HOURS: ClassVar[int] = 24

    pnr: str = Field(pattern=r"^[A-Z0-9]{6}$")
    estado: Literal["CONFIRMADA", "CANCELADA", "EN_ESPERA", "VOLADA", "NO_SHOW"]
    codigo_vuelo: str = Field(pattern=r"^AN\d{3,4}$")
    fecha_vuelo: str  # ISO 8601 (fecha)
    fecha_compra: str  # ISO 8601 (fecha) -- solo carga, no esta en DatosReservaData
    pasajeros: list[PasajeroContract] = Field(min_length=1, max_length=MAX_PASAJEROS)
    clase_tarifa: Literal["BASICA", "FLEX", "PREMIUM", "BUSINESS"]
    equipaje_facturado: int = Field(ge=0, le=20)
    mascota_en_cabina: bool
    reembolsable: bool
    canal_compra: Literal["WEB", "MOSTRADOR", "AGENCIA", "CALL_CENTER"]

    @model_validator(mode="after")
    def _fechas_iso_y_orden(self) -> "ReservaContract":
        try:
            fv = date.fromisoformat(self.fecha_vuelo)
        except ValueError as exc:
            raise ValueError(f"fecha_vuelo {self.fecha_vuelo!r} no es una fecha ISO 8601") from exc
        try:
            fc = date.fromisoformat(self.fecha_compra)
        except ValueError as exc:
            raise ValueError(f"fecha_compra {self.fecha_compra!r} no es una fecha ISO 8601") from exc
        # Anomalia de ruta A tipo 4 (§7.1): no se puede volar antes de comprar.
        if fv < fc:
            raise ValueError(f"fecha_vuelo ({fv}) es anterior a fecha_compra ({fc})")
        return self

    @model_validator(mode="after")
    def _menores_e_infantes_acompanados(self) -> "ReservaContract":
        """Un INFANTE o MENOR no viaja solo: exige al menos un ADULTO en el PNR.

        SUPONGO (no literal en el PRD): regla de negocio aeronautica estandar.
        Si el generador sintetico de F2b necesita PNR de menor no acompanado,
        se revisa esta regla, no se salta.
        """
        tipos = {p.tipo for p in self.pasajeros}
        if tipos & {"MENOR", "INFANTE"} and "ADULTO" not in tipos:
            raise ValueError("reserva con MENOR/INFANTE sin ningun ADULTO acompanante")
        return self
