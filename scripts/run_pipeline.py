#!/usr/bin/env python
"""Orquesta la cadena medallion Bronze -> Silver -> Gold (PRD §13 paso 3).

Ejecuta los pasos en orden y **se detiene en el primer fallo**. Si una
expectativa aborta, `promote_silver` sale != 0 y aqui paramos: el sistema
degrada a "datos de ayer", nunca a "datos rotos" (§6A.6).

  1. generate_synthetic.py --seed <s> --profile <p>
  2. ingest_bronze.py
  3. promote_silver.py            (puerta de contrato + expectativas)
  4. build_gold_dynamo.py --profile <p> --seed <s>
  5. build_gold_rag.py            (F4: aqui es un stub)
  6. manifest.py --profile <p>

Uso:  python scripts/run_pipeline.py --profile dev --seed 42
      make data
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _run(label: str, cmd: list[str]) -> None:
    print(f"\n{'=' * 70}\n[{label}] {' '.join(cmd)}\n{'=' * 70}")
    r = subprocess.run(cmd, cwd=_ROOT)
    if r.returncode != 0:
        print(f"\n[{label}] FALLO (exit {r.returncode}). Pipeline detenido.", file=sys.stderr)
        raise SystemExit(r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=["dev", "full"], default="dev")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only", choices=["corpus"], help="recarga solo el corpus (make data-corpus)")
    ap.add_argument("--from-local", action="store_true",
                    help="promote_silver lee data/source/ en vez de Bronze (iteracion rapida)")
    ap.add_argument("--allow-volume-drift", action="store_true",
                    help="E-08: permite un salto de volumen > 20 %% (p. ej. cambiar de perfil dev->full)")
    args = ap.parse_args()

    py = [sys.executable]

    _run("1 generate", py + ["scripts/generate_synthetic.py", "--seed", str(args.seed),
                             "--profile", args.profile])
    _run("2 bronze", py + ["-m", "pipelines.ingest_bronze"])
    promote = py + ["-m", "pipelines.promote_silver"]
    if args.from_local:
        promote.append("--from-local")
    if args.allow_volume_drift:
        promote.append("--allow-volume-drift")
    _run("3 silver", promote)

    if args.only == "corpus":
        # Recarga del corpus (§6A.6): reembebido incremental + indice + CURRENT.
        # Gold DynamoDB no se toca.
        _run("5 gold-rag", py + ["-m", "pipelines.build_gold_rag"])
        _run("6 manifest", py + ["-m", "pipelines.manifest", "--profile", args.profile])
        print("\nRecarga de corpus completa (Gold DynamoDB sin tocar).")
        return 0

    _run("4 gold-dynamo", py + ["-m", "pipelines.build_gold_dynamo",
                                "--profile", args.profile, "--seed", str(args.seed)])
    _run("5 gold-rag", py + ["-m", "pipelines.build_gold_rag"])
    _run("6 manifest", py + ["-m", "pipelines.manifest", "--profile", args.profile])

    print("\nPipeline medallion completo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
