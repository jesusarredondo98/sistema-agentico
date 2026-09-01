#!/usr/bin/env python
"""Gold (RAG): construye, versiona y promueve el indice LanceDB (PRD §6.2, §6A.5).

Opera sobre `silver/corpus/chunks.parquet`, **nunca sobre la fuente cruda**.

Orden no negociable (§6A.5):
  1. construir en `gold/rag/politicas.lance/v=<UTC compacto>/`  (nunca sobrescribir)
  2. `_manifest.json` (12 campos de §6A.7) junto al indice
  3. prueba de humo: 5 consultas, cada una >= 1 resultado > 0,35; si falla, exit != 0
  4. conmutar `gold/rag/CURRENT` -> la version nueva  (ULTIMO paso, atomico)

Reembebido incremental (§6A.6): un documento con `checksum_cuerpo` sin cambios
reutiliza sus vectores de la version anterior; el indice se reconstruye entero.

Uso:  python -m pipelines.build_gold_rag [--allow-smoke-fail]
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import lancedb
import numpy as np
import pyarrow.parquet as pq

from pipelines._lake import lake_bucket, s3, utc_now_iso, work_dir
from src.contracts.corpus import DocumentoNormativoContract
from src.contracts.expectations import SIMILITUD_MAX_FRAGMENTOS, check_e07
from src.logic.embeddings import EMBED_DIM, embed_text
from src.logic.rag_index import TABLE_NAME

CURRENT_KEY = "gold/rag/CURRENT"
INDEX_PREFIX = f"gold/rag/{TABLE_NAME}.lance"

# Prueba de humo: una consulta por las 5 categorias con mas documentos (§6A.5).
SMOKE_QUERIES: list[tuple[str, str]] = [
    ("EQUIPAJE", "cuanto equipaje de mano puedo llevar y cual es el limite de peso"),
    ("MASCOTAS", "puedo llevar a mi mascota en cabina en el vuelo"),
    ("CAMBIOS", "como cambio la fecha de mi billete y que plazo tengo"),
    ("REEMBOLSOS", "en que casos tengo derecho a reembolso y en cuanto tiempo"),
    ("MENORES", "que requisitos hay para que un menor viaje no acompanado"),
]
SMOKE_THRESHOLD = 0.35


# --------------------------------------------------------------------------- #
def _read_parquet(bucket: str, key: str) -> list[dict]:
    body = s3().get_object(Bucket=bucket, Key=key)["Body"].read()
    return pq.read_table(io.BytesIO(body)).to_pylist()


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        return "unknown"


def _load_previous(bucket: str) -> tuple[dict[str, str], dict[tuple[str, int], list[float]]]:
    """Devuelve (checksums previos {doc_id: checksum}, vectores {(doc_id, chunk_index): vec})."""
    try:
        current = s3().get_object(Bucket=bucket, Key=CURRENT_KEY)["Body"].read().decode().strip()
    except Exception:
        return {}, {}
    prev_dir = work_dir() / "rag_prev"
    if prev_dir.exists():
        import shutil
        shutil.rmtree(prev_dir)
    prev_dir.mkdir(parents=True)
    prefix = current.rstrip("/") + "/"
    n = 0
    for page in s3().get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(prefix):]
            if not rel:
                continue
            (prev_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            s3().download_file(bucket, obj["Key"], str(prev_dir / rel))
            n += 1
    if n == 0:
        return {}, {}
    try:
        checksums = json.loads((prev_dir / "_checksums.json").read_text())
    except Exception:
        checksums = {}
    vectors: dict[tuple[str, int], list[float]] = {}
    try:
        tbl = lancedb.connect(str(prev_dir)).open_table(TABLE_NAME)
        for row in tbl.to_arrow().to_pylist():
            vectors[(row["doc_id"], int(row["chunk_index"]))] = list(row["vector"])
    except Exception:
        vectors = {}
    return checksums, vectors


# --------------------------------------------------------------------------- #
def _cuarentena_e06(filas: list[dict]) -> tuple[list[dict], int, list[str]]:
    """E-06 (§7.1, §6A.5): casi-duplicados coseno >= 0,98 -> CUARENTENA del
    fragmento, el lote continua. Titan V2 normaliza, asi que coseno = producto
    punto; se compara sobre la matriz de Gram y se descarta el segundo de cada par.
    """
    if len(filas) < 2:
        return filas, 0, []
    m = np.asarray([f["vector"] for f in filas], dtype=np.float32)
    gram = m @ m.T
    descartar: set[int] = set()
    detalle: list[str] = []
    for i in range(len(filas)):
        if i in descartar:
            continue
        for j in range(i + 1, len(filas)):
            if j in descartar:
                continue
            if gram[i, j] >= SIMILITUD_MAX_FRAGMENTOS:
                descartar.add(j)
                detalle.append(
                    f"{filas[j]['doc_id']}#{filas[j]['chunk_index']} ~ "
                    f"{filas[i]['doc_id']}#{filas[i]['chunk_index']} (coseno {gram[i, j]:.4f})"
                )
    limpio = [f for k, f in enumerate(filas) if k not in descartar]
    return limpio, len(descartar), detalle


# --------------------------------------------------------------------------- #
def build(bucket: str) -> tuple[Path, dict, dict[str, str]]:
    documentos = _read_parquet(bucket, "silver/corpus/documents.parquet")
    chunks = _read_parquet(bucket, "silver/corpus/chunks.parquet")
    checksum_por_doc = {d["doc_id"]: d["checksum_cuerpo"] for d in documentos}

    prev_checksums, prev_vectors = _load_previous(bucket)
    reused = embedded = 0
    filas: list[dict] = []
    for ch in chunks:
        doc_id, idx = ch["doc_id"], int(ch["chunk_index"])
        sin_cambios = prev_checksums.get(doc_id) == checksum_por_doc.get(doc_id)
        vec = prev_vectors.get((doc_id, idx)) if sin_cambios else None
        if vec is not None and len(vec) == EMBED_DIM:
            reused += 1
        else:
            vec = embed_text(ch["fragmento"])
            embedded += 1
        filas.append({
            "vector": vec,
            "doc_id": doc_id,
            "titulo": ch["titulo"],
            "categoria": ch["categoria"],
            "vigencia_desde": str(ch["vigencia_desde"]),
            "fragmento": ch["fragmento"],
            "chunk_index": idx,
        })

    # E-06: casi-duplicados -> cuarentena del fragmento, el lote continua.
    total_chunks = len(filas)
    filas, n_e06, detalle_e06 = _cuarentena_e06(filas)
    for d in detalle_e06:
        print(f"  E-06 cuarentena: {d}", file=sys.stderr)

    # Verificacion E-07 sobre TODOS los vectores (§6.2 paso 4).
    e07 = check_e07([f["vector"] for f in filas])
    if not e07.passed:
        raise RuntimeError(f"E-07 fallo: {e07.detail}")

    version = datetime.now(timezone.utc).strftime("v=%Y%m%dT%H%M%SZ")
    local = work_dir() / "rag_build" / version
    if local.exists():
        import shutil
        shutil.rmtree(local)
    local.mkdir(parents=True)

    db = lancedb.connect(str(local))
    db.create_table(TABLE_NAME, data=filas)

    manifest = {
        "version": version,
        "built_at": utc_now_iso(),
        "contract_name": DocumentoNormativoContract.CONTRACT_NAME,
        "contract_version": DocumentoNormativoContract.CONTRACT_VERSION,
        "source_bronze_partition": f"ingest_date={datetime.now(timezone.utc):%Y-%m-%d}",
        "embedding_model": "amazon.titan-embed-text-v2:0",
        "embedding_dimensions": EMBED_DIM,
        "counts": {
            "documents": len(documentos),
            "chunks": len(filas),
            "embedded": embedded,
            "reused": reused,
            "quarantined_e06": n_e06,
        },
        "quarantine_rate": round(n_e06 / max(total_chunks, 1), 4),
        "expectations": {
            "E-06": "pass" if n_e06 == 0 else f"pass ({n_e06} en cuarentena)",
            "E-07": "pass" if e07.passed else "FAIL",
        },
        "smoke_test": "pending",
        "git_sha": _git_sha(),
        "index_version": version,
    }
    (local / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    (local / "_checksums.json").write_text(json.dumps(checksum_por_doc, ensure_ascii=False, indent=2))
    return local, manifest, checksum_por_doc


def smoke_test(local_dir: Path) -> tuple[bool, list[str]]:
    tbl = lancedb.connect(str(local_dir)).open_table(TABLE_NAME)
    lineas: list[str] = []
    ok = True
    for categoria, consulta in SMOKE_QUERIES:
        qvec = embed_text(consulta)
        filas = (
            tbl.search(qvec).metric("cosine").limit(4)
            .where(f"categoria = '{categoria}'", prefilter=True).to_list()
        )
        mejor = max((1.0 - float(r["_distance"]) for r in filas), default=0.0)
        paso = mejor >= SMOKE_THRESHOLD
        ok = ok and paso
        lineas.append(f"  {'OK ' if paso else 'FALLA'} {categoria}: score max {mejor:.3f}")
    return ok, lineas


def upload_version(bucket: str, local_dir: Path, version: str) -> int:
    prefix = f"{INDEX_PREFIX}/{version}"
    n = 0
    for path in sorted(local_dir.rglob("*")):
        if path.is_file():
            key = f"{prefix}/{path.relative_to(local_dir).as_posix()}"
            s3().upload_file(str(path), bucket, key)
            n += 1
    return n


def prune_old_versions(bucket: str, keep: int = 3, protect: str | None = None) -> list[str]:
    """Conserva las `keep` versiones mas nuevas (mas la que apunta CURRENT). §2.4.

    S3 Lifecycle no cuenta versiones basadas en prefijo, asi que el podado lo
    hace el pipeline aqui, despues de conmutar CURRENT.
    """
    versiones: set[str] = set()
    for page in s3().get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=f"{INDEX_PREFIX}/", Delimiter="/"
    ):
        for cp in page.get("CommonPrefixes", []):
            name = cp["Prefix"].rstrip("/").split("/")[-1]
            if name.startswith("v="):
                versiones.add(name)
    ordenadas = sorted(versiones, reverse=True)
    a_conservar = set(ordenadas[:keep])
    if protect:
        a_conservar.add(protect)
    borradas = []
    for v in ordenadas[keep:]:
        if v in a_conservar:
            continue
        pfx = f"{INDEX_PREFIX}/{v}/"
        objs = []
        for page in s3().get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=pfx):
            objs += [{"Key": o["Key"]} for o in page.get("Contents", [])]
        for i in range(0, len(objs), 1000):
            s3().delete_objects(Bucket=bucket, Delete={"Objects": objs[i:i + 1000]})
        borradas.append(v)
    return borradas


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-smoke-fail", action="store_true",
                    help="NO promover aunque el humo falle, pero salir 0 (depuracion)")
    args = ap.parse_args()

    bucket = lake_bucket()
    local, manifest, _ = build(bucket)
    version = manifest["version"]
    print(f"indice construido: {version}  "
          f"({manifest['counts']['chunks']} chunks, "
          f"{manifest['counts']['embedded']} embebidos, {manifest['counts']['reused']} reutilizados)")

    n = upload_version(bucket, local, version)
    print(f"subidos {n} objetos a s3://{bucket}/{INDEX_PREFIX}/{version}/")

    print("prueba de humo (5 consultas, umbral 0,35):")
    ok, lineas = smoke_test(local)
    print("\n".join(lineas))

    # Actualizar smoke_test en el manifiesto local y remoto.
    manifest["smoke_test"] = "pass" if ok else "FAIL"
    blob = json.dumps(manifest, ensure_ascii=False, indent=2)
    (local / "_manifest.json").write_text(blob)
    s3().put_object(Bucket=bucket, Key=f"{INDEX_PREFIX}/{version}/_manifest.json", Body=blob.encode())

    if not ok:
        print(f"\nPRUEBA DE HUMO FALLIDA. La version {version} NO se promueve. "
              f"CURRENT sin tocar.", file=sys.stderr)
        return 0 if args.allow_smoke_fail else 2

    # Conmutacion atomica de CURRENT: ULTIMO paso (§6A.5 paso 4).
    s3().put_object(Bucket=bucket, Key=CURRENT_KEY,
                    Body=f"{INDEX_PREFIX}/{version}".encode("utf-8"))
    print(f"\nCURRENT -> {INDEX_PREFIX}/{version}")

    borradas = prune_old_versions(bucket, keep=3, protect=version)
    if borradas:
        print(f"podadas {len(borradas)} versiones antiguas: {', '.join(borradas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
