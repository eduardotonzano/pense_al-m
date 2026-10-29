"""Triagem do mercado inteiro de CRA/CRI sobre data/cvm_open.db (só leitura).

Gera reports/market_ranking.{md,csv}: as emissões ordenadas por sinais de risco ou de erro cadastral,
para decidir quais ativos aprofundar (documentos e Termo). Candidatos a revisão, não conclusões.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.market_checks import WEIGHTS, merge_alias_certificates, rank_emissions, reference_competence

LATEST_SERIES = """
    SELECT * FROM (
        SELECT t.*, ROW_NUMBER() OVER (
            PARTITION BY Codigo_Identificacao_Certificado, Numero_Serie, Codigo_ISIN
            ORDER BY Data_Referencia DESC) AS _latest
        FROM {table} t) WHERE _latest = 1
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        results, summary = {}, {}
        for kind in ("cra", "cri"):
            counts = {
                row[0]: row[1] for row in connection.execute(
                    f"SELECT Data_Referencia, COUNT(DISTINCT Codigo_Identificacao_Certificado) "
                    f"FROM {kind}_geral_vigente GROUP BY 1")
            }
            reference = reference_competence(counts)
            rows = [dict(r) for r in connection.execute(LATEST_SERIES.format(table=f"{kind}_classe_vigente"))]
            last_filing = {
                r[0]: r[1] for r in connection.execute(
                    f"SELECT Codigo_Identificacao_Certificado, MAX(Data_Referencia) FROM {kind}_classe_vigente GROUP BY 1")
            }
            rows, last_filing, _ = merge_alias_certificates(rows, last_filing)  # mesma emissão com dois códigos vira uma
            ranking = rank_emissions(rows, reference, last_filing)
            results[kind] = ranking
            ativos = [i for i in ranking if i["ultima_competencia"] >= reference]
            summary[kind] = {
                "reference": reference, "emissoes": len(ranking), "emissoes_com_informe_recente": len(ativos),
                "com_sinal": sum(1 for i in ranking if i["score"] > 0),
                "flags": Counter(f for i in ranking for f in i["flags"]),
                "saldo_total": sum((i["saldo"] for i in ranking), Decimal(0)),
            }
    finally:
        connection.close()

    flags = list(WEIGHTS)
    (ROOT / "reports" / "market_summary.json").write_text(json.dumps({
        kind: {"referencia": info["reference"], "emissoes": info["emissoes"],
               "emissoes_com_informe_recente": info["emissoes_com_informe_recente"], "com_sinal": info["com_sinal"],
               "saldo_total": str(info["saldo_total"]), "sinais": dict(info["flags"])}
        for kind, info in summary.items()
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "reports" / "market_ranking.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["tipo", "certificado", "emissora_cnpj", "series", "saldo_brl", "ultima_competencia", "score"] + flags)
        for kind, ranking in results.items():
            for item in ranking:
                if item["score"] > 0:
                    writer.writerow([kind.upper(), item["certificado"], item["emissora"], item["series"],
                                     f"{item['saldo']:.2f}", item["ultima_competencia"], item["score"]]
                                    + [item["flags"].get(f, 0) for f in flags])

    lines = ["# Triagem do mercado de CRI e CRA", "",
             "Fonte: Informe Mensal dos dados abertos da CVM (`data/cvm_open.db`). Só leitura. **Candidatos a revisão, não conclusões**:",
             "o dado é o do próprio Informe e erro de preenchimento vem junto.", ""]
    for kind, info in summary.items():
        lines += [f"## {kind.upper()} (competência de referência {info['reference']})", "",
                  f"- {info['emissoes']} emissões desde 2019; {info['emissoes_com_informe_recente']} com informe recente; "
                  f"{info['com_sinal']} com algum sinal.",
                  f"- Saldo das séries com informe recente: R$ {info['saldo_total']:,.0f}.", "",
                  "| Sinal | Emissões com o sinal |", "|---|---|"]
        for flag in flags:
            lines.append(f"| `{flag}` | {sum(1 for i in results[kind] if i['flags'].get(flag))} |")
        lines += ["", f"Top {args.top} por pontuação e saldo:", "",
                  "| Certificado | Séries | Saldo (R$ mi) | Última competência | Pontos | Sinais |", "|---|---|---|---|---|---|"]
        for item in results[kind][: args.top]:
            lines.append(f"| {item['certificado']} | {item['series']} | {item['saldo'] / 1_000_000:,.1f} | "
                         f"{item['ultima_competencia'][:7]} | {item['score']} | "
                         + ", ".join(f"{f}×{n}" for f, n in item["flags"].items()) + " |")
        lines.append("")
    lines += ["## Pesos", "", ", ".join(f"`{f}` = {w}" for f, w in WEIGHTS.items()),
              "", "Pesos são uma proposta para ordenar a fila de aprofundamento; ajuste conforme o que importar mais."]
    (ROOT / "reports" / "market_ranking.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:34]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
