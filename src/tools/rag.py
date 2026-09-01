"""``buscar_politicas_rag`` (PRD §5.4.3, §6.3).

Solo lectura sobre `gold/rag/` (I-10). Nunca lanza excepcion al LLM.

Umbral 0,35: por debajo se descarta. Si no queda ningun fragmento, `NOT_FOUND`
-- devolver fragmentos irrelevantes es la via principal por la que un RAG
induce alucinacion (§6.3).
"""
from __future__ import annotations

from pydantic import ValidationError

from src.logic.embeddings import embed_text
from src.logic.rag_index import (
    RAG_SCORE_THRESHOLD,
    RagContractTooOld,
    RagUnavailable,
    get_index,
)
from src.config import get_settings
from src.tools._runtime import ToolTimeout, emit_tool_metric, run_with_timeout, timed
from src.tools.schemas import (
    BuscarPoliticasRagInput,
    BusquedaPoliticasData,
    FragmentoPolitica,
    ToolResult,
)

NOMBRE = "buscar_politicas_rag"


def buscar_politicas_rag(consulta: str, categoria: str | None = None) -> ToolResult:
    """Recupera fragmentos de politica normativa relevantes a la consulta."""
    with timed() as t:
        result = _buscar(consulta, categoria)
    emit_tool_metric(NOMBRE, result.ok, t.ms)
    return result


def _buscar(consulta: str, categoria: str | None) -> ToolResult:
    try:
        entrada = BuscarPoliticasRagInput(consulta=consulta, categoria=categoria)
    except ValidationError as e:
        err = e.errors()[0]
        return ToolResult.fail("INVALID_INPUT", f"{'.'.join(map(str, err['loc']))}: {err['msg']}")

    # La carga del indice (descarga de S3 a /tmp, abrir tabla) es de UNA VEZ por
    # contenedor y NO entra en el presupuesto de 3 s de la consulta (§6.3): el
    # timeout protege contra una consulta lenta, no contra el arranque en frio.
    try:
        idx = get_index()
    except RagContractTooOld as e:
        return ToolResult.fail("UPSTREAM_ERROR", f"indice incoherente con el codigo: {e}")
    except RagUnavailable as e:
        return ToolResult.fail("UPSTREAM_ERROR", f"indice de politicas no disponible: {e}")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail("UPSTREAM_ERROR", f"no se pudo abrir el indice: {e}")

    # El embedding de la consulta es una llamada de red a Bedrock: como la carga
    # del indice, es latencia de infraestructura (mas alta aun en el primer uso
    # de un contenedor) y NO entra en el presupuesto de 3 s, que protege contra
    # una BUSQUEDA lenta en LanceDB, no contra el arranque en frio (§6.3).
    try:
        qvec = embed_text(entrada.consulta)
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail("UPSTREAM_ERROR", f"no se pudo generar el embedding: {e}")

    try:
        fragmentos = run_with_timeout(lambda: _consultar_indice(idx, entrada, qvec))
    except ToolTimeout as e:
        return ToolResult.fail("TIMEOUT", str(e))
    except Exception as e:  # noqa: BLE001 - la tool no propaga nada al LLM
        return ToolResult.fail("UPSTREAM_ERROR", f"error al consultar politicas: {e}")

    if not fragmentos:
        return ToolResult.fail("NOT_FOUND", "ninguna politica supera el umbral de relevancia")

    data = BusquedaPoliticasData(
        resultados=fragmentos,
        consulta_normalizada=entrada.consulta.strip(),
    )
    return ToolResult.success(data.model_dump())


def _consultar_indice(idx, entrada: BuscarPoliticasRagInput, qvec: list[float]) -> list[FragmentoPolitica]:
    top_k = get_settings().rag_top_k
    q = idx.table.search(qvec).metric("cosine").limit(top_k)
    if entrada.categoria:
        q = q.where(f"categoria = '{entrada.categoria}'", prefilter=True)
    filas = q.to_list()

    out: list[FragmentoPolitica] = []
    for row in filas:
        score = 1.0 - float(row["_distance"])  # coseno: distancia -> similitud
        if score < RAG_SCORE_THRESHOLD:
            continue
        out.append(FragmentoPolitica(
            doc_id=row["doc_id"],
            titulo=row["titulo"],
            categoria=row["categoria"],
            fragmento=row["fragmento"],
            score=round(score, 4),
            vigencia_desde=str(row["vigencia_desde"]),
        ))
    return out
