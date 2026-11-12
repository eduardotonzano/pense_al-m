"""Relatório Mensal (Relatório investidor) da Canal Securitizadora: baixa o mais recente (até 365 dias) de cada série
viva e lê o quadro de garantias (fundos e índices como ILG e LTV: exigido × apurado × Enquadrado/Desenquadrado).

    python scripts/collect_canal_reports.py --dry-run                # quantas séries e emissões, quais do nosso universo
    python scripts/collect_canal_reports.py --commit [--only 24J2139130] [--only 121] [--limit 20]
    python scripts/collect_canal_reports.py --parse-only             # relê os PDFs já baixados (sem rede)

Não grava no banco. PDFs em data/documents/canal/<emissão>/<AAAA-MM>_<upload>.pdf (já baixado não baixa de novo;
séries da mesma emissão com o mesmo arquivo baixam uma vez); proveniência (URL, SHA-256, data) em
data/canal/manifest.csv; o catálogo com a competência mais recente publicada de cada série em data/canal/series.csv
(a publicação atrasa meses: a defasagem vai para o .md); saída em reports/canal_monitoramentos.{csv,md}, uma linha
por item e por série. Site da securitizadora é a fonte de menor prioridade (regra 3): complementa, nunca sobrescreve
CVM nem Termo.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.canal_monthly_report import PARSER, as_rows, competencia_label, parse_report, with_competencia
from credit_assets.canal_portal import CanalPortal, is_live, monthly_reports

DOCS = ROOT / "data" / "documents" / "canal"
MANIFEST = ROOT / "data" / "canal" / "manifest.csv"
SERIES = ROOT / "data" / "canal" / "series.csv"
MANIFEST_FIELDS = ["emissao", "categoria", "devedor", "codigos_cetip", "competencia", "document_id", "titulo",
                   "arquivo", "sha256", "url", "obtido_em"]
SERIES_FIELDS = ["codigo_cetip", "emissao", "serie", "categoria", "devedor", "lastro", "data_emissao", "data_vencimento",
                 "relatorios_mensais", "competencia_mais_recente", "documento_mais_recente", "verificado_em"]
OUT_FIELDS = ["codigo_opea", "codigo_cetip", "isin", "devedor", "status_opea", "no_universo", "competencia",
              "cetip_no_relatorio", "saldo_devedor", "grupo_tipo", "grupo", "item", "valor_referencia",
              "condicao_referencia", "valor_apurado", "condicao_apurada", "situacao", "data_verificacao",
              "proxima_verificacao", "pagina", "arquivo", "sha256", "parser"]
EXCLUDED = ("OTS",)


def universe() -> set[str]:
    codes = set()
    with (ROOT / "config" / "ativos_mercado.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            codes |= {row["codigo_cetip"].upper(), row["isin"].upper()}
    try:
        import sqlite3
        connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True)
        for cetip, isin in connection.execute("SELECT codigo_cetip, isin FROM assets"):
            codes |= {str(cetip or "").upper(), str(isin or "").upper()}
        connection.close()
    except Exception:
        pass
    return codes - {""}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def save_manifest(rows: dict[str, dict]) -> None:
    _write(MANIFEST, MANIFEST_FIELDS, sorted(rows.values(), key=lambda r: (_number(r["emissao"]), r["competencia"])))


def _number(text: str) -> int:
    match = re.match(r"\d+", str(text or ""))
    return int(match.group()) if match else 10**6


def months_behind(competencia: str, today: date) -> int | None:
    """Meses entre a competência ("AAAA-MM") e o mês de hoje."""

    if not re.fullmatch(r"\d{4}-\d{2}", competencia or ""):
        return None
    return (today.year - int(competencia[:4])) * 12 + today.month - int(competencia[5:])


def label(competencia: str) -> str:
    return competencia_label(int(competencia[:4]), int(competencia[5:])) if re.fullmatch(r"\d{4}-\d{2}", competencia or "") else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--parse-only", action="store_true")
    parser.add_argument("--only", action="append", help="código CETIP ou número da emissão")
    parser.add_argument("--limit", type=int, help="número máximo de emissões")
    parser.add_argument("--max-age-days", type=int, default=365)
    parser.add_argument("--min-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()

    today = date.today()
    ours = universe()
    portal = CanalPortal(min_interval_seconds=args.min_interval_seconds)
    if args.parse_only:
        series = [s for s in _read(SERIES)]
    else:
        series = [s for s in portal.catalog() if is_live(s, today)]
    # OTS (outros títulos de securitização) têm numeração própria de emissão e ficam fora do escopo CRI/CRA
    excluded = Counter(s.get("categoria") for s in series if str(s.get("categoria") or "").upper() in EXCLUDED)
    series = [s for s in series if str(s.get("categoria") or "").upper() not in EXCLUDED]
    if args.only:
        wanted = {code.upper() for code in args.only}
        series = [s for s in series if {s["codigo_cetip"].upper(), str(s.get("emissao") or "")} & wanted]
    by_emission: dict[str, list[dict]] = defaultdict(list)
    for s in series:
        by_emission[str(s.get("emissao") or s["codigo_cetip"])].append(s)
    order = sorted(by_emission, key=lambda e: (not any(s["codigo_cetip"].upper() in ours for s in by_emission[e]),
                                               _number(e), e))
    if args.limit:
        order = order[: args.limit]
    selected = {e: by_emission[e] for e in order}
    in_universe = [s for e in selected for s in selected[e] if s["codigo_cetip"].upper() in ours]
    if args.dry_run:
        print(json.dumps({"dry_run": True, "series_vivas": sum(len(v) for v in selected.values()),
                          "emissoes": len(selected), "series_no_nosso_universo": len(in_universe),
                          "fora_do_escopo": dict(excluded),
                          "por_categoria": Counter(s.get("categoria") or "" for v in selected.values() for s in v),
                          "emissao_com_categorias_diferentes": [e for e, v in selected.items()
                                                                if len({s.get("categoria") for s in v}) > 1]},
                         ensure_ascii=False, indent=2))
        return 0

    manifest = {row["arquivo"]: row for row in _read(MANIFEST)}
    stats = Counter()
    if args.commit:
        checked = {row["codigo_cetip"]: row for row in _read(SERIES)}
        for number, emission in enumerate(order, start=1):
            downloaded: dict[tuple[str, str], str] = {}  # (competência, nome do arquivo) → arquivo já salvo
            for s in selected[emission]:
                cetip = s["codigo_cetip"]
                try:
                    documents = portal.reports(cetip)
                except Exception as error:  # rede ou site: segue para a próxima série
                    stats["erro_relatorios"] += 1
                    print(f"{cetip}: erro na lista de relatórios ({type(error).__name__})", file=sys.stderr)
                    continue
                every = monthly_reports(documents, today, max_age_days=10**6)
                checked[cetip] = {**s, "relatorios_mensais": len(every),
                                  "competencia_mais_recente": every[0]["competencia"] if every else "",
                                  "documento_mais_recente": every[0]["document_id"] if every else "",
                                  "verificado_em": datetime.now(timezone.utc).isoformat()}
                recent = monthly_reports(documents, today, max_age_days=args.max_age_days)
                if not recent:
                    stats["sem_relatorio_recente" if every else "sem_relatorio"] += 1
                    continue
                doc = recent[0]
                key = (doc["competencia"], urllib.parse.unquote(doc["url"].rsplit("/", 1)[-1]))
                target = DOCS / emission / f"{doc['competencia']}_{doc['document_id']}.pdf"
                relative = downloaded.get(key) or str(target.relative_to(ROOT)).replace("\\", "/")
                if relative in manifest and (ROOT / relative).exists():
                    codes = manifest[relative]["codigos_cetip"].split()
                    if cetip not in codes:
                        manifest[relative]["codigos_cetip"] = " ".join(codes + [cetip])
                    stats["mesmo_pdf_de_outra_serie" if key in downloaded else "ja_baixado"] += 1
                    downloaded[key] = relative
                    continue
                try:
                    download = portal.download(doc)
                except Exception as error:
                    stats["erro_download"] += 1
                    print(f"{cetip}: erro no download ({type(error).__name__})", file=sys.stderr)
                    continue
                if not download.content.startswith(b"%PDF"):
                    stats["nao_pdf"] += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(download.content)
                manifest[relative] = {
                    "emissao": emission, "categoria": s.get("categoria") or "", "devedor": s.get("devedor") or "",
                    "codigos_cetip": cetip, "competencia": doc["competencia"], "document_id": doc["document_id"],
                    "titulo": doc["titulo"], "arquivo": relative, "sha256": download.sha256, "url": download.url,
                    "obtido_em": download.fetched_at}
                downloaded[key] = relative
                stats["baixado"] += 1
            if number % 10 == 0:
                save_manifest(manifest)
                _write(SERIES, SERIES_FIELDS, sorted(checked.values(), key=lambda r: (_number(r["emissao"]), r["codigo_cetip"])))
                print(f"{number}/{len(order)} {dict(stats)}", file=sys.stderr)
        save_manifest(manifest)
        _write(SERIES, SERIES_FIELDS, sorted(checked.values(), key=lambda r: (_number(r["emissao"]), r["codigo_cetip"])))
        status = {row["codigo_cetip"]: row for row in checked.values()}
        selected = {e: [status.get(s["codigo_cetip"], s) for s in v] for e, v in selected.items()}

    # leitura: para cada série, o relatório mais recente do manifesto que a inclui (um PDF lido uma vez)
    latest: dict[str, dict] = {}
    for row in manifest.values():
        for cetip in row["codigos_cetip"].split():
            if cetip not in latest or (row["competencia"], _number(row["document_id"])) > \
                    (latest[cetip]["competencia"], _number(latest[cetip]["document_id"])):
                latest[cetip] = row
    out_rows, failures, parsed = [], [], {}
    for emission in order:
        for s in sorted(selected[emission], key=lambda r: r["codigo_cetip"]):
            row = latest.get(s["codigo_cetip"])
            if not row:
                continue
            if row["arquivo"] not in parsed:
                try:
                    report = parse_report(ROOT / row["arquivo"])
                    if not report.competencia:
                        report = with_competencia(report, label(row["competencia"]))
                    parsed[row["arquivo"]] = report
                except Exception as error:
                    parsed[row["arquivo"]] = None
                    failures.append(f"{emission} ({row['arquivo']}): {type(error).__name__}: {error}")
            report = parsed[row["arquivo"]]
            if report is None:
                continue
            base = {"codigo_opea": emission, "codigo_cetip": s["codigo_cetip"], "isin": "",
                    "devedor": s.get("devedor") or row["devedor"], "status_opea": "Ativa",
                    "no_universo": "", "arquivo": row["arquivo"], "sha256": row["sha256"]}
            rows = as_rows(base, report)
            for r in rows:
                r["no_universo"] = "sim" if {r["codigo_cetip"].upper(), str(r["isin"] or "").upper()} & ours else "nao"
            out_rows.extend(rows)
    models = Counter(report.modelo or "sem_modelo" for report in parsed.values() if report is not None)
    write_outputs(out_rows, failures, selected, order, today, models, args.max_age_days)
    print(json.dumps({"coleta": dict(stats), "relatorios_lidos": len([r for r in parsed.values() if r is not None]),
                      "emissoes_com_relatorio": len({r['codigo_opea'] for r in out_rows}), "linhas": len(out_rows),
                      "modelos": dict(models), "falhas_de_leitura": len(failures)}, ensure_ascii=False, indent=2))
    return 0


def write_outputs(rows: list[dict], failures: list[str], selected: dict[str, list[dict]], order: list[str],
                  today: date, models: Counter, max_age_days: int) -> None:
    with (ROOT / "reports" / "canal_monitoramentos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    # contagens por item da emissão (o CSV repete o item em cada série que aponta para o mesmo relatório)
    items = {(r["codigo_opea"], r["arquivo"], r["pagina"], r["grupo_tipo"], r["grupo"], r["item"]): r
             for r in rows if r["item"] != "(sem monitoramentos)"}
    checked = {k: r for k, r in items.items() if r["grupo_tipo"] != "Saldo de conta"}
    situations = Counter(r["situacao"] or "sem_apuracao" for r in checked.values())
    balances = len(items) - len(checked)
    by_emission = defaultdict(list)
    for r in rows:
        by_emission[r["codigo_opea"]].append(r)
    universe_of = {e: any(r["no_universo"] == "sim" for r in rs) for e, rs in by_emission.items()}
    empty = sorted({(e, r["arquivo"], r["competencia"]) for e, rs in by_emission.items() for r in rs
                    if all(x["item"] == "(sem monitoramentos)" for x in rs if x["arquivo"] == r["arquivo"])},
                   key=lambda t: _number(t[0]))
    only_balances = sorted({e for e, rs in by_emission.items()
                            if rs and all(r["grupo_tipo"] == "Saldo de conta" for r in rs if r["item"] != "(sem monitoramentos)")
                            and any(r["grupo_tipo"] == "Saldo de conta" for r in rs)}, key=_number)
    failing = defaultdict(list)
    for key, r in checked.items():
        if r["situacao"] == "nao_atendido":
            failing[key[0]].append(r)

    # defasagem: competência mais recente publicada de cada emissão viva (do catálogo verificado nesta coleta)
    lag_rows, lag_hist, no_report = [], Counter(), []
    for e in order:
        comps = [s.get("competencia_mais_recente") or "" for s in selected[e]]
        newest = max(comps) if any(comps) else ""
        first = selected[e][0]
        if not newest:
            if any("relatorios_mensais" in s for s in selected[e]):
                no_report.append(e)
            continue
        lag = months_behind(newest, today)
        bucket = "0-2" if lag <= 2 else "3-4" if lag <= 4 else "5-7" if lag <= 7 else "8-12" if lag <= 12 else "13+"
        lag_hist[bucket] += 1
        lag_rows.append((lag, e, first.get("devedor") or "", " ".join(s["codigo_cetip"] for s in selected[e]), newest))
    verified = sum(1 for e in order if any("relatorios_mensais" in s for s in selected[e]))
    lags = sorted(r[0] for r in lag_rows)
    median = lags[len(lags) // 2] if lags else None

    lines = [
        "# Monitoramentos da Canal (Relatório Mensal / Relatório investidor)", "",
        f"Fonte: páginas públicas de emissões da Canal Securitizadora (sem login), relatório mensal mais recente (até "
        f"{max_age_days} dias) de cada série viva (vencimento a partir de hoje); leitor `{PARSER}`. Site da "
        "securitizadora é a fonte de menor prioridade: complementa, não substitui CVM nem Termo. Os valores são copiados "
        "do relatório; a situação (Enquadrado = atendido, Desenquadrado = não atendido) é a que a Canal informa, e a nota "
        "de rodapé do item (\"*AGT convocada\", \"*Fundo reenquadrado\") vai junto na condição apurada. O relatório não "
        "traz covenants financeiros do devedor (DL/EBITDA): cobre fundos (limite mínimo × status) e índices de garantia "
        "(ILG, LTV, razão). Os saldos das contas vinculadas saem como itens \"Saldo de conta\", sem situação: o relatório "
        "não diz qual saldo atende qual limite. O CSV tem uma linha por item e por série; as contagens abaixo são por "
        "item da emissão.", "",
        f"Gerado em {today.isoformat()}. Emissões com relatório lido: **{len(by_emission)}** "
        f"(modelos: {', '.join(f'{k} {v}' for k, v in models.most_common()) or '-'}); itens de garantia: "
        f"**{sum(situations.values())}**; saldos de conta: {balances}.", "",
        "| Situação informada | Itens |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in situations.most_common()], "",
        f"## Emissões com item não atendido ({len(failing)})", "",
        "| Emissão | CETIP | Devedor | Universo | Competência | Item não atendido | Exigido | Apurado | Condição informada | Data |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e, its in sorted(failing.items(), key=lambda kv: (not universe_of.get(kv[0]), _number(kv[0]))):
        cetips = " ".join(sorted({r["codigo_cetip"] for r in by_emission[e]}))
        for r in its:
            lines.append(f"| {e} | {cetips} | {r['devedor'].replace('|', '/')} | {'sim' if universe_of.get(e) else 'nao'} | "
                         f"{r['competencia']} | {r['grupo_tipo']}: {r['item'].replace('|', '/')} | "
                         f"{r['valor_referencia']} {r['condicao_referencia']} | {r['valor_apurado']} | "
                         f"{r['condicao_apurada'].replace('|', '/')} | {r['data_verificacao']} |")
    lines += [
        "", "## Defasagem da publicação", "",
        f"Competência mais recente publicada na aba de relatórios de cada emissão viva, contra {today.strftime('%m/%Y')} "
        f"(emissões verificadas: {verified}; sem nenhum relatório mensal publicado: {len(no_report)}). "
        f"Mediana: **{median if median is not None else '-'} meses**.", "",
        "| Meses de atraso | Emissões |", "|---|---|",
        *[f"| {k} | {lag_hist[k]} |" for k in ("0-2", "3-4", "5-7", "8-12", "13+") if lag_hist[k]], "",
        "| Emissão | Devedor | Séries | Competência mais recente | Meses de atraso |", "|---|---|---|---|---|",
        *[f"| {e} | {d.replace('|', '/')} | {c} | {label(n)} | {lag} |"
          for lag, e, d, c, n in sorted(lag_rows, key=lambda r: (-r[0], _number(r[1])))],
    ]
    if no_report:
        lines += ["", f"Sem relatório mensal publicado ({len(no_report)}): {', '.join(no_report)}."]
    lines += ["", f"## Relatórios sem item lido ({len(empty)})", "",
              "Relatório baixado e lido sem nenhum item de garantia reconhecido (modelo não tratado, quadro vazio ou só "
              "texto em imagem).", ""]
    lines += [f"- {e}: {arquivo} ({comp})" for e, arquivo, comp in empty] or ["- nenhum"]
    if only_balances:
        lines += ["", f"Com saldos de conta, mas sem fundo ou índice com status ({len(only_balances)}): "
                      f"{', '.join(only_balances)}."]
    if failures:
        lines += ["", f"## Falhas de leitura ({len(failures)})", "", *[f"- {f}" for f in failures]]
    (ROOT / "reports" / "canal_monitoramentos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
