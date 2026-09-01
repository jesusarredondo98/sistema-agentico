#!/usr/bin/env python
"""GIF de demo: 5 consultas reales al sistema AeroNova para la presentacion.

Golpea el endpoint desplegado (con cache en disco para no repetir el gasto),
y dibuja una animacion tipo chat con Pillow -> GIF en bucle. Sin ffmpeg ni
navegador: solo Pillow.

    AERONOVA_API_URL=... AERONOVA_API_KEY=... python scripts/demo_gif.py
    # o toma las credenciales de: terraform -chdir=terraform/10-app output

Salida: docs/ppt/aeronova_demo.gif  (respuestas cacheadas en build/ppt-context/)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "ppt"
CACHE_DIR = ROOT / "build" / "ppt-context"
CACHE = CACHE_DIR / "demo_responses.json"
GIF = DOCS / "aeronova_demo.gif"

CONSULTAS = [
    "¿El vuelo AN1008 está demorado?",
    "Dame los datos de la reserva GVJIYN",
    "¿Puedo llevar un gato en cabina y qué peso máximo tiene?",
    "Dame el radar operativo de BCN",
    "¿Cuántos vuelos nacionales e internacionales salen de MEX?",
]

# --- Paleta heredada del design system de AeroNova (skills/pdf-report) --------
NAVY = (27, 58, 92)
ACCENT = (46, 117, 182)
BG = (244, 247, 251)
CARD = (255, 255, 255)
INK = (31, 41, 51)
MUTE = (110, 124, 140)
PILL_BG = (231, 239, 247)
BORDER = (214, 224, 234)

W, H = 900, 560
MARGIN = 34
FONT_DIR = "/System/Library/Fonts"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


F_TITLE = _font("HelveticaNeue.ttc", 19)
F_BODY = _font("Helvetica.ttc", 18)
F_SMALL = _font("Helvetica.ttc", 14)
F_MONO = _font("Menlo.ttc", 14)


# --------------------------------------------------------------------------- #
def _endpoint() -> tuple[str, str]:
    url = os.environ.get("AERONOVA_API_URL")
    key = os.environ.get("AERONOVA_API_KEY")
    if url and key:
        return url, key
    tf = ["terraform", f"-chdir={ROOT}/terraform/10-app", "output", "-raw"]
    return (subprocess.check_output([*tf, "api_url"], text=True).strip(),
            subprocess.check_output([*tf, "api_key"], text=True).strip())


def fetch() -> list[dict]:
    if CACHE.exists():
        print(f"usando cache {CACHE}")
        return json.loads(CACHE.read_text())
    url, key = _endpoint()
    out = []
    for i, q in enumerate(CONSULTAS, 1):
        body = json.dumps({"employee_id": "EMP_001",
                           "session_id": f"demo-gif-{i:02d}-aeronova",
                           "message": q}).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "content-type": "application/json", "x-api-key": key})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
        out.append({"q": q,
                    "reply": d.get("reply", ""),
                    "tools": [t["name"] for t in d.get("tools_used", [])]})
        print(f"  [{i}/5] {q[:40]}... -> {out[-1]['tools']}")
        time.sleep(2)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


# --------------------------------------------------------------------------- #
def _demarkdown(txt: str) -> str:
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)
    txt = re.sub(r"`([^`]+)`", r"\1", txt)
    txt = re.sub(r"^\s*[-*]\s+", "-  ", txt, flags=re.M)
    txt = re.sub(r"^\s*#+\s*", "", txt, flags=re.M)
    txt = txt.replace("**", "")
    # Helvetica.ttc no trae flechas ni algun signo; se sustituyen para no dejar tofus.
    for a, b in (("→", "-"), ("⇄", "-"), ("←", "-"), ("↔", "-"),
                 ("–", "-"), ("—", "-"), ("№", "num."), ("•", "-")):
        txt = txt.replace(a, b)
    return txt


def _wrap(txt: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in txt.splitlines() or [""]:
        if not para.strip():
            continue
        cur = ""
        for word in para.split():
            probe = f"{cur} {word}".strip()
            if font.getlength(probe) <= max_w:
                cur = probe
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def _base() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 46], fill=NAVY)
    d.ellipse([18, 18, 30, 30], fill=(255, 255, 255))
    d.text((40, 13), "AeroNova · Asistente de mostrador", font=F_TITLE, fill=(255, 255, 255))
    return img


def _bubble(d, x, y, w, lines, font, *, fill, text_fill, align_right=False, lh=24, pad=14):
    h = pad * 2 + lh * len(lines)
    x0 = W - MARGIN - w if align_right else x
    d.rounded_rectangle([x0, y, x0 + w, y + h], radius=14, fill=fill)
    for i, ln in enumerate(lines):
        tw = font.getlength(ln)
        tx = x0 + w - pad - tw if align_right else x0 + pad
        d.text((tx, y + pad + i * lh), ln, font=font, fill=text_fill)
    return y + h


def frames_for(item: dict, idx: int) -> list[Image.Image]:
    q, reply, tools = item["q"], _demarkdown(item["reply"]), item["tools"]
    fr: list[Image.Image] = []
    reply_lines = _wrap(reply, F_BODY, W - 2 * MARGIN - 120 - 28)[:6]
    tools_txt = "  ".join(f"▸ {t}" for t in tools) or "▸ (sin herramienta)"

    def compose(user_chars: int, show_think: bool, show_tools: bool, n_reply: int):
        img = _base()
        d = ImageDraw.Draw(img)
        d.text((MARGIN, 60), f"Consulta {idx} de 5", font=F_SMALL, fill=MUTE)
        y = 88
        u_lines = _wrap(q[:user_chars] + ("|" if user_chars < len(q) else ""),
                        F_BODY, W - 2 * MARGIN - 160)
        y = _bubble(d, MARGIN, y, min(560, int(max(F_BODY.getlength(x) for x in u_lines)) + 60),
                    u_lines, F_BODY, fill=ACCENT, text_fill=(255, 255, 255), align_right=True)
        y += 18
        if show_think:
            d.text((MARGIN, y), "· · · consultando datos", font=F_SMALL, fill=MUTE)
            y += 26
        if show_tools:
            d.rounded_rectangle([MARGIN, y, MARGIN + F_MONO.getlength(tools_txt) + 24, y + 26],
                                radius=8, fill=PILL_BG)
            d.text((MARGIN + 12, y + 5), tools_txt, font=F_MONO, fill=NAVY)
            y += 40
        if n_reply:
            _bubble(d, MARGIN, y, W - 2 * MARGIN - 120, reply_lines[:n_reply], F_BODY,
                    fill=CARD, text_fill=INK, lh=25)
        return img

    step = max(1, len(q) // 10)
    for c in range(0, len(q) + 1, step):
        fr.append(compose(c, False, False, 0))
    fr += [compose(len(q), True, False, 0)] * 3
    fr.append(compose(len(q), False, True, 0))
    fr += [compose(len(q), False, True, 0)]
    for n in range(1, len(reply_lines) + 1):
        fr.append(compose(len(q), False, True, n))
    fr += [compose(len(q), False, True, len(reply_lines))] * 7
    return fr


def main() -> int:
    data = fetch()
    frames: list[Image.Image] = []
    for i, item in enumerate(data, 1):
        frames += frames_for(item, i)
    DOCS.mkdir(parents=True, exist_ok=True)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    pal[0].save(GIF, save_all=True, append_images=pal[1:], duration=170, loop=0, optimize=True)
    kb = GIF.stat().st_size / 1024
    print(f"\n{GIF}  ·  {len(frames)} frames  ·  {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
