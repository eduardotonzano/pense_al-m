"""Extrai o texto por página dos PDFs vigentes que ainda não o têm.

Usa o mesmo ``pdftotext -layout`` do restante do projeto e grava em
``document_text_pages`` com a versão do extrator. Versões que já têm páginas
gravadas não são tocadas. PDFs que saem sem texto (imagem) ficam listados:
exigem OCR e nenhum fato pode ser tirado deles antes disso.

    python scripts/extract_document_text.py --cetip CRA022009VM
    python scripts/extract_document_text.py --cetip CRA022009VM --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.database.migrations import ensure_schema_current
from credit_assets.services.contract_terms_service import store_pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    connection = connect(args.database)
    try:
        ensure_schema_current(connection)
        pending = connection.execute(
            """SELECT v.version_id, d.source_document_id, d.document_name
               FROM document_versions v
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE a.codigo_cetip = ? AND v.is_current = 1 AND v.validation_status = 'valid'
                 AND lower(v.file_format) = 'pdf'
                 AND NOT EXISTS (SELECT 1 FROM document_text_pages t
                                 WHERE t.document_version_id = v.version_id)
               ORDER BY CAST(d.source_document_id AS INTEGER)""",
            (args.cetip,),
        ).fetchall()
        result = {"pending": len(pending), "stored": [], "needs_ocr": [], "failed": []}
        for row in pending:
            item = {"source_document_id": row["source_document_id"], "name": row["document_name"]}
            if args.dry_run:
                result["stored"].append(item)
                continue
            try:
                stored = store_pages(connection, ROOT, row["version_id"])
            except Exception as error:  # falha operacional: não vira versão nem dado
                result["failed"].append({**item, "error": f"{type(error).__name__}: {error}"})
                continue
            item.update(pages=stored["pages"], empty_pages=stored["empty_pages"])
            bucket = "needs_ocr" if stored["empty_pages"] == stored["pages"] else "stored"
            result[bucket].append(item)
    finally:
        connection.close()
    print(json.dumps({**result, "dry_run": args.dry_run}, ensure_ascii=False, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
