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
    parser.add_argument(
        "--preview", action="store_true",
        help="avalia sem gravar alertas; aceita regras pendentes e gera *_avaliacao_contratual_previa.csv",
    )
    args = parser.parse_args()
    config = json.loads(args.rules.read_text(encoding="utf-8"))
    if config.get("approval_status") != "approved" and not args.preview:
        raise SystemExit("regras contratuais não aprovadas (use --preview para avaliar sem gravar)")
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    try:
        asset = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (config["asset"]["codigo_cetip"], config["asset"]["isin"]),
        ).fetchone()
        result = evaluate_asset(connection, asset["asset_id"], config, persist=not args.preview)
    finally:
        connection.close()
    rows = [
        {"rule_id": rule_id, "competencia_mes": item["month"],
         "resultado": "conforme" if item["compliant"] else "ALERTA",
         "message": item["message"], "evidence_json": json.dumps(item["evidence"], ensure_ascii=False)}
        for rule_id, items in result["evaluations"].items() for item in items
    ]
    suffix = "_previa" if args.preview else ""
    cetip = config["asset"]["codigo_cetip"].lower()
    # Arquivos de regras que não são "contractual_*" ganham o próprio nome, para não sobrescrever a prévia das demais.
    family = args.rules.stem.removesuffix(f"_{cetip}")
    kind = "contratual" if family == "contractual" else family
    path = ROOT / "reports" / f"{cetip}_avaliacao_{kind}{suffix}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["rule_id", "competencia_mes", "resultado", "message", "evidence_json"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {k: v for k, v in result.items() if k != "evaluations"}
    print(json.dumps({**summary, "report": str(path.relative_to(ROOT))}, ensure_ascii=False, indent=2))
    for row in rows:
        print(f"  {row['resultado']:8} {row['rule_id']:26} {row['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
