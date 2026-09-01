"""Contratos Pydantic de entrada y salida de las herramientas (PRD §5.4).

**Distintos de los data contracts de `src/contracts/`** (§6A.8, R-09): el data
contract gobierna la *carga* a Silver; estos modelos gobiernan la *respuesta* de
la tool en cada invocacion. Son dos capas y no se elimina ninguna.

El sobre `ToolResult` es uniforme para las tres herramientas. **Ninguna
herramienta lanza excepcion hacia el LLM**: un fallo es un dato estructurado.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Sobre uniforme (§5.4)
# --------------------------------------------------------------------------- #
ToolErrorCode = Literal["NOT_FOUND", "INVALID_INPUT", "UPSTREAM_ERROR", "TIMEOUT"]


class ToolError(BaseModel):
    code: ToolErrorCode
    message: str


class ToolResult(BaseModel):
    ok: bool
    data: Any | None = None
    error: ToolError | None = None

    @classmethod
    def fail(cls, code: ToolErrorCode, message: str) -> "ToolResult":
        return cls(ok=False, error=ToolError(code=code, message=message))

    @classmethod
    def success(cls, data: Any) -> "ToolResult":
        return cls(ok=True, data=data)


# --------------------------------------------------------------------------- #
# consultar_estado_vuelo (§5.4.1)
# --------------------------------------------------------------------------- #
class ConsultarEstadoVueloInput(BaseModel):
    codigo_vuelo: str = Field(
        description="Codigo de vuelo de AeroNova, ej. 'AN405'. Formato AN seguido de 3 o 4 digitos.",
        pattern=r"^AN\d{3,4}$",
    )


class EstadoVueloData(BaseModel):
    codigo_vuelo: str
    estado: Literal["A_TIEMPO", "DEMORADO", "CANCELADO", "EMBARCANDO", "EN_VUELO", "ATERRIZADO"]
    origen: str                      # IATA, 3 letras
    destino: str                     # IATA, 3 letras
    salida_programada: str           # ISO 8601 con zona horaria
    salida_estimada: str | None = None
    minutos_demora: int = 0
    puerta: str | None = None
    motivo: str | None = None        # solo si estado es DEMORADO o CANCELADO
    fecha_consulta: str


# --------------------------------------------------------------------------- #
# obtener_datos_reserva (§5.4.2)
# --------------------------------------------------------------------------- #
class ObtenerDatosReservaInput(BaseModel):
    pnr: str = Field(
        description="Localizador de reserva alfanumerico de exactamente 6 caracteres en mayusculas, ej. 'ABC123'.",
        pattern=r"^[A-Z0-9]{6}$",
    )


class PasajeroData(BaseModel):
    nombre: str
    tipo: Literal["ADULTO", "MENOR", "INFANTE"]
    asiento: str | None = None


class DatosReservaData(BaseModel):
    pnr: str
    estado: Literal["CONFIRMADA", "CANCELADA", "EN_ESPERA", "VOLADA", "NO_SHOW"]
    codigo_vuelo: str
    fecha_vuelo: str
    # §5.4.2 no fija min_length; el runtime SI lo exige: una reserva con 0
    # pasajeros es la corrupcion de ruta B tipo 1 (§7.1) y esta validacion de
    # respuesta es la que la convierte en ok=False code=UPSTREAM_ERROR (R-09).
    pasajeros: list[PasajeroData] = Field(min_length=1)
    clase_tarifa: Literal["BASICA", "FLEX", "PREMIUM", "BUSINESS"]
    equipaje_facturado: int
    mascota_en_cabina: bool
    reembolsable: bool
    canal_compra: Literal["WEB", "MOSTRADOR", "AGENCIA", "CALL_CENTER"]
    # `fecha_compra` viaja en Gold (campo de carga de ReservaContract) pero no
    # forma parte de la respuesta: el modelo lo ignora (extra="ignore" por defecto).


# --------------------------------------------------------------------------- #
# buscar_politicas_rag (§5.4.3)
# --------------------------------------------------------------------------- #
CategoriaPolitica = Literal[
    "EQUIPAJE", "MASCOTAS", "CAMBIOS", "REEMBOLSOS", "MENORES", "COMPENSACIONES", "ACCESIBILIDAD"
]


class BuscarPoliticasRagInput(BaseModel):
    consulta: str = Field(
        description="Pregunta en lenguaje natural sobre politicas o normativa de AeroNova.",
        min_length=3,
        max_length=500,
    )
    categoria: CategoriaPolitica | None = None


class FragmentoPolitica(BaseModel):
    doc_id: str
    titulo: str
    categoria: str
    fragmento: str
    score: float
    vigencia_desde: str


class BusquedaPoliticasData(BaseModel):
    resultados: list[FragmentoPolitica]
    consulta_normalizada: str


# --------------------------------------------------------------------------- #
# Tools de operacion (ACU-006) -- solo lectura, sobre GSIs
# --------------------------------------------------------------------------- #
SentidoVuelo = Literal["salidas", "llegadas", "ambos"]


class VuelosPorCiudadInput(BaseModel):
    ciudad: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto/ciudad (p. ej. MEX, MAD, JFK).",
        pattern=r"^[A-Za-z]{3}$",
    )
    sentido: SentidoVuelo = "ambos"


class PasajerosDeVueloInput(BaseModel):
    codigo_vuelo: str = Field(description="Codigo del vuelo (AN + 3 o 4 digitos).", pattern=r"^AN\d{3,4}$")


class MascotasPorVueloInput(BaseModel):
    codigo_vuelo: str = Field(description="Codigo del vuelo (AN + 3 o 4 digitos).", pattern=r"^AN\d{3,4}$")


class RankingCabinaInput(BaseModel):
    ciudad: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto (p. ej. MEX, MAD, JFK).",
        pattern=r"^[A-Za-z]{3}$",
    )
    sentido: SentidoVuelo = "salidas"


class ResumenDemorasCiudadInput(BaseModel):
    ciudad: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto (p. ej. MEX, MAD, JFK).",
        pattern=r"^[A-Za-z]{3}$",
    )
    sentido: SentidoVuelo = "salidas"


class OcupacionVueloInput(BaseModel):
    codigo_vuelo: str = Field(description="Codigo del vuelo (AN + 3 o 4 digitos).", pattern=r"^AN\d{3,4}$")


class PerfilReservasVueloInput(BaseModel):
    codigo_vuelo: str = Field(description="Codigo del vuelo (AN + 3 o 4 digitos).", pattern=r"^AN\d{3,4}$")


class BuscarVuelosRutaInput(BaseModel):
    origen: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto de origen.",
        pattern=r"^[A-Za-z]{3}$",
    )
    destino: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto de destino.",
        pattern=r"^[A-Za-z]{3}$",
    )


class CoberturaReservasInput(BaseModel):
    ciudad: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto (p. ej. MEX, MAD, JFK).",
        pattern=r"^[A-Za-z]{3}$",
    )
    sentido: SentidoVuelo = "salidas"


class VuelosAContinenteInput(BaseModel):
    ciudad: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto de origen.",
        pattern=r"^[A-Za-z]{3}$",
    )
    continente: str = Field(
        description="Continente de destino: Norteamerica, Centroamerica, Sudamerica o Europa.",
        min_length=2, max_length=40,
    )


class NacionalesInternacionalesInput(BaseModel):
    ciudad: str = Field(
        description="Codigo IATA de 3 letras del aeropuerto (p. ej. MEX, MAD, JFK).",
        pattern=r"^[A-Za-z]{3}$",
    )
    sentido: SentidoVuelo = "salidas"
