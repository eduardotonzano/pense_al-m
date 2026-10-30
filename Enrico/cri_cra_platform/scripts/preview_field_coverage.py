"""Prévia do localizador de campos nos Termos já baixados (só leitura; não grava no banco).

Lê o texto dos Termos/Aditamentos no banco (nativo; OCR quando o PDF é imagem; sem páginas no banco,
pdftotext em memória) e conta, por ativo, quantos dos
36 campos padrão têm ao menos uma página sugerida. Campo sem página pode não existir no Termo ou estar
com redação diferente: é ponto de leitura, não conclusão. PDF ainda sem texto vai para a lista de OCR.
Gera reports/field_coverage_preview.{md,csv}.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.contract_fields import load_catalog
from credit_assets.field_finder import hit_pages, load_topics
from credit_assets.services.contract_terms_service import document_pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    args = parser.parse_args()
    catalog = load_catalog(ROOT / "config" / "contract_terms" / "standard_fields.json")
    topics = load_topics(ROOT / "config" / "contract_terms" / "field_topics.json")
    field_ids = [f["id"] for f in catalog["fields"]]
    importance = {f["id"]: f["importance"] for f in catalog["fields"]}
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT a.codigo_cetip, a.tipo_ativo, d.source_document_id, d.category, d.document_name, v.version_id, v.local_file_path
           FROM document_versions v
           JOIN documents d ON d.document_pk = v.document_id
           JOIN assets a ON a.asset_id = d.asset_id
           WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
             AND d.category IN ('Termo de Securitização', 'Aditamento')
           ORDER BY a.codigo_cetip, d.source_document_id"""
    ).fetchall()

    per_asset: dict[str, dict] = {}
    needs_ocr: list[str] = []
    for row in rows:
        pages = document_pages(connection, row["version_id"], ROOT / row["local_file_path"])
        if not pages:
            continue
        numbered = [(number, text) for number, text, _ in pages]
        if not any(text.strip() for _, text in numbered):
            needs_ocr.append(f"{row['codigo_cetip']} {row['source_document_id']}")
            continue
        item = per_asset.setdefault(row["codigo_cetip"], {"tipo": row["tipo_ativo"], "docs": 0, "pages": 0, "hits": {}})
        item["docs"] += 1
        item["pages"] += len(numbered)
        for field in field_ids:
            hits = hit_pages(numbered, topics[field])
            if hits:
                item["hits"][field] = item["hits"].get(field, 0) + len(hits)

    connection.close()
    with (ROOT / "reports" / "field_coverage_preview.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["ativo", "tipo", "documentos", "paginas"] + field_ids)
        for cetip, item in per_asset.items():
            writer.writerow([cetip, item["tipo"], item["docs"], item["pages"]] + [item["hits"].get(f, 0) for f in field_ids])

    core = [f for f in field_ids if importance[f] == "core"]
    lines = ["# Prévia do localizador de campos nos Termos baixados", "",
             f"Só leitura. {len(per_asset)} ativos com Termo/Aditamento em texto; {len(needs_ocr)} PDFs sem texto (precisam de OCR).", "",
             "| Ativo | Tipo | Docs | Páginas | Campos com página (de 36) | Core com página (de "
             f"{len(core)}) | Core sem página |", "|---|---|---|---|---|---|---|"]
    for cetip, item in sorted(per_asset.items(), key=lambda kv: -len(kv[1]["hits"])):
        missing = [f.split(".", 1)[1] for f in core if f not in item["hits"]]
        lines.append(f"| {cetip} | {item['tipo']} | {item['docs']} | {item['pages']} | {len(item['hits'])} | "
                     f"{len(core) - len(missing)} | {', '.join(missing) or '-'} |")
    if per_asset:
        absent = {f: sum(1 for i in per_asset.values() if f not in i["hits"]) for f in field_ids}
        lines += ["", "Campos sem página no maior número de ativos (ponto de leitura; pode não se aplicar):", ""]
        lines += [f"- `{f}`: {n} de {len(per_asset)}" for f, n in sorted(absent.items(), key=lambda kv: -kv[1])[:10] if n]
    if needs_ocr:
        lines += ["", "PDFs sem texto (OCR): " + ", ".join(needs_ocr)]
    (ROOT / "reports" / "field_coverage_preview.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
