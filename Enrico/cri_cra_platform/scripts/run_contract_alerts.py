from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.contract_alerts_service import evaluate_asset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.rules.read_text(encoding="utf-8"))
    if config.get("approval_status") != "approved":
        raise SystemExit("regras contratuais não aprovadas")
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    try:
        asset = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (config["asset"]["codigo_cetip"], config["asset"]["isin"]),
        ).fetchone()
        result = evaluate_asset(connection, asset["asset_id"], config)
    finally:
        connection.close()
    rows = [
        {"rule_id": rule_id, "competencia_mes": item["month"],
         "resultado": "conforme" if item["compliant"] else "ALERTA",
         "message": item["message"], "evidence_json": json.dumps(item["evidence"], ensure_ascii=False)}
        for rule_id, items in result["evaluations"].items() for item in items
    ]
    path = ROOT / "reports" / f"{config['asset']['codigo_cetip'].lower()}_avaliacao_contratual.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    summary = {k: v for k, v in result.items() if k != "evaluations"}
    print(json.dumps({**summary, "report": str(path.relative_to(ROOT))}, ensure_ascii=False, indent=2))
    for row in rows:
        print(f"  {row['resultado']:8} {row['rule_id']:26} {row['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
