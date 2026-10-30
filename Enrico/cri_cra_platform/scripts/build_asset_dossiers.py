"""Ficha por ativo do catálogo: tudo o que a plataforma sabe dele numa página (só leitura).

Junta: cadastro do catálogo, última competência do Informe na CVM (séries, saldo, situação, taxa, vencimento,
rating), eventos de crédito dos últimos 12 meses, sinais de triagem, devedores (CNPJ), Termo × Informe,
assuntos de assembleias/fatos e documentos do catálogo. Gera reports/fichas/<código>.md e reports/fichas/README.md.
Rodar depois dos relatórios de mercado (run_monthly_market.py), de run_termo_vs_cvm.py e de run_assembly_topics.py.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.cvm_lookup import emission, history
from credit_assets.market_checks import balance_is_suspect, fold, money
from credit_assets.market_events import compare

REPORTS = ROOT / "reports"


def read_csv(name: str) -> list[dict[str, str]]:
    path = REPORTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def mi(value: Decimal) -> str:
    return f"{value / 1_000_000:,.1f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--cvm", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--cetip", help="só um ativo")
    args = parser.parse_args()
    catalog = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True, timeout=30)
    catalog.row_factory = sqlite3.Row
    cvm = sqlite3.connect(f"file:{args.cvm}?mode=ro", uri=True)
    cvm.row_factory = sqlite3.Row
    assets = catalog.execute(
        "SELECT * FROM assets" + (" WHERE codigo_cetip = ?" if args.cetip else "") + " ORDER BY codigo_cetip",
        (args.cetip,) if args.cetip else ()).fetchall()
    doc_counts = defaultdict(Counter)
    for row in catalog.execute(
            """SELECT d.asset_id, d.category, CASE WHEN v.version_id IS NULL THEN 'não baixado' ELSE 'baixado' END AS st
               FROM documents d LEFT JOIN document_versions v ON v.document_id = d.document_pk AND v.is_current = 1"""):
        doc_counts[row["asset_id"]][(row["category"], row["st"])] += 1
    approved = Counter(r[0] for r in catalog.execute(
        "SELECT asset_id FROM contract_parameters WHERE review_status = 'approved'"))
    catalog.close()

    ranking = read_csv("market_ranking.csv")
    debtors = read_csv("market_debtors.csv")
    termo = read_csv("termo_vs_cvm.csv")
    assemblies = read_csv("assembleias_topicos.csv")
    out_dir = REPORTS / "fichas"
    out_dir.mkdir(exist_ok=True)
    index = []
    for asset in assets:
        kind = asset["tipo_ativo"].lower()
        cetip = asset["codigo_cetip"]
        lines = [f"# Ficha: {cetip} ({asset['tipo_ativo']})", "",
                 f"- Securitizadora: {asset['securitizadora']} ({asset['cnpj_securitizadora']}); emissão {asset['emissao']}; "
                 f"ISIN de referência {asset['isin']}.",
                 f"- Parâmetros contratuais aprovados no catálogo: {approved.get(asset['asset_id'], 0)}."]
        if (REPORTS / "fichas_contratuais" / f"{cetip.lower()}.md").is_file():
            lines.append(f"- Ficha contratual (trecho de cada campo do Termo): [../fichas_contratuais/{cetip.lower()}.md]"
                         f"(../fichas_contratuais/{cetip.lower()}.md).")
        lines.append("")
        em = emission(cvm, kind, asset["isin"]) if asset["isin"] else None
        flags_line = ""
        late = 0
        total = Decimal(0)
        if em is None:
            lines += ["Sem dados na base da CVM para este ISIN.", ""]
        else:
            geral = em["geral"]
            lines += [f"## Informe Mensal na CVM (competência {em['last'][:7]})", "",
                      f"{geral.get('Companhia_Emissora', '')} | {geral.get('Nome_Emissao', '')} | emissão de {em['data_emissao']} | "
                      f"códigos do certificado: {', '.join(em['codes'])}", "",
                      "| Série | ISIN | Classe | Situação | Saldo (R$ mi) | Vencimento | Taxa | Rating |", "|---|---|---|---|---|---|---|---|"]
            for s in sorted(em["series"], key=lambda r: str(r.get("Numero_Serie"))):
                balance = money(s.get("Valor_Certificados"))
                suspect = balance_is_suspect(s)
                total += Decimal(0) if suspect else balance
                late += fold(s.get("Situacao")) == "em atraso"
                lines.append(f"| {s.get('Numero_Serie')} | {s.get('Codigo_ISIN') or '-'} | {s.get('Classe') or '-'} | "
                             f"{s.get('Situacao') or '-'} | {mi(balance)}{' ⚠' if suspect else ''} | {(s.get('Data_Vencimento') or '-')[:10]} | "
                             f"{s.get('Taxa_Juros') or '-'} | {s.get('Classificacao_Risco_Atual') or '-'} |")
            year, month = int(em["last"][:4]), int(em["last"][5:7])
            since = f"{year - 1:04d}-{month:02d}-01"
            rows = history(cvm, kind, em["codes"], since)
            by_series = defaultdict(list)
            for r in rows:
                by_series[r["Codigo_ISIN"] or str(r["Numero_Serie"])].append(r)
            events = []
            for key, items in by_series.items():
                previous = None
                for r in items:
                    if previous and previous["Data_Referencia"] != r["Data_Referencia"]:
                        for ev in compare(previous, r):
                            events.append((r["Data_Referencia"][:7], key, ev))
                    previous = r
            lines += ["", "## Eventos de crédito nos últimos 12 meses", ""]
            lines += [f"- {m} | {k} | {ev}" for m, k, ev in sorted(set(events))] or ["- nenhum"]
            codes = set(em["codes"])
            signals = [r for r in ranking if r["certificado"] in codes]
            if signals:
                r = signals[0]
                flags = {k: v for k, v in r.items() if k not in ("tipo", "certificado", "emissora_cnpj", "series", "saldo_brl",
                                                                  "ultima_competencia", "score") and v not in ("0", "")}
                flags_line = ", ".join(f"{k}×{v}" for k, v in flags.items())
                lines += ["", f"## Sinais de triagem (pontos {r['score']})", "", f"- {flags_line}"]
            linked = [d for d in debtors if codes & set(d["certificados"].split("|"))]
            lines += ["", "## Devedores (CNPJ, do Informe)", ""]
            lines += [f"- {d['cnpj_devedor']}: {d['emissoes']} emissões no mercado, {d['emissoes_em_atraso']} em atraso, exposição "
                      f"estimada R$ {Decimal(d['exposicao_estimada_brl']) / 1_000_000:,.1f} mi{' — **contágio**' if d['contagio'] == '1' else ''}"
                      for d in linked] or ["- nenhum CNPJ válido informado"]
        checks = [r for r in termo if r["ativo"] == cetip]
        if checks:
            counter = Counter(r["resultado"] for r in checks)
            lines += ["", "## Termo × Informe da CVM", "", "- " + ", ".join(f"{k}: {v}" for k, v in counter.items()), ""]
            lines += [f"- **diverge** {r['campo']}: Termo {r['termo'][:80]} × CVM {r['cvm']}" for r in checks if r["resultado"] == "diverge"]
        topics = [r for r in assemblies if r["ativo"] == cetip and r.get("assuntos_relevantes")]
        lines += ["", "## Assembleias, fatos relevantes e comunicados (assuntos)", ""]
        lines += [f"- {r['data']} | {r['categoria']} {r['documento']} | {r['assuntos_relevantes']}"
                  f"{' | não instalada' if r['nao_instalada'] == '1' else ''}" for r in sorted(topics, key=lambda r: r["data"])] or ["- nenhum assunto relevante nos documentos baixados"]
        counts = doc_counts.get(asset["asset_id"], Counter())
        lines += ["", "## Documentos no catálogo", "", "| Categoria | Baixados | Não baixados |", "|---|---|---|"]
        for category in sorted({c for c, _ in counts}):
            lines.append(f"| {category} | {counts[(category, 'baixado')]} | {counts[(category, 'não baixado')]} |")
        lines += ["", "Fontes: catálogo do projeto, dados abertos da CVM, relatórios em `reports/`. Sinais são triagem, não conclusões."]
        (out_dir / f"{cetip.lower()}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        divergences = sum(1 for r in checks if r["resultado"] == "diverge")
        index.append((cetip, asset["tipo_ativo"], total, late, divergences, len(topics), flags_line))
    cvm.close()
    lines = ["# Fichas dos ativos do catálogo", "", "| Ativo | Tipo | Saldo (R$ mi) | Séries em atraso | Divergências Termo × CVM | "
             "Documentos com assunto relevante | Sinais |", "|---|---|---|---|---|---|---|"]
    for cetip, tipo, total, late, divergences, topics, flags in sorted(index, key=lambda r: (-r[3], -r[4], r[0])):
        lines.append(f"| [{cetip}]({cetip.lower()}.md) | {tipo} | {mi(total)} | {late} | {divergences} | {topics} | {flags[:80]} |")
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(index)} fichas em reports/fichas/")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
