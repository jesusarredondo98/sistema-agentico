#!/usr/bin/env python
"""Manifiesto de linaje del pipeline (PRD §6A.7).

Reune el informe de `promote_silver` y el resultado de la siembra en un
`_manifest.json` auditable que alimenta el entregable §16.5. Se escribe en
`silver/_manifest.json` (el manifiesto del indice RAG Gold es de F4).

Uso:  python -m pipelines.manifest --profile dev [--out data/work/_manifest.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pipelines._lake import lake_bucket, s3
from src.contracts.corpus import DocumentoNormativoContract


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def _rag_index_manifest(bucket: str) -> dict:
    """Manifiesto del indice RAG Gold vigente (lo que apunta `gold/rag/CURRENT`).

    Aporta E-07 y el resultado real de la prueba de humo, que en F4 eran un stub.
    """
    try:
        current = s3().get_object(Bucket=bucket, Key="gold/rag/CURRENT")["Body"].read().decode().strip()
        key = current.rstrip("/") + "/_manifest.json"
        return json.loads(s3().get_object(Bucket=bucket, Key=key)["Body"].read())
    except Exception:  # noqa: BLE001
        return {}


def build_manifest(profile: str) -> dict:
    bucket = lake_bucket()
    report = json.loads(
        s3().get_object(Bucket=bucket, Key="silver/_promote_report.json")["Body"].read()
    )
    rag = _rag_index_manifest(bucket)
    counts = report["counts"]
    q = counts["quarantined"]
    silver = counts["silver"]
    bronze = counts["bronze"]
    total_bronze = sum(bronze.values())
    total_q = sum(q.values())
    return {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "profile": profile,
        "ingest_date": report["ingest_date"],
        "contract_name": DocumentoNormativoContract.CONTRACT_NAME,
        "contract_version": DocumentoNormativoContract.CONTRACT_VERSION,
        "source_bronze_partition": f"ingest_date={report['ingest_date']}",
        "embedding_model": "amazon.titan-embed-text-v2:0",
        "embedding_dimensions": 1024,
        "counts": {
            "bronze": bronze,
            "silver": silver,
            "quarantined": q,
            "chunks": silver.get("chunks", 0),
        },
        "quarantine_rate": {
            "reservations": round(q["reservations"] / max(bronze["reservations"], 1), 4),
            "batch": round(total_q / max(total_bronze, 1), 4),
        },
        "expectations": {**report["expectations"], **rag.get("expectations", {})},
        "smoke_test": rag.get("smoke_test", "pending (F4)"),
        "rag_index_version": rag.get("index_version") or rag.get("version"),
        "git_sha": _git_sha(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=["dev", "full"], default="dev")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    manifest = build_manifest(args.profile)
    blob = json.dumps(manifest, ensure_ascii=False, indent=2)

    bucket = lake_bucket()
    s3().put_object(Bucket=bucket, Key="silver/_manifest.json", Body=blob.encode("utf-8"))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(blob, encoding="utf-8")
    print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
