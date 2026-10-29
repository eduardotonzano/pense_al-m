"""Termo de Securitização × Informe Mensal da CVM, para todos os ativos com Termo baixado (só leitura).

Lê o texto dos PDFs de Termo/Aditamento em memória (pdftotext), extrai valores com regex
(credit_assets.termo_values: candidatos, nunca parâmetros aprovados) e compara com o que a securitizadora
informa à CVM: data de emissão, vencimento por série, valor total, quantidade e valor nominal unitário.
Nos pilotos, mede também o acerto do extrator contra os parâmetros aprovados.
Gera reports/termo_vs_cvm.{md,csv}. Triagem: divergência pede leitura humana, não é conclusão.
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

from credit_assets.market_checks import integralized, money
from credit_assets.services.contract_terms_service import extract_pdf_pages
from credit_assets.cross_checks import tokenize
from credit_assets.termo_values import best, extract, remuneration_numbers

TOLERANCE = Decimal("0.01")
APPROVED_MAP = {
    "data_emissao": ("data_emissao",),
    "valor_total": ("valor_total_emissao",),
    "quantidade": ("quantidade_total_cra", "quantidade_cri"),
    "valor_nominal_unitario": ("valor_nominal_unitario", "valor_nominal_unitario_emissao"),
}


def close(a: Decimal, b: Decimal) -> bool:
    return b != 0 and abs(a - b) / abs(b) <= TOLERANCE


def cvm_emission(connection: sqlite3.Connection, kind: str, isin: str):
    row = connection.execute(
        f"SELECT CNPJ_Emissora, Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE Codigo_ISIN = ? "
        "ORDER BY Data_Referencia DESC LIMIT 1", (isin,)).fetchone()
    if row is None:
        return None
    cnpj, cert = row
    isins = [r[0] for r in connection.execute(
        f"SELECT DISTINCT Codigo_ISIN FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado = ? AND Codigo_ISIN <> ''",
        (cert,))]
    codes = {cert} | {r[0] for r in connection.execute(
        f"SELECT DISTINCT Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE CNPJ_Emissora = ? AND Codigo_ISIN IN "
        f"({','.join('?' * len(isins))})", (cnpj, *isins))} if isins else {cert}
    marks = ",".join("?" * len(codes))
    last = connection.execute(
        f"SELECT MAX(Data_Referencia) FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado IN ({marks})",
        tuple(codes)).fetchone()[0]
    series = {}
    for r in connection.execute(
            f"SELECT * FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado IN ({marks}) AND Data_Referencia = ?",
            (*codes, last)):
        series[(r["Codigo_ISIN"] or r["Numero_Serie"])] = dict(r)
    geral = connection.execute(
        f"SELECT Data_Emissao FROM {kind}_geral_vigente WHERE Codigo_Identificacao_Certificado IN ({marks}) "
        "ORDER BY Data_Referencia DESC LIMIT 1", tuple(codes)).fetchone()
    return {"codes": sorted(codes), "last": last, "series": list(series.values()),
            "data_emissao": (geral[0] or "")[:10] if geral else ""}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--cvm", default=str(ROOT / "data" / "cvm_open.db"))
    args = parser.parse_args()
    catalog = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True, timeout=30)
    catalog.row_factory = sqlite3.Row
    cvm = sqlite3.connect(f"file:{args.cvm}?mode=ro", uri=True)
    cvm.row_factory = sqlite3.Row
    docs = defaultdict(list)
    for row in catalog.execute(
            """SELECT a.asset_id, a.codigo_cetip, a.isin, a.tipo_ativo, d.source_document_id, d.category, v.local_file_path
               FROM document_versions v JOIN documents d ON d.document_pk = v.document_id JOIN assets a ON a.asset_id = d.asset_id
               WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
                 AND d.category IN ('Termo de Securitização', 'Aditamento')
               ORDER BY a.codigo_cetip, (d.category <> 'Termo de Securitização'), CAST(d.source_document_id AS INTEGER)"""):
        docs[row["asset_id"]].append(dict(row))
    approved = defaultdict(dict)
    for row in catalog.execute(
            "SELECT asset_id, parameter_name, parameter_value FROM contract_parameters WHERE review_status = 'approved' "
            "AND (valid_to IS NULL OR valid_to >= date('now'))"):
        approved[row["asset_id"]][row["parameter_name"]] = row["parameter_value"]
    catalog.close()

    results, accuracy = [], Counter()
    for asset_id, items in docs.items():
        first = items[0]
        per_doc: list[tuple[str, list]] = []  # na ordem: Termos antes de aditamentos, do mais antigo ao mais novo
        rate_numbers: set[str] = set()
        for doc in items:
            path = ROOT / doc["local_file_path"]
            if not path.is_file():
                continue
            pages, _ = extract_pdf_pages(path)
            numbered = [(i + 1, t) for i, t in enumerate(pages)]
            per_doc.append((doc["source_document_id"], extract(numbered)))
            rate_numbers |= remuneration_numbers(numbered)

        def termo(field):
            """Data de emissão: a do primeiro documento que a traz. Demais campos: união do melhor de cada documento
            (um aditamento pode mudar vencimento, valor ou quantidade)."""
            chosen = []
            for sid, cands in per_doc:
                picked = [(sid, c) for c in best(cands, field)]
                if field == "data_emissao" and picked:
                    return picked
                chosen += picked
            return chosen
        emission = cvm_emission(cvm, first["tipo_ativo"].lower(), first["isin"])
        row = {"ativo": first["codigo_cetip"], "isin": first["isin"], "tipo": first["tipo_ativo"],
               "termos": len(items), "competencia_cvm": (emission or {}).get("last", "")[:7] if emission else ""}

        def verdict(field, ok, termo_value, cvm_value, source=""):
            results.append({**row, "campo": field, "resultado": ok, "termo": termo_value, "cvm": cvm_value, "fonte_termo": source})

        if emission is None:
            verdict("emissao", "sem_dado_cvm", "", "")
            continue
        # data de emissão
        emi = termo("data_emissao")
        if emi:
            sid, c = emi[0]
            verdict("data_emissao", "concorda" if c.value == emission["data_emissao"] else "diverge", c.value,
                    emission["data_emissao"], f"{sid} p.{c.page}")
        else:
            verdict("data_emissao", "sem_valor_no_termo", "", emission["data_emissao"])
        # vencimento por série
        dates = {c.value for _, c in termo("data_vencimento")}
        lastro_dates = {c.value for _, c in termo("data_vencimento_lastro")}
        for s in emission["series"]:
            due = (s.get("Data_Vencimento") or "")[:10]
            label = f"vencimento {s.get('Codigo_ISIN') or 'série ' + str(s.get('Numero_Serie'))}"
            if not dates and not lastro_dates:
                verdict(label, "sem_valor_no_termo", "", due)
            elif due in dates:
                verdict(label, "concorda", "; ".join(sorted(dates)), due)
            elif due in lastro_dates:
                # o Informe traz o vencimento do lastro (debênture, nota comercial, CCB), não o do CRA/CRI
                verdict(label, "informe_usa_data_do_lastro", "; ".join(sorted(dates)), due)
            else:
                verdict(label, "diverge", "; ".join(sorted(dates | {f"lastro {d}" for d in lastro_dates})), due)
        # valor total e quantidade
        totals = [Decimal(c.value) for _, c in termo("valor_total")]
        paid_in = sum((integralized(s) for s in emission["series"]), Decimal(0))
        if totals and paid_in:
            series_paid = [integralized(s) for s in emission["series"] if integralized(s) > 0]
            # concorda se algum valor do Termo bate com o total integralizado ou com o de uma série (programa com várias séries)
            ok = any(close(t, paid_in) or any(close(t, x) for x in series_paid) for t in totals)
            verdict("valor_total", "concorda" if ok else "diverge", "; ".join(f"{t:.2f}" for t in sorted(set(totals))), f"{paid_in:.2f}")
        quantities = {int(c.value) for _, c in termo("quantidade")}
        cvm_qty = [int(money(s.get("Quantidade_Certificados"))) for s in emission["series"]]
        if quantities and cvm_qty:
            total_qty = sum(cvm_qty)
            ok = total_qty in quantities or all(q in quantities for q in cvm_qty)
            verdict("quantidade", "concorda" if ok else "diverge", "; ".join(map(str, sorted(quantities))), str(total_qty))
        # remuneração: os números da taxa informada à CVM (multiplicador e spread/taxa) aparecem no Termo?
        for s in emission["series"]:
            informed = {f"{slot}={format(round(Decimal(value), 2).normalize(), 'f')}"
                        for slot, _, value in (t.partition("=") for t in tokenize(s.get("Taxa_Juros") or "", "remuneracao"))
                        if slot in ("mult", "taxa")}
            # "100%" do índice é o padrão e quase nunca aparece escrito ao lado do spread: não decide sozinho
            decisive = {n for n in informed if n != "mult=100"}
            label = f"remuneracao {s.get('Codigo_ISIN') or 'série ' + str(s.get('Numero_Serie'))}"
            if not decisive:
                continue
            if not rate_numbers:
                verdict(label, "sem_valor_no_termo", "", s.get("Taxa_Juros") or "")
            else:
                verdict(label, "concorda" if decisive <= rate_numbers else "diverge",
                        "; ".join(sorted(rate_numbers))[:120], s.get("Taxa_Juros") or "")
        vnus = [Decimal(c.value) for _, c in termo("valor_nominal_unitario")]
        unit = [integralized(s) / money(s.get("Quantidade_Certificados")) for s in emission["series"]
                if money(s.get("Quantidade_Certificados")) > 0 and integralized(s) > 0]
        if vnus and unit:
            verdict("valor_nominal_unitario", "concorda" if any(close(v, unit[0]) for v in vnus) else "diverge",
                    "; ".join(f"{v:.2f}" for v in vnus), f"{unit[0]:.2f}")
        # acerto do extrator contra parâmetros aprovados (pilotos)
        params = approved.get(asset_id, {})
        for field, names in APPROVED_MAP.items():
            value = next((params[n] for n in names if n in params), None)
            extracted = [c.value for _, c in termo(field)]
            if value is None or not extracted:
                continue
            hit = (value in extracted) if field == "data_emissao" else any(
                close(Decimal(x), Decimal(value)) for x in extracted)
            accuracy[(field, "acerto" if hit else "erro")] += 1
        for name, value in params.items():
            if name.startswith("vencimento_serie_") or name in ("data_vencimento", "data_vencimento_termo_original"):
                extracted = {c.value for _, c in termo("data_vencimento")}
                if extracted:
                    accuracy[("data_vencimento", "acerto" if value in extracted else "erro")] += 1
    cvm.close()

    with (ROOT / "reports" / "termo_vs_cvm.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ativo", "isin", "tipo", "termos", "competencia_cvm", "campo", "resultado",
                                                    "termo", "cvm", "fonte_termo"], delimiter=";")
        writer.writeheader()
        writer.writerows(results)
    per_asset = defaultdict(Counter)
    for r in results:
        per_asset[r["ativo"]][r["resultado"]] += 1
    lines = ["# Termo de Securitização × Informe Mensal da CVM", "",
             "Valores do Termo extraídos por regex (candidatos, não parâmetros aprovados) comparados com o Informe da CVM. "
             "Divergência pede leitura humana: pode ser erro do Informe, aditamento não lido ou extração errada.", ""]
    if accuracy:
        lines += ["## Acerto do extrator contra parâmetros aprovados (pilotos)", "", "| Campo | Acertos | Erros |", "|---|---|---|"]
        for field in sorted({f for f, _ in accuracy}):
            lines.append(f"| {field} | {accuracy[(field, 'acerto')]} | {accuracy[(field, 'erro')]} |")
        lines.append("")
    totals = Counter((r["campo"].split(" ")[0], r["resultado"]) for r in results)
    lines += ["## Resultado por campo", "", "| Campo | Concorda | Diverge | Informe usa data do lastro | Sem valor no Termo |",
              "|---|---|---|---|---|"]
    for field in ("data_emissao", "vencimento", "remuneracao", "valor_total", "quantidade", "valor_nominal_unitario"):
        lines.append(f"| {field} | {totals[(field, 'concorda')]} | {totals[(field, 'diverge')]} | "
                     f"{totals[(field, 'informe_usa_data_do_lastro')]} | {totals[(field, 'sem_valor_no_termo')]} |")
    lines += ["", "## Resumo por ativo", "", "| Ativo | Concorda | Diverge | Informe usa data do lastro | Sem valor no Termo | Sem dado CVM |",
              "|---|---|---|---|---|---|"]
    for asset, c in sorted(per_asset.items(), key=lambda kv: -kv[1]["diverge"]):
        lines.append(f"| {asset} | {c['concorda']} | {c['diverge']} | {c['informe_usa_data_do_lastro']} | "
                     f"{c['sem_valor_no_termo']} | {c['sem_dado_cvm']} |")
    lines += ["", "## Divergências", "", "| Ativo | Campo | Termo | CVM | Fonte no Termo |", "|---|---|---|---|---|"]
    for r in results:
        if r["resultado"] == "diverge":
            lines.append(f"| {r['ativo']} | {r['campo']} | {r['termo'][:70]} | {r['cvm']} | {r['fonte_termo']} |")
    (ROOT / "reports" / "termo_vs_cvm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
