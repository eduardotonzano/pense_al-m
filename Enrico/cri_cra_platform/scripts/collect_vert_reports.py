"""Relatório Mensal de Acompanhamento da Vert: baixa o mais recente (até 180 dias) de cada CRI/CRA vivo no portal
VERT Data e lê os índices e acompanhamentos (fundos de despesas e de reserva, LTV, razão de garantia, covenants
financeiros: exigido × apurado × Enquadrado/Desenquadrado).

    python scripts/collect_vert_reports.py --dry-run                # quantas emissões, quais do nosso universo
    python scripts/collect_vert_reports.py --commit [--only CRA021002C2] [--limit 50]
    python scripts/collect_vert_reports.py --parse-only             # relê os PDFs já baixados

Não grava no banco. PDFs em data/documents/vert/<id>/<AAAA-MM>_<documento>.pdf (já baixado não baixa de novo);
proveniência (URL sem a assinatura da S3, SHA-256, data) em data/vert/manifest.csv; saída em
reports/vert_monitoramentos.{csv,md}, uma linha por item e por série (código CETIP e ISIN de cada série).
Site da securitizadora é a fonte de menor prioridade (regra 3): complementa, nunca sobrescreve CVM nem Termo.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.vert_monthly_report import PARSER, as_rows, competencia_from_date, parse_report
from credit_assets.vert_portal import VertPortal, is_live, monthly_reports

DOCS = ROOT / "data" / "documents" / "vert"
MANIFEST = ROOT / "data" / "vert" / "manifest.csv"
MANIFEST_FIELDS = ["vert_id", "external_id", "nome", "tipo", "codigos_cetip", "isins", "competencia", "document_id",
                   "titulo", "data_base", "arquivo", "sha256", "url", "obtido_em"]
OUT_FIELDS = ["codigo_opea", "codigo_cetip", "isin", "devedor", "status_opea", "no_universo", "competencia",
              "cetip_no_relatorio", "saldo_devedor", "grupo_tipo", "grupo", "item", "valor_referencia",
              "condicao_referencia", "valor_apurado", "condicao_apurada", "situacao", "data_verificacao",
              "proxima_verificacao", "pagina", "arquivo", "sha256", "parser"]


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


def series_codes(emission: dict) -> set[str]:
    return {str(s.get(k) or "").upper() for s in emission.get("series") or [] for k in ("codeCetip", "codeIsin")} - {""}


def load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8") as handle:
        return {row["arquivo"]: row for row in csv.DictReader(handle)}


def save_manifest(rows: dict[str, dict]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: (int(r["vert_id"]), r["competencia"])))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--parse-only", action="store_true")
    parser.add_argument("--only", action="append", help="código CETIP, ISIN ou id do VERT Data")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-age-days", type=int, default=180)
    parser.add_argument("--min-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()

    portal = VertPortal(min_interval_seconds=args.min_interval_seconds)
    ours = universe()
    catalog = portal.emissions()
    emissions = [e for e in catalog if is_live(e)]
    if args.only:
        wanted = {code.upper() for code in args.only}
        emissions = [e for e in emissions if (series_codes(e) | {str(e["id"])}) & wanted]
    emissions.sort(key=lambda e: (not (series_codes(e) & ours), int(e["id"])))
    if args.limit:
        emissions = emissions[: args.limit]
    in_universe = sum(1 for e in emissions if series_codes(e) & ours)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "emissoes_no_catalogo": len(catalog), "cri_cra_vivos": len(emissions),
                          "no_nosso_universo": in_universe,
                          "por_tipo": Counter(str(e.get("financialTitle")) for e in emissions)},
                         ensure_ascii=False, indent=2))
        return 0

    manifest = load_manifest()
    info = {str(e["id"]): e for e in emissions}
    stats = Counter()
    if args.commit:
        for number, emission in enumerate(emissions, start=1):
            ident = str(emission["id"])
            try:
                reports = monthly_reports(portal.documents(emission["id"]), max_age_days=args.max_age_days)
            except Exception as error:  # rede ou API: segue para a próxima emissão
                stats["erro_documentos"] += 1
                print(f"{ident}: erro nos documentos ({type(error).__name__})", file=sys.stderr)
                continue
            if not reports:
                stats["sem_relatorio_recente"] += 1
                continue
            doc = reports[0]
            month = str(doc.get("referenceDate") or "")[:7]
            target = DOCS / ident / f"{month}_{doc['id']}.pdf"
            relative = str(target.relative_to(ROOT)).replace("\\", "/")
            if relative in manifest and target.exists():
                stats["ja_baixado"] += 1
                continue
            try:
                download = portal.download(doc)
            except Exception as error:
                stats["erro_download"] += 1
                print(f"{ident}: erro no download ({type(error).__name__})", file=sys.stderr)
                continue
            if not download.content.startswith(b"%PDF"):
                stats["nao_pdf"] += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(download.content)
            series = emission.get("series") or []
            manifest[relative] = {
                "vert_id": ident, "external_id": emission.get("external_id") or "", "nome": emission.get("name") or "",
                "tipo": emission.get("financialTitle") or "",
                "codigos_cetip": " ".join(str(s.get("codeCetip") or "") for s in series),
                "isins": " ".join(str(s.get("codeIsin") or "") for s in series), "competencia": month,
                "document_id": doc["id"], "titulo": doc.get("name") or "", "data_base": doc.get("referenceDate") or "",
                "arquivo": relative, "sha256": download.sha256, "url": download.url, "obtido_em": download.fetched_at}
            stats["baixado"] += 1
            if number % 10 == 0:
                save_manifest(manifest)
                print(f"{number}/{len(emissions)} {dict(stats)}", file=sys.stderr)
        save_manifest(manifest)

    # leitura: o relatório mais recente de cada emissão no manifesto
    latest: dict[str, dict] = {}
    for row in manifest.values():
        if row["vert_id"] not in latest or row["competencia"] > latest[row["vert_id"]]["competencia"]:
            latest[row["vert_id"]] = row
    out_rows, failures = [], []
    for ident, row in sorted(latest.items(), key=lambda kv: int(kv[0])):
        if ident not in info:
            continue  # fora do filtro (--only/--limit) ou não está mais vivo
        emission = info[ident]
        try:
            report = parse_report(ROOT / row["arquivo"])
        except Exception as error:
            failures.append(f"{ident} ({emission.get('name')}): {type(error).__name__}: {error}")
            continue
        if not report.competencia:
            report = report.__class__(competencia_from_date(row["data_base"]), report.cetip, report.comentario,
                                      report.saldo_devedor, report.monitoramentos)
        for series in emission.get("series") or [{}]:
            cetip, isin = str(series.get("codeCetip") or ""), str(series.get("codeIsin") or "")
            base = {"codigo_opea": ident, "codigo_cetip": cetip, "isin": isin,
                    "devedor": emission.get("originator") or emission.get("name") or "",
                    "status_opea": "Encerrada" if series.get("isClosed") else "Ativa",
                    "no_universo": "sim" if {cetip.upper(), isin.upper()} & ours else "nao",
                    "arquivo": row["arquivo"], "sha256": row["sha256"]}
            out_rows.extend(as_rows(base, report))
    write_outputs(out_rows, failures, info)
    print(json.dumps({"coleta": dict(stats), "relatorios_lidos": len({r['codigo_opea'] for r in out_rows}),
                      "linhas": len(out_rows), "falhas_de_leitura": len(failures)}, ensure_ascii=False, indent=2))
    return 0


def write_outputs(rows: list[dict], failures: list[str], info: dict[str, dict]) -> None:
    with (ROOT / "reports" / "vert_monitoramentos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    # contagens por item da emissão (o CSV repete o item em cada série)
    items = {(r["codigo_opea"], r["pagina"], r["grupo"], r["item"]): r for r in rows if r["item"] != "(sem monitoramentos)"}
    situations = Counter(r["situacao"] or "sem_apuracao" for r in items.values())
    by_emission = defaultdict(list)
    for r in rows:
        by_emission[r["codigo_opea"]].append(r)
    failing = defaultdict(list)
    for key, r in items.items():
        if r["situacao"] == "nao_atendido":
            failing[key[0]].append(r)
    universe_of = {code: any(r["no_universo"] == "sim" for r in rs) for code, rs in by_emission.items()}
    empty = sum(1 for rs in by_emission.values() if all(r["item"] == "(sem monitoramentos)" for r in rs))
    lines = [
        "# Monitoramentos da Vert (Relatório Mensal de Acompanhamento)", "",
        f"Fonte: portal VERT Data (API pública), relatório mensal de acompanhamento mais recente (até 180 dias) de cada "
        f"CRI/CRA com série aberta; leitor `{PARSER}`. Site da securitizadora é a fonte de menor prioridade: complementa, "
        "não substitui CVM nem Termo. Os valores são copiados do relatório; a situação (Enquadrado = atendido, "
        "Desenquadrado = não atendido) é a que a Vert informa. O CSV tem uma linha por item e por série; as contagens "
        "abaixo são por item da emissão.", "",
        f"Emissões com relatório lido: **{len(by_emission)}** (sem nenhum item reconhecido: {empty}); "
        f"itens: **{sum(situations.values())}**.", "",
        "| Situação informada | Itens |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in situations.most_common()], "",
        f"## Emissões com item não atendido ({len(failing)})", "",
        "| Emissão (id VERT) | CETIP | Devedor | Universo | Competência | Item não atendido | Exigido | Apurado | Data |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for code, its in sorted(failing.items(), key=lambda kv: (not universe_of.get(kv[0]), int(kv[0]))):
        emission = info.get(code, {})
        open_codes = [str(s.get("codeCetip") or "") for s in emission.get("series") or [] if not s.get("isClosed")]
        cetips = " ".join(open_codes[:3]) + (f" (+{len(open_codes) - 3})" if len(open_codes) > 3 else "")
        name = str(emission.get("name") or its[0]["devedor"]).replace("|", "/")
        for r in its:
            lines.append(f"| {code} {name} | {cetips} | {r['devedor'].replace('|', '/')} | "
                         f"{'sim' if universe_of.get(code) else 'nao'} | {r['competencia']} | "
                         f"{r['grupo_tipo']}: {r['item'].replace('|', '/')} | {r['valor_referencia']} {r['condicao_referencia']} | "
                         f"{r['valor_apurado']} | {r['data_verificacao']} |")
    if failures:
        lines += ["", f"## Falhas de leitura ({len(failures)})", "", *[f"- {f}" for f in failures]]
    (ROOT / "reports" / "vert_monitoramentos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
