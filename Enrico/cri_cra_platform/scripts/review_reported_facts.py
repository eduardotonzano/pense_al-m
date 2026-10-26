from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra a revisão humana de fatos reportados.")
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--status", choices=("approved", "rejected"), required=True)
    parser.add_argument("--by", required=True)
    parser.add_argument("--fact", action="append", help="fact_name; omitido = todos os pendentes")
    args = parser.parse_args()
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        with connection:
            query = """UPDATE reported_facts SET review_status = ?, reviewed_by = ?, reviewed_at = ?
                       WHERE review_status = 'pending'
                         AND asset_id = (SELECT asset_id FROM assets WHERE codigo_cetip = ?)"""
            params: list = [args.status, args.by, date.today().isoformat(), args.cetip]
            if args.fact:
                query += f" AND fact_name IN ({','.join('?' * len(args.fact))})"
                params += args.fact
            changed = connection.execute(query, params).rowcount
    finally:
        connection.close()
    print({"reviewed": changed, "status": args.status})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
