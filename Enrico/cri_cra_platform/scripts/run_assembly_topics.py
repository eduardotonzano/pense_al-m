"""Assuntos das atas, editais, fatos relevantes e comunicados baixados, por ativo (só leitura; não grava no banco).

Nas atas, também o que foi decidido (credit_assets.assembly_outcomes): aprovada, rejeitada, não instalada, suspensa,
sem quórum, e os eventos (vencimento antecipado declarado ou não, waiver, repactuação, troca de prestador...).
Lê o texto das páginas no banco (nativo; OCR quando o PDF é imagem; sem páginas no banco, pdftotext em memória), classifica por palavras-chave (credit_assets.assembly_topics) e monta a linha do
tempo dos assuntos relevantes de cada ativo. Gera reports/assembleias_topicos.{md,csv}. Triagem: aponta o que foi
discutido, não o que foi decidido. Documento lido por OCR vem marcado: o trecho pode ter erro de leitura.
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

from credit_assets.assembly_outcomes import decide
from credit_assets.assembly_topics import classify, relevant
from credit_assets.services.contract_terms_service import document_pages

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
                   d.reference_date, v.version_id, v.local_file_path
            FROM document_versions v JOIN documents d ON d.document_pk = v.document_id JOIN assets a ON a.asset_id = d.asset_id
            WHERE v.is_current = 1 AND v.validation_status = 'valid' AND lower(v.file_format) = 'pdf'
              AND d.category IN ({','.join('?' * len(CATEGORIES))})""", CATEGORIES).fetchall()

    def iso(value: str | None) -> str:
        text = (value or "").strip()
        if len(text) >= 10 and text[2] == "/":
            return f"{text[6:10]}-{text[3:5]}-{text[0:2]}"
        return text[:10]

    rows, per_asset, decided = [], defaultdict(list), defaultdict(list)
    skipped_image = read_by_ocr = 0
    for doc in docs:
        name = (doc["document_name"] or "").lower()
        # "Outro" mistura DFs, documentos de oferta e comunicados: só comunicados entram (o resto é texto padrão)
        if doc["category"] == "Outro" and (not ("comunicado" in name or "fato" in name or "assembleia" in name)
                                           or any(w in name for w in EXCLUDED_NAMES)):
            continue
        date = iso(doc["publication_date"]) or iso(doc["reference_date"])
        if date and date < args.since:
            continue
        pages = document_pages(connection, doc["version_id"], ROOT / doc["local_file_path"])
        if not pages:
            continue
        text = "\n".join(t for _, t, _ in pages)
        if not text.strip():
            skipped_image += 1
            continue
        ocr = any(o and t.strip() for _, t, o in pages)
        read_by_ocr += ocr
        hits, marks = classify(text)
        topics = relevant(hits)
        outcome = decide(text) if doc["category"] == "Ata/Edital" else None
        row = {"ativo": doc["codigo_cetip"], "tipo": doc["tipo_ativo"], "documento": doc["source_document_id"],
               "categoria": doc["category"], "nome": doc["document_name"], "data": date,
               "assuntos_relevantes": "; ".join(topics), "rotina": "; ".join(h.topic for h in hits if h.level == "rotina"),
               "ocr": int(ocr), "nao_instalada": int(marks["nao_instalada"]), "segunda_convocacao": int(marks["segunda_convocacao"]),
               "trecho": next((h.excerpt for h in hits if h.level == "relevante"), "")[:300],
               "documento_tipo": outcome.kind if outcome else "", "resultado": outcome.status if outcome else "",
               "decisoes": "; ".join(d.event for d in outcome.decisions) if outcome else "",
               "trecho_decisao": (outcome.decisions[0].excerpt[:400] if outcome and outcome.decisions else "")}
        rows.append(row)
        if topics:
            per_asset[doc["codigo_cetip"]].append(row)
        if outcome and outcome.kind == "ata":
            decided[doc["codigo_cetip"]].append(row)

    connection.close()
    with (ROOT / "reports" / "assembleias_topicos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["ativo"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    topic_count = Counter(t for r in rows for t in r["assuntos_relevantes"].split("; ") if t)
    lines = ["# Assuntos de atas, editais, fatos relevantes e comunicados", "",
             f"Documentos lidos desde {args.since}: {len(rows)}, {read_by_ocr} deles por OCR (PDFs ainda sem texto: {skipped_image}). Classificação por palavras-chave: "
             "o que foi discutido, não o que foi decidido.", "",
             "| Assunto relevante | Documentos |", "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in topic_count.most_common()]
    atas = [r for r in rows if r["documento_tipo"] == "ata"]
    status_count = Counter(r["resultado"] for r in atas)
    event_count = Counter(e for r in atas for e in r["decisoes"].split("; ") if e)
    lines += ["", "## O que as atas decidiram", "",
              f"{len(atas)} atas (o resto são editais e comunicados). Regras de texto sobre a parte da decisão, depois da ordem do "
              "dia: candidatos para leitura, não conclusões.", "", "| Resultado | Atas |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {n} |" for k, n in status_count.most_common()]
    lines += ["", "| Decisão | Atas |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {n} |" for k, n in event_count.most_common() if k != "nao_instalada"]
    lines += ["", "### Decisões de crédito por ativo (mais recentes primeiro)", "",
              "| Ativo | Data | Ata | Resultado | Decisões | Trecho |", "|---|---|---|---|---|---|"]
    credit = ("vencimento_antecipado", "waiver", "prorrogacao", "liquidacao", "dacao", "resgate", "garantias", "troca_prestador",
              "nao_declaracao", "assembleia_suspensa", "sem_quorum", "ordem_do_dia", "recuperacao_judicial", "aporte_titulares",
              "assessor_legal", "uso_fundo_reserva", "titulares_se_abstiveram")
    for asset, items in sorted(decided.items()):
        for r in sorted(items, key=lambda r: r["data"], reverse=True):
            if any(r["decisoes"].startswith(c) or f"; {c}" in r["decisoes"] for c in credit):
                lines.append(f"| {asset} | {r['data']} | {r['documento']} | {r['resultado'].replace('_', ' ')} | "
                             f"{r['decisoes'].replace('_', ' ')} | {r['trecho_decisao'][:180].replace('|', '/')} |")
    recovery = [r for r in atas if "recuperacao_judicial" in r["decisoes"]]
    lines += ["", "## Recuperação judicial ou extrajudicial nas decisões das atas", "",
              "Atas em que a decisão trata de recuperação judicial ou extrajudicial (plano, habilitação ou individualização de crédito, "
              "assessor para o processo). Sinal de devedor em recuperação: confirmar na ata e no processo.", "",
              "| Ativo | Atas | Última | Decisões da última | Trecho |", "|---|---|---|---|---|"]
    by_asset: dict[str, list] = defaultdict(list)
    for r in recovery:
        by_asset[r["ativo"]].append(r)
    for asset, items in sorted(by_asset.items(), key=lambda kv: max(r["data"] for r in kv[1]), reverse=True):
        last = max(items, key=lambda r: r["data"])
        lines.append(f"| {asset} | {len(items)} | {last['data']} | {last['decisoes'].replace('_', ' ')} | "
                     f"{last['trecho_decisao'][:200].replace('|', '/')} |")
    lines += ["", "## Ativos com mais assuntos relevantes", "", "| Ativo | Documentos relevantes | Assuntos |", "|---|---|---|"]
    for asset, items in sorted(per_asset.items(), key=lambda kv: -len(kv[1])):
        topics = Counter(t for r in items for t in r["assuntos_relevantes"].split("; ") if t)
        lines.append(f"| {asset} | {len(items)} | {', '.join(f'{t}×{n}' for t, n in topics.most_common())} |")
    lines += ["", "## Linha do tempo (assuntos relevantes)", ""]
    for asset, items in sorted(per_asset.items()):
        lines += [f"### {asset}", "", "| Data | Documento | Assuntos | Resultado da ata | Marcas | Trecho |", "|---|---|---|---|---|---|"]
        for r in sorted(items, key=lambda r: r["data"]):
            marks = ", ".join(m for m, flag in (("não instalada", r["nao_instalada"]), ("2ª convocação", r["segunda_convocacao"]), ("lido por OCR", r["ocr"])) if flag)
            lines.append(f"| {r['data']} | {r['categoria']} {r['documento']} | {r['assuntos_relevantes']} | "
                         f"{r['resultado'].replace('_', ' ') if r['documento_tipo'] == 'ata' else ''} | {marks} | "
                         f"{r['trecho'][:160].replace('|', '/')} |")
        lines.append("")
    (ROOT / "reports" / "assembleias_topicos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:45]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
