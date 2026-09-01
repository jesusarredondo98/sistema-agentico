#!/usr/bin/env python
"""Arma el GIF de demo a partir de las capturas REALES de la UI desplegada.

Las capturas las produce `scripts/demo_shots.js` (Chrome real sobre la web en
CloudFront, 5 consultas reales) en `build/ppt-context/shots/`. Este script las
escala, les pone tiempos por tipo de fotograma y las une en un GIF en bucle.
Solo Pillow: sin ffmpeg.

    node scripts/demo_shots.js          # 1) capturas reales
    python scripts/demo_gif.py          # 2) -> docs/ppt/aeronova_demo.gif
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "build" / "ppt-context" / "shots"
GIF = ROOT / "docs" / "ppt" / "aeronova_demo.gif"

TARGET_W = 920            # ancho final del GIF
COLORS = 80               # paleta; menos = archivo más pequeño
SKIP_SUFFIXES = ("_reply2.png",)   # fotogramas redundantes que no van al GIF

# Milisegundos por fotograma según el sufijo del nombre.
DURMS = {
    "inicio": 1100,
    "typing": 110,
    "typed": 550,
    "working": 750,
    "reply": 3200,
    "reply2": 2100,
}


def _kind(name: str) -> str:
    for k in DURMS:
        if name.endswith(f"_{k}.png") or name == f"{k}.png" or name.endswith(f"{k}.png"):
            return k
    return "reply"


def main() -> int:
    pngs = [p for p in sorted(SHOTS.glob("*.png"))
            if not p.name.endswith(SKIP_SUFFIXES)]
    if not pngs:
        print(f"no hay capturas en {SHOTS}. Corre antes:  node scripts/demo_shots.js",
              file=sys.stderr)
        return 1

    frames, durs = [], []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        w, h = im.size
        im = im.resize((TARGET_W, round(h * TARGET_W / w)), Image.LANCZOS)
        frames.append(im.convert("P", palette=Image.ADAPTIVE, colors=COLORS))
        durs.append(DURMS[_kind(p.name)])

    # Pausa final más larga antes de reiniciar el bucle.
    durs[-1] = 2600
    GIF.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(GIF, save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, optimize=True, disposal=2)
    kb = GIF.stat().st_size / 1024
    print(f"{GIF}  ·  {len(frames)} fotogramas  ·  {kb:.0f} KB  ·  "
          f"{sum(durs) / 1000:.1f}s por vuelta")
    return 0


if __name__ == "__main__":
    sys.exit(main())
