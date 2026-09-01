#!/usr/bin/env python
"""Gold (DynamoDB): siembra `aeronova-flights` y `aeronova-reservations` (PRD §7.2).

Lee **Silver** (`silver/*.parquet`), nunca la fuente ni Bronze. Escritura con
`batch_writer` (lotes de 25, reintento automatico de `UnprocessedItems`),
paralelizada en 16 hilos. **Idempotente**: `PutItem` sobre la misma clave
sobrescribe; re-ejecutar no duplica ni falla.

Ruta B de §7.1 (`--inject-gold-corruption N`): inyecta N reservas corruptas
**directamente en DynamoDB, saltandose el contrato a proposito**. Desactivada
por defecto; imprime un aviso explicito. Demuestra que la validacion en runtime
sigue haciendo falta (§6A.8).

Uso:
  python -m pipelines.build_gold_dynamo [--reset] [--profile dev|full] [--seed 42]
  python -m pipelines.build_gold_dynamo --inject-gold-corruption 2000   # ruta B
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import boto3
import pyarrow.parquet as pq

from pipelines._lake import REGION, lake_bucket, s3

FLIGHTS_TABLE = "aeronova-flights"
RESERVATIONS_TABLE = "aeronova-reservations"
THREADS = 16


def _to_dynamo(v):
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, list):
        return [_to_dynamo(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_dynamo(x) for k, x in v.items()}
    return v


def _read_silver_parquet(bucket: str, key: str) -> list[dict]:
    body = s3().get_object(Bucket=bucket, Key=key)["Body"].read()
    table = pq.read_table(io.BytesIO(body))
    return table.to_pylist()


def _seed_table(table_name: str, rows: list[dict]) -> int:
    def _shard(shard_rows: list[dict]) -> int:
        tbl = boto3.resource("dynamodb", region_name=REGION).Table(table_name)
        with tbl.batch_writer() as bw:
            for r in shard_rows:
                bw.put_item(Item=_to_dynamo(r))
        return len(shard_rows)

    shards = [rows[i::THREADS] for i in range(THREADS)]
    written = 0
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        for n in pool.map(_shard, shards):
            written += n
    return written


def _reset_table(table_name: str, key_name: str) -> int:
    tbl = boto3.resource("dynamodb", region_name=REGION).Table(table_name)
    n = 0
    scan_kw = {"ProjectionExpression": "#k", "ExpressionAttributeNames": {"#k": key_name}}
    while True:
        page = tbl.scan(**scan_kw)
        with tbl.batch_writer() as bw:
            for item in page["Items"]:
                bw.delete_item(Key={key_name: item[key_name]})
                n += 1
        if "LastEvaluatedKey" not in page:
            break
        scan_kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return n


_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# Offset 36**5: garantiza PNR de exactamente 6 caracteres [A-Z0-9] -> pasan la
# validacion de entrada de la tool y llegan a la validacion de SALIDA (R-09),
# que es donde la corrupcion de ruta B se convierte en ok=False sin traza.
# Prefijo "RB" para que parezcan localizadores de verdad (`RB0000`, `RB0001`, ...):
# con codigos todo-digitos como `100000` el agente los rechaza por "no parecer un PNR"
# y la familia anomalia_* del golden no llega a probarse.
_RUTA_B_OFFSET = int("RB0000", 36)


def _b36(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = _B36[r] + s
    return s or "0"


def ruta_b_pnrs(n: int, exclude: set[str]) -> list[str]:
    """N PNR deterministas de 6 alfanumericos que no colisionan con `exclude`."""
    out, i = [], 0
    while len(out) < n:
        p = _b36(_RUTA_B_OFFSET + i)
        i += 1
        if p not in exclude:
            out.append(p)
    return out


def _inject_ruta_b(n: int, existing_pnrs: set[str]) -> tuple[int, list[str]]:
    """Inyecta N reservas corruptas (§7.1 ruta B) directamente en DynamoDB."""
    tbl = boto3.resource("dynamodb", region_name=REGION).Table(RESERVATIONS_TABLE)
    tipos = [n // 3, n // 3, n - 2 * (n // 3)]
    pnrs = ruta_b_pnrs(n, existing_pnrs)
    base = dict(
        estado="CONFIRMADA", codigo_vuelo="AN400", fecha_vuelo="2026-09-01",
        fecha_compra="2026-08-01", clase_tarifa="FLEX", equipaje_facturado=1,
        mascota_en_cabina=False, reembolsable=True, canal_compra="WEB",
        pasajeros=[{"nombre": "Corrupto Ruta B", "tipo": "ADULTO", "asiento": "1A"}],
    )
    k = 0
    with tbl.batch_writer(overwrite_by_pkeys=["pnr"]) as bw:
        for _ in range(tipos[0]):  # lista de pasajeros vacia
            bw.put_item(Item={**base, "pnr": pnrs[k], "pasajeros": []})
            k += 1
        for _ in range(tipos[1]):  # clase_tarifa fuera del enum
            bw.put_item(Item={**base, "pnr": pnrs[k], "clase_tarifa": "GOLD"})
            k += 1
        for _ in range(tipos[2]):  # campo obligatorio ausente
            item = {**base, "pnr": pnrs[k]}
            item.pop("canal_compra")
            bw.put_item(Item=item)
            k += 1
    return k, pnrs[:k]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="vacia las tablas antes de sembrar")
    ap.add_argument("--profile", choices=["dev", "full"], default="dev", help="solo para el manifiesto")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--inject-gold-corruption", type=int, default=0, metavar="N",
                    help="RUTA B (§7.1): inyecta N reservas corruptas SALTANDOSE EL CONTRATO")
    args = ap.parse_args()

    bucket = lake_bucket()

    if args.reset:
        d = _reset_table(FLIGHTS_TABLE, "codigo_vuelo")
        r = _reset_table(RESERVATIONS_TABLE, "pnr")
        print(f"reset: {d} vuelos y {r} reservas borrados")

    flights = _read_silver_parquet(bucket, "silver/flights/flights.parquet")
    reservations = _read_silver_parquet(bucket, "silver/reservations/reservations.parquet")

    nf = _seed_table(FLIGHTS_TABLE, flights)
    nr = _seed_table(RESERVATIONS_TABLE, reservations)
    print(f"gold DynamoDB: {nf} vuelos, {nr} reservas (perfil {args.profile}, seed {args.seed})")

    injected = 0
    if args.inject_gold_corruption > 0:
        print(
            "\n" + "!" * 72 + "\n"
            f"AVISO: --inject-gold-corruption {args.inject_gold_corruption} activo.\n"
            "Se van a ESCRIBIR reservas corruptas DIRECTAMENTE en DynamoDB, saltandose\n"
            "la puerta de contrato A PROPOSITO (ruta B de §7.1). Solo para F3/F9.\n"
            + "!" * 72,
            file=sys.stderr,
        )
        existing = {r["pnr"] for r in reservations}
        injected, rb_pnrs = _inject_ruta_b(args.inject_gold_corruption, existing)
        s3().put_object(
            Bucket=bucket, Key="gold/_ruta_b_pnrs.json",
            Body=json.dumps({"count": injected, "pnrs": rb_pnrs}).encode("utf-8"),
        )
        print(f"ruta B: {injected} reservas corruptas inyectadas; "
              f"PNR en s3://{bucket}/gold/_ruta_b_pnrs.json", file=sys.stderr)

    print(json.dumps({
        "flights_written": nf, "reservations_written": nr,
        "ruta_b_injected": injected, "profile": args.profile, "seed": args.seed,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
