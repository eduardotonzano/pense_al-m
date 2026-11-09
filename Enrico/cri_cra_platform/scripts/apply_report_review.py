"""Aplica decisões de revisão humana aos relatórios e recalcula a versão vigente.

Mapeia cada ``proposed_action`` da planilha para uma decisão explícita
passada por argumento; nenhuma ação é aplicada sem decisão correspondente.
A versão vigente de cada (ativo, mês de competência) é o relatório aprovado
de maior ``source_version`` (regra do handoff: mais recente, válida e aprovada).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.repositories.report_review_repository import recompute_current

ACTION_DECISIONS = {
    "aprovar": ("approved", "Maior versão do mês com validação automática valid."),
    "nao_usar_substituida": ("rejected", "Substituída por versão posterior da mesma competência."),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--decision-source", required=True)
    parser.add_argument(
        "--decidir-as", choices=("approved", "rejected"),
        help="decisão para linhas 'decidir'; omitido = não aplicar",
    )
    parser.add_argument("--decidir-justification", default="")
    args = parser.parse_args()
    if args.decidir_as and not args.decidir_justification:
        parser.error("--decidir-as exige --decidir-justification")

    decisions = dict(ACTION_DECISIONS)
    if args.decidir_as:
        decisions["decidir"] = (args.decidir_as, args.decidir_justification)
    with args.sheet.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    applied, skipped = {}, 0
    try:
        with connection:
            for row in rows:
                decision = decisions.get(row["proposed_action"])
                if decision is None:
                    skipped += 1
                    continue
                status, justification = decision
                connection.execute(
                    """INSERT INTO report_reviews (report_id, review_status, reviewed_by,
                           reviewed_at, decision_source, justification)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (int(row["report_id"]), status, args.reviewer, date.today().isoformat(),
                     args.decision_source, justification),
                )
                connection.execute(
                    "UPDATE extracted_reports SET human_review_status = ? WHERE report_id = ?",
                    (status, int(row["report_id"])),
                )
                applied[status] = applied.get(status, 0) + 1
            current = recompute_current(connection)
    finally:
        connection.close()
    print({"applied": applied, "skipped": skipped, "current_months": current})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
