"""Linhas ativas do config/ativos_piloto.csv, para testes que esperam o que o CSV traz."""

from __future__ import annotations

import csv
from pathlib import Path

PILOT_CSV = Path(__file__).resolve().parents[1] / "config" / "ativos_piloto.csv"


def pilot_rows() -> list[dict[str, str]]:
    """As linhas com ativo=true, na ordem do arquivo (o mesmo filtro do run_foundation.py)."""

    with PILOT_CSV.open(encoding="utf-8-sig", newline="") as source:
        return [row for row in csv.DictReader(source) if row.get("ativo", "").lower() == "true"]


def typed_cnpjs(row: dict[str, str]) -> tuple[str, str | None]:
    """(securitizadora, devedor) como o upsert grava um ativo novo: o texto digitado
    sem espacos nas pontas; devedor vazio vira None."""

    return row["cnpj_securitizadora"].strip(), row.get("cnpj_devedor", "").strip() or None
