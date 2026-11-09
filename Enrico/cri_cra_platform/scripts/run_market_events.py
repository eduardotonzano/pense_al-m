"""Eventos de crédito do mercado inteiro de CRA/CRI no último mês completo (só leitura de data/cvm_open.db).

Gera reports/market_events.{md,csv}: eventos do mês de referência (entrada/saída de atraso, rating, vencimento,
taxa, queda de saldo sem amortização, saldo zerado) e a contagem mensal dos últimos 12 meses.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.market_checks import reference_competence
from credit_assets.market_events import EVENTS, detect


def months_back(month: str, n: int) -> list[str]:
    year, mon = int(month[:4]), int(month[5:7])
    out = []
    for _ in range(n):
        out.append(f"{year:04d}-{mon:02d}")
        mon -= 1
        if mon == 0:
            year, mon = year - 1, 12
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    all_events, monthly, reference = [], {}, {}
    for kind in ("cra", "cri"):
        counts = {r[0]: r[1] for r in connection.execute(
            f"SELECT Data_Referencia, COUNT(DISTINCT Codigo_Identificacao_Certificado) FROM {kind}_geral_vigente GROUP BY 1")}
        ref = reference_competence(counts)[:7]
        reference[kind] = ref
        window = months_back(ref, args.months + 1)
        rows = [dict(r) for r in connection.execute(
            f"SELECT * FROM {kind}_classe_vigente WHERE substr(Data_Referencia, 1, 7) >= ?", (window[0],))]
        for month in window[1:]:
            found = detect(rows, month)
            monthly[(kind, month)] = Counter(e["evento"] for e in found)
            if month == ref:
                for event in found:
                    all_events.append({"tipo": kind.upper(), **event})
    connection.close()

    fields = ["tipo", "evento", "isin", "certificado", "emissora", "mes_anterior", "mes", "antes", "depois", "saldo"]
    with (ROOT / "reports" / "market_events.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(all_events)

    lines = ["# Eventos de crédito no mercado de CRA e CRI", "",
             "Fonte: Informe Mensal dos dados abertos da CVM. Série a série, mês de referência contra o mês anterior informado.",
             "Sinais para olhar o ativo, não conclusões (o dado é o do próprio Informe).", ""]
    for kind in ("cra", "cri"):
        ref = reference[kind]
        events = [e for e in all_events if e["tipo"] == kind.upper()]
        lines += [f"## {kind.upper()}: {ref}", "", "| Evento | Séries |", "|---|---|"]
        counter = Counter(e["evento"] for e in events)
        lines += [f"| {EVENTS[name]} | {counter.get(name, 0)} |" for name in EVENTS]
        months = [m for (k, m) in monthly if k == kind]
        lines += ["", "Últimos meses (séries com o evento):", "",
                  "| Mês | " + " | ".join(EVENTS) + " |", "|---|" + "---|" * len(EVENTS)]
        for month in sorted(months):
            c = monthly[(kind, month)]
            lines.append(f"| {month} | " + " | ".join(str(c.get(name, 0)) for name in EVENTS) + " |")
        important = [e for e in events if e["evento"] in ("entrou_em_atraso", "saldo_caiu_sem_amortizacao", "vencimento_mudou", "taxa_mudou")]
        important.sort(key=lambda e: -Decimal(e["saldo"] or 0))
        lines += ["", f"Maiores saldos com evento relevante em {ref}:", "",
                  "| Evento | ISIN | Certificado | Antes | Depois | Saldo (R$ mi) |", "|---|---|---|---|---|---|"]
        for e in important[: args.top]:
            lines.append(f"| {e['evento']} | {e['isin']} | {e['certificado']} | {e['antes']} | {e['depois']} | "
                         f"{Decimal(e['saldo'] or 0) / 1_000_000:,.1f} |")
        lines.append("")
    (ROOT / "reports" / "market_events.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
