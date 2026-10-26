"""Gera a planilha de revisão humana dos relatórios extraídos.

Usa a extração bem-sucedida mais recente de cada document_version com a
mapping_version informada. Agrupa por ativo e mês de competência (AAAA-MM do
literal; o literal é mantido intacto) e propõe uma ação por relatório:

- ``aprovar``: maior versão do mês e validação automática ``valid``;
- ``nao_usar_substituida``: existe versão maior para o mesmo mês;
- ``decidir``: maior versão do mês, mas com warning/invalid.

Nada é gravado no banco: a aprovação é aplicada por apply_report_review.py.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect

COLUMNS = (
    "report_id", "codigo_cetip", "isin", "competencia_mes", "reference_date",
    "source_version", "source_document_id", "publication_date",
    "automatic_validation_status", "findings", "proposed_action", "reason",
    "decision", "reviewed_by", "comment",
)


def latest_reports(connection, mapping_version: str):
    return connection.execute(
        """SELECT r.report_id, a.codigo_cetip, a.isin, r.reference_date,
                  r.source_version, d.source_document_id, r.publication_date,
                  r.automatic_validation_status,
                  (SELECT group_concat(rule || ':' || replace(xml_path, '/InformeMensalCRA', ''), ' ; ')
                     FROM (SELECT DISTINCT rule, xml_path FROM extraction_findings f
                           WHERE f.report_id = r.report_id)) AS findings
           FROM extracted_reports r
           JOIN extraction_runs x ON x.extraction_run_id = r.extraction_run_id
           JOIN documents d ON d.document_pk = r.document_id
           JOIN assets a ON a.asset_id = r.asset_id
           WHERE x.status = 'success' AND x.mapping_version = ?
             AND x.started_at = (
                 SELECT max(x2.started_at) FROM extraction_runs x2
                 WHERE x2.document_version_id = x.document_version_id
                   AND x2.status = 'success' AND x2.mapping_version = x.mapping_version)
           ORDER BY a.codigo_cetip, r.reference_date, CAST(r.source_version AS INTEGER)""",
        (mapping_version,),
    ).fetchall()


def propose(rows) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["codigo_cetip"], (row["reference_date"] or "")[:7])].append(row)
    proposals = []
    for (cetip, month), items in sorted(groups.items()):
        top = max(int(item["source_version"] or 0) for item in items)
        for item in items:
            version = int(item["source_version"] or 0)
            if version < top:
                action, reason = "nao_usar_substituida", f"substituída pela versão {top}"
            elif item["automatic_validation_status"] == "valid":
                action, reason = "aprovar", "maior versão do mês e validação automática valid"
            else:
                action, reason = "decidir", f"maior versão do mês com status {item['automatic_validation_status']}"
            proposals.append({
                **{key: item[key] for key in item.keys()},
                "competencia_mes": month,
                "proposed_action": action,
                "reason": reason,
                "decision": "", "reviewed_by": "", "comment": "",
            })
    return proposals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping-version", default="0.1.1")
    args = parser.parse_args()
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        proposals = propose(latest_reports(connection, args.mapping_version))
    finally:
        connection.close()
    path = ROOT / "reports" / f"report_review_informe_mensal_cra_{args.mapping_version}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(proposals)
    summary = defaultdict(int)
    for proposal in proposals:
        summary[(proposal["codigo_cetip"], proposal["proposed_action"])] += 1
    print(path.relative_to(ROOT))
    for key, count in sorted(summary.items()):
        print(" ", *key, count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
