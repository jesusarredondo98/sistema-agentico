"""Registro de las herramientas expuestas al LLM (PRD §5.4, §3).

En F3 estan las dos de datos. ``buscar_politicas_rag`` se anade en F4. El
grafo (F5) toma este registro y hace el ``bind_tools``. Todas son de **solo
lectura** (I-13, D-3): ninguna con efectos secundarios.
"""
from __future__ import annotations

from src.tools.flights import consultar_estado_vuelo
from src.tools.operaciones import (
    buscar_vuelos_ruta,
    cobertura_reservas,
    mascotas_por_vuelo,
    ocupacion_vuelo,
    pasajeros_de_vuelo,
    perfil_reservas_vuelo,
    radar_operativo,
    ranking_cabina,
    resumen_demoras_ciudad,
    vuelos_a_continente,
    vuelos_nac_int,
    vuelos_por_ciudad,
)
from src.tools.pnr import obtener_datos_reserva
from src.tools.rag import buscar_politicas_rag
from src.tools.schemas import (
    BuscarPoliticasRagInput,
    BuscarVuelosRutaInput,
    CoberturaReservasInput,
    ConsultarEstadoVueloInput,
    MascotasPorVueloInput,
    NacionalesInternacionalesInput,
    ObtenerDatosReservaInput,
    OcupacionVueloInput,
    PasajerosDeVueloInput,
    PerfilReservasVueloInput,
    RankingCabinaInput,
    ResumenDemorasCiudadInput,
    ToolError,
    ToolResult,
    VuelosAContinenteInput,
    VuelosPorCiudadInput,
)

# nombre -> (callable, modelo de entrada). El grafo (F5) hace el bind_tools.
TOOL_REGISTRY: dict[str, tuple] = {
    "consultar_estado_vuelo": (consultar_estado_vuelo, ConsultarEstadoVueloInput),
    "obtener_datos_reserva": (obtener_datos_reserva, ObtenerDatosReservaInput),
    "buscar_politicas_rag": (buscar_politicas_rag, BuscarPoliticasRagInput),
    # ACU-006 (solo lectura, sobre GSIs)
    "vuelos_por_ciudad": (vuelos_por_ciudad, VuelosPorCiudadInput),
    "pasajeros_de_vuelo": (pasajeros_de_vuelo, PasajerosDeVueloInput),
    "mascotas_por_vuelo": (mascotas_por_vuelo, MascotasPorVueloInput),
    "ranking_cabina": (ranking_cabina, RankingCabinaInput),
    "resumen_demoras_ciudad": (resumen_demoras_ciudad, ResumenDemorasCiudadInput),
    "ocupacion_vuelo": (ocupacion_vuelo, OcupacionVueloInput),
    "perfil_reservas_vuelo": (perfil_reservas_vuelo, PerfilReservasVueloInput),
    "buscar_vuelos_ruta": (buscar_vuelos_ruta, BuscarVuelosRutaInput),
    "cobertura_reservas": (cobertura_reservas, CoberturaReservasInput),
    "vuelos_a_continente": (vuelos_a_continente, VuelosAContinenteInput),
    "vuelos_nac_int": (vuelos_nac_int, NacionalesInternacionalesInput),
    "radar_operativo": (radar_operativo, VuelosPorCiudadInput),
}

__all__ = [
    "TOOL_REGISTRY",
    "consultar_estado_vuelo",
    "obtener_datos_reserva",
    "buscar_politicas_rag",
    "vuelos_por_ciudad",
    "pasajeros_de_vuelo",
    "mascotas_por_vuelo",
    "ranking_cabina",
    "resumen_demoras_ciudad",
    "ocupacion_vuelo",
    "perfil_reservas_vuelo",
    "buscar_vuelos_ruta",
    "cobertura_reservas",
    "vuelos_a_continente",
    "vuelos_nac_int",
    "radar_operativo",
    "ToolResult",
    "ToolError",
]
