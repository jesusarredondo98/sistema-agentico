"""Cliente de embeddings Amazon Titan Text Embeddings V2 (PRD §6.2).

`dimensions: 1024`, `normalize: true`. Una llamada por texto (Titan V2 no tiene
API de lote para embeddings); el paralelismo y el reintento exponencial ante
`ThrottlingException` los pone este modulo.

La **misma dimension (1024) DEBE usarse en la construccion del indice y en la
consulta** (§6.3): un desajuste da resultados silenciosamente incorrectos.
"""
from __future__ import annotations

import functools
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.config import get_settings

EMBED_DIM = 1024
_MAX_RETRIES = 8
_BASE_DELAY = 0.5
_THREADS = 8
_THROTTLE_CODES = {"ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"}


@functools.lru_cache(maxsize=1)
def _client():
    cfg = get_settings()
    # Timeouts acotados: en el camino de una consulta, `embed_text` corre fuera
    # del guard de 3 s de la herramienta (rag.py), asi que una llamada colgada a
    # Bedrock no puede quedarse pegada hasta el limite de 29 s de API Gateway.
    return boto3.client(
        "bedrock-runtime",
        region_name=cfg.aws_region,
        config=Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=2,
            read_timeout=6,
        ),
    )


def embed_text(texto: str) -> list[float]:
    """Vector de 1024 float32 normalizado para un texto. Reintento exponencial."""
    cfg = get_settings()
    body = json.dumps({"inputText": texto, "dimensions": EMBED_DIM, "normalize": True})
    for intento in range(_MAX_RETRIES):
        try:
            resp = _client().invoke_model(
                modelId=cfg.bedrock_embed_model,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            vec = json.loads(resp["body"].read())["embedding"]
            if len(vec) != EMBED_DIM:
                raise ValueError(f"Titan devolvio {len(vec)} dims, se esperaban {EMBED_DIM}")
            return vec
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in _THROTTLE_CODES or intento == _MAX_RETRIES - 1:
                raise
            time.sleep(_BASE_DELAY * (2 ** intento) + random.uniform(0, 0.3))
    raise RuntimeError("embed_text agoto los reintentos")  # pragma: no cover


def embed_batch(textos: list[str]) -> list[list[float]]:
    """Embebe una lista de textos en paralelo, conservando el orden."""
    if not textos:
        return []
    with ThreadPoolExecutor(max_workers=_THREADS) as pool:
        return list(pool.map(embed_text, textos))
