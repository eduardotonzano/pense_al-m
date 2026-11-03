"""Situação das operações no portal da Riza × situação das séries no Informe Mensal da CVM (só leitura).

A Riza marca cada operação como "Em Andamento", "Em Estruturação" ou "Default" no portal do investidor. Operação em
"Default" no portal e "Adimplente" no Informe da CVM é divergência entre fontes: alerta para leitura, não conclusão
(o portal é a fonte de menor prioridade e não diz desde quando nem por quê).

    python scripts/riza_status_vs_cvm.py
Gera reports/riza_status_vs_cvm.{md,csv}.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.riza_portal import RizaPortal


def cvm_situation(path: Path) -> dict[str, tuple[str, str, str]]:
    """código (CETIP ou ISIN) → (competência mais recente, situação, saldo dos certificados) da série no Informe vigente."""

    latest: dict[str, tuple[str, str, str]] = {}
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    for kind in ("cra", "cri"):
        for code, isin, ref, situation, balance in connection.execute(
                f"SELECT Codigo_CETIP, Codigo_ISIN, Data_Referencia, Situacao, Valor_Certificados FROM {kind}_classe_vigente"):
            for key in (code, isin):
                if key and (key not in latest or ref > latest[key][0]):
                    latest[key] = (ref, situation or "", balance or "")
    connection.close()
    return latest


def main() -> int:
    operations = RizaPortal(min_interval_seconds=0.5).operations()
    latest = cvm_situation(ROOT / "data" / "cvm_open.db")
    rows = []
    for op in operations:
        for series in op.get("series") or []:
            code = series.get("instrumentCode") or ""
            ref, situation, balance = latest.get(code, ("", "sem dado na CVM", ""))
            rows.append({"operacao": op["id"], "tipo": op.get("type"), "apelido": op.get("alias"), "emissao": op.get("issuanceNumber"),
                         "status_riza": op.get("status"), "serie": series.get("number"), "codigo_cetip": code,
                         "status_serie_riza": series.get("status"), "competencia_cvm": ref, "situacao_cvm": situation,
                         "saldo_cvm": balance})
    with (ROOT / "reports" / "riza_status_vs_cvm.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    by_op: dict[str, dict] = {}
    for r in rows:
        item = by_op.setdefault(r["operacao"], {**r, "series": [], "atraso": False})
        item["series"].append(r["codigo_cetip"])
        item["atraso"] |= "atraso" in r["situacao_cvm"].lower()
    table = Counter((o["status_riza"], "Em atraso" if o["atraso"] else o["situacao_cvm"] or "vazio") for o in by_op.values())
    divergent = sorted((o for o in by_op.values() if o["status_riza"] == "Default" and not o["atraso"]),
                       key=lambda o: o["operacao"])
    lines = ["# Situação no portal da Riza × Informe Mensal da CVM", "",
             "Portal do investidor da Riza (API pública) contra a série mais recente do Informe Mensal (dados abertos da CVM). "
             "Divergência é alerta para leitura: o portal é a fonte de menor prioridade e não informa a data nem o motivo do "
             "\"Default\".", "", "| Portal da Riza | Informe da CVM | Operações |", "|---|---|---|",
             *[f"| {a} | {b} | {n} |" for (a, b), n in sorted(table.items(), key=lambda kv: -kv[1])], "",
             f"## \"Default\" no portal e sem atraso no Informe ({len(divergent)})", "",
             "| Operação | Tipo | Emissão | Séries (CETIP) | Informe da CVM | Competência |", "|---|---|---|---|---|---|"]
    lines += [f"| {o['operacao']} | {o['tipo']} | {o['emissao']} | {', '.join(o['series'][:4])} | {o['situacao_cvm'] or 'vazio'} | "
              f"{o['competencia_cvm']} |" for o in divergent]
    (ROOT / "reports" / "riza_status_vs_cvm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(dict(table))
    print(len(divergent), "operações em Default no portal sem atraso no Informe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
