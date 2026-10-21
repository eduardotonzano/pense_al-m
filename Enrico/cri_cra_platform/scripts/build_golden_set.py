"""Congela observações do XML bruto no golden set e gera a planilha de revisão.

Itens já congelados nunca são reescritos: são verificados contra o arquivo e,
se divergirem, a execução falha.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.golden_set import coverage, load_golden_set, locate, verify_item

REVIEW_COLUMNS = (
    "item_id", "source_document_id", "source_version", "xml_path", "line", "raw_text", "xsi_nil",
    "evidence_excerpt", "case_types", "proposed_field_state", "decision_question",
    "notes", "human_review_status", "reviewed_by", "review_comment", "corrected_value",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--golden", type=Path,
        default=ROOT / "config" / "golden_sets" / "informe_mensal_cra_cafe_brasil.json",
    )
    args = parser.parse_args()
    golden = load_golden_set(args.golden)
    connection = connect(ROOT / "data" / "cri_cra.db")
    problems: dict[str, list[str]] = {}
    frozen = 0
    try:
        for item in golden["items"]:
            row = connection.execute(
                """SELECT v.version_id, v.local_file_path, v.file_hash, v.source_version
                   FROM document_versions v
                   JOIN documents d ON d.document_pk = v.document_id
                   JOIN assets a ON a.asset_id = d.asset_id
                   WHERE d.source_document_id = ? AND a.isin = ?
                     AND v.is_current = 1 AND v.validation_status = 'valid'""",
                (item["source_document_id"], golden["asset"]["isin"]),
            ).fetchone()
            if row is None:
                problems[item["item_id"]] = ["sem versão física válida no banco"]
                continue
            data = (ROOT / row["local_file_path"]).read_bytes()
            item.setdefault("source_version", row["source_version"])
            if item.get("observed"):
                found = verify_item(item, data)
                if found:
                    problems[item["item_id"]] = found
                continue
            observed = locate(data, item["xml_path"], item["instance_index"])
            if not observed["element_present"]:
                problems[item["item_id"]] = ["caminho não encontrado no XML"]
                continue
            item["document_version_id"] = row["version_id"]
            item["local_file_path"] = row["local_file_path"]
            item["raw_file_hash"] = row["file_hash"]
            item["observed"] = observed
            frozen += 1
    finally:
        connection.close()
    if problems:
        print(json.dumps({"problems": problems}, ensure_ascii=False, indent=2))
        return 1

    args.golden.write_text(
        json.dumps(golden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    review_path = ROOT / "reports" / f"golden_set_review_{golden['golden_set_id']}.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, delimiter=";")
        writer.writeheader()
        for item in golden["items"]:
            observed = item["observed"]
            writer.writerow({
                **{key: item.get(key) for key in REVIEW_COLUMNS},
                "line": observed.get("line"),
                "raw_text": observed.get("raw_text"),
                "xsi_nil": observed.get("xsi_nil"),
                "evidence_excerpt": observed.get("evidence_excerpt"),
                "case_types": " | ".join(item["case_types"]),
            })
    print(json.dumps(
        {"frozen_now": frozen, "review_sheet": str(review_path.relative_to(ROOT)), **coverage(golden)},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
