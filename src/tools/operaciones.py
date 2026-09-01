"""Herramientas de operacion (ACU-006). Solo lectura, sobre GSIs de DynamoDB.

- ``vuelos_por_ciudad``       -> vuelos de un aeropuerto + desglose por estado
- ``pasajeros_de_vuelo``      -> muestra determinista de 5 pasajeros de un vuelo
- ``mascotas_por_vuelo``      -> recuento de mascotas en cabina de un vuelo
- ``ranking_cabina``          -> vuelos de un aeropuerto ordenados por mascotas y menores en cabina
- ``resumen_demoras_ciudad``  -> demoras de un aeropuerto: media, maximo, puntualidad, motivos
- ``ocupacion_vuelo``         -> agregados de pasaje de un vuelo: por tipo, por tarifa, equipaje
- ``perfil_reservas_vuelo``   -> reservas de un vuelo por estado, tarifa, canal y reembolsabilidad
- ``buscar_vuelos_ruta``      -> vuelos en una ruta origen -> destino
- ``cobertura_reservas``      -> vuelos de un aeropuerto con/sin reservas (conteo)
- ``vuelos_a_continente``     -> vuelos de un aeropuerto hacia un continente
- ``vuelos_nac_int``          -> reparto nacional / internacional de un aeropuerto
- ``radar_operativo``         -> briefing completo de una ciudad (la tool "wow")

Ninguna lanza excepcion al LLM: todo fallo es un ``ToolResult``. Presupuesto
duro de 3 s por llamada; enriquecimientos acotados para que no se disparen.
"""
from __future__ import annotations

import random
from collections import Counter

from pydantic import ValidationError

from concurrent.futures import ThreadPoolExecutor

from src.logic import geo
from src.logic.dynamo import (
    query_flights_by_city,
    query_reservations_by_flight,
)
from src.tools._runtime import ToolTimeout, emit_tool_metric, run_with_timeout, timed
from src.tools.schemas import (
    BuscarVuelosRutaInput,
    CoberturaReservasInput,
    MascotasPorVueloInput,
    NacionalesInternacionalesInput,
    OcupacionVueloInput,
    PasajerosDeVueloInput,
    PerfilReservasVueloInput,
    RankingCabinaInput,
    ResumenDemorasCiudadInput,
    ToolResult,
    VuelosAContinenteInput,
    VuelosPorCiudadInput,
)

_ESTADOS_VUELO_OPERADOS = frozenset({"EMBARCANDO", "EN_VUELO", "ATERRIZADO", "DEMORADO"})

# Topes defensivos (§5.4.4, "no se dispare").
_MAX_VUELOS_LISTADOS = 20
_MAX_VUELOS_ENRIQUECIDOS = 12
_MAX_VUELOS_RANKING = 40
_TOP_N_RANKING = 5
_MUESTRA_PASAJEROS = 5
_TIPOS_MENOR = ("MENOR", "INFANTE")


def _first_msg(e: ValidationError) -> str:
    err = e.errors()[0]
    return f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"


def _con_metrica(nombre: str, fn) -> ToolResult:
    with timed() as t:
        try:
            res = run_with_timeout(fn)
        except ToolTimeout as e:
            res = ToolResult.fail("TIMEOUT", str(e))
        except Exception as e:  # noqa: BLE001 - la tool no propaga nada al LLM
            res = ToolResult.fail("UPSTREAM_ERROR", f"error en {nombre}: {e}")
    emit_tool_metric(nombre, res.ok, t.ms)
    return res


# --------------------------------------------------------------------------- #
def vuelos_por_ciudad(ciudad: str, sentido: str = "ambos") -> ToolResult:
    """Vuelos de un aeropuerto (por codigo IATA) con desglose por estado."""
    try:
        entrada = VuelosPorCiudadInput(ciudad=ciudad, sentido=sentido)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        iata = entrada.ciudad.upper()
        vuelos = query_flights_by_city(iata, entrada.sentido)
        if not vuelos:
            return ToolResult.fail("NOT_FOUND", f"no hay vuelos para {iata} ({entrada.sentido})")
        por_estado = Counter(str(v.get("estado", "?")) for v in vuelos)
        listado = [
            {"codigo_vuelo": v.get("codigo_vuelo"), "origen": v.get("origen"),
             "destino": v.get("destino"), "estado": v.get("estado")}
            for v in vuelos[:_MAX_VUELOS_LISTADOS]
        ]
        return ToolResult.success({
            "ciudad": iata,
            "sentido": entrada.sentido,
            "total": len(vuelos),
            "por_estado": dict(por_estado),
            "vuelos": listado,
        })

    return _con_metrica("vuelos_por_ciudad", _run)


# --------------------------------------------------------------------------- #
def pasajeros_de_vuelo(codigo_vuelo: str) -> ToolResult:
    """Muestra determinista de 5 pasajeros de un vuelo (demo)."""
    try:
        entrada = PasajerosDeVueloInput(codigo_vuelo=codigo_vuelo)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        reservas = query_reservations_by_flight(entrada.codigo_vuelo)
        if not reservas:
            return ToolResult.fail("NOT_FOUND", f"no hay reservas para el vuelo {entrada.codigo_vuelo}")
        pax = [
            {"nombre": p.get("nombre", ""), "tipo": p.get("tipo", ""), "pnr": r.get("pnr", "")}
            for r in reservas for p in (r.get("pasajeros") or [])
        ]
        rng = random.Random(entrada.codigo_vuelo)  # semilla = codigo -> reproducible en la demo
        muestra = rng.sample(pax, min(_MUESTRA_PASAJEROS, len(pax)))
        return ToolResult.success({
            "codigo_vuelo": entrada.codigo_vuelo,
            "total_pasajeros": len(pax),
            "muestra": muestra,
            "nota": "Muestra aleatoria de 5, reproducible. Datos sinteticos.",
        })

    return _con_metrica("pasajeros_de_vuelo", _run)


# --------------------------------------------------------------------------- #
def mascotas_por_vuelo(codigo_vuelo: str) -> ToolResult:
    """Recuento de mascotas en cabina de un vuelo."""
    try:
        entrada = MascotasPorVueloInput(codigo_vuelo=codigo_vuelo)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        reservas = query_reservations_by_flight(entrada.codigo_vuelo)
        if not reservas:
            return ToolResult.fail("NOT_FOUND", f"no hay reservas para el vuelo {entrada.codigo_vuelo}")
        con = sum(1 for r in reservas if r.get("mascota_en_cabina"))
        return ToolResult.success({
            "codigo_vuelo": entrada.codigo_vuelo,
            "reservas": len(reservas),
            "con_mascota_en_cabina": con,
        })

    return _con_metrica("mascotas_por_vuelo", _run)


# --------------------------------------------------------------------------- #
def ranking_cabina(ciudad: str, sentido: str = "salidas") -> ToolResult:
    """Vuelos de un aeropuerto ordenados por mascotas en cabina y por menores a bordo."""
    try:
        entrada = RankingCabinaInput(ciudad=ciudad, sentido=sentido)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        iata = entrada.ciudad.upper()
        vuelos = query_flights_by_city(iata, entrada.sentido)
        if not vuelos:
            return ToolResult.fail("NOT_FOUND", f"no hay vuelos para {iata} ({entrada.sentido})")

        analizados = vuelos[:_MAX_VUELOS_RANKING]

        def _fila(v: dict) -> dict:
            cod = v.get("codigo_vuelo", "")
            rs = query_reservations_by_flight(cod, limit=300)
            masc = sum(1 for r in rs if r.get("mascota_en_cabina"))
            menores = sum(
                1
                for r in rs
                for p in (r.get("pasajeros") or [])
                if p.get("tipo") in _TIPOS_MENOR
            )
            return {
                "codigo_vuelo": cod, "origen": v.get("origen"), "destino": v.get("destino"),
                "estado": v.get("estado"), "mascotas_en_cabina": masc, "menores_en_cabina": menores,
            }

        with ThreadPoolExecutor(max_workers=10) as pool:
            filas = list(pool.map(_fila, analizados))

        top_masc = sorted(filas, key=lambda f: f["mascotas_en_cabina"], reverse=True)[:_TOP_N_RANKING]
        top_men = sorted(filas, key=lambda f: f["menores_en_cabina"], reverse=True)[:_TOP_N_RANKING]
        nota = (
            f"Ranking sobre los primeros {len(filas)} vuelos de {iata} ({entrada.sentido})."
            if len(vuelos) > len(filas)
            else None
        )
        return ToolResult.success({
            "ciudad": iata,
            "sentido": entrada.sentido,
            "vuelos_analizados": len(filas),
            **({"nota": nota} if nota else {}),
            "totales": {
                "mascotas_en_cabina": sum(f["mascotas_en_cabina"] for f in filas),
                "menores_en_cabina": sum(f["menores_en_cabina"] for f in filas),
            },
            "top_mascotas_en_cabina": [
                {"codigo_vuelo": f["codigo_vuelo"], "origen": f["origen"], "destino": f["destino"],
                 "estado": f["estado"], "mascotas_en_cabina": f["mascotas_en_cabina"]}
                for f in top_masc
            ],
            "top_menores_en_cabina": [
                {"codigo_vuelo": f["codigo_vuelo"], "origen": f["origen"], "destino": f["destino"],
                 "estado": f["estado"], "menores_en_cabina": f["menores_en_cabina"]}
                for f in top_men
            ],
        })

    return _con_metrica("ranking_cabina", _run)


# --------------------------------------------------------------------------- #
def resumen_demoras_ciudad(ciudad: str, sentido: str = "salidas") -> ToolResult:
    """Demoras de un aeropuerto: media, maximo, puntualidad y motivos mas frecuentes."""
    try:
        entrada = ResumenDemorasCiudadInput(ciudad=ciudad, sentido=sentido)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        iata = entrada.ciudad.upper()
        vuelos = query_flights_by_city(iata, entrada.sentido)
        if not vuelos:
            return ToolResult.fail("NOT_FOUND", f"no hay vuelos para {iata} ({entrada.sentido})")

        demoras = [int(v.get("minutos_demora", 0) or 0) for v in vuelos if v.get("estado") == "DEMORADO"]
        a_tiempo = sum(1 for v in vuelos if v.get("estado") == "A_TIEMPO")
        cancelados = sum(1 for v in vuelos if v.get("estado") == "CANCELADO")
        motivos = Counter(
            str(v.get("motivo")) for v in vuelos
            if v.get("estado") in ("DEMORADO", "CANCELADO") and v.get("motivo")
        )
        peores = sorted(
            ({"codigo_vuelo": v.get("codigo_vuelo"), "destino": v.get("destino"),
              "origen": v.get("origen"), "minutos_demora": int(v.get("minutos_demora", 0) or 0)}
             for v in vuelos if v.get("estado") == "DEMORADO"),
            key=lambda x: x["minutos_demora"], reverse=True,
        )[:5]
        return ToolResult.success({
            "ciudad": iata,
            "sentido": entrada.sentido,
            "total_vuelos": len(vuelos),
            "a_tiempo": a_tiempo,
            "demorados": len(demoras),
            "cancelados": cancelados,
            "puntualidad_pct": round(100 * a_tiempo / len(vuelos)) if vuelos else 0,
            "demora_media_min": round(sum(demoras) / len(demoras)) if demoras else 0,
            "demora_max_min": max(demoras) if demoras else 0,
            "motivos_frecuentes": [{"motivo": m, "vuelos": n} for m, n in motivos.most_common(3)],
            "peores_demoras": peores,
        })

    return _con_metrica("resumen_demoras_ciudad", _run)


# --------------------------------------------------------------------------- #
def ocupacion_vuelo(codigo_vuelo: str) -> ToolResult:
    """Agregados de pasaje de un vuelo: por tipo de pasajero, por tarifa y equipaje."""
    try:
        entrada = OcupacionVueloInput(codigo_vuelo=codigo_vuelo)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        reservas = query_reservations_by_flight(entrada.codigo_vuelo)
        if not reservas:
            return ToolResult.fail("NOT_FOUND", f"no hay reservas para el vuelo {entrada.codigo_vuelo}")
        pax = [p for r in reservas for p in (r.get("pasajeros") or [])]
        por_tipo = Counter(str(p.get("tipo", "?")) for p in pax)
        por_tarifa = Counter(str(r.get("clase_tarifa", "?")) for r in reservas)
        equipaje = sum(int(r.get("equipaje_facturado", 0) or 0) for r in reservas)
        return ToolResult.success({
            "codigo_vuelo": entrada.codigo_vuelo,
            "reservas": len(reservas),
            "pasajeros": len(pax),
            "por_tipo_pasajero": dict(por_tipo),
            "por_clase_tarifa": dict(por_tarifa),
            "tamano_medio_reserva": round(len(pax) / len(reservas), 1) if reservas else 0,
            "equipaje_facturado_total": equipaje,
        })

    return _con_metrica("ocupacion_vuelo", _run)


# --------------------------------------------------------------------------- #
def perfil_reservas_vuelo(codigo_vuelo: str) -> ToolResult:
    """Reservas de un vuelo por estado, tarifa, canal de compra y reembolsabilidad."""
    try:
        entrada = PerfilReservasVueloInput(codigo_vuelo=codigo_vuelo)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        reservas = query_reservations_by_flight(entrada.codigo_vuelo)
        if not reservas:
            return ToolResult.fail("NOT_FOUND", f"no hay reservas para el vuelo {entrada.codigo_vuelo}")
        return ToolResult.success({
            "codigo_vuelo": entrada.codigo_vuelo,
            "reservas": len(reservas),
            "por_estado": dict(Counter(str(r.get("estado", "?")) for r in reservas)),
            "por_clase_tarifa": dict(Counter(str(r.get("clase_tarifa", "?")) for r in reservas)),
            "por_canal_compra": dict(Counter(str(r.get("canal_compra", "?")) for r in reservas)),
            "reembolsables": sum(1 for r in reservas if r.get("reembolsable")),
        })

    return _con_metrica("perfil_reservas_vuelo", _run)


# --------------------------------------------------------------------------- #
def buscar_vuelos_ruta(origen: str, destino: str) -> ToolResult:
    """Vuelos en una ruta concreta origen -> destino (por codigos IATA)."""
    try:
        entrada = BuscarVuelosRutaInput(origen=origen, destino=destino)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        o, d = entrada.origen.upper(), entrada.destino.upper()
        if o == d:
            return ToolResult.fail("INVALID_INPUT", "origen y destino no pueden coincidir")
        salidas = query_flights_by_city(o, "salidas")
        en_ruta = [v for v in salidas if str(v.get("destino", "")).upper() == d]
        if not en_ruta:
            return ToolResult.fail("NOT_FOUND", f"no hay vuelos en la ruta {o} -> {d}")
        por_estado = Counter(str(v.get("estado", "?")) for v in en_ruta)
        listado = sorted(
            ({"codigo_vuelo": v.get("codigo_vuelo"), "estado": v.get("estado"),
              "salida_programada": v.get("salida_programada"), "puerta": v.get("puerta")}
             for v in en_ruta),
            key=lambda x: str(x["salida_programada"] or ""),
        )[:_MAX_VUELOS_LISTADOS]
        return ToolResult.success({
            "origen": o,
            "destino": d,
            "total": len(en_ruta),
            "por_estado": dict(por_estado),
            "vuelos": listado,
        })

    return _con_metrica("buscar_vuelos_ruta", _run)


# --------------------------------------------------------------------------- #
def cobertura_reservas(ciudad: str, sentido: str = "salidas") -> ToolResult:
    """Vuelos de un aeropuerto con y sin reservas. Señala como incoherentes los
    vuelos en estado operado (embarcando/en vuelo/aterrizado/demorado) sin
    ninguna reserva."""
    try:
        entrada = CoberturaReservasInput(ciudad=ciudad, sentido=sentido)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        iata = entrada.ciudad.upper()
        vuelos = query_flights_by_city(iata, entrada.sentido)
        if not vuelos:
            return ToolResult.fail("NOT_FOUND", f"no hay vuelos para {iata} ({entrada.sentido})")

        analizados = vuelos[:_MAX_VUELOS_RANKING]

        def _fila(v: dict) -> dict:
            cod = v.get("codigo_vuelo", "")
            rs = query_reservations_by_flight(cod, limit=300)
            return {"codigo_vuelo": cod, "estado": v.get("estado"),
                    "destino": v.get("destino"), "origen": v.get("origen"),
                    "reservas": len(rs)}

        with ThreadPoolExecutor(max_workers=10) as pool:
            filas = list(pool.map(_fila, analizados))

        con = [f for f in filas if f["reservas"] > 0]
        sin = [f for f in filas if f["reservas"] == 0]
        incoherentes = [f for f in sin if f["estado"] in _ESTADOS_VUELO_OPERADOS]
        nota = (f"Analizados los primeros {len(filas)} vuelos de {iata}."
                if len(vuelos) > len(filas) else None)
        return ToolResult.success({
            "ciudad": iata,
            "sentido": entrada.sentido,
            "vuelos_analizados": len(filas),
            "con_reservas": len(con),
            "sin_reservas": len(sin),
            "reservas_totales": sum(f["reservas"] for f in filas),
            "sin_reservas_pero_operando": [
                {"codigo_vuelo": f["codigo_vuelo"], "estado": f["estado"], "destino": f["destino"]}
                for f in incoherentes
            ],
            "top_por_reservas": sorted(filas, key=lambda f: f["reservas"], reverse=True)[:_TOP_N_RANKING],
            **({"nota": nota} if nota else {}),
        })

    return _con_metrica("cobertura_reservas", _run)


# --------------------------------------------------------------------------- #
def vuelos_a_continente(ciudad: str, continente: str) -> ToolResult:
    """Vuelos que salen de un aeropuerto hacia un continente (Norteamerica,
    Centroamerica, Sudamerica o Europa)."""
    try:
        entrada = VuelosAContinenteInput(ciudad=ciudad, continente=continente)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    cont = geo.normaliza_continente(entrada.continente)
    if cont is None:
        return ToolResult.fail(
            "INVALID_INPUT",
            f"continente no reconocido: {entrada.continente!r}. Usa uno de: {', '.join(geo.CONTINENTES)}",
        )

    def _run():
        iata = entrada.ciudad.upper()
        vuelos = query_flights_by_city(iata, "salidas")
        if not vuelos:
            return ToolResult.fail("NOT_FOUND", f"no hay salidas registradas para {iata}")

        en_cont = [v for v in vuelos if geo.continente(str(v.get("destino", ""))) == cont]
        por_estado = Counter(str(v.get("estado", "?")) for v in en_cont)
        por_pais = Counter(geo.pais(str(v.get("destino", ""))) for v in en_cont)
        listado = [
            {"codigo_vuelo": v.get("codigo_vuelo"), "destino": v.get("destino"),
             "ciudad_destino": geo.ciudad(str(v.get("destino", ""))),
             "pais": geo.pais(str(v.get("destino", ""))), "estado": v.get("estado")}
            for v in en_cont[:_MAX_VUELOS_LISTADOS]
        ]
        return ToolResult.success({
            "ciudad": iata,
            "continente": cont,
            "hay_vuelos": bool(en_cont),
            "total": len(en_cont),
            "por_pais": dict(por_pais),
            "por_estado": dict(por_estado),
            "vuelos": listado,
        })

    return _con_metrica("vuelos_a_continente", _run)


# --------------------------------------------------------------------------- #
def vuelos_nac_int(ciudad: str, sentido: str = "salidas") -> ToolResult:
    """Reparto de vuelos nacionales / internacionales de un aeropuerto."""
    try:
        entrada = NacionalesInternacionalesInput(ciudad=ciudad, sentido=sentido)
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        iata = entrada.ciudad.upper()
        pais_base = geo.pais(iata)
        if not pais_base:
            return ToolResult.fail("NOT_FOUND", f"aeropuerto {iata} no esta en el catalogo")
        vuelos = query_flights_by_city(iata, entrada.sentido)
        if not vuelos:
            return ToolResult.fail("NOT_FOUND", f"no hay vuelos para {iata} ({entrada.sentido})")

        otro_extremo = "destino" if entrada.sentido != "llegadas" else "origen"
        nac = internac = 0
        int_por_pais: Counter = Counter()
        for v in vuelos:
            p = geo.pais(str(v.get(otro_extremo, "")))
            if p == pais_base:
                nac += 1
            else:
                internac += 1
                int_por_pais[p or "?"] += 1
        return ToolResult.success({
            "ciudad": iata,
            "pais": pais_base,
            "sentido": entrada.sentido,
            "total": len(vuelos),
            "nacionales": nac,
            "internacionales": internac,
            "internacionales_por_pais": dict(int_por_pais.most_common(10)),
        })

    return _con_metrica("vuelos_nac_int", _run)


# --------------------------------------------------------------------------- #
def radar_operativo(ciudad: str) -> ToolResult:
    """Briefing operativo completo de una ciudad en una sola consulta (la tool 'wow')."""
    try:
        entrada = VuelosPorCiudadInput(ciudad=ciudad, sentido="ambos")
    except ValidationError as e:
        return ToolResult.fail("INVALID_INPUT", _first_msg(e))

    def _run():
        iata = entrada.ciudad.upper()
        salidas = query_flights_by_city(iata, "salidas")
        llegadas = query_flights_by_city(iata, "llegadas")
        if not salidas and not llegadas:
            return ToolResult.fail("NOT_FOUND", f"no hay operacion registrada para {iata}")

        est_sal = Counter(str(v.get("estado", "?")) for v in salidas)
        est_lle = Counter(str(v.get("estado", "?")) for v in llegadas)
        cancelados = [v.get("codigo_vuelo") for v in salidas if v.get("estado") == "CANCELADO"][:10]
        demoras = [int(v.get("minutos_demora", 0) or 0) for v in salidas if v.get("estado") == "DEMORADO"]

        mascotas = pax_afectados = 0
        criticos = [v for v in salidas if v.get("estado") in ("CANCELADO", "DEMORADO")][:_MAX_VUELOS_ENRIQUECIDOS]
        for v in criticos:
            rs = query_reservations_by_flight(v.get("codigo_vuelo", ""), limit=200)
            mascotas += sum(1 for r in rs if r.get("mascota_en_cabina"))
            pax_afectados += sum(len(r.get("pasajeros") or []) for r in rs)

        return ToolResult.success({
            "ciudad": iata,
            "salidas": {"total": len(salidas), "por_estado": dict(est_sal)},
            "llegadas": {"total": len(llegadas), "por_estado": dict(est_lle)},
            "cancelaciones_salida": {"total": len(cancelados), "codigos": cancelados},
            "demoras_salida": {
                "vuelos": len(demoras),
                "media_min": round(sum(demoras) / len(demoras)) if demoras else 0,
                "max_min": max(demoras) if demoras else 0,
            },
            "impacto_en_vuelos_criticos": {
                "vuelos_revisados": len(criticos),
                "pasajeros_afectados": pax_afectados,
                "mascotas_en_cabina": mascotas,
            },
        })

    return _con_metrica("radar_operativo", _run)
