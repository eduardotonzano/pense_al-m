from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Any

FINANCIAL_STATEMENTS_PATTERN = re.compile(r"\bdemonstra\w*\s+financeira")


def _fold(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in folded if not unicodedata.combining(c))


def reclassify_financial_statements(
    connection: sqlite3.Connection, *, apply: bool = False
) -> dict[str, Any]:
    """Rebaixa para 'Outro' documentos de Demonstrações Financeiras classificados
    antes da regra do classificador. Não toca arquivos, versões nem hashes."""
    rows = connection.execute(
        "SELECT document_pk, source_document_id, category, document_name "
        "FROM documents WHERE category <> 'Outro'"
    ).fetchall()
    targets = [
        row for row in rows
        if FINANCIAL_STATEMENTS_PATTERN.search(_fold(row["document_name"]))
    ]
    changed = []
    if apply and targets:
        with connection:
            for row in targets:
                connection.execute(
                    "UPDATE documents SET category = 'Outro' WHERE document_pk = ?",
                    (row["document_pk"],),
                )
    for row in targets:
        changed.append({
            "document_pk": row["document_pk"],
            "source_document_id": row["source_document_id"],
            "from": row["category"],
            "to": "Outro",
        })
    return {"applied": apply and bool(targets), "candidates": len(targets), "documents": changed}
