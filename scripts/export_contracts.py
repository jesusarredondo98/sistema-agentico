#!/usr/bin/env python
"""Exporta los data contracts de ``src/contracts/`` a ``docs/contracts/`` (S-09).

Genera, **desde los modelos Pydantic** (fuente unica normativa):
- ``docs/contracts/<name>.schema.json`` -- JSON Schema por contrato.
- ``docs/contracts/CONTRACTS.md`` -- tabla revisable por negocio.

Los ficheros de ``docs/contracts/`` son **derivados y no se editan a mano**.
Entregable §16.4. Uso: ``python scripts/export_contracts.py`` (o ``make`` en F2b).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.contracts.base import DataContract  # noqa: E402
from src.contracts.corpus import DocumentoNormativoContract  # noqa: E402
from src.contracts.flights import VueloContract  # noqa: E402
from src.contracts.reservations import ReservaContract  # noqa: E402

CONTRATOS: list[type[DataContract]] = [
    DocumentoNormativoContract,
    VueloContract,
    ReservaContract,
]

OUT_DIR = _ROOT / "docs" / "contracts"


def _schema_filename(contract: type[DataContract]) -> str:
    return f"{contract.CONTRACT_NAME.replace('.', '_')}.schema.json"


def export_json_schemas() -> list[Path]:
    written: list[Path] = []
    for contract in CONTRATOS:
        schema = contract.model_json_schema()
        schema["x-contract"] = contract.contract_metadata()
        path = OUT_DIR / _schema_filename(contract)
        path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def export_markdown() -> Path:
    lines: list[str] = [
        "# Data contracts de AeroNova",
        "",
        "> Generado por `scripts/export_contracts.py` desde `src/contracts/`. **No editar a mano** (S-09).",
        "",
        "| Contrato | Version | Responsable | SLA (h) | Campos |",
        "|---|---|---|---:|---|",
    ]
    for contract in CONTRATOS:
        campos = ", ".join(f"`{n}`" for n in contract.model_fields)
        md = contract.contract_metadata()
        lines.append(
            f"| `{md['name']}` | {md['version']} | {md['owner']} | {md['sla_hours']} | {campos} |"
        )
    lines += ["", "## Detalle por contrato", ""]
    for contract in CONTRATOS:
        md = contract.contract_metadata()
        lines += [
            f"### `{md['name']}` v{md['version']}",
            "",
            f"- **Responsable:** {md['owner']}",
            f"- **SLA de frescura:** {md['sla_hours']} h",
            f"- **JSON Schema:** [`{_schema_filename(contract)}`]({_schema_filename(contract)})",
            "",
            "| Campo | Tipo | Requerido |",
            "|---|---|---|",
        ]
        for name, field in contract.model_fields.items():
            tipo = getattr(field.annotation, "__name__", str(field.annotation))
            lines.append(f"| `{name}` | `{tipo}` | {'si' if field.is_required() else 'no'} |")
        lines.append("")
    path = OUT_DIR / "CONTRACTS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    schemas = export_json_schemas()
    md = export_markdown()
    for p in [*schemas, md]:
        print(f"escrito {p.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()
