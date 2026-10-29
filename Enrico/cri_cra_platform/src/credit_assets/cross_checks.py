"""Comparação do mesmo campo entre documentos (Termo, oferta, relatório do AF, DFs).

Só lê ``contract_parameters`` e ``reported_facts``. Compara valores numéricos,
datas e códigos depois de normalizar; texto livre não é comparado: fica listado
para leitura. Nunca decide qual fonte está certa: divergência vira item de revisão.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

KINDS = ("number", "date", "code")
REVIEW_RANK = {"approved": 0, "pending": 1}


def load_checks(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    ids = [check["id"] for check in config["checks"]]
    if len(ids) != len(set(ids)):
        raise ValueError("id duplicado nas verificações")
    for check in config["checks"]:
        if check["kind"] not in KINDS:
            raise ValueError(f"{check['id']}: kind inválido")
        check["_param"] = [re.compile(p) for p in check.get("parameters", [])]
        check["_fact"] = [re.compile(p) for p in check.get("facts", [])]
    return config


def normalize(value: str | None, kind: str) -> str | None:
    """Forma comparável do valor ou None se não for do tipo esperado."""

    text = (value or "").strip()
    if not text:
        return None
    if kind == "number":
        try:
            return format(Decimal(text).normalize(), "f")
        except InvalidOperation:
            return None
    if kind == "date":
        return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None
    if kind == "code":
        return re.sub(r"\s+", "", text).upper()
    return None


def _group(match: re.Match) -> str:
    return match.groupdict().get("n") or "-"


def _collect(connection: sqlite3.Connection, asset_id: int, check: dict[str, Any]):
    entries = []
    for row in connection.execute(
        """SELECT parameter_id, parameter_name, parameter_value, unit, review_status,
                  source_reference
           FROM contract_parameters
           WHERE asset_id = ? AND review_status <> 'rejected'""", (asset_id,),
    ):
        for pattern in check["_param"]:
            match = pattern.search(row["parameter_name"])
            if match:
                entries.append({
                    "group": _group(match), "origin": "parâmetro",
                    "name": row["parameter_name"], "raw": row["parameter_value"],
                    "unit": row["unit"], "status": row["review_status"],
                    "source": row["source_reference"], "id": row["parameter_id"],
                })
                break
    for row in connection.execute(
        """SELECT f.fact_id, f.fact_name, f.value, f.unit, f.review_status, f.page_number,
                  d.source_document_id, d.category, d.document_name
           FROM reported_facts f
           JOIN document_versions v ON v.version_id = f.document_version_id
           JOIN documents d ON d.document_pk = v.document_id
           WHERE f.asset_id = ? AND f.review_status <> 'rejected'""", (asset_id,),
    ):
        for pattern in check["_fact"]:
            match = pattern.search(row["fact_name"])
            if match:
                entries.append({
                    "group": _group(match), "origin": "fato",
                    "name": row["fact_name"], "raw": row["value"], "unit": row["unit"],
                    "status": row["review_status"],
                    "source": f"{row['document_name']} {row['source_document_id']}, p.{row['page_number']}",
                    "id": row["fact_id"],
                })
                break
    allowed = check.get("units")
    for entry in entries:
        entry["comparable"] = allowed is None or (entry["unit"] or "") in allowed
        entry["normalized"] = normalize(entry["raw"], check["kind"]) if entry["comparable"] else None
    return entries


def run_checks(connection: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for asset in connection.execute(
        "SELECT asset_id, codigo_cetip, tipo_ativo FROM assets ORDER BY codigo_cetip"
    ).fetchall():
        for check in config["checks"]:
            if asset["tipo_ativo"] not in check.get("applies_to", ["CRI", "CRA"]):
                continue
            by_group = defaultdict(list)
            for entry in _collect(connection, asset["asset_id"], check):
                by_group[entry["group"]].append(entry)
            for group, entries in sorted(by_group.items()):
                comparable = [e for e in entries if e["normalized"] is not None]
                values = sorted({e["normalized"] for e in comparable})
                origins = {e["source"] for e in comparable}
                if len(comparable) < 2 or len(origins) < 2:
                    verdict = "uma_fonte"
                elif len(values) == 1:
                    verdict = "concordam"
                else:
                    verdict = "divergem"
                all_approved = all(e["status"] == "approved" for e in comparable)
                results.append({
                    "codigo_cetip": asset["codigo_cetip"], "check_id": check["id"],
                    "label": check["label"], "group": group, "verdict": verdict,
                    "all_approved": all_approved, "values": values, "entries": entries,
                })
    return results
