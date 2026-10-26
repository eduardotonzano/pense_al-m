"""Carrega uma proposta de parâmetros contratuais (pendentes) e gera a planilha de revisão.

Cada parâmetro precisa apontar para um candidato existente cujo hash de
trecho confira; caso contrário a carga é recusada. Parâmetros já carregados
não são sobrescritos (a revisão humana fica preservada).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.contract_terms_service import candidate_from_anchor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, required=True)
    args = parser.parse_args()
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    try:
        asset = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (proposal["asset"]["codigo_cetip"], proposal["asset"]["isin"]),
        ).fetchone()
        if asset is None:
            raise SystemExit("ativo não encontrado")
        inserted = 0
        with connection:
            for item in proposal["parameters"]:
                source_id = item.get("source_document_id", proposal.get("source_document_id"))
                if "anchor" in item:
                    version = connection.execute(
                        """SELECT v.version_id FROM document_versions v
                           JOIN documents d ON d.document_pk = v.document_id
                           WHERE d.source_document_id = ? AND d.asset_id = ? AND v.is_current = 1""",
                        (source_id, asset["asset_id"]),
                    ).fetchone()
                    if version is None:
                        raise SystemExit(f"{item['parameter_name']}: documento {source_id} sem versão")
                    item["candidate_id"] = candidate_from_anchor(
                        connection, version["version_id"], proposal.get("topic", "documento"),
                        item["anchor"], "anchor-0.1.0",
                    )
                    item["candidate_excerpt_sha256"] = connection.execute(
                        "SELECT excerpt_sha256 FROM contract_parameter_candidates WHERE candidate_id = ?",
                        (item["candidate_id"],),
                    ).fetchone()[0]
                candidate = connection.execute(
                    """SELECT c.candidate_id, c.excerpt_sha256, c.page_number, c.line_start, c.line_end
                       FROM contract_parameter_candidates c WHERE c.candidate_id = ?""",
                    (item["candidate_id"],),
                ).fetchone()
                if candidate is None or candidate["excerpt_sha256"] != item["candidate_excerpt_sha256"]:
                    raise SystemExit(f"{item['parameter_name']}: candidato ausente ou trecho alterado")
                kind = proposal.get("source_kind", "termo")
                reference = (
                    f"{'Termo' if kind == 'termo' else 'Ata'} {source_id}, p.{candidate['page_number']}, "
                    f"linhas {candidate['line_start']}-{candidate['line_end']}"
                )
                inserted += connection.execute(
                    """INSERT OR IGNORE INTO contract_parameters (
                        asset_id, candidate_id, parameter_name, parameter_value, unit,
                        applies_when, source_reference, proposed_by, justification,
                        valid_from, source_kind, supersedes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (asset["asset_id"], item["candidate_id"], item["parameter_name"],
                     item["parameter_value"], item["unit"], item["applies_when"], reference,
                     proposal["proposed_by"], item.get("note"), item.get("valid_from"), kind,
                     ",".join(item.get("supersedes") or []) or None),
                ).rowcount
        rows = [dict(row) for row in connection.execute(
            """SELECT p.parameter_id, p.parameter_name, p.parameter_value, p.unit, p.applies_when,
                      p.valid_from, p.valid_to, p.source_kind, p.supersedes, p.source_reference, p.justification AS observacao, p.review_status,
                      c.excerpt AS trecho_literal
               FROM contract_parameters p
               JOIN contract_parameter_candidates c ON c.candidate_id = p.candidate_id
               WHERE p.asset_id = ? ORDER BY p.parameter_id""",
            (asset["asset_id"],),
        )]
    finally:
        connection.close()
    path = ROOT / "reports" / f"{proposal['asset']['codigo_cetip'].lower()}_parametros_contratuais_revisao.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print({"inserted": inserted, "total": len(rows), "review_sheet": str(path.relative_to(ROOT))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
