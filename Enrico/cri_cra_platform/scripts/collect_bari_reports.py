"""Relatório de gestão da Bari Securitizadora: baixa o mais recente (até 180 dias) de cada série viva e lê índices e
fundos (índice de cobertura, de garantia, ICSD, ICM/ITO, fundos de reserva e de despesas: exigido × apurado ×
Enquadrado/Desenquadrado) e a posição de cobrança da carteira por faixa de atraso.

    python scripts/collect_bari_reports.py --dry-run                # quantas séries, quais do nosso universo
    python scripts/collect_bari_reports.py --commit [--only 24L1252219] [--limit 20]
    python scripts/collect_bari_reports.py --parse-only             # relê os PDFs já baixados

Não grava no banco. PDFs em data/documents/bari/<emissão>/<AAAA-MM>_<documento>.pdf (já baixado não baixa de novo);
proveniência (URL, SHA-256, data) em data/bari/manifest.csv, uma linha por série e relatório; saída em
reports/bari_monitoramentos.{csv,md}, uma linha por item e por série (código CETIP e ISIN de cada série).
Cada série usa o relatório publicado na própria página; série sem relatório recente usa o mais recente da mesma
emissão (o patrimônio separado é da emissão), menos na 1ª emissão, em que cada série é uma operação independente.
Site da securitizadora é a fonte de menor prioridade (regra 3): complementa, nunca sobrescreve CVM nem Termo.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.bari_monthly_report import PARSER, as_rows, competencia_label, parse_report
from credit_assets.bari_portal import BariPortal, competencia, file_url, is_live, management_reports

DOCS = ROOT / "data" / "documents" / "bari"
MANIFEST = ROOT / "data" / "bari" / "manifest.csv"
MANIFEST_FIELDS = ["codigo_cetip", "isin", "emissao", "serie", "origem", "competencia", "document_id", "titulo",
                   "data_documento", "arquivo", "sha256", "url", "obtido_em"]
OUT_FIELDS = ["codigo_opea", "codigo_cetip", "isin", "devedor", "status_opea", "no_universo", "competencia",
              "cetip_no_relatorio", "saldo_devedor", "grupo_tipo", "grupo", "item", "valor_referencia",
              "condicao_referencia", "valor_apurado", "condicao_apurada", "situacao", "data_verificacao",
              "proxima_verificacao", "pagina", "arquivo", "sha256", "parser"]
INDEPENDENT_SERIES = {1}  # 1ª emissão: cada série é uma operação com relatório próprio


def universe() -> set[str]:
    codes = set()
    with (ROOT / "config" / "ativos_mercado.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            codes |= {row["codigo_cetip"].upper(), row["isin"].upper()}
    try:
        import sqlite3
        connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True, timeout=120)
        for cetip, isin in connection.execute("SELECT codigo_cetip, isin FROM assets"):
            codes |= {str(cetip or "").upper(), str(isin or "").upper()}
        connection.close()
    except Exception:
        pass
    return codes - {"", "-"}


def codes_of(series: dict) -> set[str]:
    return {str(series.get("code") or "").upper(), str(series.get("ISIN") or "").upper()} - {"", "-"}


def load_manifest() -> dict[tuple[str, str], dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8") as handle:
        return {(row["codigo_cetip"], row["arquivo"]): row for row in csv.DictReader(handle)}


def save_manifest(rows: dict[tuple[str, str], dict]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: (int(r["emissao"]), int(r["serie"]), r["competencia"])))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--parse-only", action="store_true")
    parser.add_argument("--only", action="append", help="código CETIP, ISIN ou número da emissão")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-age-days", type=int, default=180)
    parser.add_argument("--min-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()

    portal = BariPortal(min_interval_seconds=args.min_interval_seconds)
    ours = universe()
    catalog = portal.emissions()
    series = [s for s in catalog if is_live(s)]
    if args.only:
        wanted = {code.upper() for code in args.only}
        series = [s for s in series if (codes_of(s) | {str(s.get("emissionNumber"))}) & wanted]
    series.sort(key=lambda s: (not (codes_of(s) & ours), int(s.get("emissionNumber") or 0), int(s.get("serieNumber") or 0)))
    if args.limit:
        series = series[: args.limit]
    in_universe = sum(1 for s in series if codes_of(s) & ours)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "series_no_catalogo": len(catalog), "series_vivas": len(series),
                          "emissoes_vivas": len({s.get("emissionNumber") for s in series}), "no_nosso_universo": in_universe,
                          "por_situacao_no_catalogo": Counter(str(s.get("emissionStatus")) for s in catalog)},
                         ensure_ascii=False, indent=2))
        return 0

    manifest = load_manifest()
    stats = Counter()
    if args.commit:
        own: dict[str, list[dict]] = {}
        for number, item in enumerate(series, start=1):
            try:
                page = portal.series_page(item["code"])
            except Exception as error:  # rede ou site: segue para a próxima série
                stats["erro_pagina"] += 1
                print(f"{item['code']}: erro na página ({type(error).__name__})", file=sys.stderr)
                continue
            own[item["code"]] = management_reports(page.get("emissionCrisDocuments") or [], max_age_days=args.max_age_days)
            if number % 25 == 0:
                print(f"páginas {number}/{len(series)}", file=sys.stderr)
        by_emission = defaultdict(list)
        for item in series:
            by_emission[item.get("emissionNumber")].append(item)
        downloaded: dict[str, tuple[str, str, str, str]] = {}  # url -> (arquivo, sha256, obtido_em, competência)
        for item in series:
            code, emission = item["code"], int(item.get("emissionNumber") or 0)
            origin = "propria"
            reports = own.get(code)
            if reports is None:
                continue
            if not reports and emission not in INDEPENDENT_SERIES:
                siblings = [(own[s["code"]][0], s) for s in by_emission[item.get("emissionNumber")]
                            if s["code"] != code and own.get(s["code"])]
                if siblings:
                    doc, sibling = max(siblings, key=lambda ds: (competencia(ds[0]), str(ds[0].get("date") or "")))
                    reports, origin = [doc], f"emissao (serie {sibling.get('serieNumber')})"
            if not reports:
                stats["sem_relatorio_recente"] += 1
                continue
            doc = reports[0]
            url, month = file_url(doc), competencia(doc)
            if url in downloaded:
                relative, sha, fetched, _ = downloaded[url]
            else:
                target = DOCS / str(emission) / f"{month}_{doc['id']}.pdf"
                relative = str(target.relative_to(ROOT)).replace("\\", "/")
                previous = next((r for r in manifest.values() if r["arquivo"] == relative), None)
                if previous and target.exists():
                    sha, fetched = previous["sha256"], previous["obtido_em"]
                    stats["ja_baixado"] += 1
                else:
                    try:
                        download = portal.download(url)
                    except Exception as error:
                        stats["erro_download"] += 1
                        print(f"{code}: erro no download ({type(error).__name__})", file=sys.stderr)
                        continue
                    if not download.content.startswith(b"%PDF"):
                        stats["nao_pdf"] += 1
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(download.content)
                    sha, fetched = download.sha256, download.fetched_at
                    stats["baixado"] += 1
                downloaded[url] = (relative, sha, fetched, month)
            manifest[(code, relative)] = {
                "codigo_cetip": code, "isin": "" if item.get("ISIN") in (None, "-") else item["ISIN"],
                "emissao": emission, "serie": item.get("serieNumber") or 0, "origem": origin, "competencia": month,
                "document_id": doc.get("id"), "titulo": str(doc.get("documentName") or "").strip(),
                "data_documento": doc.get("date") or "", "arquivo": relative, "sha256": sha, "url": url,
                "obtido_em": fetched}
            stats["series_com_relatorio"] += 1
        save_manifest(manifest)

    # leitura: o relatório mais recente de cada série no manifesto
    live = {s["code"]: s for s in series}
    latest: dict[str, dict] = {}
    for row in manifest.values():
        code = row["codigo_cetip"]
        if code not in latest or (row["competencia"], row["data_documento"]) > (latest[code]["competencia"], latest[code]["data_documento"]):
            latest[code] = row
    out_rows, failures, parsed = [], [], {}
    for code, row in sorted(latest.items(), key=lambda kv: (int(kv[1]["emissao"]), int(kv[1]["serie"]))):
        if code not in live:
            continue  # fora do filtro (--only/--limit) ou não está mais viva
        item = live[code]
        if row["arquivo"] not in parsed:
            try:
                parsed[row["arquivo"]] = parse_report(ROOT / row["arquivo"])
            except Exception as error:
                parsed[row["arquivo"]] = None
                failures.append(f"E{row['emissao']} S{row['serie']} {code} ({row['arquivo']}): {type(error).__name__}: {error}")
        report = parsed[row["arquivo"]]
        if report is None:
            continue
        if not report.competencia:
            report = replace(report, competencia=competencia_label(row["competencia"]))
        base = {"codigo_opea": row["emissao"], "codigo_cetip": code, "isin": row["isin"],
                "devedor": str(item.get("ballastNature") or "").strip(),
                "status_opea": item.get("emissionStatus") or "",
                "no_universo": "sim" if codes_of(item) & ours else "nao",
                "arquivo": row["arquivo"], "sha256": row["sha256"],
                "_serie": row["serie"], "_origem": row["origem"], "_titulo": row["titulo"], "_modelo": report.modelo}
        out_rows.extend(as_rows(base, report))
    write_outputs(out_rows, failures, len(series))
    print(json.dumps({"coleta": dict(stats), "series_lidas": len({r['codigo_cetip'] for r in out_rows}),
                      "relatorios_lidos": len({r['arquivo'] for r in out_rows}), "linhas": len(out_rows),
                      "relatorios_sem_item": len({r['arquivo'] for r in out_rows if r['item'] == '(sem monitoramentos)'}),
                      "falhas_de_leitura": len(failures)}, ensure_ascii=False, indent=2))
    return 0


def _cell(text: str) -> str:
    return str(text).replace("|", "/")


def write_outputs(rows: list[dict], failures: list[str], live_series: int) -> None:
    with (ROOT / "reports" / "bari_monitoramentos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    # contagens por item do relatório (o CSV repete o item em cada série que usa o relatório)
    by_report = defaultdict(list)
    for r in rows:
        by_report[r["arquivo"]].append(r)
    items = {(r["arquivo"], r["grupo"], r["item"]): r for r in rows if r["item"] != "(sem monitoramentos)"}
    situations = Counter(r["situacao"] or "sem_situacao" for r in items.values())
    kinds = Counter(r["grupo_tipo"] for r in items.values())
    models = Counter(rs[0]["_modelo"] for rs in by_report.values())
    empty = sorted(a for a, rs in by_report.items() if all(r["item"] == "(sem monitoramentos)" for r in rs))
    series_of = defaultdict(list)
    for r in rows:
        if f"S{r['_serie']} {r['codigo_cetip']}" not in series_of[r["arquivo"]]:
            series_of[r["arquivo"]].append(f"S{r['_serie']} {r['codigo_cetip']}")
    universe_of = {a: any(r["no_universo"] == "sim" for r in rs) for a, rs in by_report.items()}
    inherited = sorted({(r["codigo_opea"], r["_serie"], r["codigo_cetip"], r["_origem"]) for r in rows
                        if r["_origem"] != "propria"}, key=lambda t: (int(t[0]), int(t[1])))
    failing = defaultdict(list)
    for key, r in items.items():
        if r["situacao"] == "nao_atendido":
            failing[key[0]].append(r)
    lines = [
        "# Monitoramentos da Bari (Relatório de Gestão / Acompanhamento do CRI)", "",
        "Fonte: portal de emissões da Bari Securitizadora (Strapi e páginas Next.js públicas), relatório de gestão mais "
        f"recente (até 180 dias) de cada série viva; leitor `{PARSER}`. Site da securitizadora é a fonte de menor "
        "prioridade: complementa, não substitui CVM nem Termo. Os valores são copiados do relatório; a situação "
        "(Enquadrado = atendido, Desenquadrado = não atendido) é a que a Bari informa. Quando o relatório traz mínimo e "
        "apurado sem situação, a situação fica vazia (não é deduzida). O CSV tem uma linha por item e por série; as "
        "contagens abaixo são por item do relatório.", "",
        f"Séries vivas no catálogo: **{live_series}**; séries com relatório lido: **{len({r['codigo_cetip'] for r in rows})}**; "
        f"relatórios lidos: **{len(by_report)}** (sem nenhum item lido: {len(empty)}); itens: **{sum(situations.values())}**.", "",
        "| Situação informada | Itens |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in situations.most_common()], "",
        "| Tipo de item | Itens |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in kinds.most_common()], "",
        "| Modelo de relatório | Relatórios |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in models.most_common()], "",
        f"## Itens não atendidos ({sum(len(v) for v in failing.values())} em {len(failing)} relatórios)", "",
        "| Emissão | Séries | Lastro | Universo | Competência | Item não atendido | Exigido | Apurado | Situação |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arquivo, its in sorted(failing.items(), key=lambda kv: (not universe_of[kv[0]], int(kv[1][0]["codigo_opea"]))):
        for r in its:
            lines.append(f"| {r['codigo_opea']} | {', '.join(series_of[arquivo])} | {_cell(r['devedor'])} | "
                         f"{'sim' if universe_of[arquivo] else 'nao'} | {r['competencia']} | {_cell(r['grupo'])}: "
                         f"{_cell(r['item'])} | {_cell(r['valor_referencia'])} {r['condicao_referencia']} | "
                         f"{_cell(r['valor_apurado'])} | {_cell(r['condicao_apurada'])} |")
    attention = [r for r in items.values() if r["grupo_tipo"] in ("Índice", "Fundo") and not r["situacao"]
                 and r["valor_referencia"] and r["valor_apurado"]]
    lines += ["", f"## Itens com exigido e apurado mas sem situação informada ({len(attention)})", "",
              "A Bari não informa a situação; ela não é deduzida aqui (comparar com o Termo).", "",
              "| Emissão | Séries | Competência | Item | Exigido | Apurado |", "|---|---|---|---|---|---|"]
    for r in sorted(attention, key=lambda r: (int(r["codigo_opea"]), r["arquivo"])):
        lines.append(f"| {r['codigo_opea']} | {', '.join(series_of[r['arquivo']])} | {r['competencia']} | "
                     f"{_cell(r['grupo'])}: {_cell(r['item'])} | {_cell(r['valor_referencia'])} {r['condicao_referencia']} | "
                     f"{_cell(r['valor_apurado'])} |")
    lines += ["", f"## Relatórios sem item lido ({len(empty)})", "",
              "Relatório baixado e aberto, mas sem índice, fundo nem posição de cobrança reconhecidos (em geral só saldos e "
              "pagamentos das séries).", "", "| Emissão | Séries | Competência | Título | Arquivo |", "|---|---|---|---|---|"]
    for arquivo in sorted(empty, key=lambda a: int(by_report[a][0]["codigo_opea"])):
        r = by_report[arquivo][0]
        lines.append(f"| {r['codigo_opea']} | {', '.join(series_of[arquivo])} | {r['competencia']} | {_cell(r['_titulo'])} | {arquivo} |")
    other_code = sorted({(r["codigo_opea"], r["_serie"], r["codigo_cetip"], r["cetip_no_relatorio"], r["arquivo"]) for r in rows
                         if r["cetip_no_relatorio"] and r["_origem"] == "propria"
                         and r["cetip_no_relatorio"] != r["codigo_cetip"]}, key=lambda t: (int(t[0]), int(t[1])))
    if other_code:
        lines += ["", f"## Código IF no relatório diferente do catálogo da Bari ({len(other_code)})", "",
                  "Provável cópia de modelo no relatório (ou série com mais de um código); os itens seguem atribuídos à série "
                  "da página onde o relatório foi publicado.", "",
                  *[f"- E{e} S{s} {c}: o relatório traz {o} ({a})" for e, s, c, o, a in other_code]]
    if inherited:
        lines += ["", f"## Séries sem relatório próprio que usam o da emissão ({len(inherited)})", "",
                  *[f"- E{e} S{s} {c}: {o}" for e, s, c, o in inherited]]
    if failures:
        lines += ["", f"## Falhas de leitura ({len(failures)})", "", *[f"- {f}" for f in failures]]
    (ROOT / "reports" / "bari_monitoramentos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
