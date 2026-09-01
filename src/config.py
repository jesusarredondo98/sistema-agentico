"""Settings tipados de AeroNova (PRD §2.7).

``pydantic-settings`` lee la configuracion del entorno que inyecta Terraform
(las 15 variables de §2.7). Los valores por defecto son los de esa tabla.

La clave de Anthropic **NUNCA** es una variable de entorno en texto plano: se
lee del parametro SSM ``SecureString`` cuyo *nombre* viaja en
``ANTHROPIC_API_KEY_PARAM``. La lectura vive en una funcion de ambito de modulo
cacheada con ``lru_cache`` -> se resuelve **una vez por contenedor, no por
invocacion**, y se conserva en memoria (PRD §2.7, S-04, hallazgo 11).
"""
from __future__ import annotations

import os
from functools import lru_cache

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion de ejecucion. Un valor por variable de §2.7."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")

    # Region (S-01). No es de §2.7 pero boto3 la necesita explicita fuera de Lambda.
    aws_region: str = "us-east-1"

    # Anthropic -- ANTHROPIC_API_KEY_PARAM es el NOMBRE del parametro SSM, no la clave.
    anthropic_api_key_param: str = "/aeronova/anthropic_api_key"
    anthropic_model: str = "claude-sonnet-5"  # sin sufijo de fecha (I-02, §5.3)

    # DynamoDB
    memory_table: str = "aeronova-memory"
    flights_table: str = "aeronova-flights"
    reservations_table: str = "aeronova-reservations"

    # Lago S3 / RAG
    s3_bucket_lake: str = ""  # sin valor por defecto en §2.7; lo fija Terraform
    rag_current_pointer: str = "gold/rag/CURRENT"  # fichero puntero, no el indice
    rag_contract_version_min: str = "1.0.0"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"

    # Cortacircuitos de coste por sesion (§12A.4). Valor del PRD = 0.25; ACU-006
    # lo sube para la demo. Env var, reversible.
    session_cost_limit_usd: float = 0.25

    # Grafo / LLM -- valores que NO se ajustan sin decision (I-02, I-03, §2.7)
    max_tool_rounds: int = 3
    max_output_tokens: int = 1024
    history_window_messages: int = 8  # bajado de 12 por coste; manda §2.7
    memory_ttl_hours: int = 24
    rag_top_k: int = 4

    # Origen de la UI (CloudFront) para la cabecera CORS de la respuesta real.
    # Lo inyecta Terraform; vacio en local y pruebas -> no se anade la cabecera.
    ui_origin: str = ""

    # Observabilidad
    log_level: str = "INFO"
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "aeronova-agent"
    # Nombre del parametro SSM con la clave de LangSmith (no la clave). Igual que
    # ANTHROPIC_API_KEY_PARAM: se lee de SSM en ambito de modulo, nunca env var
    # en texto plano ni por .tfvars (S-04).
    langsmith_api_key_param: str = "/aeronova/langsmith_api_key"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings del contenedor. Se construyen una sola vez."""
    return Settings()


@lru_cache(maxsize=1)
def get_anthropic_api_key() -> str:
    """Devuelve la clave de Anthropic.

    En Lambda **no** hay ``ANTHROPIC_API_KEY`` en el entorno (S-04): solo viaja el
    *nombre* del parametro, y la clave se lee del SSM ``SecureString``. En local
    (dev y pruebas de integracion) se respeta un ``ANTHROPIC_API_KEY`` ya
    presente en el entorno para no exigir credenciales AWS. Cacheada: una sola
    resolucion por contenedor (PRD §2.7). El nodo LLM la pasa a ``ChatAnthropic``.
    """
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    cfg = get_settings()
    ssm = boto3.client("ssm", region_name=cfg.aws_region)
    resp = ssm.get_parameter(Name=cfg.anthropic_api_key_param, WithDecryption=True)
    return resp["Parameter"]["Value"]


@lru_cache(maxsize=1)
def configure_langsmith() -> bool:
    """Activa el trazado en LangSmith si `LANGCHAIN_TRACING_V2` esta a true.

    Lee la clave del parametro SSM (S-04) y fija las variables que espera el SDK
    de LangChain. Se invoca en ambito de modulo del handler (F7). Devuelve si
    quedo activo. Cualquier fallo se traga: la observabilidad no rompe el arranque.
    """
    cfg = get_settings()
    if not cfg.langchain_tracing_v2:
        return False
    try:
        if not os.environ.get("LANGCHAIN_API_KEY"):
            ssm = boto3.client("ssm", region_name=cfg.aws_region)
            resp = ssm.get_parameter(Name=cfg.langsmith_api_key_param, WithDecryption=True)
            os.environ["LANGCHAIN_API_KEY"] = resp["Parameter"]["Value"]
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", cfg.langchain_project)
        return True
    except Exception:  # noqa: BLE001
        return False


# Ambito de modulo: las settings quedan resueltas al importar (PRD §2.7).
# La clave NO se resuelve aqui a proposito: mantener este import libre de una
# llamada de red a SSM permite que las pruebas unitarias de F3/F5 importen
# config.py sin credenciales AWS. La garantia "una vez por contenedor" la da el
# lru_cache de get_anthropic_api_key, que el nodo LLM llama a nivel de modulo.
settings = get_settings()
