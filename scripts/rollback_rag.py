#!/usr/bin/env python
"""Vuelta atras del indice RAG (PRD §6A.5 paso 5).

Reescribe `gold/rag/CURRENT` a una version anterior. Recuperacion en segundos,
sin reconstruir ni redesplegar nada. La Lambda sirve la version previa tras el
siguiente ping de calentamiento (§6.3, R-10).

Uso:
  python scripts/rollback_rag.py --list
  python scripts/rollback_rag.py --to v=20260828T140311Z
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipelines._lake import lake_bucket, s3  # noqa: E402
from src.logic.rag_index import TABLE_NAME  # noqa: E402

CURRENT_KEY = "gold/rag/CURRENT"
INDEX_PREFIX = f"gold/rag/{TABLE_NAME}.lance"


def list_versions(bucket: str) -> list[str]:
    """Versiones disponibles en S3, mas nueva primero."""
    vs: set[str] = set()
    for page in s3().get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=f"{INDEX_PREFIX}/", Delimiter="/"
    ):
        for cp in page.get("CommonPrefixes", []):
            name = cp["Prefix"].rstrip("/").split("/")[-1]
            if name.startswith("v="):
                vs.add(name)
    return sorted(vs, reverse=True)


def current(bucket: str) -> str:
    try:
        return s3().get_object(Bucket=bucket, Key=CURRENT_KEY)["Body"].read().decode().strip()
    except Exception:
        return "(sin CURRENT)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--to", metavar="v=<ts>", help="version a la que apuntar CURRENT")
    ap.add_argument("--list", action="store_true", help="lista las versiones disponibles")
    args = ap.parse_args()

    bucket = lake_bucket()
    versiones = list_versions(bucket)

    if args.list or not args.to:
        print(f"CURRENT actual: {current(bucket)}")
        print("versiones disponibles (mas nueva primero):")
        for v in versiones:
            print(f"  {v}")
        return 0

    destino = args.to if args.to.startswith("v=") else f"v={args.to}"
    if destino not in versiones:
        print(f"la version {destino} no existe en s3://{bucket}/{INDEX_PREFIX}/", file=sys.stderr)
        return 1

    antes = current(bucket)
    nuevo_prefijo = f"{INDEX_PREFIX}/{destino}"
    s3().put_object(Bucket=bucket, Key=CURRENT_KEY, Body=nuevo_prefijo.encode("utf-8"))
    print(f"CURRENT: {antes}  ->  {nuevo_prefijo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
