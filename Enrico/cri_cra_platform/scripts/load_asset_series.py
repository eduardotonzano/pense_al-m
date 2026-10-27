"""Cadastra as séries de um ativo a partir do Informe Mensal vigente mais recente.

Código de negociação, ISIN e classe vêm do bloco DadosGerais/Series do XML
(com a linha da evidência); a classe do Termo vem do parâmetro contratual
aprovado ``classe_serie_N``, quando existe. As séries entram como
``pending``: a aprovação é humana. Séries já cadastradas não são reescritas.

    python scripts/load_asset_series.py --cetip CRA02500C1D --dry-run
    python scripts/load_asset_series.py --cetip CRA02500C1D --commit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.database.migrations import ensure_schema_current

ROOTS = {"CRA": "/InformeMensalCRA", "CRI": "/InformeMensalCRI"}
FIELDS = {
    "codigo_negociacao": "/DadosGerais/Series/Serie/CodigoNegociacaoMercadoSec",
    "isin": "/DadosGerais/Series/Serie/CodigoISIN",
    "classe_informe": "/DadosGerais/Series/Serie/Classe",
}


def propose(connection, cetip: str) -> list[dict]:
    asset = connection.execute(
        "SELECT asset_id, tipo_ativo FROM assets WHERE codigo_cetip = ?", (cetip,)
    ).fetchone()
    if asset is None:
        raise SystemExit("ativo não encontrado")
    report = connection.execute(
        """SELECT r.report_id, r.reference_date, d.source_document_id
           FROM extracted_reports r JOIN documents d ON d.document_pk = r.document_id
           WHERE r.asset_id = ? AND r.is_current = 1
           ORDER BY r.reference_date DESC LIMIT 1""",
        (asset["asset_id"],),
    ).fetchone()
    if report is None:
        raise SystemExit("ativo sem Informe Mensal vigente")
    root = ROOTS[asset["tipo_ativo"]]
    series: dict[str, dict] = {}
    for field, path in FIELDS.items():
        for row in connection.execute(
            """SELECT v.instance_key, v.original_value, e.line_number
               FROM extracted_values v JOIN evidences e USING (extracted_value_id)
               WHERE v.report_id = ? AND v.xml_path = ? AND v.instance_key IS NOT NULL""",
            (report["report_id"], root + path),
        ):
            item = series.setdefault(row["instance_key"], {"evidence": {}})
            # O literal fica na evidência; a coluna guarda o valor sem espaços nas pontas
            # (decisão 2026-10-27 sobre o ISIN com espaço final).
            item[field] = (row["original_value"] or "").strip() or None
            item["evidence"][field] = {
                "xml_path": root + path, "line": row["line_number"], "literal": row["original_value"],
            }
    proposals = []
    for key in sorted(series, key=int):
        item = series[key]
        parameter = connection.execute(
            """SELECT parameter_id, parameter_value FROM contract_parameters
               WHERE asset_id = ? AND parameter_name = ? AND review_status = 'approved'
                 AND valid_to IS NULL""",
            (asset["asset_id"], f"classe_serie_{key}"),
        ).fetchall()
        if len(parameter) > 1:
            raise SystemExit(f"classe_serie_{key}: mais de um parâmetro aprovado vigente")
        proposals.append({
            "asset_id": asset["asset_id"], "numero_serie": int(key),
            "codigo_negociacao": item.get("codigo_negociacao"), "isin": item.get("isin"),
            "classe_informe": item.get("classe_informe"),
            "classe_termo": parameter[0]["parameter_value"] if parameter else None,
            "classe_termo_parameter_id": parameter[0]["parameter_id"] if parameter else None,
            "source_report_id": report["report_id"],
            "source_document_id": report["source_document_id"],
            "evidence_json": json.dumps(
                {"competencia": report["reference_date"], **item["evidence"]},
                ensure_ascii=False, sort_keys=True,
            ),
        })
    return proposals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    connection = connect(args.database)
    try:
        ensure_schema_current(connection)
        proposals = propose(connection, args.cetip)
        inserted = 0
        with connection:
            for item in proposals:
                exists = connection.execute(
                    "SELECT 1 FROM asset_series WHERE asset_id = ? AND numero_serie = ?",
                    (item["asset_id"], item["numero_serie"]),
                ).fetchone()
                print(("já cadastrada" if exists else "nova"), item["numero_serie"],
                      item["codigo_negociacao"], item["isin"],
                      f"informe={item['classe_informe']}", f"termo={item['classe_termo']}")
                if exists or args.dry_run:
                    continue
                connection.execute(
                    f"INSERT INTO asset_series ({', '.join(item)}) VALUES ({', '.join('?' * len(item))})",
                    tuple(item.values()),
                )
                inserted += 1
    finally:
        connection.close()
    print({"series": len(proposals), "inserted": inserted, "dry_run": args.dry_run})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
