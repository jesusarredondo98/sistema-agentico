"""``DataContract``: clase base de los data contracts (PRD §6A.3, S-09).

Los contratos viven aqui como modelos **Pydantic v2** y son la fuente unica
normativa. `scripts/export_contracts.py` genera a partir de ellos el JSON Schema
y la tabla Markdown de `docs/contracts/`, que **nunca** se editan a mano.

> El data contract NO sustituye a la validacion Pydantic de las tools de §5.4.
> Defienden fallos distintos (§6A.8, R-09). No se elimina ninguna de las dos.
"""
from __future__ import annotations

import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

# SemVer estricto (§6A.5): MAJOR.MINOR.PATCH numericos.
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class DataContract(BaseModel):
    """Base de todo data contract.

    - ``extra="forbid"``: un campo no declarado es un rechazo, no un dato que se
      ignora en silencio.
    - ``str_strip_whitespace=True``: el espacio de borde no cambia la validez.

    Toda subclase concreta DEBE declarar los cuatro ``ClassVar`` de metadatos.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    CONTRACT_NAME: ClassVar[str]        # p. ej. "corpus.documento_normativo"
    CONTRACT_VERSION: ClassVar[str]     # SemVer -- ver §6A.5
    CONTRACT_OWNER: ClassVar[str]       # responsable funcional del dataset
    CONTRACT_SLA_HOURS: ClassVar[int]   # frescura maxima admisible del lote

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Subclases intermedias (sin metadatos propios) se permiten; la
        # comprobacion se aplica solo a las que declaran CONTRACT_NAME.
        if "CONTRACT_NAME" not in cls.__dict__:
            return
        faltan = [
            attr
            for attr in ("CONTRACT_NAME", "CONTRACT_VERSION", "CONTRACT_OWNER", "CONTRACT_SLA_HOURS")
            if attr not in cls.__dict__
        ]
        if faltan:
            raise TypeError(f"{cls.__name__}: faltan metadatos de contrato: {faltan}")
        if not _SEMVER.match(cls.CONTRACT_VERSION):
            raise TypeError(
                f"{cls.__name__}.CONTRACT_VERSION={cls.CONTRACT_VERSION!r} no es SemVer MAJOR.MINOR.PATCH"
            )
        if not isinstance(cls.CONTRACT_SLA_HOURS, int) or cls.CONTRACT_SLA_HOURS <= 0:
            raise TypeError(f"{cls.__name__}.CONTRACT_SLA_HOURS debe ser un entero positivo")

    @classmethod
    def contract_metadata(cls) -> dict[str, str | int]:
        """Los cuatro metadatos, para el exportador y el registro de cuarentena."""
        return {
            "name": cls.CONTRACT_NAME,
            "version": cls.CONTRACT_VERSION,
            "owner": cls.CONTRACT_OWNER,
            "sla_hours": cls.CONTRACT_SLA_HOURS,
        }

    @classmethod
    def contract_major(cls) -> int:
        """Componente MAJOR de la version (§6A.5, R-11)."""
        return int(cls.CONTRACT_VERSION.split(".", 1)[0])
