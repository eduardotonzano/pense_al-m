"""Compara a última extração bem-sucedida de cada arquivo com os golden sets.

Confere presença, texto literal, xsi:nil, linha da evidência e field_state.
Estados semânticos (zero, absent...) só são avaliados quando a extração usou
uma mapping_version com regras (não rascunho ``0.0.0-*``).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.golden_set import load_golden_set

SEMANTIC_STATES = {"zero", "absent", "not_applicable", "invalid"}


def main() -> int:
    connection = connect(ROOT / "data" / "cri_cra.db")
    results = {"matched": 0, "mismatched": [], "not_evaluated": [], "no_extraction": []}
    try:
        for golden_path in sorted((ROOT / "config" / "golden_sets").glob("*.json")):
            golden = load_golden_set(golden_path)
            for item in golden["items"]:
                run = connection.execute(
                    """SELECT r.report_id, x.mapping_version FROM extracted_reports r
                       JOIN extraction_runs x ON x.extraction_run_id = r.extraction_run_id
                       WHERE r.document_version_id = ? AND x.status = 'success'
                         AND x.raw_file_hash = ?
                       ORDER BY x.started_at DESC LIMIT 1""",
                    (item["document_version_id"], item["raw_file_hash"]),
                ).fetchone()
                if run is None:
                    results["no_extraction"].append(item["item_id"])
                    continue
                row = connection.execute(
                    """SELECT v.original_value, v.xsi_nil, v.field_state, e.line_number
                       FROM extracted_values v JOIN evidences e USING (extracted_value_id)
                       WHERE v.report_id = ? AND v.xml_path = ? AND v.instance_index = ?""",
                    (run["report_id"], item["xml_path"], item["instance_index"]),
                ).fetchone()
                observed = item["observed"]
                problems = []
                semantic = not run["mapping_version"].startswith("0.0.0")
                if not observed["element_present"]:
                    if row is not None and (
                        row["field_state"] != "absent" or row["original_value"] is not None
                    ):
                        problems.append("caminho ausente extraído com valor")
                    elif row is None and semantic:
                        problems.append("caminho mapeado ausente sem linha 'absent'")
                elif row is None:
                    problems.append("valor não extraído")
                else:
                    if row["original_value"] != observed["raw_text"]:
                        problems.append(
                            f"texto {row['original_value']!r} != {observed['raw_text']!r}"
                        )
                    if bool(row["xsi_nil"]) != bool(observed.get("xsi_nil")):
                        problems.append("xsi_nil diverge")
                    if row["line_number"] != observed.get("line"):
                        problems.append(f"linha {row['line_number']} != {observed.get('line')}")
                    expected_state = item["proposed_field_state"]
                    if expected_state in SEMANTIC_STATES and not semantic:
                        results["not_evaluated"].append(
                            f"{item['item_id']}: field_state {expected_state} (extração bruta: {row['field_state']})"
                        )
                    elif row["field_state"] != expected_state:
                        problems.append(f"field_state {row['field_state']} != {expected_state}")
                if problems:
                    results["mismatched"].append({item["item_id"]: problems})
                else:
                    results["matched"] += 1
    finally:
        connection.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if not results["mismatched"] and not results["no_extraction"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
