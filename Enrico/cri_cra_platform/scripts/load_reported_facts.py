"""Carrega fatos lidos de documentos textuais, conferindo o trecho literal na página.

Recusa a carga se o trecho não existir no texto extraído da página indicada
(comparação com espaços normalizados). Fatos entram como ``pending``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.facts.read_text(encoding="utf-8"))
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    inserted = 0
    try:
        asset = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (payload["asset"]["codigo_cetip"], payload["asset"]["isin"]),
        ).fetchone()
        if asset is None:
            raise SystemExit("ativo não encontrado")
        with connection:
            for fact in payload["facts"]:
                page = connection.execute(
                    """SELECT p.document_version_id, p.text, p.text_sha256
                       FROM document_text_pages p
                       JOIN document_versions v ON v.version_id = p.document_version_id
                       JOIN documents d ON d.document_pk = v.document_id
                       WHERE d.source_document_id = ? AND d.asset_id = ? AND v.is_current = 1
                         AND p.page_number = ?""",
                    (fact["source_document_id"], asset["asset_id"], fact["page_number"]),
                ).fetchone()
                if page is None:
                    raise SystemExit(f"{fact['fact_name']}: página sem texto extraído")
                if _squash(fact["excerpt"]) not in _squash(page["text"]):
                    raise SystemExit(
                        f"{fact['fact_name']} {fact['reference_date']}: trecho não encontrado na página"
                    )
                inserted += connection.execute(
                    """INSERT OR IGNORE INTO reported_facts (
                        asset_id, document_version_id, page_number, page_text_sha256, fact_name,
                        reference_date, value, unit, excerpt, extraction_method, proposed_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (asset["asset_id"], page["document_version_id"], fact["page_number"],
                     page["text_sha256"], fact["fact_name"], fact["reference_date"], fact["value"],
                     fact["unit"], fact["excerpt"], payload["extraction_method"], payload["proposed_by"]),
                ).rowcount
    finally:
        connection.close()
    print({"inserted": inserted, "total": len(payload["facts"])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
