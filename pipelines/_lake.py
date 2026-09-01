"""Utilidades compartidas del pipeline medallion (§6A.1, §2.4).

Resuelve el nombre del bucket del lago y da clientes de AWS. Los prefijos y el
formato (Parquet tabular, JSONL para rechazos) los fija §2.4 / S-10.
"""
from __future__ import annotations

import functools
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import boto3

_ROOT = Path(__file__).resolve().parents[1]
REGION = os.environ.get("AWS_REGION", "us-east-1")


@functools.lru_cache(maxsize=1)
def lake_bucket() -> str:
    """Nombre del bucket del lago.

    Orden: variable de entorno ``S3_BUCKET_LAKE`` -> salida de
    ``terraform/00-bootstrap``. Falla claro si no hay ninguna.
    """
    env = os.environ.get("S3_BUCKET_LAKE")
    if env:
        return env
    tf_dir = _ROOT / "terraform" / "00-bootstrap"
    try:
        out = subprocess.run(
            ["terraform", f"-chdir={tf_dir}", "output", "-raw", "s3_lake_bucket"],
            capture_output=True, text=True, check=True,
        )
        name = out.stdout.strip()
        if name:
            return name
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            "no se pudo resolver el bucket del lago: define S3_BUCKET_LAKE o aplica "
            "terraform/00-bootstrap"
        ) from exc
    raise RuntimeError("terraform devolvio un s3_lake_bucket vacio")


@functools.lru_cache(maxsize=1)
def s3():
    return boto3.client("s3", region_name=REGION)


@functools.lru_cache(maxsize=1)
def dynamodb():
    return boto3.client("dynamodb", region_name=REGION)


def ingest_date() -> str:
    """Particion de Bronze del dia (§6A.1)."""
    return date.today().isoformat()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def source_dir() -> Path:
    return _ROOT / "data" / "source"


def work_dir() -> Path:
    d = _ROOT / "data" / "work"
    d.mkdir(parents=True, exist_ok=True)
    return d
