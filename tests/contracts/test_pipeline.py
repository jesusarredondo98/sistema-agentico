"""Pruebas de pipeline de §8.1 evaluables en F2 (sin red, sin embeddings).

Los casos que dependen de embeddings o de la promocion a Gold (reembebido
incremental, prueba de humo, rollback, idempotencia frente a Bedrock) se
implementan en F4; aqui quedan marcados como pendientes de esa fase.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.contracts.corpus import DocumentoNormativoContract, sha256_cuerpo
from src.contracts.expectations import BatchAborted, check_e02, check_e04, evaluate
from tests.contracts.conftest import make_cuerpo


def _doc(doc_id: str, categoria: str, referencias: list[str] | None = None) -> DocumentoNormativoContract:
    cuerpo = make_cuerpo(referencias=referencias)
    return DocumentoNormativoContract(
        doc_id=doc_id,
        titulo=f"Politica {doc_id}",
        categoria=categoria,
        vigencia_desde=date(2025, 1, 1),
        cuerpo=cuerpo,
        referencias=referencias or [],
        checksum_cuerpo=sha256_cuerpo(cuerpo),
    )


def test_lote_con_referencia_colgante_aborta_por_e02():
    """Criterio de salida de F2 (PRD §14): CURRENT no cambia."""
    lote = [_doc("POL-MAS-001", "MASCOTAS", referencias=["POL-EQU-011"])]  # POL-EQU-011 no esta
    with pytest.raises(BatchAborted, match="E-02"):
        evaluate([check_e02(lote)])


def test_lote_valido_pasa_la_puerta():
    """Criterio de salida de F2 (PRD §14): un lote correcto promociona."""
    a = _doc("POL-MAS-001", "MASCOTAS", referencias=["POL-CAM-002"])
    b = _doc("POL-CAM-002", "CAMBIOS")
    resultados = evaluate([check_e02([a, b]), check_e04(n_aceptados=2, n_rechazados=0)])
    assert all(r.passed for r in resultados)


def test_lote_con_tasa_de_rechazo_del_3pc_aborta_por_e04():
    with pytest.raises(BatchAborted, match="E-04"):
        evaluate([check_e04(n_aceptados=97, n_rechazados=3)])


@pytest.mark.skip(reason="F4: reembebido incremental de 3 documentos nuevos, CURRENT avanza")
def test_lote_valido_con_3_documentos_nuevos_reembebe_solo_esos():
    ...


@pytest.mark.skip(reason="F4: indice que falla la prueba de humo no se promueve")
def test_indice_que_falla_smoke_no_se_promueve():
    ...


@pytest.mark.skip(reason="F4: rollback_rag.py --to <anterior> retrocede CURRENT")
def test_rollback_retrocede_current():
    ...


@pytest.mark.skip(reason="F4: reejecucion idempotente, 0 llamadas a Bedrock")
def test_reejecucion_sin_cambios_es_idempotente():
    ...
