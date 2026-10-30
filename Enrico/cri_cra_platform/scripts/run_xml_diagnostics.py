from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.xml_diagnostics import (
    analyze_xml_bytes,
    build_union,
    load_mapping,
    summarize_file,
)


def _csv_value(value):
    if isinstance(value, (list, tuple)):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if not rows:
            return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: _csv_value(value) for key, value in row.items()} for row in rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument("--category", default="Informe Mensal")
    parser.add_argument(
        "--mapping", type=Path,
        default=ROOT / "config" / "xml_mappings" / "informe_mensal_cra.json",
    )
    parser.add_argument("--union-name", default="cafe_brasil_xml_union")
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        rows = connection.execute(
            """SELECT d.source_document_id, d.publication_date, v.version_id,
                      v.local_file_path, v.file_hash, v.file_size_bytes
               FROM document_versions v
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE a.codigo_cetip = ? AND a.isin = ? AND d.category = ?
                 AND v.is_current = 1 AND v.validation_status = 'valid'
                 AND lower(v.file_format) = 'xml'
               ORDER BY CAST(d.source_document_id AS INTEGER)""",
            (args.cetip, args.isin, args.category),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        print("Nenhuma versão XML válida encontrada.")
        return 1

    files = []
    errors = []
    output_dir = ROOT / "reports" / "xml_diagnostics"
    for row in rows:
        source_id = str(row["source_document_id"])
        path = (ROOT / row["local_file_path"]).resolve()
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["file_hash"] or len(data) != row["file_size_bytes"]:
            errors.append({"source_document_id": source_id, "error": "hash/tamanho divergente do banco"})
            continue
        try:
            analysis = analyze_xml_bytes(data)
        except Exception as error:
            errors.append({"source_document_id": source_id, "error": f"{type(error).__name__}: {error}"})
            continue
        summary = summarize_file(analysis)
        file_info = {
            "source_document_id": source_id,
            "document_version_id": row["version_id"],
            "publication_date": row["publication_date"],
            "local_file_path": row["local_file_path"],
            **{key: value for key, value in analysis.items() if key != "paths"},
            "layout_validation_status": "structural_only",
            "paths_total": len(summary),
            "summary": summary,
        }
        stem = f"{args.cetip}_{source_id}"
        write_json(output_dir / f"{stem}.json", file_info)
        write_csv(output_dir / f"{stem}.csv", summary)
        files.append(file_info)

    union = build_union(files, mapping)
    union["errors"] = errors
    union["asset"] = {"codigo_cetip": args.cetip, "isin": args.isin, "category": args.category}
    write_json(ROOT / "reports" / f"{args.union_name}.json", union)
    write_csv(ROOT / "reports" / f"{args.union_name}.csv", union["paths"])
    print(json.dumps(
        {key: value for key, value in union.items() if key != "paths"},
        ensure_ascii=False, indent=2,
    ))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
