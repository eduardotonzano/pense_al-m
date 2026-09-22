from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.download_diagnostics import (
    SAMPLE_CATEGORIES,
    build_inventory,
    select_samples,
)

def markdown(report: dict) -> str:
    inventory = report["inventory"]
    lines = [
        "# Inventário documental — CRA Café Brasil",
        "",
        f"- Asset ID: `{inventory['asset']['asset_id']}`",
        f"- Código CETIP: `{inventory['asset']['codigo_cetip']}`",
        f"- Total de documentos: **{inventory['total_documents']}**",
        f"- Período: `{inventory['period']['min']}` a `{inventory['period']['max']}`",
        "",
        "## Categorias",
        "",
        "| Categoria | Quantidade |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {category} | {count} |"
        for category, count in inventory["category_counts"].items()
    )
    lines.extend(["", "## Amostra de diagnóstico", ""])
    if report["download_diagnostics"]:
        lines.extend(
            f"- `{item['document_id']}` — {item['category']} — {item['status']}"
            for item in report["download_diagnostics"]
        )
    else:
        lines.append("Nenhum documento disponível para amostra.")
    if report["limitations"]:
        lines.extend(["", "## Limitações", ""])
        lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(["", "## Recomendação", "", report["recommendation"]])
    return "\n".join(lines) + "\n"


def run(database_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    assets = connection.execute(
        """SELECT * FROM assets
           WHERE isin = 'BRECOACRABX0'
           ORDER BY CASE WHEN codigo_cetip = 'CRA022009VM' THEN 0 ELSE 1 END, asset_id"""
    ).fetchall()
    asset = assets[0] if assets else None
    limitations = []
    if asset is None:
        raise RuntimeError("ativo CRA022009VM/BRECOACRABX0 não encontrado")
    asset_ids = [row["asset_id"] for row in assets]
    placeholders = ",".join("?" for _ in asset_ids)
    rows = connection.execute(
        f"SELECT * FROM documents WHERE asset_id IN ({placeholders}) ORDER BY document_pk",
        asset_ids,
    ).fetchall()
    if len(asset_ids) > 1:
        limitations.append(
            "mesmo ISIN está associado a múltiplos ativos no banco: "
            + ", ".join(f"{row['codigo_cetip']}/asset_id={row['asset_id']}" for row in assets)
        )
    if len(rows) != 124:
        limitations.append(
            f"banco desta sessão contém {len(rows)} documentos; esperado atualmente: 124"
        )
    inventory = build_inventory(rows, asset)
    samples = select_samples(rows)
    diagnostics = []
    for sample in samples:
        diagnostics.append({
            **sample,
            "status": "não executado nesta rodada sem documentos catalogados"
                if not rows else "pendente de execução Playwright",
            "visualization_url": sample["source_url"],
            "download_url": None,
        })
    report = {
        "inventory": inventory,
        "asset_records": [
            {"asset_id": row["asset_id"], "codigo_cetip": row["codigo_cetip"]}
            for row in assets
        ],
        "sample_selection": samples,
        "download_diagnostics": diagnostics,
        "limitations": limitations,
        "official_database_modified": False,
        "temporary_files_removed": True,
        "recommendation": (
            "Executar a amostra Playwright somente após disponibilizar os documentos "
            "catalogados no SQLite desta sessão; limitar a um documento por categoria "
            "e não atualizar status_download/file_hash antes de aprovação."
        ),
    }
    (output_dir / "cafe_brasil_document_inventory.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "cafe_brasil_document_inventory.md").write_text(
        markdown(report), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    print(json.dumps(run(args.database, args.output_dir), ensure_ascii=False, indent=2))
