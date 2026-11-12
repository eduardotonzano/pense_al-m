from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.contract_terms_service import store_candidates, store_pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument(
        "--config", type=Path,
        default=ROOT / "config" / "contract_terms" / "termo_securitizacao.json",
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    summary = []
    try:
        versions = connection.execute(
            """SELECT v.version_id, d.source_document_id
               FROM document_versions v
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE a.codigo_cetip = ? AND a.isin = ?
                 AND d.category IN ('Termo de Securitização', 'Aditamento')
                 AND v.is_current = 1 AND v.validation_status = 'valid'
                 AND lower(v.file_format) = 'pdf'""",
            (args.cetip, args.isin),
        ).fetchall()
        if not versions:
            raise SystemExit("nenhum Termo/Aditamento PDF baixado para o ativo")
        for version in versions:
            pages = store_pages(connection, ROOT, version["version_id"])
            found = store_candidates(connection, version["version_id"], config)
            summary.append({"source_document_id": version["source_document_id"], **pages, **found})
        rows = [dict(row) for row in connection.execute(
            """SELECT c.candidate_id, d.source_document_id, c.topic, c.page_number,
                      c.line_start, c.line_end, c.values_found_json, c.excerpt
               FROM contract_parameter_candidates c
               JOIN document_versions v ON v.version_id = c.document_version_id
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE a.codigo_cetip = ? AND a.isin = ?
               ORDER BY c.topic, c.page_number, c.line_start""",
            (args.cetip, args.isin),
        )]
    finally:
        connection.close()
    path = ROOT / "reports" / f"{args.cetip.lower()}_clausulas_candidatas.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["candidate_id"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"documents": summary, "report": str(path.relative_to(ROOT))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
