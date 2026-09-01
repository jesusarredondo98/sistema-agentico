#!/usr/bin/env python
"""Prueba de carga (PRD §8.4). Se ejecuta UNA sola vez, en F9, y se archiva.

- 500 sesiones concurrentes, un mensaje por sesion.
- **Reparto: 100 con LLM real + 400 en `dry_run`** (coste ~0,88 USD en vez de 4,38).
- Lo que mide es el **encolado y el TTL de DynamoDB**, no el escalado: la
  concurrencia reservada (§2.2) hace que las 500 se encolen. Esto se documenta
  en el informe y **NO** se presenta como prueba de escalado (hallazgo 29).
- Verificacion de TTL: tras la carga se comprueba el **atributo `expires_at`** de
  los items STATE, no la desaparicion (la expiracion real de DynamoDB tarda
  hasta 48 h).
- Pide confirmacion interactiva e imprime el coste estimado antes de arrancar y
  el real al terminar. `dry_run` queda en el log de cada invocacion y NO esta
  disponible desde la UI.

Uso:  AWS_PROFILE=aeronova python scripts/load_test.py
      AWS_PROFILE=aeronova python scripts/load_test.py --yes   # sin confirmacion
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

TOTAL = 500
REALES = 100
DRY_RUN = TOTAL - REALES
CONCURRENCIA = 60          # hilos del cliente; el servidor encola por su cuenta
COSTE_ESTIMADO_USD = 0.88  # §8.4 / §9.4
MENSAJE = "¿El vuelo AN1002 está a tiempo?"


def _endpoint() -> tuple[str, str]:
    url = os.environ.get("AERONOVA_API_URL")
    key = os.environ.get("AERONOVA_API_KEY")
    if url and key:
        return url, key
    tf = ["terraform", f"-chdir={_ROOT}/terraform/10-app", "output", "-raw"]
    return (subprocess.check_output([*tf, "api_url"], text=True).strip(),
            subprocess.check_output([*tf, "api_key"], text=True).strip())


def _post(url: str, key: str, sid: str, dry: bool) -> dict:
    payload = {"employee_id": "EMP_001", "session_id": sid, "message": MENSAJE}
    if dry:
        payload["dry_run"] = True
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers={"content-type": "application/json", "x-api-key": key})
    t0 = time.perf_counter()
    try:
        r = urllib.request.urlopen(req, timeout=120)
        b = json.loads(r.read())
        return {"sid": sid, "dry": dry, "status": r.status, "ms": int((time.perf_counter() - t0) * 1000),
                "cost": float((b.get("usage") or {}).get("cost_usd", 0) or 0)}
    except urllib.error.HTTPError as e:
        return {"sid": sid, "dry": dry, "status": e.code, "ms": int((time.perf_counter() - t0) * 1000),
                "cost": 0.0, "err": e.read()[:120].decode("utf-8", "ignore")}
    except Exception as e:  # noqa: BLE001
        return {"sid": sid, "dry": dry, "status": "EXC", "ms": int((time.perf_counter() - t0) * 1000),
                "cost": 0.0, "err": str(e)[:120]}


def _verificar_ttl(sids: list[str]) -> dict:
    # La verificacion de TTL es un chequeo posterior: si boto3 no tiene
    # credenciales (falta AWS_PROFILE, sesion caducada) no se descartan las
    # ~500 peticiones ya hechas; se reporta el fallo y se sigue.
    try:
        import boto3

        tbl = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")).Table("aeronova-memory")
        ahora = int(time.time())
        con, sin, futuro_ok = 0, 0, 0
        for sid in sids[:50]:  # muestra
            it = tbl.get_item(Key={"session_id": sid, "sk": "STATE"}).get("Item")
            if not it:
                continue
            exp = it.get("expires_at")
            if exp is None:
                sin += 1
            else:
                con += 1
                # §2.7: TTL de 24 h -> expires_at debe caer ~24 h en el futuro, en SEGUNDOS
                if ahora < int(exp) <= ahora + 26 * 3600:
                    futuro_ok += 1
        return {"muestra": min(50, len(sids)), "con_expires_at": con, "sin_expires_at": sin,
                "expires_at_en_ventana_24h": futuro_ok}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {str(e)[:160]}",
                "nota": "verificacion de TTL no ejecutada; revisa credenciales AWS y repite solo este paso"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true", help="omite la confirmacion interactiva")
    args = ap.parse_args()

    url, key = _endpoint()
    print(f"Endpoint: {url}")
    print(f"Plan: {TOTAL} sesiones ({REALES} reales + {DRY_RUN} dry_run), {CONCURRENCIA} hilos.")
    print(f"Coste estimado: ~{COSTE_ESTIMADO_USD:.2f} USD (solo las {REALES} reales).")
    print("Consume 500 peticiones de la cuota mensual G-1 (25 % de 2.000), dry_run incluido.")
    print("Mide ENCOLADO y TTL, no escalado (la concurrencia reservada encola las 500).")
    if not args.yes:
        if input("\n¿Arrancar la prueba de carga? [escribe 'si']: ").strip().lower() != "si":
            print("Cancelada.")
            return 1

    trabajos = ([(str(uuid.uuid4()), False) for _ in range(REALES)]
                + [(str(uuid.uuid4()), True) for _ in range(DRY_RUN)])
    resultados: list[dict] = []
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCIA) as pool:
        futs = [pool.submit(_post, url, key, sid, dry) for sid, dry in trabajos]
        for i, f in enumerate(as_completed(futs), 1):
            resultados.append(f.result())
            if i % 50 == 0:
                print(f"  {i}/{TOTAL} completadas")
    dur = time.perf_counter() - t0

    ok = [r for r in resultados if r["status"] == 200]
    err = [r for r in resultados if r["status"] != 200]
    lat = sorted(r["ms"] for r in resultados)
    p50 = lat[len(lat) // 2]
    p95 = lat[int(len(lat) * 0.95)]
    coste_real = sum(r["cost"] for r in resultados)

    ttl = _verificar_ttl([r["sid"] for r in resultados])

    informe = {
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": TOTAL, "reales": REALES, "dry_run": DRY_RUN,
        "duracion_s": round(dur, 1),
        "ok_200": len(ok), "errores": len(err),
        "codigos_error": sorted({str(r["status"]) for r in err}),
        "latencia_ms": {"p50": p50, "p95": p95, "max": lat[-1]},
        "coste_real_usd": round(coste_real, 4),
        "cuota_g1_consumida": TOTAL,
        "ttl": ttl,
        "nota": "Mide encolado y TTL de DynamoDB, NO escalado (concurrencia reservada, hallazgo 29).",
    }
    dest = _ROOT / "tests" / "golden" / "load_test_result.json"
    dest.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    print(f"\nInforme -> {dest}")
    return 0 if len(err) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
