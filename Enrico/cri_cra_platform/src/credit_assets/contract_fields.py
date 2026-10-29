"""Catálogo padrão de campos contratuais e cobertura por ativo.

O catálogo (``config/contract_terms/standard_fields.json``) lista os campos que
buscamos em todo ativo. A cobertura só lê ``contract_parameters``: nunca grava,
nunca interpreta valor e nunca aprova nada.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

IMPORTANCE = ("core", "important", "complementary")
STATUSES = ("approved", "pending", "rejected")


def load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    ids = [field["id"] for field in catalog["fields"]]
    if len(ids) != len(set(ids)):
        raise ValueError("id duplicado no catálogo de campos")
    for field in catalog["fields"]:
        if field["importance"] not in IMPORTANCE:
            raise ValueError(f"{field['id']}: importance inválida")
        field["_patterns"] = [re.compile(alias) for alias in field["aliases"]]
    return catalog


def match_field(parameter_name: str, catalog: dict[str, Any]) -> list[str]:
    """Campos padrão cujos aliases casam com o nome. Mais de um é ambiguidade
    do catálogo e o relatório a mostra, em vez de escolher em silêncio."""

    return [
        field["id"] for field in catalog["fields"]
        if any(pattern.search(parameter_name) for pattern in field["_patterns"])
    ]


def load_not_applicable(path: Path) -> list[dict[str, Any]]:
    entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
    for entry in entries:
        if entry["status"] == "approved" and not entry.get("reviewed_by"):
            raise ValueError(f"{entry['field_id']}: aprovação sem revisor")
    return entries


def coverage(
    connection: sqlite3.Connection,
    catalog: dict[str, Any],
    not_applicable: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    assets = connection.execute(
        "SELECT asset_id, codigo_cetip, tipo_ativo FROM assets ORDER BY codigo_cetip"
    ).fetchall()
    rows = connection.execute(
        "SELECT asset_id, parameter_name, review_status FROM contract_parameters"
    ).fetchall()
    matrix: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"approved": 0, "pending": 0, "rejected": 0})
    )
    unmapped: dict[str, set[str]] = defaultdict(set)
    ambiguous: dict[str, list[str]] = {}
    for row in rows:
        fields = match_field(row["parameter_name"], catalog)
        if not fields:
            unmapped[row["asset_id"]].add(row["parameter_name"])
            continue
        if len(fields) > 1:
            ambiguous[row["parameter_name"]] = fields
        for field_id in fields:
            matrix[row["asset_id"]][field_id][row["review_status"]] += 1
    result_assets = []
    for asset in assets:
        if asset["asset_id"] not in matrix and asset["asset_id"] not in unmapped:
            continue
        per_field = {}
        for field in catalog["fields"]:
            if asset["tipo_ativo"] not in field["applies_to"]:
                continue
            counts = matrix[asset["asset_id"]].get(
                field["id"], {"approved": 0, "pending": 0, "rejected": 0}
            )
            status = (
                "approved" if counts["approved"] else
                "pending" if counts["pending"] else "missing"
            )
            if status == "missing":
                entry = next(
                    (e for e in not_applicable or []
                     if e["codigo_cetip"] == asset["codigo_cetip"] and e["field_id"] == field["id"]),
                    None,
                )
                if entry is not None:
                    status = "not_applicable" if entry["status"] == "approved" else "not_applicable_pending"
            per_field[field["id"]] = {**counts, "status": status}
        result_assets.append({
            "codigo_cetip": asset["codigo_cetip"], "tipo_ativo": asset["tipo_ativo"],
            "fields": per_field,
            "unmapped_parameters": sorted(unmapped.get(asset["asset_id"], set())),
        })
    return {"catalog_version": catalog["catalog_version"], "assets": result_assets,
            "ambiguous_parameters": ambiguous}


def _bucket(status: str) -> str:
    # "não se aplica" aprovado fecha o campo; proposto continua contando como faltando.
    return "approved" if status == "not_applicable" else (
        "missing" if status == "not_applicable_pending" else status
    )


def summarize(report: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    importance = {field["id"]: field["importance"] for field in catalog["fields"]}
    summary = []
    for asset in report["assets"]:
        counts: dict[str, dict[str, int]] = {
            level: {"approved": 0, "pending": 0, "missing": 0} for level in IMPORTANCE
        }
        for field_id, info in asset["fields"].items():
            counts[importance[field_id]][_bucket(info["status"])] += 1
        summary.append({"codigo_cetip": asset["codigo_cetip"], **counts})
    return summary
