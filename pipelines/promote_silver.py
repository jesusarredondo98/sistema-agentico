#!/usr/bin/env python
"""Silver: puerta de contrato + expectativas de lote (PRD §6A.3, §6A.4, §6.2).

Lee **Bronze** (nunca la fuente), valida registro a registro contra el data
contract, aplica las expectativas de lote y escribe:

    silver/flights/flights.parquet
    silver/reservations/reservations.parquet
    silver/corpus/documents.parquet
    silver/corpus/chunks.parquet
    quarantine/<dataset>/ingest_date=<hoy>/rejects.jsonl   (motivo estructurado)

Si una expectativa con accion ABORTA falla, **no se escribe Silver** y el
proceso sale con codigo != 0: el sistema degrada a "datos de ayer", nunca a
"datos rotos" (§6A.6).

Uso:  python -m pipelines.promote_silver [--from-local] [--allow-volume-drift]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import ValidationError

from pipelines._chunking import chunk_documento
from pipelines._lake import ingest_date, lake_bucket, s3, source_dir, utc_now_iso
from src.contracts import expectations as ex
from src.contracts.corpus import CATEGORIAS, DocumentoNormativoContract
from src.contracts.flights import VueloContract
from src.contracts.reservations import ReservaContract


# --------------------------------------------------------------------------- #
# Lectura de Bronze
# --------------------------------------------------------------------------- #
def _read_bronze_jsonl(bucket: str, dataset: str, part: str, from_local: bool) -> list[dict]:
    if from_local:
        p = source_dir() / f"{dataset}.jsonl"
        return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    key = f"bronze/{dataset}/ingest_date={part}/{dataset}.jsonl"
    body = s3().get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return [json.loads(ln) for ln in body.splitlines() if ln.strip()]


def _read_bronze_corpus(bucket: str, part: str, from_local: bool) -> list[dict]:
    if from_local:
        return [json.loads(p.read_text()) for p in sorted((source_dir() / "corpus").glob("*.json"))]
    prefix = f"bronze/corpus/ingest_date={part}/"
    docs = []
    paginator = s3().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            body = s3().get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            docs.append(json.loads(body))
    return sorted(docs, key=lambda d: d["doc_id"])


# --------------------------------------------------------------------------- #
# Puerta de contrato registro a registro
# --------------------------------------------------------------------------- #
def _quarantine_row(dataset: str, version: str, rule: str, key: str, reason: str, raw: dict) -> dict:
    return {
        "rejected_at": utc_now_iso(),
        "dataset": dataset,
        "contract_version": version,
        "rule": rule,
        "record_key": key,
        "reason": reason,
        "raw": raw,
    }


def _gate(records: list[dict], contract, dataset: str, key_field: str):
    accepted, rejects = [], []
    for r in records:
        try:
            contract(**r)
            accepted.append(r)
        except ValidationError as e:
            msg = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors())
            rejects.append(
                _quarantine_row(dataset, contract.CONTRACT_VERSION, "CONTRACT",
                                str(r.get(key_field, "?")), msg, r)
            )
    return accepted, rejects


# --------------------------------------------------------------------------- #
# Escritura Parquet / Quarantine
# --------------------------------------------------------------------------- #
def _put_parquet(bucket: str, key: str, rows: list[dict]) -> None:
    table = pa.Table.from_pylist(rows)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    s3().put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def _put_jsonl(bucket: str, key: str, rows: list[dict]) -> None:
    body = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows)
    s3().put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-local", action="store_true",
                    help="lee data/source/ en vez de Bronze en S3 (solo iteracion rapida)")
    ap.add_argument("--allow-volume-drift", action="store_true")
    args = ap.parse_args()

    bucket = lake_bucket()
    part = ingest_date()
    batch_ts = datetime.now(timezone.utc)

    flights_raw = _read_bronze_jsonl(bucket, "flights", part, args.from_local)
    res_raw = _read_bronze_jsonl(bucket, "reservations", part, args.from_local)
    corpus_raw = _read_bronze_corpus(bucket, part, args.from_local)

    # --- puerta de contrato ---
    fl_ok, fl_rej = _gate(flights_raw, VueloContract, "flights.vuelo", "codigo_vuelo")
    res_ok, res_rej = _gate(res_raw, ReservaContract, "reservations.reserva", "pnr")
    doc_ok, doc_rej = _gate(corpus_raw, DocumentoNormativoContract, "corpus.documento_normativo", "doc_id")

    # --- E-05: integridad referencial reservations.codigo_vuelo -> flights ---
    codigos_vuelo = {v["codigo_vuelo"] for v in fl_ok}
    res_final, res_orphan = [], []
    for r in res_ok:
        (res_final if r["codigo_vuelo"] in codigos_vuelo else res_orphan).append(r)
    for r in res_orphan:
        res_rej.append(
            _quarantine_row("reservations.reserva", ReservaContract.CONTRACT_VERSION, "E-05",
                            r["pnr"], f"codigo_vuelo {r['codigo_vuelo']} sin vuelo en el lote", r)
        )

    # --- fragmentacion del corpus (Silver) ---
    chunks = [row for d in doc_ok for row in chunk_documento(d)]

    total_bronze = len(flights_raw) + len(res_raw) + len(corpus_raw)
    total_rej = len(fl_rej) + len(res_rej) + len(doc_rej)

    # --- expectativas de lote ---
    resultados = [
        ex.check_e01([v["codigo_vuelo"] for v in fl_ok], dataset="flights"),
        ex.check_e01([r["pnr"] for r in res_final], dataset="reservations"),
        ex.check_e01([d["doc_id"] for d in doc_ok], dataset="corpus"),
        ex.check_e02(_as_ns(doc_ok)),
        ex.check_e03(_as_ns(doc_ok), CATEGORIAS),
        ex.check_e05([r["codigo_vuelo"] for r in res_ok], list(codigos_vuelo)),
        ex.check_e10(fl_ok, [r["codigo_vuelo"] for r in res_final]),
        ex.check_e04(total_bronze - total_rej, total_rej),
        ex.check_e08(len(res_final), _prev_count(bucket, "reservations"), allow_volume_drift=args.allow_volume_drift),
        ex.check_e09(batch_ts, DocumentoNormativoContract.CONTRACT_SLA_HOURS, now=batch_ts),
    ]

    quarantine_rates = {
        "flights": len(fl_rej) / max(len(flights_raw), 1),
        "reservations": len(res_rej) / max(len(res_raw), 1),
        "corpus": len(doc_rej) / max(len(corpus_raw), 1),
        "batch": total_rej / max(total_bronze, 1),
    }

    _print_report(resultados, quarantine_rates,
                  {"flights": len(fl_ok), "reservations": len(res_final), "corpus": len(doc_ok),
                   "chunks": len(chunks)})

    try:
        ex.evaluate(resultados)
    except ex.BatchAborted as e:
        print(f"\nLOTE ABORTADO: {e}\nSilver NO se escribe. CURRENT sin tocar.", file=sys.stderr)
        return 2

    # --- escritura de Silver ---
    _put_parquet(bucket, "silver/flights/flights.parquet", fl_ok)
    _put_parquet(bucket, "silver/reservations/reservations.parquet", res_final)
    _put_parquet(bucket, "silver/corpus/documents.parquet", doc_ok)
    _put_parquet(bucket, "silver/corpus/chunks.parquet", chunks)

    for ds, rej in (("flights", fl_rej), ("reservations", res_rej), ("corpus", doc_rej)):
        _put_jsonl(bucket, f"quarantine/{ds}/ingest_date={part}/rejects.jsonl", rej)

    report = {
        "promoted_at": utc_now_iso(),
        "ingest_date": part,
        "counts": {
            "bronze": {"flights": len(flights_raw), "reservations": len(res_raw), "corpus": len(corpus_raw)},
            "silver": {"flights": len(fl_ok), "reservations": len(res_final), "corpus": len(doc_ok), "chunks": len(chunks)},
            "quarantined": {"flights": len(fl_rej), "reservations": len(res_rej), "corpus": len(doc_rej)},
        },
        "quarantine_rate": quarantine_rates,
        "expectations": {r.id: ("pass" if r.passed else f"FAIL ({r.action})") for r in resultados},
    }
    s3().put_object(Bucket=bucket, Key="silver/_promote_report.json",
                    Body=json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))
    print("\nSilver escrito. Informe en s3://%s/silver/_promote_report.json" % bucket)
    return 0


class _NS:
    def __init__(self, d: dict):
        self.doc_id = d["doc_id"]
        self.categoria = d["categoria"]
        self.referencias = d.get("referencias", [])


def _as_ns(docs: list[dict]) -> list[_NS]:
    return [_NS(d) for d in docs]


def _prev_count(bucket: str, dataset: str) -> int | None:
    try:
        body = s3().get_object(Bucket=bucket, Key="silver/_promote_report.json")["Body"].read()
        return json.loads(body)["counts"]["silver"].get(dataset)
    except Exception:
        return None


def _print_report(resultados, rates, counts) -> None:
    print("\n=== Informe de calidad (promote_silver) ===")
    print(f"Silver: {counts}")
    print("Tasa de cuarentena: " + ", ".join(f"{k}={v:.2%}" for k, v in rates.items()))
    for r in resultados:
        marca = "OK  " if r.passed else f"FAIL[{r.action}]"
        print(f"  {marca} {r.id}: {r.detail}")


if __name__ == "__main__":
    raise SystemExit(main())
