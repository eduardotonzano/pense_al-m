"""Compara o mesmo dado entre documentos e lista as divergências (só leitura do SQLite).

Gera reports/cross_document_checks.md e .csv. Não decide qual fonte está certa.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.cross_checks import load_checks, run_checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument(
        "--checks", type=Path,
        default=ROOT / "config" / "contract_terms" / "cross_checks.json",
    )
    args = parser.parse_args()
    config = load_checks(args.checks)
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        results = run_checks(connection, config)
    finally:
        connection.close()

    with (ROOT / "reports" / "cross_document_checks.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["ativo", "verificacao", "grupo", "resultado", "origem", "nome",
                         "valor", "unidade", "revisao", "fonte"])
        for result in results:
            for entry in result["entries"]:
                writer.writerow([result["codigo_cetip"], result["check_id"], result["group"],
                                 result["verdict"], entry["origin"], entry["name"], entry["raw"],
                                 entry["unit"], entry["status"], entry["source"]])

    counts = {}
    for result in results:
        counts.setdefault(
            result["codigo_cetip"],
            {"concordam": 0, "compativeis": 0, "divergem": 0, "uma_fonte": 0},
        )
        counts[result["codigo_cetip"]][result["verdict"]] += 1
    lines = [
        "# Comparação do mesmo dado entre documentos",
        "",
        f"Verificações `{config['version']}` (propostas). Só lê parâmetros e fatos não rejeitados. "
        "Este relatório lista; não decide qual fonte está certa.",
        "",
        "| Ativo | Concordam | Compatíveis (texto) | Divergem | Uma fonte só |",
        "|---|---|---|---|---|",
    ]
    for cetip, c in counts.items():
        lines.append(
            f"| {cetip} | {c['concordam']} | {c['compativeis']} | {c['divergem']} | {c['uma_fonte']} |"
        )
    for cetip in counts:
        divergent = [r for r in results if r["codigo_cetip"] == cetip and r["verdict"] == "divergem"]
        partial = [r for r in results if r["codigo_cetip"] == cetip and r["verdict"] == "compativeis"]
        lines += ["", f"## {cetip}: divergências", ""]
        if not divergent:
            lines.append("Nenhuma.")
        for result in divergent:
            title = result["label"] + (f" (série {result['group']})" if result["group"] != "-" else "")
            lines += [f"### {title}", ""]
            lines.append("| Valor | Fichas | Origem | Nome | Revisão | Fonte |")
            lines.append("|---|---|---|---|---|---|")
            for entry in sorted(result["entries"], key=lambda e: (e["normalized"] or "", e["name"])):
                if entry["normalized"] is None:
                    continue
                shown = (entry["raw"] or "").replace("|", "/")[:160]
                tokens = ", ".join(sorted(entry["tokens"])) if entry["tokens"] is not None else ""
                lines.append(
                    f"| {shown} | {tokens} | {entry['origin']} | `{entry['name']}` | {entry['status']} | {entry['source']} |"
                )
            lines.append("")
        if partial:
            lines += [f"### {cetip}: textos compatíveis (uma fonte traz só parte do que a outra diz)", ""]
            for result in partial:
                title = result["label"] + (f" (série {result['group']})" if result["group"] != "-" else "")
                parts = "; ".join(
                    f"{e['name']} → {', '.join(sorted(e['tokens']))}"
                    for e in result["entries"] if e["normalized"]
                )
                lines.append(f"- {title}: {parts}")
            lines.append("")
    (ROOT / "reports" / "cross_document_checks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
