from __future__ import annotations

import sqlite3


def recompute_current(connection: sqlite3.Connection) -> int:
    """Marca como vigente, por (ativo, mês de competência), o relatório aprovado
    de maior source_version. Regra do handoff: mais recente, válida e aprovada."""
    connection.execute("UPDATE extracted_reports SET is_current = 0")
    rows = connection.execute(
        """SELECT report_id, asset_id, substr(reference_date, 1, 7) AS month,
                  CAST(source_version AS INTEGER) AS version
           FROM extracted_reports
           WHERE human_review_status = 'approved'"""
    ).fetchall()
    best: dict[tuple, tuple] = {}
    for row in rows:
        key = (row["asset_id"], row["month"])
        candidate = (row["version"], row["report_id"])
        if key not in best or candidate > best[key]:
            best[key] = candidate
    for _, report_id in best.values():
        connection.execute(
            "UPDATE extracted_reports SET is_current = 1 WHERE report_id = ?", (report_id,)
        )
    return len(best)
