"""Relatório Mensal de Acompanhamento da Leverage: baixa o mais recente de cada emissão viva (CRI/CRA com série ativa,
competência de até 180 dias) e lê fundos e índices monitorados (exigido × apurado × Enquadrado/Desenquadrado).

    python scripts/collect_leverage_reports.py --dry-run                # quantas emissões, quais do nosso universo
    python scripts/collect_leverage_reports.py --commit [--only 26G2474440] [--limit 50]
    python scripts/collect_leverage_reports.py --parse-only             # relê os PDFs já baixados (sem rede)

Não grava no banco. O portal só responde dentro do navegador (sessão de visitante), então a coleta usa Playwright
headless no fluxo normal do site, uma ação por segundo. PDFs em data/documents/leverage/<emissao_id>/<AAAA-MM>_<arquivo>.pdf
(já baixado não baixa de novo); proveniência (URL, SHA-256, data) em data/leverage/manifest.csv; saída em
reports/leverage_monitoramentos.{csv,md}, com as colunas de reports/opea_monitoramentos.csv (codigo_opea = id da emissão
no portal da Leverage). Site da securitizadora é a fonte de menor prioridade (regra 3): complementa, nunca sobrescreve
CVM nem Termo.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.leverage_monthly_report import PARSER, as_rows, parse_report
from credit_assets.leverage_portal import LeveragePortal, live_emissions, monthly_reports, recent_enough

DOCS = ROOT / "data" / "documents" / "leverage"
MANIFEST = ROOT / "data" / "leverage" / "manifest.csv"
EMISSIONS = ROOT / "data" / "leverage" / "emissoes.json"  # última lista do portal, para o --parse-only
MANIFEST_FIELDS = ["emissao_id", "emissao_nome", "codigo_cetip", "isin", "competencia", "arquivo_id", "nome_original",
                   "enviado_em", "arquivo", "sha256", "url", "obtido_em"]
OUT_FIELDS = ["codigo_opea", "codigo_cetip", "isin", "devedor", "status_opea", "no_universo", "competencia",
              "cetip_no_relatorio", "saldo_devedor", "grupo_tipo", "grupo", "item", "valor_referencia",
              "condicao_referencia", "valor_apurado", "condicao_apurada", "situacao", "data_verificacao",
              "proxima_verificacao", "pagina", "arquivo", "sha256", "parser"]


CETIP = re.compile(r"^(?:\d{2}[A-L]\d{7}|CR[AI]\d{3}[0-9A-Z]{4})$")


def universe() -> set[str]:
    codes = set()
    with (ROOT / "config" / "ativos_mercado.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            codes |= {row["codigo_cetip"].upper(), row["isin"].upper()}
    try:
        connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True, timeout=120)
        for cetip, isin in connection.execute("SELECT codigo_cetip, isin FROM assets"):
            codes |= {str(cetip or "").upper(), str(isin or "").upper()}
        connection.close()
    except Exception:
        pass
    return codes - {""}


def isin_by_cetip() -> dict[str, str]:
    """CETIP -> ISIN pelos informes mensais da CVM (dados abertos, só leitura): o ISIN mais frequente da série, porque
    um mês com erro de preenchimento (ISIN de outra série repetido) não pode vencer. O portal da Leverage não publica
    ISIN."""

    counts: dict[str, Counter] = defaultdict(Counter)
    try:
        connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cvm_open.db'}?mode=ro", uri=True)
        for table in ("cri_classe", "cra_classe"):
            for cetip, isin in connection.execute(
                    f"SELECT Codigo_CETIP, Codigo_ISIN FROM {table} WHERE Codigo_ISIN LIKE 'BR%'"):
                cetip = str(cetip).strip().upper()
                if cetip not in ("", "-"):
                    counts[cetip][str(isin).strip().upper()] += 1
        connection.close()
    except Exception:
        pass
    return {cetip: isins.most_common(1)[0][0] for cetip, isins in counts.items()}


def series_codes(emission: dict) -> list[str]:
    return [s["codigo_if"] for s in emission.get("detalhes") or [] if (s.get("codigo_if") or "-") != "-"]


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
        writer.writerows(sorted(rows.values(), key=lambda r: (int(r["emissao_id"]), r["competencia"])))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--parse-only", action="store_true")
    parser.add_argument("--only", action="append", help="código CETIP, ISIN ou id da emissão no portal")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-age-days", type=int, default=180)
    parser.add_argument("--min-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()

    ours, isins = universe(), isin_by_cetip()

    def codes(e: dict) -> set[str]:
        cetips = {c.upper() for c in series_codes(e)}
        return cetips | {isins[c] for c in cetips if c in isins}

    if args.parse_only:
        portal = None
        emissions = json.loads(EMISSIONS.read_text(encoding="utf-8")) if EMISSIONS.exists() else []
    else:
        portal = LeveragePortal(min_interval_seconds=args.min_interval_seconds).__enter__()
        emissions = portal.emissions()
        if args.commit:
            EMISSIONS.parent.mkdir(parents=True, exist_ok=True)
            EMISSIONS.write_text(json.dumps(emissions, ensure_ascii=False), encoding="utf-8")
    try:
        total = len(emissions)
        emissions = live_emissions(emissions)
        if args.only:
            wanted = {code.upper() for code in args.only}
            emissions = [e for e in emissions if (codes(e) | {str(e["emissao_id"])}) & wanted]
        emissions.sort(key=lambda e: (not (codes(e) & ours), int(e["emissao_id"])))
        if args.limit:
            emissions = emissions[: args.limit]
        in_universe = sum(1 for e in emissions if codes(e) & ours)
        if args.dry_run:
            print(json.dumps({"dry_run": True, "emissoes_no_portal": total, "emissoes_vivas_cri_cra": len(emissions),
                              "no_nosso_universo": in_universe,
                              "por_tipo": Counter(e["emissao_tipo"] for e in emissions)}, ensure_ascii=False, indent=2))
            return 0

        manifest = load_manifest()
        stats = Counter()
        if args.commit:
            today = date.today()
            for number, emission in enumerate(emissions, start=1):
                ident = int(emission["emissao_id"])
                try:
                    reports = monthly_reports(portal.documents(ident))
                except Exception as error:  # rede ou portal: segue para a próxima emissão
                    stats["erro_documentos"] += 1
                    print(f"{ident}: erro nos documentos ({type(error).__name__}: {error})"[:300], file=sys.stderr)
                    continue
                if not reports:
                    stats["sem_relatorio"] += 1
                    continue
                month, item = reports[0]
                if not recent_enough(month, today, args.max_age_days):
                    stats["relatorio_antigo"] += 1
                    continue
                target = DOCS / str(ident) / f"{month}_{item['id']}.pdf"
                relative = str(target.relative_to(ROOT)).replace("\\", "/")
                if relative in manifest and target.exists():
                    stats["ja_baixado"] += 1
                    continue
                try:
                    downloaded = portal.download(month, item)
                except Exception as error:
                    stats["erro_download"] += 1
                    print(f"{ident}: erro no download ({type(error).__name__}: {error})"[:300], file=sys.stderr)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(downloaded.content)
                cetips = series_codes(emission)
                manifest[relative] = {
                    "emissao_id": str(ident), "emissao_nome": emission.get("emissao_nome") or "",
                    "codigo_cetip": ",".join(cetips), "isin": ",".join(isins.get(c.upper(), "") for c in cetips),
                    "competencia": month, "arquivo_id": downloaded.arquivo_id, "nome_original": downloaded.nome_original,
                    "enviado_em": downloaded.enviado_em, "arquivo": relative, "sha256": downloaded.sha256,
                    "url": downloaded.url, "obtido_em": downloaded.fetched_at}
                stats["baixado"] += 1
                if number % 20 == 0:
                    save_manifest(manifest)
                    print(f"{number}/{len(emissions)} {dict(stats)}", file=sys.stderr)
            save_manifest(manifest)
    finally:
        if portal:
            portal.__exit__(None, None, None)

    # leitura: o relatório mais recente de cada emissão no manifesto
    info = {str(e["emissao_id"]): e for e in emissions}
    latest: dict[str, dict] = {}
    for row in manifest.values():
        if row["emissao_id"] not in latest or row["competencia"] > latest[row["emissao_id"]]["competencia"]:
            latest[row["emissao_id"]] = row
    out_rows, failures = [], []
    for ident, row in sorted(latest.items(), key=lambda kv: int(kv[0])):
        if ident not in info:
            continue  # fora do filtro (--only/--limit) ou não está mais viva
        emission = info[ident]
        try:
            report = parse_report(ROOT / row["arquivo"])
        except Exception as error:
            failures.append(f"{ident}: {type(error).__name__}: {error}")
            continue
        # o portal às vezes lista menos séries que o relatório: junta os códigos da tabela de séries do relatório
        cetips = list(dict.fromkeys(series_codes(emission) + [code for _, code in report.series if CETIP.match(code or "")]))
        series_isins = [isins.get(c.upper(), "") for c in cetips]
        nickname = str(emission.get("emissao_apelido") or "")
        base = {"codigo_opea": ident, "codigo_cetip": ",".join(cetips), "isin": ",".join(series_isins),
                "devedor": nickname.removeprefix(f"{emission.get('emissao_tipo')} ").strip(),
                "status_opea": ",".join(sorted({s.get("situacao") or "" for s in emission.get("detalhes") or []})),
                "no_universo": "sim" if ({c.upper() for c in cetips} | set(series_isins)) & ours else "nao",
                "arquivo": row["arquivo"], "sha256": row["sha256"]}
        out_rows.extend(as_rows(base, report))
    write_outputs(out_rows, failures)
    print(json.dumps({"coleta": dict(stats), "relatorios_lidos": len({r['codigo_opea'] for r in out_rows}),
                      "itens": sum(1 for r in out_rows if r["item"] != "(sem monitoramentos)"),
                      "por_situacao": Counter(r["situacao"] or "sem_apuracao" for r in out_rows
                                              if r["item"] != "(sem monitoramentos)"),
                      "falhas_de_leitura": len(failures)}, ensure_ascii=False, indent=2))
    return 0


def write_outputs(rows: list[dict], failures: list[str]) -> None:
    with (ROOT / "reports" / "leverage_monitoramentos.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    situations = Counter(r["situacao"] or "sem_apuracao" for r in rows if r["item"] != "(sem monitoramentos)")
    by_asset = defaultdict(list)
    for r in rows:
        by_asset[r["codigo_opea"]].append(r)
    empty = sum(1 for items in by_asset.values() if items[0]["item"] == "(sem monitoramentos)")
    failing = {code: [r for r in items if r["situacao"] == "nao_atendido"] for code, items in by_asset.items()}
    failing = {code: items for code, items in failing.items() if items}
    lines = [
        "# Monitoramentos da Leverage (Relatório Mensal de Acompanhamento)", "",
        f"Fonte: portal de emissões da Leverage (sessão pública de visitante), relatório mais recente de cada emissão "
        f"CRI/CRA com série ativa; leitor `{PARSER}`. Site da securitizadora é a fonte de menor prioridade: complementa, "
        "não substitui CVM nem Termo. Os valores são copiados do relatório; a situação (Enquadrado = atendido, "
        "Desenquadrado = não atendido, Não Apurado = não verificado) é a que a Leverage informa. O relatório não traz "
        "data de verificação por item: `data_verificacao` é a competência (MM/AAAA). Coluna Emissão = id no portal.", "",
        f"Emissões com relatório lido: **{len(by_asset)}** ({empty} sem fundo ou índice monitorado); "
        f"itens: **{sum(situations.values())}**.", "",
        "| Situação informada | Itens |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in situations.most_common()], "",
        f"## Emissões com item não atendido ({len(failing)})", "",
        "| Emissão | CETIP | Devedor | Situação Leverage | Universo | Competência | Item não atendido | Exigido | Apurado |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for code, items in sorted(failing.items(), key=lambda kv: (kv[1][0]["no_universo"] != "sim", int(kv[0]))):
        for r in items:
            # índice: sigla e, quando repetido por empreendimento, o empreendimento ("RGFM · Parque Jardins")
            detail = f" ({r['grupo']})" if r["grupo_tipo"] == "Índice" and r["grupo"] else ""
            lines.append(f"| {code} | {r['codigo_cetip']} | {r['devedor'].replace('|', '/')} | {r['status_opea']} | "
                         f"{r['no_universo']} | {r['competencia']} | {r['grupo_tipo']}: {r['item']}{detail} | "
                         f"{r['valor_referencia']} {r['condicao_referencia']} | {r['valor_apurado']} |")
    if failures:
        lines += ["", f"## Falhas de leitura ({len(failures)})", "", *[f"- {f}" for f in failures]]
    (ROOT / "reports" / "leverage_monitoramentos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
