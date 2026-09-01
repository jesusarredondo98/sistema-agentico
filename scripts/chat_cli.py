#!/usr/bin/env python
"""Cliente de terminal del agente (PRD §3). Mantiene `session_id` entre turnos.

Ejecuta el grafo de `src/agent/graph.py` contra el LLM y DynamoDB reales. Sirve
para el escenario multi-turno de memoria del criterio de salida de F5 y para
depuracion manual (§9.5: gasto que NO pasa por API Gateway).

Uso:
  AWS_PROFILE=aeronova python scripts/chat_cli.py --session usr_demo --employee emp_1
  (una linea por turno; 'salir' para terminar)
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Cargar .env local (la clave nunca se hardcodea).
_env = _ROOT / ".env"
if _env.is_file():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", default=f"usr_{uuid.uuid4().hex[:8]}")
    ap.add_argument("--employee", default="emp_demo")
    ap.add_argument("--message", action="append", help="turno no interactivo; repetible")
    args = ap.parse_args()

    from src.agent.graph import run_turn
    from src.logic.memory import SessionForbidden

    print(f"sesion: {args.session}  |  empleado: {args.employee}")

    def turno(texto: str) -> None:
        try:
            final = run_turn(session_id=args.session, employee_id=args.employee, user_message=texto)
        except SessionForbidden as e:
            print(f"  [403 SESSION_FORBIDDEN] {e}")
            return
        respuesta = final["messages"][-1]
        print(f"  agente: {respuesta.content}")
        print(f"  (finish_reason={final.get('finish_reason')}  "
              f"tool_rounds={final.get('tool_rounds')}  pnr_activo={final.get('pnr_activo')})")

    if args.message:
        for m in args.message:
            print(f"\nusuario: {m}")
            turno(m)
        return 0

    print("escribe tu mensaje ('salir' para terminar):")
    while True:
        try:
            texto = input("usuario: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if texto.lower() in {"salir", "exit", "quit"}:
            return 0
        if texto:
            turno(texto)


if __name__ == "__main__":
    raise SystemExit(main())
