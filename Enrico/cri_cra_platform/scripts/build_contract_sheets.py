"""Fichas contratuais por ativo: o trecho literal de cada um dos 36 campos padrão nos Termos e aditamentos (só leitura).

Para cada campo: até dois trechos (definição e cláusula, com documento, página e marca de OCR), as outras páginas
onde o campo aparece, o parâmetro já aprovado no catálogo e, quando houver, o valor tirado do Termo por regex e o
informado à CVM (de reports/termo_vs_cvm.csv; rodar scripts/run_termo_vs_cvm.py antes). Mede também, nos parâmetros
aprovados, se o trecho mostrado cai na página da evidência aprovada.
Gera reports/fichas_contratuais/<código>.md e README.md. Nada aqui aprova parâmetro: é material de leitura.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.contract_fields import load_catalog, match_field
from credit_assets.contract_sheet import field_excerpts, fold, value_variants
from credit_assets.field_finder import load_topics
from credit_assets.services.contract_terms_service import document_pages

GROUPS = {"identificacao": "Identificação", "emissao": "Emissão", "remuneracao": "Remuneração e amortização",
          "garantias": "Garantias e fundos", "covenants": "Covenants", "vencimento_antecipado": "Vencimento antecipado",
          "resgate": "Resgate e waiver", "obrigacoes": "Obrigações de informação", "governanca": "Governança"}
TERMO_VS_CVM = {"data_emissao": "emissao.data_emissao", "vencimento": "emissao.data_vencimento",
                "remuneracao": "remuneracao.taxa", "devedor": "identificacao.devedor", "valor_total": "emissao.valor_total",
                "quantidade": "emissao.quantidade_titulos", "valor_nominal_unitario": "emissao.valor_nominal_unitario"}
IMPORTANCE = {"core": "essencial", "important": "importante", "complementary": "complementar"}


def iso(value: str | None) -> str:
    text = (value or "").strip()
    if len(text) >= 10 and text[2] == "/":
        return f"{text[6:10]}-{text[3:5]}-{text[0:2]}"
    return text[:10]


def quote(text: str) -> str:
    return text.replace("`", "'").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--only", nargs="*", help="códigos CETIP (padrão: todos os ativos com Termo baixado)")
    args = parser.parse_args()
    catalog = load_catalog(ROOT / "config" / "contract_terms" / "standard_fields.json")
    topics = load_topics(ROOT / "config" / "contract_terms" / "field_topics.json")
    fields = catalog["fields"]
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    docs = defaultdict(list)
    for row in connection.execute(
            """SELECT a.asset_id, a.codigo_cetip, a.tipo_ativo, a.securitizadora, d.source_document_id, d.category,
                      d.document_name, d.publication_date, d.reference_date, v.version_id, v.local_file_path
               FROM document_versions v JOIN documents d ON d.document_pk = v.document_id JOIN assets a ON a.asset_id = d.asset_id
               WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
                 AND d.category IN ('Termo de Securitização', 'Aditamento')"""):
        if args.only and row["codigo_cetip"] not in args.only:
            continue
        docs[row["codigo_cetip"]].append(dict(row))
    approved = defaultdict(lambda: defaultdict(list))
    for row in connection.execute(
            """SELECT a.codigo_cetip, p.parameter_id, p.parameter_name, p.parameter_value, p.unit, c.page_number, c.document_version_id
               FROM contract_parameters p JOIN assets a ON a.asset_id = p.asset_id
               LEFT JOIN contract_parameter_candidates c ON c.candidate_id = p.candidate_id
               WHERE p.review_status = 'approved' AND p.source_kind = 'termo'
                 AND (p.valid_to IS NULL OR p.valid_to >= date('now'))"""):
        for field_id in match_field(row["parameter_name"], catalog):
            approved[row["codigo_cetip"]][field_id].append(dict(row))
    comparisons = defaultdict(lambda: defaultdict(list))
    termo_csv = ROOT / "reports" / "termo_vs_cvm.csv"
    if termo_csv.is_file():
        with termo_csv.open(encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                field_id = TERMO_VS_CVM.get(row["campo"].split(" ")[0])
                if field_id:
                    comparisons[row["ativo"]][field_id].append(row)

    out_dir = ROOT / "reports" / "fichas_contratuais"
    out_dir.mkdir(parents=True, exist_ok=True)
    index, quality = [], Counter()
    for cetip, items in sorted(docs.items()):
        items.sort(key=lambda d: (iso(d["publication_date"]) or iso(d["reference_date"]) or "9999",
                                  int(d["source_document_id"]) if str(d["source_document_id"]).isdigit() else 0))
        loaded = [(str(d["source_document_id"]), document_pages(connection, d["version_id"], ROOT / d["local_file_path"]))
                  for d in items]
        version_doc = {d["version_id"]: str(d["source_document_id"]) for d in items}
        page_text = {(doc, number): text for doc, pages in loaded for number, text, _ in pages}
        first = items[0]
        total_pages = sum(len(pages) for _, pages in loaded)
        ocr_pages = sum(1 for _, pages in loaded for _, text, ocr in pages if ocr and text.strip())
        lines = [f"# Ficha contratual: {cetip} ({first['tipo_ativo']})", "",
                 f"- Securitizadora: {first['securitizadora']}.",
                 f"- Documentos lidos ({len(items)}, do mais antigo para o mais novo; {total_pages} páginas"
                 + (f", {ocr_pages} por OCR" if ocr_pages else "") + "): "
                 + "; ".join(f"{d['category']} {d['source_document_id']} ({iso(d['publication_date']) or 's/ data'})" for d in items) + ".",
                 "- **Material de leitura, não parâmetro aprovado.** Trechos localizados por palavras-chave "
                 "(`config/contract_terms/field_topics.json`): a definição vem do documento mais recente que a traz; a cláusula é a "
                 "página do corpo com mais menções do campo, com as páginas vizinhas que também o mencionam; anexos aparecem à parte. "
                 "Página de OCR pode ter erro de leitura: conferir no PDF.", ""]
        found_fields = core_found = 0
        missing = []
        for group, label in GROUPS.items():
            group_fields = [f for f in fields if f["group"] == group and first["tipo_ativo"] in f.get("applies_to", ["CRI", "CRA"])]
            if not group_fields:
                continue
            lines += [f"## {label}", ""]
            for field in group_fields:
                result = field_excerpts(loaded, topics.get(field["id"], []))
                params = approved[cetip].get(field["id"], [])
                compared = comparisons[cetip].get(field["id"], [])
                if result.excerpts:
                    found_fields += 1
                    core_found += field["importance"] == "core"
                else:
                    missing.append(field)
                lines.append(f"### {field['label']} (`{field['id']}`, {IMPORTANCE.get(field['importance'], field['importance'])})")
                lines.append("")
                shown_text = fold(" ".join(page_text.get((e.document, n), "") for e in result.excerpts
                                           for n in range(e.pages[0], e.pages[1] + 1)))
                for position, p in enumerate(params):
                    variants = value_variants(str(p["parameter_value"]), p["unit"])
                    seen = bool(variants) and any(v in shown_text for v in variants)
                    if variants:
                        quality["valor_conferivel"] += 1
                        quality["valor_nas_paginas_mostradas"] += seen
                    if position < 6:
                        where = (f"; evidência no doc {version_doc.get(p['document_version_id'], '?')} p. {p['page_number']}"
                                 if p["page_number"] else "")
                        lines.append(f"- Aprovado: `{p['parameter_name']}` = {quote(str(p['parameter_value']))[:120]}"
                                     f"{' ' + p['unit'] if p['unit'] else ''} (parâmetro {p['parameter_id']}{where})"
                                     + (" — o valor aparece nas páginas mostradas abaixo" if seen else ""))
                    if p["page_number"] and p["document_version_id"] in version_doc:
                        doc = version_doc[p["document_version_id"]]
                        shown = any(e.document == doc and e.pages[0] - 1 <= p["page_number"] <= e.pages[1] + 1
                                    for e in result.excerpts)
                        quality["trecho_na_pagina_da_evidencia" if shown else "trecho_em_outra_pagina"] += 1
                if len(params) > 6:
                    lines.append(f"- … e mais {len(params) - 6} parâmetros aprovados deste campo.")
                for c in compared[:4]:
                    lines.append(f"- Termo (regex) × CVM, {c['campo']}: **{c['resultado'].replace('_', ' ')}**; Termo: {c['termo'][:90] or '-'}; "
                                 f"CVM: {c['cvm'][:60] or '-'}")
                if len(compared) > 4:
                    others = Counter(c["resultado"] for c in compared[4:])
                    lines.append(f"- … e mais {len(compared) - 4} comparações ({', '.join(f'{k.replace(chr(95), chr(32))} {v}' for k, v in others.items())}).")
                if not result.excerpts:
                    lines += ["- Sem trecho localizado: o campo pode não se aplicar ou estar com outra redação.", ""]
                    continue
                for e in result.excerpts:
                    if e.kind == "definicao":
                        where = f"Definição, doc {e.document} p. {e.page}"
                    elif e.pages[0] == e.pages[1]:
                        where = f"Cláusula, doc {e.document} p. {e.page}"
                    else:
                        where = f"Cláusula, doc {e.document} p. {e.pages[0]}–{e.pages[1]} (trecho da p. {e.page})"
                    lines += [f"- {where}{' (OCR)' if e.ocr else ''}:", "", f"  > {quote(e.text)}", ""]
                if result.other_pages:
                    lines += ["- Também em: " + ", ".join(f"{doc} p. {page}" for doc, page in result.other_pages), ""]
                if result.annex_pages:
                    lines += ["- Em anexos: " + ", ".join(f"{doc} p. {page}" for doc, page in result.annex_pages), ""]
        applicable = [f for f in fields if first["tipo_ativo"] in f.get("applies_to", ["CRI", "CRA"])]
        core_total = sum(1 for f in applicable if f["importance"] == "core")
        summary = [f"**Cobertura:** {found_fields} de {len(applicable)} campos com trecho; essenciais {core_found} de {core_total}."]
        if missing:
            summary.append("Sem trecho: " + ", ".join(f"`{f['id']}`" for f in missing) + ".")
        lines[5:5] = summary + [""]
        filename = f"{cetip.lower()}.md"
        (out_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
        index.append({"ativo": cetip, "tipo": first["tipo_ativo"], "documentos": len(items), "paginas": total_pages,
                      "ocr": ocr_pages, "campos": f"{found_fields}/{len(applicable)}", "core": f"{core_found}/{core_total}",
                      "aprovados": sum(len(v) for v in approved[cetip].values()), "arquivo": filename,
                      "sem_trecho": ", ".join(f["id"].split(".", 1)[1] for f in missing if f["importance"] == "core")})
    connection.close()

    checked = quality["trecho_na_pagina_da_evidencia"] + quality["trecho_em_outra_pagina"]
    readme = ["# Fichas contratuais", "",
              "Uma ficha por ativo com Termo ou aditamento baixado: o trecho literal de cada um dos 36 campos padrão, com documento e "
              "página, o parâmetro aprovado (quando há) e a comparação do Termo com o Informe da CVM. Material de leitura para a "
              "revisão humana; nada aqui é parâmetro aprovado. Gerado por `scripts/build_contract_sheets.py`.", ""]
    if quality["valor_conferivel"]:
        readme += [f"**Qualidade nos parâmetros aprovados (datas, valores em R$, quantidades e taxas):** em "
                   f"{quality['valor_nas_paginas_mostradas']} de {quality['valor_conferivel']} "
                   f"({100 * quality['valor_nas_paginas_mostradas'] / quality['valor_conferivel']:.0f}%) o valor aprovado aparece escrito "
                   "nas páginas que a ficha mostra para o campo.", ""]
    if checked:
        readme += [f"Pela página: em {quality['trecho_na_pagina_da_evidencia']} de {checked} "
                   f"({100 * quality['trecho_na_pagina_da_evidencia'] / checked:.0f}%) a página da evidência aprovada está dentro das "
                   "páginas mostradas (tolerância de 1 página). A medida é estrita: a ficha prefere o texto mais recente (Termo consolidado "
                   "do aditamento) e a lista de características, e a evidência aprovada muitas vezes está no Termo original ou na cláusula "
                   "detalhada, com o mesmo valor.", ""]
    readme += ["| Ativo | Tipo | Docs | Páginas | OCR | Campos com trecho | Essenciais | Aprovados | Essenciais sem trecho |",
               "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(index, key=lambda r: r["ativo"]):
        readme.append(f"| [{r['ativo']}]({r['arquivo']}) | {r['tipo']} | {r['documentos']} | {r['paginas']} | {r['ocr'] or ''} | "
                      f"{r['campos']} | {r['core']} | {r['aprovados'] or ''} | {r['sem_trecho'] or '-'} |")
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print("\n".join(readme))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
