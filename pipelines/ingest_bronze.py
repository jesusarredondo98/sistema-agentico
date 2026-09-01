#!/usr/bin/env python
"""Bronze: copia cruda e inmutable de la fuente (PRD §6A.1, §6A.2).

Sube ``data/source/`` a ``s3://<lago>/bronze/<dataset>/ingest_date=<hoy>/`` **sin
transformar nada**. Bronze nunca se corrige: cada ejecucion escribe una
particion nueva por fecha. Lee: solo el pipeline.

Uso:  python -m pipelines.ingest_bronze [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from pipelines._lake import ingest_date, lake_bucket, s3, source_dir


def _upload(bucket: str, local, key: str, dry: bool) -> None:
    if dry:
        print(f"  [dry-run] s3://{bucket}/{key}")
        return
    s3().upload_file(str(local), bucket, key)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = source_dir()
    if not (src / "flights.jsonl").exists():
        print("no hay fuente en data/source/. Ejecuta generate_synthetic.py primero.", file=sys.stderr)
        return 1

    bucket = lake_bucket()
    part = ingest_date()
    n = 0

    for dataset, fname in (("flights", "flights.jsonl"), ("reservations", "reservations.jsonl")):
        key = f"bronze/{dataset}/ingest_date={part}/{fname}"
        _upload(bucket, src / fname, key, args.dry_run)
        n += 1

    for doc in sorted((src / "corpus").glob("*.json")):
        key = f"bronze/corpus/ingest_date={part}/{doc.name}"
        _upload(bucket, doc, key, args.dry_run)
        n += 1

    print(f"bronze: {n} objetos {'(dry-run) ' if args.dry_run else ''}en s3://{bucket}/bronze/*/ingest_date={part}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
