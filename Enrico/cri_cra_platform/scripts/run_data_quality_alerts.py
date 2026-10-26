from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.data_quality_alerts_service import detect_asset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument(
        "--rules", type=Path,
        default=ROOT / "config" / "alert_rules" / "data_quality_informe_mensal_cra.json",
    )
    args = parser.parse_args()
    config = json.loads(args.rules.read_text(encoding="utf-8"))
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    try:
        asset = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (args.cetip, args.isin),
        ).fetchone()
        if asset is None:
            raise SystemExit("ativo não encontrado")
        summary = detect_asset(connection, asset["asset_id"], config)
        alerts = [dict(row) for row in connection.execute(
            """SELECT alert_id, competencia_mes, rule_id, severity, instance_key, message,
                      alert_status, evidence_json
               FROM data_quality_alerts WHERE asset_id = ?
               ORDER BY competencia_mes, rule_id""",
            (asset["asset_id"],),
        )]
    finally:
        connection.close()
    path = ROOT / "reports" / f"{args.cetip.lower()}_alertas_qualidade.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, delimiter=";",
            fieldnames=["alert_id", "competencia_mes", "rule_id", "severity", "instance_key",
                        "message", "alert_status", "evidence_json"],
        )
        writer.writeheader()
        writer.writerows(alerts)
    print(json.dumps({**summary, "rules_version": config["rules_version"],
                      "approval_status": config["approval_status"], "report": str(path.relative_to(ROOT))},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
