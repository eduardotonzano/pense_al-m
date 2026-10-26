from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect


def main() -> int:
    parser = argparse.ArgumentParser(description="Altera o status de um alerta de qualidade de dado.")
    parser.add_argument("--alert-id", type=int, required=True)
    parser.add_argument("--status", choices=("open", "acknowledged", "resolved", "dismissed"), required=True)
    parser.add_argument("--by", required=True)
    parser.add_argument("--reason", help="obrigatório para dismissed")
    args = parser.parse_args()
    if args.status == "dismissed" and not args.reason:
        parser.error("--reason é obrigatório para dismissed")
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        with connection:
            changed = connection.execute(
                """UPDATE data_quality_alerts
                   SET alert_status = ?, dismiss_reason = ?, status_changed_by = ?, status_changed_at = ?
                   WHERE alert_id = ?""",
                (args.status, args.reason, args.by, date.today().isoformat(), args.alert_id),
            ).rowcount
    finally:
        connection.close()
    if not changed:
        raise SystemExit(f"alerta {args.alert_id} não encontrado")
    print(f"alerta {args.alert_id}: {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
