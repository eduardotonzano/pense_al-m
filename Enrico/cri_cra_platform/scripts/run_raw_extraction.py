from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.raw_xml_extraction_service import (
    EXTRACTOR_VERSION,
    RawXmlExtractionService,
)
from credit_assets.xml_diagnostics import load_mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument("--category", default="Informe Mensal")
    parser.add_argument(
        "--mapping", type=Path,
        default=ROOT / "config" / "xml_mappings" / "informe_mensal_cra.json",
    )
    parser.add_argument(
        "--reprocess", action="store_true",
        help="cria nova extraction_run mesmo se já houver uma bem-sucedida",
    )
    args = parser.parse_args()
    mapping = load_mapping(args.mapping)
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    try:
        versions = connection.execute(
            """SELECT v.version_id, d.source_document_id
               FROM document_versions v
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE a.codigo_cetip = ? AND a.isin = ? AND d.category = ?
                 AND v.is_current = 1 AND v.validation_status = 'valid'
                 AND lower(v.file_format) = 'xml'
               ORDER BY CAST(d.source_document_id AS INTEGER)""",
            (args.cetip, args.isin, args.category),
        ).fetchall()
        service = RawXmlExtractionService(connection, ROOT)
        summary = {"extracted": 0, "skipped": 0, "failed": 0, "runs": []}
        for version in versions:
            already = connection.execute(
                """SELECT 1 FROM extraction_runs
                   WHERE document_version_id = ? AND status = 'success'
                     AND extractor_version = ? AND mapping_version = ?""",
                (version["version_id"], EXTRACTOR_VERSION, mapping["mapping_version"]),
            ).fetchone()
            if already and not args.reprocess:
                summary["skipped"] += 1
                continue
            result = service.extract_version(version["version_id"], mapping)
            result["source_document_id"] = version["source_document_id"]
            summary["runs"].append(result)
            summary["failed" if result["status"] == "failed" else "extracted"] += 1
        print(json.dumps(
            {k: v for k, v in summary.items() if k != "runs"}
            | {"failures": [r for r in summary["runs"] if r["status"] == "failed"]},
            ensure_ascii=False, indent=2,
        ))
        return 0 if summary["failed"] == 0 else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
