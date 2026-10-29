"""Universo limpo de CRA/CRI (chave = ISIN da série) e candidatos ao lote-piloto (só leitura).

Lê data/cvm_open.db e (só leitura) data/cri_cra.db. Gera reports/market_universe.md e
config/lote_piloto_candidatos.csv (mesmo formato de ativos_piloto.csv, com ativo=false: nada entra
no catálogo sem aprovação). Não grava em nenhum banco.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.market_checks import (
    ISIN_PATTERN, WEIGHTS, merge_alias_certificates, rank_emissions, reference_competence,
)

LATEST_SERIES = """
    SELECT * FROM (
        SELECT t.*, ROW_NUMBER() OVER (
            PARTITION BY Codigo_Identificacao_Certificado, Numero_Serie, Codigo_ISIN
            ORDER BY Data_Referencia DESC) AS _latest
        FROM {table} t) WHERE _latest = 1
"""
LATEST_GERAL = """
    SELECT * FROM (
        SELECT t.*, ROW_NUMBER() OVER (
            PARTITION BY Codigo_Identificacao_Certificado ORDER BY Data_Referencia DESC) AS _latest
        FROM {table} t) WHERE _latest = 1
"""
FIELDS = ["codigo_cetip", "isin", "securitizadora", "cnpj_securitizadora", "emissao", "serie", "tipo_ativo",
          "devedor", "cnpj_devedor", "ativo", "score", "sinais", "saldo_brl", "series", "codigos_certificado"]


def series_number(value: str | None) -> int:
    try:
        return int(str(value).strip())
    except ValueError:
        return 10**6


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cvm", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--catalog", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--per-kind", type=int, default=15)
    parser.add_argument("--per-issuer", type=int, default=4)
    parser.add_argument("--min-balance", type=int, default=10_000_000)
    args = parser.parse_args()

    cvm = sqlite3.connect(f"file:{args.cvm}?mode=ro", uri=True)
    cvm.row_factory = sqlite3.Row
    catalog = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)
    known = {r[0].upper() for r in catalog.execute("SELECT isin FROM assets WHERE isin IS NOT NULL")}
    known |= {r[0].upper() for r in catalog.execute("SELECT isin FROM asset_series WHERE isin IS NOT NULL")}
    catalog.close()

    lines = ["# Universo de CRA e CRI (chave: ISIN da série)", "",
             "Fonte: dados abertos da CVM (`data/cvm_open.db`). Só leitura; nada entra no catálogo sem aprovação.", ""]
    picks: list[dict] = []
    for kind in ("cra", "cri"):
        counts = {r[0]: r[1] for r in cvm.execute(
            f"SELECT Data_Referencia, COUNT(DISTINCT Codigo_Identificacao_Certificado) FROM {kind}_geral_vigente GROUP BY 1")}
        reference = reference_competence(counts)
        rows = [dict(r) for r in cvm.execute(LATEST_SERIES.format(table=f"{kind}_classe_vigente"))]
        last = {r[0]: r[1] for r in cvm.execute(
            f"SELECT Codigo_Identificacao_Certificado, MAX(Data_Referencia) FROM {kind}_classe_vigente GROUP BY 1")}
        geral = {r["Codigo_Identificacao_Certificado"]: dict(r) for r in cvm.execute(
            LATEST_GERAL.format(table=f"{kind}_geral_vigente"))}
        merged, filing, aliases = merge_alias_certificates(rows, last)
        ranking = rank_emissions(merged, reference, filing)
        isins = {r["Codigo_ISIN"].upper() for r in merged if r["Codigo_ISIN"]}
        current = [i for i in ranking if i["ultima_competencia"] >= reference]
        in_catalog = sorted(isins & known)
        raw_codes = len({r["Codigo_Identificacao_Certificado"] for r in rows})
        lines += [f"## {kind.upper()} (competência de referência {reference})", "",
                  f"- Códigos de certificado na base: {raw_codes}; emissões depois de unir os códigos duplicados: **{len(ranking)}** "
                  f"({raw_codes - len(ranking)} eram a mesma emissão com dois códigos).",
                  f"- ISINs de série distintos: **{len(isins)}**; emissões com informe recente: **{len(current)}**.",
                  f"- Já no catálogo do projeto (por ISIN): {len(in_catalog)} ISINs ({', '.join(in_catalog[:8])}{'...' if len(in_catalog) > 8 else ''}).", ""]
        by_series: dict[str, list[dict]] = defaultdict(list)
        for row in merged:
            by_series[row["Codigo_Identificacao_Certificado"]].append(row)
        per_issuer: Counter = Counter()
        chosen = 0
        for item in ranking:
            if chosen >= args.per_kind:
                break
            cert = item["certificado"]
            series = sorted(by_series[cert], key=lambda r: series_number(r.get("Numero_Serie")))
            first = series[0]
            if (item["score"] <= 0 or item["ultima_competencia"] < reference or item["saldo"] < args.min_balance
                    or not ISIN_PATTERN.match((first["Codigo_ISIN"] or "").upper()) or any(r["Codigo_ISIN"].upper() in known for r in series if r["Codigo_ISIN"])
                    or per_issuer[item["emissora"]] >= args.per_issuer):
                continue
            info = geral.get(cert) or next((geral[a] for a in aliases[cert] if a in geral), {})
            per_issuer[item["emissora"]] += 1
            chosen += 1
            picks.append({
                "codigo_cetip": first.get("Codigo_CETIP") or cert, "isin": first["Codigo_ISIN"],
                "securitizadora": info.get("Companhia_Emissora", ""), "cnpj_securitizadora": item["emissora"],
                "emissao": info.get("Numero_Emissao", ""), "serie": first.get("Numero_Serie", ""),
                "tipo_ativo": kind.upper(), "devedor": "", "cnpj_devedor": "", "ativo": "false",
                "score": item["score"], "sinais": "; ".join(f"{f}x{n}" for f, n in item["flags"].items()),
                "saldo_brl": f"{item['saldo']:.2f}", "series": item["series"],
                "codigos_certificado": "|".join(aliases[cert]),
            })
        lines.append(f"Candidatos ao lote-piloto ({chosen}): ver `config/lote_piloto_candidatos.csv`.")
        lines.append("")
    cvm.close()

    out = ROOT / "config" / "lote_piloto_candidatos.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(picks)
    lines += ["## Candidatos ao lote-piloto", "",
              f"Critério: pontuação de triagem > 0, informe recente, saldo ≥ R$ {args.min_balance / 1e6:.0f} mi, ISIN presente, fora do catálogo, "
              f"até {args.per_issuer} por securitizadora e {args.per_kind} por tipo. **Pesos:** "
              + ", ".join(f"`{f}`={w}" for f, w in WEIGHTS.items()) + ".", "",
              "| Tipo | Código | ISIN | Securitizadora | Emissão | Saldo (R$ mi) | Pontos | Sinais |", "|---|---|---|---|---|---|---|---|"]
    for p in picks:
        lines.append(f"| {p['tipo_ativo']} | {p['codigo_cetip']} | {p['isin']} | {p['securitizadora']} | {p['emissao']} | "
                     f"{Decimal(p['saldo_brl']) / 1_000_000:,.1f} | {p['score']} | {p['sinais']} |")
    (ROOT / "reports" / "market_universe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:22]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
