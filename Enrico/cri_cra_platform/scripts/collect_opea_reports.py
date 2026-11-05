"""Relatório Mensal de Gestão da Opea: baixa o mais recente de cada emissão ativa ou em execução e lê a tabela de
Monitoramentos (garantias, obrigações e covenants: exigido × apurado × atendido, com datas de verificação).

    python scripts/collect_opea_reports.py --dry-run                # quantas emissões, quais do nosso universo
    python scripts/collect_opea_reports.py --commit [--only 24G2100031] [--limit 50]
    python scripts/collect_opea_reports.py --parse-only             # relê os PDFs já baixados

Não grava no banco. PDFs em data/documents/opea/<codigoOpea>/<AAAA-MM>_<evento>.pdf (já baixado não baixa de
novo); proveniência (URL, SHA-256, data) em data/opea/manifest.csv; saída em reports/opea_monitoramentos.{csv,md}.
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

from credit_assets.opea_monthly_report import PARSER, as_rows, parse_report
from credit_assets.opea_portal import OpeaPortal, monthly_reports

DOCS = ROOT / "data" / "documents" / "opea"
MANIFEST = ROOT / "data" / "opea" / "manifest.csv"
MANIFEST_FIELDS = ["codigo_opea", "codigo_cetip", "isin", "competencia", "event_id", "titulo", "data_ocorrencia",
                   "arquivo", "sha256", "url", "obtido_em"]
OUT_FIELDS = ["codigo_opea", "codigo_cetip", "isin", "devedor", "status_opea", "no_universo", "competencia",
              "cetip_no_relatorio", "saldo_devedor", "grupo_tipo", "grupo", "item", "valor_referencia",
              "condicao_referencia", "valor_apurado", "condicao_apurada", "situacao", "data_verificacao",
              "proxima_verificacao", "pagina", "arquivo", "sha256", "parser"]
LIVE = ("Ativa", "Execução")


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
        writer.writerows(sorted(rows.values(), key=lambda r: (r["codigo_opea"], r["competencia"])))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--parse-only", action="store_true")
    parser.add_argument("--only", action="append", help="código CETIP, ISIN ou código Opea")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--min-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()

    portal = OpeaPortal(min_interval_seconds=args.min_interval_seconds)
    ours = universe()
    emissions = [e for e in portal.emissions() if (e.get("statusPassivoOperacao") or {}).get("value") in LIVE]
    if args.only:
        wanted = {code.upper() for code in args.only}
        emissions = [e for e in emissions if {str(e.get("codigoIf") or "").upper(), str(e.get("isin") or "").upper(),
                                               str(e.get("codigoOpea") or "").upper()} & wanted]
    emissions.sort(key=lambda e: (not ({str(e.get("codigoIf") or "").upper(), str(e.get("isin") or "").upper()} & ours),
                                  e["codigoOpea"]))
    if args.limit:
        emissions = emissions[: args.limit]
    in_universe = sum(1 for e in emissions if {str(e.get("codigoIf") or "").upper(), str(e.get("isin") or "").upper()} & ours)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "emissoes_ativas_ou_em_execucao": len(emissions), "no_nosso_universo": in_universe,
                          "por_situacao": Counter((e.get("statusPassivoOperacao") or {}).get("value") for e in emissions)},
                         ensure_ascii=False, indent=2))
        return 0

    manifest = load_manifest()
    info = {e["codigoOpea"]: e for e in emissions}
    stats = Counter()
    if args.commit:
        for number, emission in enumerate(emissions, start=1):
            code = emission["codigoOpea"]
            try:
                reports = monthly_reports(portal.events(code))
            except Exception as error:  # rede ou API: segue para a próxima emissão
                stats["erro_eventos"] += 1
                print(f"{code}: erro nos eventos ({type(error).__name__})", file=sys.stderr)
                continue
            if not reports:
                stats["sem_relatorio"] += 1
                continue
            month, event = reports[0]
            target = DOCS / code.replace("/", "_") / f"{month}_{event['id']}.pdf"
            relative = str(target.relative_to(ROOT)).replace("\\", "/")
            if relative in manifest and target.exists():
                stats["ja_baixado"] += 1
                continue
            try:
                files = [a for a in portal.attachments(event) if a.file_name.lower().endswith(".pdf")]
            except Exception as error:
                stats["erro_anexo"] += 1
                print(f"{code}: erro no anexo ({type(error).__name__})", file=sys.stderr)
                continue
            if not files:
                stats["anexo_sem_pdf"] += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(files[0].content)
            manifest[relative] = {
                "codigo_opea": code, "codigo_cetip": emission.get("codigoIf") or "", "isin": emission.get("isin") or "",
                "competencia": month, "event_id": event["id"], "titulo": event.get("titulo") or "",
                "data_ocorrencia": event.get("dataOcorrencia") or "", "arquivo": relative, "sha256": files[0].sha256,
                "url": files[0].url, "obtido_em": files[0].fetched_at}
            stats["baixado"] += 1
            if number % 50 == 0:
                save_manifest(manifest)
                print(f"{number}/{len(emissions)} {dict(stats)}", file=sys.stderr)
        save_manifest(manifest)

    # leitura: o relatório mais recente de cada emissão no manifesto
    latest: dict[str, dict] = {}
    for row in manifest.values():
        if row["codigo_opea"] not in latest or row["competencia"] > latest[row["codigo_opea"]]["competencia"]:
            latest[row["codigo_opea"]] = row
    out_rows, failures = [], []
    for code, row in sorted(latest.items()):
        if args.only and code not in info:
            continue
        emission = info.get(code, {})
        base = {"codigo_opea": code, "codigo_cetip": row["codigo_cetip"], "isin": row["isin"],
                "devedor": emission.get("nomeDevedor") or "",
                "status_opea": (emission.get("statusPassivoOperacao") or {}).get("value") or "",
                "no_universo": "sim" if {row["codigo_cetip"].upper(), row["isin"].upper()} & ours else "nao",
                "arquivo": row["arquivo"], "sha256": row["sha256"]}
        try:
            out_rows.extend(as_rows(base, parse_report(ROOT / row["arquivo"])))
        except Exception as error:
            failures.append(f"{code}: {type(error).__name__}: {error}")
    write_outputs(out_rows, failures, stats)
    print(json.dumps({"coleta": dict(stats), "relatorios_lidos": len({r['codigo_opea'] for r in out_rows}),
                      "itens": len(out_rows), "falhas_de_leitura": len(failures)}, ensure_ascii=False, indent=2))
    return 0


def write_outputs(rows: list[dict], failures: list[str], stats: Counter) -> None:
    with (ROOT / "reports" / "opea_monitoramentos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    situations = Counter(r["situacao"] or "sem_apuracao" for r in rows if r["item"] != "(sem monitoramentos)")
    by_asset = defaultdict(list)
    for r in rows:
        by_asset[r["codigo_opea"]].append(r)
    failing = {code: [r for r in items if r["situacao"] == "nao_atendido"] for code, items in by_asset.items()}
    failing = {code: items for code, items in failing.items() if items}
    lines = [
        "# Monitoramentos da Opea (Relatório Mensal de Gestão)", "",
        f"Fonte: portal de emissões da Opea (API pública), relatório mais recente de cada emissão ativa ou em execução; "
        f"leitor `{PARSER}`. Site da securitizadora é a fonte de menor prioridade: complementa, não substitui CVM nem Termo. "
        "Os valores são copiados do relatório; a situação (atendido, não atendido, não verificado) é a que a Opea informa.", "",
        f"Emissões com relatório lido: **{len(by_asset)}**; itens: **{sum(situations.values())}**.", "",
        "| Situação informada | Itens |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in situations.most_common()], "",
        f"## Emissões com item não atendido ({len(failing)})", "",
        "| Emissão | CETIP | Devedor | Situação Opea | Universo | Competência | Item não atendido | Exigido | Apurado |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for code, items in sorted(failing.items(), key=lambda kv: (kv[1][0]["no_universo"] != "sim", kv[0])):
        for r in items:
            lines.append(f"| {code} | {r['codigo_cetip']} | {r['devedor'].replace('|', '/')} | {r['status_opea']} | {r['no_universo']} | "
                         f"{r['competencia']} | {r['grupo_tipo']}: {r['item']} | {r['valor_referencia']} {r['condicao_referencia']} | "
                         f"{r['valor_apurado']} |")
    if failures:
        lines += ["", f"## Falhas de leitura ({len(failures)})", "", *[f"- {f}" for f in failures]]
    (ROOT / "reports" / "opea_monitoramentos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
