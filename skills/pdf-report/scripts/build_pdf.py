#!/usr/bin/env python3
"""
Renderiza un HTML a PDF con Chrome headless, el mismo motor (Skia/PDF) que
produjo el documento de referencia del design system.

    python3 build_pdf.py informe.html [-o informe.pdf]

No requiere dependencias de terceros: solo Chrome instalado.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_chrome() -> str:
    if env := os.environ.get("CHROME_BIN"):
        if Path(env).exists():
            return env
        sys.exit(f"CHROME_BIN apunta a un ejecutable inexistente: {env}")
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "chromium", "chrome"):
        if p := shutil.which(name):
            return p
    sys.exit(
        "No se encontró Chrome. Instálalo o exporta CHROME_BIN con la ruta "
        "al ejecutable."
    )


def build(html: Path, out: Path, timeout: int = 120) -> None:
    if not html.is_file():
        sys.exit(f"No existe el HTML de entrada: {html}")

    chrome = find_chrome()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Perfil desechable: evita chocar con una sesión de Chrome ya abierta,
    # que es la causa habitual de que --print-to-pdf no produzca nada.
    with tempfile.TemporaryDirectory(prefix="pdfbuild-") as profile:
        # No añadir --run-all-compositor-stages-before-draw ni --virtual-time-budget:
        # juntos cuelgan indefinidamente en Chrome 150+ sin producir salida.
        # Este conjunto mínimo está verificado y es suficiente para fuentes locales.
        cmd = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-pdf-header-footer",  # los encabezados los pone el CSS, no Chrome
            f"--user-data-dir={profile}",
            f"--print-to-pdf={out.resolve()}",
            html.resolve().as_uri(),
        ]
        started = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if not out.exists() or out.stat().st_size == 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        sys.exit(f"Chrome no generó el PDF ({out}).")

    kb = out.stat().st_size / 1024
    print(f"OK  {out}  ({kb:.1f} KB, {time.time() - started:.1f}s)")

    # Verificación barata: si pdfinfo está disponible, confirma páginas y tamaño.
    if pdfinfo := shutil.which("pdfinfo"):
        info = subprocess.run([pdfinfo, str(out)], capture_output=True, text=True).stdout
        for line in info.splitlines():
            if line.startswith(("Pages:", "Page size:")):
                print("   " + line.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description="HTML -> PDF con Chrome headless.")
    ap.add_argument("html", type=Path, help="Fichero HTML de entrada")
    ap.add_argument("-o", "--out", type=Path, help="PDF de salida (por defecto: mismo nombre)")
    args = ap.parse_args()
    build(args.html, args.out or args.html.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
