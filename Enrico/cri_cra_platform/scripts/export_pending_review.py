"""Gera uma página HTML local com tudo o que aguarda revisão humana.

Cada item mostra o valor proposto, o trecho literal e um link que abre o PDF
na página de origem. A página é só leitura: a decisão continua registrada
pelos scripts de revisão.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect

STYLE = """
:root { --bg:#fff; --fg:#1d1d1f; --muted:#666; --line:#ddd; --card:#f7f7f8; --accent:#0b57d0; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16171a; --fg:#e8e8ea; --muted:#a0a0a6; --line:#34353a; --card:#1f2024; --accent:#8ab4f8; }
}
body { background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; margin:0 auto; max-width:1100px; padding:16px; }
h1 { font-size:22px; } h2 { font-size:18px; margin-top:32px; }
p.muted, td.muted { color:var(--muted); }
table { border-collapse:collapse; width:100%; }
th, td { border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }
th { background:var(--card); position:sticky; top:0; }
td.excerpt { font-family:ui-monospace, monospace; font-size:13px; white-space:pre-wrap; }
a { color:var(--accent); }
code { background:var(--card); padding:1px 4px; border-radius:4px; }
"""


def pdf_link(local_path: str | None, page: int | None) -> str:
    if not local_path:
        return "arquivo não baixado"
    path = (ROOT / local_path).resolve()
    anchor = f"#page={page}" if page else ""
    label = f"abrir p.{page}" if page else "abrir"
    return f'<a href="{html.escape(path.as_uri() + anchor)}" target="_blank">{label}</a>'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    args = parser.parse_args()
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        facts = connection.execute(
            """SELECT f.fact_id, f.fact_name, f.reference_date, f.value, f.unit, f.excerpt, f.page_number,
                      d.source_document_id, d.document_name, d.publication_date, v.local_file_path
               FROM reported_facts f
               JOIN document_versions v ON v.version_id = f.document_version_id
               JOIN documents d ON d.document_pk = v.document_id
               JOIN assets a ON a.asset_id = f.asset_id
               WHERE a.codigo_cetip = ? AND f.review_status = 'pending'
               ORDER BY d.source_document_id, f.page_number, f.fact_id""",
            (args.cetip,),
        ).fetchall()
        parameters = connection.execute(
            """SELECT p.parameter_id, p.parameter_name, p.parameter_value, p.unit, p.applies_when,
                      p.valid_from, p.source_reference, c.excerpt, c.page_number, v.local_file_path
               FROM contract_parameters p
               JOIN contract_parameter_candidates c ON c.candidate_id = p.candidate_id
               JOIN document_versions v ON v.version_id = c.document_version_id
               JOIN assets a ON a.asset_id = p.asset_id
               WHERE a.codigo_cetip = ? AND p.review_status = 'pending'
               ORDER BY p.parameter_id""",
            (args.cetip,),
        ).fetchall()
    finally:
        connection.close()

    golden_items = []
    for golden_path in sorted((ROOT / "config" / "golden_sets").glob("*.json")):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        if golden["asset"]["codigo_cetip"] == args.cetip:
            golden_items += [item for item in golden["items"] if item["human_review_status"] == "pending"]

    e = lambda value: html.escape("" if value is None else str(value))
    parts = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Revisão pendente {e(args.cetip)}</title><style>{STYLE}</style></head><body>",
        f"<h1>Revisão pendente: {e(args.cetip)}</h1>",
        f"<p class='muted'>{len(facts)} fatos, {len(parameters)} parâmetros e "
        f"{len(golden_items)} itens de golden set aguardando revisão. "
        "Confira se o valor proposto corresponde ao trecho e responda no chat "
        "(ex.: <code>aprovo todos</code> ou <code>rejeito o fato 23</code>).</p>",
    ]
    if facts:
        parts.append("<h2>Fatos lidos dos documentos</h2><table><tr><th>#</th><th>Fato</th>"
                     "<th>Valor proposto</th><th>Trecho no documento</th><th>Documento</th></tr>")
        for f in facts:
            parts.append(
                f"<tr><td>{e(f['fact_id'])}</td>"
                f"<td>{e(f['fact_name'])}<br><span class='muted'>data-base {e(f['reference_date'])}</span></td>"
                f"<td><b>{e(f['value'])}</b><br><span class='muted'>{e(f['unit'])}</span></td>"
                f"<td class='excerpt'>{e(f['excerpt'])}</td>"
                f"<td>{e(f['document_name'])} {e(f['source_document_id'])}<br>"
                f"<span class='muted'>publicado {e(f['publication_date'])}</span><br>"
                f"{pdf_link(f['local_file_path'], f['page_number'])}</td></tr>"
            )
        parts.append("</table>")
    if parameters:
        parts.append("<h2>Parâmetros contratuais</h2><table><tr><th>#</th><th>Parâmetro</th>"
                     "<th>Valor proposto</th><th>Trecho no documento</th><th>Fonte</th></tr>")
        for p in parameters:
            parts.append(
                f"<tr><td>{e(p['parameter_id'])}</td>"
                f"<td>{e(p['parameter_name'])}<br><span class='muted'>{e(p['applies_when'])}</span></td>"
                f"<td><b>{e(p['parameter_value'])}</b><br><span class='muted'>{e(p['unit'])}; "
                f"vigente desde {e(p['valid_from'] or 'emissão')}</span></td>"
                f"<td class='excerpt'>{e(p['excerpt'])}</td>"
                f"<td>{e(p['source_reference'])}<br>{pdf_link(p['local_file_path'], p['page_number'])}</td></tr>"
            )
        parts.append("</table>")
    if golden_items:
        parts.append("<h2>Golden set (conferência do XML)</h2><table><tr><th>#</th><th>Campo</th>"
                     "<th>Literal no XML</th><th>Estado proposto</th><th>Pergunta / nota</th><th>Arquivo</th></tr>")
        for item in golden_items:
            observed = item.get("observed", {})
            literal = (f"linha {observed['line']}: {observed['evidence_excerpt']}"
                       if observed.get("element_present") else "elemento ausente no arquivo")
            question = f"<b>{e(item['decision_question'])}</b><br>" if item["decision_question"] else ""
            parts.append(
                f"<tr><td>{e(item['item_id'])}</td>"
                f"<td>{e(item['xml_path'].split('/', 2)[-1])}<br><span class='muted'>"
                f"{e(', '.join(item['case_types']))}</span></td>"
                f"<td class='excerpt'>{e(literal)}</td>"
                f"<td>{e(item['proposed_field_state'])}</td>"
                f"<td>{question}<span class='muted'>{e(item['notes'])}</span></td>"
                f"<td>doc {e(item['source_document_id'])}<br>{pdf_link(item.get('local_file_path'), None)}</td></tr>"
            )
        parts.append("</table>")
    if not facts and not parameters and not golden_items:
        parts.append("<p>Nada pendente.</p>")
    parts.append("</body></html>")
    path = ROOT / "reports" / f"{args.cetip.lower()}_revisao_pendente.html"
    path.write_text("\n".join(parts), encoding="utf-8")
    print({"facts": len(facts), "parameters": len(parameters), "golden_items": len(golden_items), "page": str(path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
