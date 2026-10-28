"""Registra a revisão humana das séries cadastradas em ``asset_series``.

A aprovação confirma código, ISIN, número e as duas classes lado a lado (Informe e Termo); não escolhe
entre elas quando divergem. O valor original de cada coluna e a evidência não são alterados.

    python scripts/review_asset_series.py --cetip CRA02500C1D --status approved --by "Nome" --source "conversa"
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.database.migrations import ensure_schema_current


def main() -> int:
    parser = argparse.ArgumentParser(description="Revisão humana das séries de um ativo.")
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--status", choices=("approved", "rejected"), required=True)
    parser.add_argument("--by", required=True)
    parser.add_argument("--source", required=True, help="origem da decisão (ex.: conversa)")
    parser.add_argument("--serie", type=int, action="append", help="número da série; omitido = todas as pendentes")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    args = parser.parse_args()
    connection = connect(args.database)
    try:
        ensure_schema_current(connection)
        query = """UPDATE asset_series
                   SET review_status = ?, reviewed_by = ?, reviewed_at = ?
                   WHERE review_status = 'pending'
                     AND asset_id = (SELECT asset_id FROM assets WHERE codigo_cetip = ?)"""
        params: list = [args.status, f"{args.by} ({args.source})", date.today().isoformat(), args.cetip]
        if args.serie:
            query += f" AND numero_serie IN ({','.join('?' * len(args.serie))})"
            params += args.serie
        with connection:
            changed = connection.execute(query, params).rowcount
    finally:
        connection.close()
    print({"reviewed": changed, "status": args.status})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
