"""Relatórios mensais da Eco Securitizadora (gestão e acompanhamento) das emissões do nosso universo.

    python scripts/collect_eco_reports.py --dry-run
    python scripts/collect_eco_reports.py --commit [--only CRA022009VM]

Lê config/eco_emissoes_site.csv (CETIP → página pública da emissão), abre a página de cada emissão do universo
(config/ativos_mercado.csv e catálogo), baixa o relatório de gestão e o de acompanhamento mais recentes (publicados
nos últimos 180 dias) para data/documents/eco/<id>/ com SHA-256 e URL em data/eco/manifest.csv, e grava
reports/eco_relatorios_mensais.{csv,md}. Não grava no banco. Site é a fonte de menor prioridade (regra 3).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.eco_reports import money, parse_follow_up, parse_management, report_links

UA = {"User-Agent": "pense-al-m-cri-cra/0.1 (emissoes Eco; uso interno de research)"}
MANIFEST = ROOT / "data" / "eco" / "manifest.csv"
MAX_AGE_DAYS = 180


def fetch(url: str) -> bytes:
    request = urllib.request.Request(urllib.parse.quote(url, safe=":/?=&"), headers=UA)
    return urllib.request.urlopen(request, timeout=120).read()


def universe() -> set[str]:
    with (ROOT / "config" / "ativos_mercado.csv").open(encoding="utf-8-sig") as handle:
        codes = {row["codigo_cetip"] for row in csv.DictReader(handle)}
    connection = sqlite3.connect(f"file:{ROOT / 'data' / 'cri_cra.db'}?mode=ro", uri=True)
    codes |= {row[0] for row in connection.execute("SELECT codigo_cetip FROM assets") if row[0]}
    connection.close()
    return codes


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--only", action="append")
    args = parser.parse_args()
    import pymupdf

    with (ROOT / "config" / "eco_emissoes_site.csv").open(encoding="utf-8-sig") as handle:
        site = list(csv.DictReader(handle, delimiter=";"))
    ours = universe()
    pages: dict[str, dict] = {}
    for row in site:
        if row["codigo_cetip"] in ours and (not args.only or row["codigo_cetip"] in args.only):
            page = pages.setdefault(row["id_eco"], {**row, "cetips": []})
            page["cetips"].append(row["codigo_cetip"])
    if args.dry_run:
        print(json.dumps({"dry_run": True, "paginas_de_emissao_no_universo": len(pages)}, ensure_ascii=False))
        return 0

    now = datetime.now(timezone.utc)
    manifest = []
    rows = []
    for number, (ident, page) in enumerate(sorted(pages.items(), key=lambda kv: int(kv[0])), start=1):
        try:
            links = report_links(fetch(page["url"]).decode("utf-8", errors="replace"))
        except Exception as error:
            print(f"{ident}: erro na página ({type(error).__name__})", file=sys.stderr)
            continue
        row = {"id_eco": ident, "url_emissao": page["url"], "operacao": page["operacao"], "emissao": page["emissao"],
               "cetips": " ".join(page["cetips"])}
        for kind in ("gestao", "acompanhamento"):
            # o mais recente que abre: alguns links da página dão 404, então tenta o seguinte do mesmo tipo
            data = None
            for link in (l for l in links if l.kind == kind):
                if (now - datetime.fromtimestamp(link.uploaded, timezone.utc)).days > MAX_AGE_DAYS:
                    break
                target = ROOT / "data" / "documents" / "eco" / ident / f"{kind}_{link.uploaded}.pdf"
                if not target.exists():
                    try:
                        content = fetch(link.url)
                    except Exception as error:
                        print(f"{ident}: {link.name} indisponível ({error})", file=sys.stderr)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    time.sleep(0.5)
                data = target.read_bytes()
                break
            if data is None:
                continue
            manifest.append({"id_eco": ident, "tipo": kind, "arquivo": str(target.relative_to(ROOT)).replace("\\", "/"),
                             "nome_no_site": link.name, "publicado_em": datetime.fromtimestamp(link.uploaded, timezone.utc).date().isoformat(),
                             "sha256": hashlib.sha256(data).hexdigest(), "url": link.url, "obtido_em": now.isoformat()})
            with pymupdf.open(stream=data, filetype="pdf") as document:
                text = "\n".join(p.get_text() for p in document)
                words = [p.get_text("words") for p in document]
            fields = parse_management(text) if kind == "gestao" else parse_follow_up(words, text)
            row.update({f"{kind}_{k}": v for k, v in fields.items()})
            row[f"{kind}_publicado_em"] = manifest[-1]["publicado_em"]
        guarantees, balance = money(row.get("acompanhamento_total_garantias", "")), money(row.get("acompanhamento_saldo_devedor", ""))
        row["cobertura_garantias"] = f"{guarantees / balance:.0%}" if guarantees and balance else ""
        rows.append(row)
        if number % 25 == 0:
            print(f"{number}/{len(pages)}", file=sys.stderr)
        time.sleep(0.5)

    # bloco de saldo por classe idêntico em emissões diferentes: provável cópia de modelo no relatório da Eco
    def balance_key(r):
        return tuple(r.get(f"acompanhamento_saldo_{c}", "") for c in ("senior", "mezanino", "subordinada"))
    blocks = defaultdict(set)
    for r in rows:
        if balance_key(r)[0]:
            blocks[balance_key(r)].add(r["emissao"])
    for r in rows:
        r["saldo_igual_ao_da_emissao"] = " ".join(sorted(blocks[balance_key(r)] - {r["emissao"]})) if balance_key(r)[0] else ""
        linked, overdue = money(r.get("acompanhamento_recebiveis_vinculados", "")), money(r.get("acompanhamento_recebiveis_vencidos", ""))
        r["vencidos_sobre_vinculados"] = f"{overdue / linked:.0%}" if linked and overdue is not None else ""

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    fields = sorted({k for r in rows for k in r}, key=lambda k: (not k.startswith(("id_", "url", "oper", "emis", "cet")), k))
    with (ROOT / "reports" / "eco_relatorios_mensais.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", restval="")
        writer.writeheader()
        writer.writerows(rows)
    with_follow = [r for r in rows if r.get("acompanhamento_publicado_em")]
    alerts = [r for r in with_follow if (money(r.get("acompanhamento_recebiveis_vencidos", "")) or 0) > 0
              or int(r.get("acompanhamento_aderencia_nao_aderentes") or 0) > 0]
    alerts.sort(key=lambda r: -(money(r.get("acompanhamento_recebiveis_vencidos", "")) or 0)
                / (money(r.get("acompanhamento_recebiveis_vinculados", "")) or float("inf")))
    lines = ["# Relatórios mensais da Eco Securitizadora", "",
             "Página pública de cada emissão em ecoagro.agr.br (fonte de menor prioridade: complementa CVM e Termo). "
             f"Relatórios publicados nos últimos {MAX_AGE_DAYS} dias; valores copiados como estão.", "",
             f"Emissões do universo com página na Eco: **{len(pages)}**; com relatório de gestão recente: "
             f"**{sum(1 for r in rows if r.get('gestao_publicado_em'))}**; com relatório de acompanhamento: **{len(with_follow)}**.", "",
             "Saldo devedor = soma das classes (Sênior + Mezanino + Subordinada); cobertura = total de garantias / saldo devedor. "
             "\"Saldo igual ao da emissão\" marca relatórios cujo bloco de saldo por classe é idêntico ao de outra emissão "
             "(provável cópia de modelo no relatório: conferir antes de usar).", "",
             f"## Acompanhamento com recebíveis vencidos ou item não aderente ao Termo ({len(alerts)})", "",
             "Ordem: maior proporção de recebíveis vencidos sobre os vinculados à carteira.", "",
             "| Emissão | Operação | CETIPs | Publicado | Garantias | Saldo devedor | Cobertura | Vinculados | Vencidos | % vencidos | Não aderentes | Saldo igual ao da emissão |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r['emissao']} | {r['operacao']} | {r['cetips']} | {r['acompanhamento_publicado_em']} | "
              f"{r.get('acompanhamento_total_garantias', '')} | {r.get('acompanhamento_saldo_devedor', '')} | {r['cobertura_garantias']} | "
              f"{r.get('acompanhamento_recebiveis_vinculados', '')} | {r.get('acompanhamento_recebiveis_vencidos', '')} | "
              f"{r['vencidos_sobre_vinculados']} | {r.get('acompanhamento_aderencia_nao_aderentes', '')} | {r['saldo_igual_ao_da_emissao']} |"
              for r in alerts]
    (ROOT / "reports" / "eco_relatorios_mensais.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"paginas": len(pages), "com_gestao": sum(1 for r in rows if r.get("gestao_publicado_em")),
                      "com_acompanhamento": len(with_follow), "alertas": len(alerts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
