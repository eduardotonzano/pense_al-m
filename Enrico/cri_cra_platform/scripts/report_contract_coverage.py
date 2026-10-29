"""Cobertura dos campos contratuais padrão por ativo (só leitura do SQLite).

Gera reports/contract_field_coverage.csv e .md: para cada ativo e campo, se há
parâmetro aprovado, só pendente ou nenhum. Parâmetros que nenhum campo padrão
reconhece aparecem como "sem campo padrão" para decidir se o catálogo cresce.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.contract_fields import coverage, load_catalog, summarize


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument(
        "--catalog", type=Path,
        default=ROOT / "config" / "contract_terms" / "standard_fields.json",
    )
    args = parser.parse_args()
    catalog = load_catalog(args.catalog)
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        report = coverage(connection, catalog)
    finally:
        connection.close()
    labels = {f["id"]: f for f in catalog["fields"]}
    csv_path = ROOT / "reports" / "contract_field_coverage.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["ativo", "campo", "descricao", "importancia", "situacao",
                         "aprovados", "pendentes"])
        for asset in report["assets"]:
            for field_id, info in asset["fields"].items():
                field = labels[field_id]
                writer.writerow([asset["codigo_cetip"], field_id, field["label"],
                                 field["importance"], info["status"],
                                 info["approved"], info["pending"]])
    lines = [
        "# Cobertura dos campos contratuais padrão",
        "",
        f"Catálogo `{report['catalog_version']}` (proposto; aguarda revisão). Gerado só a partir de `contract_parameters`.",
        "",
        "| Ativo | Core aprovados | Core pendentes | Core faltando | Important aprovados | Important faltando |",
        "|---|---|---|---|---|---|",
    ]
    for item in summarize(report, catalog):
        lines.append(
            f"| {item['codigo_cetip']} | {item['core']['approved']} | {item['core']['pending']} | "
            f"{item['core']['missing']} | {item['important']['approved']} | {item['important']['missing']} |"
        )
    for asset in report["assets"]:
        missing = [fid for fid, info in asset["fields"].items() if info["status"] == "missing"]
        lines += ["", f"## {asset['codigo_cetip']}", "", "**Campos sem parâmetro:**"]
        lines += [f"- `{fid}` ({labels[fid]['importance']}): {labels[fid]['label']}" for fid in missing] or ["- nenhum"]
        if asset["unmapped_parameters"]:
            lines += ["", "**Parâmetros sem campo padrão:** "
                      + ", ".join(f"`{n}`" for n in asset["unmapped_parameters"])]
    if report["ambiguous_parameters"]:
        lines += ["", "## Nomes que casam com mais de um campo", ""]
        lines += [f"- `{n}`: {', '.join(f)}" for n, f in sorted(report["ambiguous_parameters"].items())]
    (ROOT / "reports" / "contract_field_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
