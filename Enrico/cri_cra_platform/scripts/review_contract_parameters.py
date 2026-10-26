from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra a revisão humana de parâmetros contratuais.")
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--status", choices=("approved", "rejected"), required=True)
    parser.add_argument("--by", required=True)
    parser.add_argument("--source", required=True, help="origem da decisão (ex.: conversa, reunião)")
    parser.add_argument("--parameter", action="append", help="nome do parâmetro; omitido = todos os pendentes")
    parser.add_argument(
        "--applies-when", nargs=2, action="append", metavar=("PARAMETRO", "TEXTO"),
        help="ajusta applies_when de um parâmetro junto com a revisão",
    )
    args = parser.parse_args()
    overrides = dict(args.applies_when or [])
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        rows = connection.execute(
            """SELECT p.parameter_id, p.parameter_name, p.justification FROM contract_parameters p
               JOIN assets a ON a.asset_id = p.asset_id
               WHERE a.codigo_cetip = ? AND p.review_status = 'pending'""",
            (args.cetip,),
        ).fetchall()
        selected = [r for r in rows if not args.parameter or r["parameter_name"] in args.parameter]
        with connection:
            for row in selected:
                note = f"Revisão: {args.status} por {args.by} ({args.source})."
                connection.execute(
                    """UPDATE contract_parameters
                       SET review_status = ?, reviewed_by = ?, reviewed_at = ?,
                           justification = trim(coalesce(justification, '') || ' ' || ?),
                           applies_when = coalesce(?, applies_when)
                       WHERE parameter_id = ?""",
                    (args.status, args.by, date.today().isoformat(), note,
                     overrides.get(row["parameter_name"]), row["parameter_id"]),
                )
    finally:
        connection.close()
    print({"reviewed": len(selected), "status": args.status})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
