"""Mede quanto do que já foi aprovado o localizador de campos teria achado (só leitura).

Para cada parâmetro aprovado do Termo, procura a página do trecho que o sustentou entre as
páginas sugeridas para o campo padrão do parâmetro. Gera reports/finder_recall.{md,csv}.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.contract_fields import load_catalog, match_field
from credit_assets.field_finder import found, hit_pages, load_topics
from credit_assets.services.contract_terms_service import preferred_pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--tolerance", type=int, default=1)
    args = parser.parse_args()
    catalog = load_catalog(ROOT / "config" / "contract_terms" / "standard_fields.json")
    topics = load_topics(ROOT / "config" / "contract_terms" / "field_topics.json")
    missing_topics = [f["id"] for f in catalog["fields"] if f["id"] not in topics]
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT p.parameter_id, p.parameter_name, a.codigo_cetip, c.page_number, c.document_version_id
               FROM contract_parameters p
               JOIN contract_parameter_candidates c ON c.candidate_id = p.candidate_id
               JOIN assets a ON a.asset_id = p.asset_id
               WHERE p.review_status = 'approved' AND p.source_kind = 'termo'"""
        ).fetchall()
        pages_cache: dict[int, list[tuple[int, str]]] = {}
        hits_cache: dict[tuple[int, str], list[int]] = {}
        results = []
        for row in rows:
            fields = match_field(row["parameter_name"], catalog)
            if not fields:
                continue
            version = row["document_version_id"]
            if version not in pages_cache:
                pages_cache[version] = [(p["page_number"], p["text"]) for p in preferred_pages(connection, version)]
            for field_id in fields:
                key = (version, field_id)
                if key not in hits_cache:
                    hits_cache[key] = hit_pages(pages_cache[version], topics.get(field_id, []))
                hits = hits_cache[key]
                results.append({
                    "ativo": row["codigo_cetip"], "campo": field_id, "parametro": row["parameter_name"],
                    "pagina": row["page_number"], "achado": found(row["page_number"], hits, args.tolerance),
                    "paginas_sugeridas": len(hits), "paginas_do_termo": len(pages_cache[version]),
                })
    finally:
        connection.close()

    with (ROOT / "reports" / "finder_recall.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(results)

    by_field: dict[str, list[dict]] = defaultdict(list)
    by_asset: dict[str, list[dict]] = defaultdict(list)
    for item in results:
        by_field[item["campo"]].append(item)
        by_asset[item["ativo"]].append(item)
    rate = lambda items: f"{sum(i['achado'] for i in items)}/{len(items)} ({100 * sum(i['achado'] for i in items) / len(items):.0f}%)"
    lines = ["# Recall do localizador de campos", "",
             f"Parâmetros aprovados do Termo comparados com as páginas sugeridas por `field_topics.json` (tolerância de {args.tolerance} página). Só leitura.", "",
             f"**Geral:** {rate(results)}", "", "| Ativo | Achados |", "|---|---|"]
    lines += [f"| {a} | {rate(items)} |" for a, items in sorted(by_asset.items())]
    lines += ["", "| Campo | Achados | Páginas sugeridas (média) | Páginas do Termo (média) |", "|---|---|---|---|"]
    for field, items in sorted(by_field.items(), key=lambda kv: sum(i["achado"] for i in kv[1]) / len(kv[1])):
        avg = lambda key: sum(i[key] for i in items) / len(items)
        lines.append(f"| `{field}` | {rate(items)} | {avg('paginas_sugeridas'):.0f} | {avg('paginas_do_termo'):.0f} |")
    if missing_topics:
        lines += ["", "Campos sem padrão de busca: " + ", ".join(f"`{f}`" for f in missing_topics)]
    misses = [i for i in results if not i["achado"]]
    lines += ["", f"## Não achados ({len(misses)})", "", "| Ativo | Campo | Parâmetro | Página do trecho |", "|---|---|---|---|"]
    lines += [f"| {i['ativo']} | `{i['campo']}` | `{i['parametro']}` | {i['pagina']} |" for i in misses]
    (ROOT / "reports" / "finder_recall.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:24]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
