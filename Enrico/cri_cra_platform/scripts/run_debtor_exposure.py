"""Exposição por devedor (CNPJ) no mercado inteiro de CRA/CRI e lista de contágio (só leitura).

Fonte: data/cvm_open.db (tabelas *_cedente_devedor e *_classe_vigente), no último mês completo.
Gera reports/market_debtors.{md,csv}. Sinais para olhar o devedor, não conclusões.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.debtor_exposure import aggregate, format_cnpj
from credit_assets.market_checks import fold, merge_alias_certificates, reference_competence, trusted_balance

LINKS = """
    SELECT * FROM (
        SELECT t.Codigo_Identificacao_Certificado, t.Tipo, t.CNPJ, t.Percentual,
               DENSE_RANK() OVER (PARTITION BY t.Codigo_Identificacao_Certificado
                                  ORDER BY CAST(t.Versao AS INTEGER) DESC, t._file_id DESC) AS r
        FROM {kind}_cedente_devedor t JOIN source_files f ON f.file_id = t._file_id
        WHERE f.is_current = 1 AND substr(t.Data_Referencia, 1, 7) = ?)
    WHERE r = 1
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    links, balances, delinquent, refs, names = [], {}, set(), {}, {}
    for kind in ("cra", "cri"):
        counts = {r[0]: r[1] for r in connection.execute(
            f"SELECT Data_Referencia, COUNT(DISTINCT Codigo_Identificacao_Certificado) FROM {kind}_geral_vigente GROUP BY 1")}
        ref = reference_competence(counts)
        refs[kind] = ref[:7]
        rows = [dict(r) for r in connection.execute(
            f"SELECT * FROM {kind}_classe_vigente WHERE Data_Referencia = ?", (ref,))]
        last = {r["Codigo_Identificacao_Certificado"]: ref for r in rows}
        merged, _, _ = merge_alias_certificates(rows, last)
        group_of = {r["_original"]: r["Codigo_Identificacao_Certificado"] for r in merged}
        for code in {r["Codigo_Identificacao_Certificado"] for r in rows}:
            group_of.setdefault(code, code)
        for row in merged:
            key = f"{kind}:{row['Codigo_Identificacao_Certificado']}"
            balances[key] = balances.get(key, Decimal(0)) + trusted_balance(row)
            if fold(row.get("Situacao")) == "em atraso":
                delinquent.add(key)
        for row in connection.execute(
            f"SELECT Codigo_Identificacao_Certificado, Companhia_Emissora, Nome_Emissao FROM {kind}_geral_vigente WHERE Data_Referencia = ?",
            (ref,)):
            names[f"{kind}:{group_of.get(row[0], row[0])}"] = f"{row[1]} | {row[2]}"
        for row in connection.execute(LINKS.format(kind=kind), (ref[:7],)):
            group = group_of.get(row["Codigo_Identificacao_Certificado"], row["Codigo_Identificacao_Certificado"])
            links.append({"certificado": f"{kind}:{group}", "tipo": row["Tipo"], "cnpj": row["CNPJ"],
                          "percentual": row["Percentual"], "kind": kind.upper()})
    connection.close()

    ranking, stats = aggregate(links, balances, delinquent)
    with (ROOT / "reports" / "market_debtors.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["cnpj_devedor", "tipos", "emissoes", "emissoes_em_atraso", "exposicao_estimada_brl", "contagio", "certificados"])
        for item in ranking:
            writer.writerow([format_cnpj(item["cnpj"]), "/".join(sorted(item["tipos"])), len(item["certificados"]),
                             len(item["em_atraso"]), f"{item['exposicao']:.2f}", int(item["contagio"]),
                             "|".join(sorted(c.split(":", 1)[1] for c in item["certificados"]))])

    multi = [i for i in ranking if len(i["certificados"]) > 1]
    contagion = [i for i in ranking if i["contagio"]]
    lines = ["# Exposição por devedor no mercado de CRA e CRI", "",
             f"Fonte: Informe Mensal (dados abertos da CVM), tabela de cedentes e devedores; CRA {refs['cra']}, CRI {refs['cri']}.",
             "Exposição estimada = percentual do devedor × saldo dos certificados da emissão. Só CNPJ válido entra; nada é unido por nome.",
             "Sinais para olhar o devedor, não conclusões.", "",
             f"- Vínculos de devedor no mês: {stats['vinculos']}; devedor não informado (vazio, \"0\", \"NA\", só zeros ou só noves): {stats['nao_informado']}; "
             f"CPF de pessoa física (contado, não exibido): {stats['cpf']}; CNPJ inválido: {stats['cnpj_invalido']}; "
             f"CNPJ que perdeu os zeros à esquerda, recuperado pelos dígitos verificadores: {stats['cnpj_sem_zeros']}; "
             f"percentual inválido (ex.: -1): {stats['percentual_invalido']}.",
             f"- Devedores distintos: **{len(ranking)}**; com mais de uma emissão: **{len(multi)}**; "
             f"**com contágio** (uma emissão em atraso e outra ainda adimplente): **{len(contagion)}**.", "",
             f"## Maiores exposições (top {args.top})", "",
             "| CNPJ do devedor | Tipos | Emissões | Em atraso | Exposição estimada (R$ mi) | Exemplo de emissão |", "|---|---|---|---|---|---|"]
    for item in ranking[: args.top]:
        example = names.get(sorted(item["certificados"])[0], "")
        lines.append(f"| {format_cnpj(item['cnpj'])} | {'/'.join(sorted(item['tipos']))} | {len(item['certificados'])} | "
                     f"{len(item['em_atraso'])} | {item['exposicao'] / 1_000_000:,.1f} | {example[:70]} |")
    lines += ["", "## Contágio: devedor em atraso numa emissão e adimplente em outra", "",
              "| CNPJ do devedor | Emissões | Em atraso | Adimplentes | Exposição (R$ mi) | Emissões em atraso |", "|---|---|---|---|---|---|"]
    for item in contagion:
        late = ", ".join(sorted(c.split(":", 1)[1] for c in item["em_atraso"]))
        lines.append(f"| {format_cnpj(item['cnpj'])} | {len(item['certificados'])} | {len(item['em_atraso'])} | "
                     f"{len(item['certificados']) - len(item['em_atraso'])} | {item['exposicao'] / 1_000_000:,.1f} | {late[:90]} |")
    (ROOT / "reports" / "market_debtors.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
