"""Resuelve `CURRENT`, descarga el indice a `/tmp` y abre la tabla LanceDB (§6.3).

Inicializacion en **ambito de modulo, una sola vez por contenedor**: nunca
dentro del handler. `refresh_if_changed()` relee `CURRENT` y recarga si la
version cambio -- lo invoca el ping de calentamiento en F6 (R-10).

El runtime **rechaza servir** un indice cuyo `contract_version` del manifiesto
tenga un MAJOR inferior a `RAG_CONTRACT_VERSION_MIN` (§6A.5, R-11).
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import boto3
import lancedb

from src.config import get_settings

# Umbral de similitud (§6.3, Agents.md §2: valor innegociable).
RAG_SCORE_THRESHOLD = 0.35
TABLE_NAME = "politicas"


class RagContractTooOld(RuntimeError):
    """El manifiesto del indice tiene un MAJOR de contrato inferior al minimo (R-11)."""


class RagUnavailable(RuntimeError):
    """No hay indice servible (sin CURRENT, sin version, descarga fallida)."""


@dataclass
class LoadedIndex:
    version: str            # "gold/rag/politicas.lance/v=<ts>"
    table: object           # lancedb table
    manifest: dict


_cache: LoadedIndex | None = None


def _local_root() -> Path:
    d = Path(os.environ.get("RAG_LOCAL_DIR", "/tmp")) / "aeronova_rag"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _s3():
    return boto3.client("s3", region_name=get_settings().aws_region)


def _bucket() -> str:
    b = get_settings().s3_bucket_lake or os.environ.get("S3_BUCKET_LAKE")
    if not b:
        raise RagUnavailable("S3_BUCKET_LAKE no definido")
    return b


def read_current() -> str:
    """Contenido de `gold/rag/CURRENT`: el prefijo de la version vigente."""
    cfg = get_settings()
    try:
        obj = _s3().get_object(Bucket=_bucket(), Key=cfg.rag_current_pointer)
    except Exception as exc:  # noqa: BLE001
        raise RagUnavailable(f"no se pudo leer {cfg.rag_current_pointer}: {exc}") from exc
    return obj["Body"].read().decode("utf-8").strip()


def _sync_version(version_prefix: str, dest: Path) -> None:
    """Descarga todos los objetos de `<version_prefix>/` a `dest/`."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    bucket = _bucket()
    prefix = version_prefix.rstrip("/") + "/"
    paginator = _s3().get_paginator("list_objects_v2")
    n = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(prefix):]
            if not rel:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            _s3().download_file(bucket, obj["Key"], str(target))
            n += 1
    if n == 0:
        raise RagUnavailable(f"la version {version_prefix} no tiene objetos en S3")


def _open_local(local_version_dir: Path) -> LoadedIndex:
    manifest = json.loads((local_version_dir / "_manifest.json").read_text())
    cfg = get_settings()
    min_major = int(str(cfg.rag_contract_version_min).split(".", 1)[0])
    got_major = int(str(manifest.get("contract_version", "0.0.0")).split(".", 1)[0])
    if got_major < min_major:
        raise RagContractTooOld(
            f"contract_version {manifest.get('contract_version')} < min {cfg.rag_contract_version_min}"
        )
    db = lancedb.connect(str(local_version_dir))
    table = db.open_table(TABLE_NAME)
    return LoadedIndex(version=manifest["version"], table=table, manifest=manifest)


def load_index(force: bool = False) -> LoadedIndex:
    """Carga (o recarga) el indice vigente. Cachea en variable de modulo."""
    global _cache
    if _cache is not None and not force:
        return _cache
    version_prefix = read_current()
    local = _local_root() / version_prefix.replace("/", "_")
    _sync_version(version_prefix, local)
    _cache = _open_local(local)
    return _cache


def get_index() -> LoadedIndex:
    return _cache if _cache is not None else load_index()


def _prefix_of(idx: LoadedIndex) -> str:
    """Prefijo S3 completo de la version cargada, como lo escribe build_gold_rag."""
    return f"gold/rag/{TABLE_NAME}.lance/{idx.version}".rstrip("/")


def refresh_if_changed() -> bool:
    """Relee `CURRENT`; si difiere de lo cargado, recarga. Devuelve si cambio (R-10)."""
    if _cache is None:
        load_index()
        return True
    try:
        current = read_current().rstrip("/")
    except RagUnavailable:
        return False
    if current == _prefix_of(_cache):
        return False
    load_index(force=True)
    return True


def reset_cache() -> None:
    """Solo para pruebas."""
    global _cache
    _cache = None
