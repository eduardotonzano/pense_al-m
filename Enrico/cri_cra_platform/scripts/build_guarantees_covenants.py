"""Garantias e covenants estruturados de todos os ativos com Termo ou aditamento lido (só leitura do banco).

Gera reports/garantias_covenants.csv (um item por linha, com documento, página e trecho literal) e
reports/garantias_covenants.md (resumo do mercado e quadro por ativo). Itens saem "a revisar": é triagem por
regra de texto, não parâmetro aprovado.

    python scripts/build_guarantees_covenants.py
    python scripts/build_guarantees_covenants.py --only 24G2100031
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

from credit_assets.guarantees_covenants import COVENANT_TYPES, EXTRACTOR, GUARANTEE_TYPES, as_rows, extract
from credit_assets.services.contract_terms_service import document_pages

FIELDS = ["codigo_cetip", "tipo", "grupo", "item", "rotulo", "situacao", "operador", "limite", "unidade", "periodicidade",
          "valores_no_trecho", "documento", "pagina", "ocr", "trecho", "extrator", "revisao"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "cri_cra.db")
    parser.add_argument("--only", action="append")
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    docs = defaultdict(list)
    for row in connection.execute(
            """SELECT a.codigo_cetip, a.tipo_ativo, d.source_document_id, d.category, v.version_id, v.local_file_path
               FROM document_versions v JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = d.asset_id
               WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
                 AND d.category IN ('Termo de Securitização', 'Aditamento')
               ORDER BY a.codigo_cetip, (d.category <> 'Termo de Securitização'), CAST(d.source_document_id AS INTEGER)"""):
        if args.only and row["codigo_cetip"] not in args.only:
            continue
        docs[(row["codigo_cetip"], row["tipo_ativo"])].append(row)

    rows = []
    for (cetip, kind), items in docs.items():
        pages = []
        for doc in items:
            path = ROOT / doc["local_file_path"] if doc["local_file_path"] else None
            for number, text, ocr in document_pages(connection, doc["version_id"], path):
                pages.append((str(doc["source_document_id"]), number, text, ocr))
        rows.extend(as_rows(cetip, kind, extract(pages)))
    connection.close()

    out = ROOT / "reports" / "garantias_covenants.csv"
    if not args.only:
        with out.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    assets = sorted(docs)
    present = Counter(r["item"] for r in rows if r["grupo"] == "garantia" and r["situacao"] == "presente")
    covenants = Counter(r["item"] for r in rows if r["grupo"] == "covenant")
    with_limit = Counter(r["item"] for r in rows if r["grupo"] == "covenant" and r["situacao"] == "com_limite")
    lines = ["# Garantias e covenants por ativo", "",
             f"Extrator `{EXTRACTOR}` sobre o texto do Termo de Securitização e dos aditamentos (`document_text_pages`). "
             "**Triagem, não parâmetro aprovado:** cada item traz documento, página e trecho literal para conferência; "
             "trecho de OCR precisa de conferência no PDF. Garantia *presente* = 2+ menções fora de frase negativa; "
             "*citada* = 1; *negada* = só em frase negativa.", "",
             f"Ativos com Termo ou aditamento lido: **{len(assets)}**.", "",
             "| Garantia | Ativos (presente) |", "|---|---|"]
    lines += [f"| {GUARANTEE_TYPES[k][0]} | {present.get(k, 0)} |" for k in GUARANTEE_TYPES]
    lines += ["", "| Covenant | Ativos (citado) | Com limite lido |", "|---|---|---|"]
    lines += [f"| {COVENANT_TYPES[k][0]} | {covenants.get(k, 0)} | {with_limit.get(k, 0)} |" for k in COVENANT_TYPES]
    lines += ["", "## Por ativo", "", "| Ativo | Tipo | Garantias presentes | Negadas | Covenants (limite) |", "|---|---|---|---|---|"]
    by_asset = defaultdict(list)
    for r in rows:
        by_asset[r["codigo_cetip"]].append(r)
    for cetip, kind in assets:
        items = by_asset.get(cetip, [])
        g = ", ".join(r["rotulo"] for r in items if r["grupo"] == "garantia" and r["situacao"] == "presente") or "—"
        n = ", ".join(r["rotulo"] for r in items if r["grupo"] == "garantia" and r["situacao"] == "negada") or "—"
        c = ", ".join(f"{r['rotulo']} {r['operador']} {r['limite']}{r['unidade']}".strip() for r in items
                      if r["grupo"] == "covenant") or "—"
        lines.append(f"| {cetip} | {kind} | {g} | {n} | {c} |")
    if not args.only:
        (ROOT / "reports" / "garantias_covenants.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        for r in rows:
            print(f"{r['grupo']:9} {r['item']:34} {r['situacao']:10} {r['operador']}{r['limite']}{r['unidade']} "
                  f"| doc {r['documento']} p{r['pagina']} | {r['trecho'][:160]}")
    print(f"{len(assets)} ativos, {len(rows)} itens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
