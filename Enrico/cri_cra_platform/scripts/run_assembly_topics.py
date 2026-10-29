"""Assuntos das atas, editais, fatos relevantes e comunicados baixados, por ativo (só leitura; não grava no banco).

Lê os PDFs em memória (pdftotext), classifica por palavras-chave (credit_assets.assembly_topics) e monta a linha do
tempo dos assuntos relevantes de cada ativo. Gera reports/assembleias_topicos.{md,csv}. Triagem: aponta o que foi
discutido, não o que foi decidido.
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

from credit_assets.assembly_topics import classify, relevant
from credit_assets.services.contract_terms_service import extract_pdf_pages

CATEGORIES = ("Ata/Edital", "Fato Relevante", "Outro")
EXCLUDED_NAMES = ("demonstra", "lâmina", "lamina", "anúncio de início", "anuncio de inicio", "aviso ao mercado", "prospecto",
                  "relatório", "relatorio", "termo de securitiza")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--since", default="2024-01-01", help="só documentos publicados a partir desta data (AAAA-MM-DD)")
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    docs = connection.execute(
        f"""SELECT a.codigo_cetip, a.tipo_ativo, d.source_document_id, d.category, d.document_name, d.publication_date,
                   d.reference_date, v.local_file_path
            FROM document_versions v JOIN documents d ON d.document_pk = v.document_id JOIN assets a ON a.asset_id = d.asset_id
            WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
              AND d.category IN ({','.join('?' * len(CATEGORIES))})""", CATEGORIES).fetchall()
    connection.close()

    def iso(value: str | None) -> str:
        text = (value or "").strip()
        if len(text) >= 10 and text[2] == "/":
            return f"{text[6:10]}-{text[3:5]}-{text[0:2]}"
        return text[:10]

    rows, per_asset = [], defaultdict(list)
    skipped_image = 0
    for doc in docs:
        name = (doc["document_name"] or "").lower()
        # "Outro" mistura DFs, documentos de oferta e comunicados: só comunicados entram (o resto é texto padrão)
        if doc["category"] == "Outro" and (not ("comunicado" in name or "fato" in name or "assembleia" in name)
                                           or any(w in name for w in EXCLUDED_NAMES)):
            continue
        date = iso(doc["publication_date"]) or iso(doc["reference_date"])
        if date and date < args.since:
            continue
        path = ROOT / doc["local_file_path"]
        if not path.is_file():
            continue
        pages, _ = extract_pdf_pages(path)
        text = "\n".join(pages)
        if not text.strip():
            skipped_image += 1
            continue
        hits, marks = classify(text)
        topics = relevant(hits)
        row = {"ativo": doc["codigo_cetip"], "tipo": doc["tipo_ativo"], "documento": doc["source_document_id"],
               "categoria": doc["category"], "nome": doc["document_name"], "data": date,
               "assuntos_relevantes": "; ".join(topics), "rotina": "; ".join(h.topic for h in hits if h.level == "rotina"),
               "nao_instalada": int(marks["nao_instalada"]), "segunda_convocacao": int(marks["segunda_convocacao"]),
               "trecho": next((h.excerpt for h in hits if h.level == "relevante"), "")[:300]}
        rows.append(row)
        if topics:
            per_asset[doc["codigo_cetip"]].append(row)

    with (ROOT / "reports" / "assembleias_topicos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["ativo"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    topic_count = Counter(t for r in rows for t in r["assuntos_relevantes"].split("; ") if t)
    lines = ["# Assuntos de atas, editais, fatos relevantes e comunicados", "",
             f"Documentos lidos desde {args.since}: {len(rows)} (PDFs em imagem pulados: {skipped_image}). Classificação por palavras-chave: "
             "o que foi discutido, não o que foi decidido.", "",
             "| Assunto relevante | Documentos |", "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in topic_count.most_common()]
    lines += ["", "## Ativos com mais assuntos relevantes", "", "| Ativo | Documentos relevantes | Assuntos |", "|---|---|---|"]
    for asset, items in sorted(per_asset.items(), key=lambda kv: -len(kv[1])):
        topics = Counter(t for r in items for t in r["assuntos_relevantes"].split("; ") if t)
        lines.append(f"| {asset} | {len(items)} | {', '.join(f'{t}×{n}' for t, n in topics.most_common())} |")
    lines += ["", "## Linha do tempo (assuntos relevantes)", ""]
    for asset, items in sorted(per_asset.items()):
        lines += [f"### {asset}", "", "| Data | Documento | Assuntos | Marcas | Trecho |", "|---|---|---|---|---|"]
        for r in sorted(items, key=lambda r: r["data"]):
            marks = ", ".join(m for m, flag in (("não instalada", r["nao_instalada"]), ("2ª convocação", r["segunda_convocacao"])) if flag)
            lines.append(f"| {r['data']} | {r['categoria']} {r['documento']} | {r['assuntos_relevantes']} | {marks} | "
                         f"{r['trecho'][:160].replace('|', '/')} |")
        lines.append("")
    (ROOT / "reports" / "assembleias_topicos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:45]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
