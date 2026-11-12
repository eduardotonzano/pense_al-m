"""Lista de acompanhamento de crédito dos ativos do catálogo, do mais grave para o menos (só leitura).

Junta o Informe da CVM (séries em atraso e eventos dos últimos 12 meses), as decisões das atas
(reports/assembleias_topicos.csv), as DFs (reports/market_dfin.csv), o contágio do devedor (reports/market_debtors.csv)
e a pontuação do ranking (reports/market_ranking.csv). Níveis em credit_assets.watchlist. Gera
reports/acompanhamento_credito.{md,csv}. Rodar depois de run_assembly_topics.py, run_dfin_checks.py e run_debtor_exposure.py.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.cvm_lookup import emission, history
from credit_assets.market_checks import fold, real_isin, trusted_balance
from credit_assets.market_events import compare
from credit_assets.watchlist import LEVEL_NAMES, AssetSignals, classify

REPORTS = ROOT / "reports"


def read_csv(name: str) -> list[dict[str, str]]:
    path = REPORTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def months_back(day: str, months: int) -> str:
    year, month = int(day[:4]), int(day[5:7]) - months
    while month <= 0:
        year, month = year - 1, month + 12
    return f"{year:04d}-{month:02d}-01"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--cvm", default=str(ROOT / "data" / "cvm_open.db"))
    args = parser.parse_args()
    catalog = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)
    catalog.row_factory = sqlite3.Row
    assets = catalog.execute("SELECT codigo_cetip, isin, tipo_ativo, securitizadora FROM assets ORDER BY codigo_cetip").fetchall()
    catalog.close()
    cvm = sqlite3.connect(f"file:{args.cvm}?mode=ro", uri=True)
    cvm.row_factory = sqlite3.Row

    decisions = defaultdict(list)
    for row in read_csv("assembleias_topicos.csv"):
        if row.get("documento_tipo") == "ata" and row.get("decisoes"):
            for event in row["decisoes"].split("; "):
                decisions[row["ativo"]].append((row["data"], event, row["documento"]))
    dfin = {r["certificado"]: r for r in read_csv("market_dfin.csv")}
    contagion = {code for d in read_csv("market_debtors.csv") if d["contagio"] == "1" for code in d["certificados"].split("|")}
    scores = {r["certificado"]: int(r["score"]) for r in read_csv("market_ranking.csv")}

    rows = []
    for asset in assets:
        kind = asset["tipo_ativo"].lower()
        em = emission(cvm, kind, asset["isin"]) if asset["isin"] else None
        signals = AssetSignals()
        balance = Decimal(0)
        last = ""
        codes: list[str] = []
        if em is not None:
            codes = em["codes"]
            last = em["last"]
            for s in em["series"]:
                balance += trusted_balance(s)
                signals.late_series += fold(s.get("Situacao")) == "em atraso"
            by_series = defaultdict(list)
            for r in history(cvm, kind, codes, months_back(last, 12)):
                by_series[real_isin(r["Codigo_ISIN"]) or f"{r['Codigo_Identificacao_Certificado']} série {r['Numero_Serie']}"].append(r)
            for items in by_series.values():
                previous = None
                for r in items:
                    if previous and previous["Data_Referencia"] != r["Data_Referencia"]:
                        signals.informe_events += [f"{r['Data_Referencia'][:7]} {ev}" for ev in compare(previous, r)]
                    previous = r
            df = next((dfin[c] for c in codes if c in dfin), None)
            if df:
                signals.df_opinion, signals.df_flags = df["parecer"], df["sinais"].split("; ")
            signals.contagion = any(c in contagion for c in codes)
            signals.ranking_score = max((scores.get(c, 0) for c in codes), default=0)
        cetip = asset["codigo_cetip"]
        signals.ata_decisions = [(d, e) for d, e, _ in decisions.get(cetip, [])]
        since = months_back(last or "2026-08-01", 12)
        level, reasons = classify(signals, since)
        rows.append({"nivel": level, "situacao": LEVEL_NAMES[level], "ativo": cetip, "tipo": asset["tipo_ativo"],
                     "securitizadora": asset["securitizadora"], "saldo_brl": f"{balance:.2f}", "series_em_atraso": signals.late_series,
                     "competencia_informe": last[:7], "motivos": " | ".join(reasons),
                     "ficha": f"fichas/{cetip.lower()}.md"})
    cvm.close()
    rows.sort(key=lambda r: (r["nivel"], -Decimal(r["saldo_brl"]), r["ativo"]))

    with (REPORTS / "acompanhamento_credito.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    counts = defaultdict(int)
    for r in rows:
        counts[r["nivel"]] += 1
    lines = ["# Acompanhamento de crédito dos ativos do catálogo", "",
             "Ordena por gravidade os sinais que a plataforma já tem: Informe Mensal da CVM, decisões das atas (regras de texto), "
             "DFs do patrimônio separado e contágio do devedor. **Triagem para leitura, não alerta:** cada motivo aponta a fonte, "
             "e as decisões de ata precisam ser conferidas na ata. Gerado por `scripts/build_credit_watchlist.py`.", "",
             "| Nível | Situação | Ativos |", "|---|---|---|"]
    lines += [f"| {n} | {LEVEL_NAMES[n]} | {counts[n]} |" for n in sorted(LEVEL_NAMES)]
    lines += ["", "| Nível | Ativo | Tipo | Securitizadora | Saldo (R$ mi) | Séries em atraso | Informe | Motivos |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['nivel']} | [{r['ativo']}]({r['ficha']}) | {r['tipo']} | {r['securitizadora'][:32]} | "
                     f"{Decimal(r['saldo_brl']) / 1_000_000:,.1f} | {r['series_em_atraso']} | {r['competencia_informe']} | "
                     f"{r['motivos'].replace('|', ';')[:400]} |")
    (REPORTS / "acompanhamento_credito.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
