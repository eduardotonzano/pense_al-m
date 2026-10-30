"""Placar por securitizadora: pontualidade e qualidade do Informe Mensal e situação da carteira (só leitura).

Fonte: data/cvm_open.db. Janela: últimos 12 meses completos. Gera reports/market_securitizadoras.{md,csv}.
Prazo de referência de entrega: 30 dias após o fim do mês de competência (conferir na Res. CVM 60 antes de
usar como descumprimento; aqui é só régua de comparação entre securitizadoras).
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import statistics
import sys
from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.debtor_exposure import classify_identifier
from credit_assets.market_checks import fold, reference_competence, series_flags, trusted_balance

DEADLINE_DAYS = 30


def delivery_delay(reference: str, delivered: str) -> int | None:
    try:
        year, month = int(reference[:4]), int(reference[5:7])
        end = date(year, month, monthrange(year, month)[1])
        return (date.fromisoformat(delivered[:10]) - end).days
    except (ValueError, TypeError):
        return None


def window_start(month: str, n: int) -> str:
    year, mon = int(month[:4]), int(month[5:7]) - (n - 1)
    while mon <= 0:
        year, mon = year - 1, mon + 12
    return f"{year:04d}-{mon:02d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--min-emissions", type=int, default=5)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    board: dict[str, dict] = defaultdict(lambda: {
        "nome": "", "tipos": set(), "informes": 0, "atrasos_entrega": [], "reenvios": 0, "emissoes": set(),
        "series_ref": 0, "flags_cadastro": 0, "saldo": Decimal(0), "saldo_atraso": Decimal(0),
        "devedor_vinculos": 0, "devedor_nao_informado": 0, "devedor_cnpj_invalido": 0,
    })
    refs = {}
    for kind in ("cra", "cri"):
        counts = {r[0]: r[1] for r in connection.execute(
            f"SELECT Data_Referencia, COUNT(DISTINCT Codigo_Identificacao_Certificado) FROM {kind}_geral_vigente GROUP BY 1")}
        ref = reference_competence(counts)
        refs[kind] = ref[:7]
        start = window_start(ref[:7], args.months)
        # todas as versões entregues na janela (reenvio = versão > 1), só arquivos vigentes
        for row in connection.execute(
            f"""SELECT g.CNPJ_Emissora, g.Companhia_Emissora, g.Codigo_Identificacao_Certificado, g.Data_Referencia,
                       g.Versao, g.Data_Entrega
                FROM {kind}_geral g JOIN source_files f ON f.file_id = g._file_id
                WHERE f.is_current = 1 AND substr(g.Data_Referencia, 1, 7) BETWEEN ? AND ?""", (start, ref[:7])):
            item = board[row["CNPJ_Emissora"]]
            item["nome"] = item["nome"] or (row["Companhia_Emissora"] or "")
            item["tipos"].add(kind.upper())
            if (row["Versao"] or "1").strip() not in ("", "1"):
                item["reenvios"] += 1
                continue
            item["informes"] += 1
            item["emissoes"].add(row["Codigo_Identificacao_Certificado"])
            delay = delivery_delay(row["Data_Referencia"], row["Data_Entrega"] or "")
            if delay is not None:
                item["atrasos_entrega"].append(delay)
        for row in connection.execute(f"SELECT * FROM {kind}_classe_vigente WHERE Data_Referencia = ?", (ref,)):
            row = dict(row)
            item = board[row["CNPJ_Emissora"]]
            item["series_ref"] += 1
            flags = [f for f in series_flags(row, ref) if f in ("vencimento_fora_mes_base", "serie_sem_isin", "isin_invalido",
                                                                 "vencido_com_saldo_adimplente")]
            item["flags_cadastro"] += bool(flags)
            balance = trusted_balance(row)
            item["saldo"] += balance
            if fold(row.get("Situacao")) == "em atraso":
                item["saldo_atraso"] += balance
        for row in connection.execute(
            f"""SELECT t.CNPJ_Emissora, t.CNPJ FROM {kind}_cedente_devedor t JOIN source_files f ON f.file_id = t._file_id
                WHERE f.is_current = 1 AND t.Tipo = 'Devedor' AND substr(t.Data_Referencia, 1, 7) = ?""", (ref[:7],)):
            item = board[row["CNPJ_Emissora"]]
            item["devedor_vinculos"] += 1
            kind_of_id, _ = classify_identifier(row["CNPJ"])
            item["devedor_nao_informado"] += kind_of_id == "nao_informado"
            item["devedor_cnpj_invalido"] += kind_of_id == "invalido"
    connection.close()

    rows = []
    for cnpj, item in board.items():
        if len(item["emissoes"]) < args.min_emissions:
            continue
        delays = item["atrasos_entrega"]
        late = sum(1 for d in delays if d > DEADLINE_DAYS)
        rows.append({
            "cnpj": cnpj, "nome": item["nome"].strip()[:45], "tipos": "/".join(sorted(item["tipos"])),
            "emissoes": len(item["emissoes"]), "informes": item["informes"],
            "atraso_mediano_dias": statistics.median(delays) if delays else None,
            "pct_entregue_apos_30d": round(100 * late / len(delays), 1) if delays else None,
            "reenvios_por_100_informes": round(100 * item["reenvios"] / max(1, item["informes"]), 1),
            "pct_series_com_erro_cadastral": round(100 * item["flags_cadastro"] / max(1, item["series_ref"]), 1),
            "pct_devedor_nao_informado": round(100 * item["devedor_nao_informado"] / item["devedor_vinculos"], 1)
            if item["devedor_vinculos"] else None,
            "pct_devedor_cnpj_invalido": round(100 * item["devedor_cnpj_invalido"] / item["devedor_vinculos"], 1)
            if item["devedor_vinculos"] else None,
            "saldo_mi": round(item["saldo"] / 1_000_000, 1),
            "pct_saldo_em_atraso": round(100 * item["saldo_atraso"] / item["saldo"], 1) if item["saldo"] else None,
        })
    rows.sort(key=lambda r: -r["saldo_mi"])
    with (ROOT / "reports" / "market_securitizadoras.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    fmt = lambda v: "-" if v is None else (f"{v:,.1f}" if isinstance(v, float) else str(v))
    lines = ["# Placar por securitizadora (CRA e CRI)", "",
             f"Fonte: Informe Mensal (dados abertos da CVM). Janela de {args.months} meses até CRA {refs['cra']} / CRI {refs['cri']}; "
             f"securitizadoras com pelo menos {args.min_emissions} emissões informadas.",
             f"Prazo de referência de entrega: {DEADLINE_DAYS} dias após o fim do mês (régua de comparação; conferir na norma antes de "
             "tratar como descumprimento). Erro cadastral = vencimento fora do mês-base, série sem ISIN, ISIN inválido ou vencido com "
             "saldo e adimplente. Devedor não informado = CNPJ vazio, \"0\" ou \"NA\"; CNPJ inválido = dígitos verificadores não batem (CPF de pessoa física não conta como inválido).", "",
             "| Securitizadora | Tipos | Emissões | Saldo (R$ mi) | % saldo em atraso | Atraso mediano de entrega (dias) | "
             "% entregue após 30 dias | reenvios por 100 informes | % séries com erro cadastral | % devedor não informado | "
             "% CNPJ de devedor inválido |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['nome']} | {r['tipos']} | {r['emissoes']} | {r['saldo_mi']:,.1f} | {fmt(r['pct_saldo_em_atraso'])} | "
                     f"{fmt(r['atraso_mediano_dias'])} | {fmt(r['pct_entregue_apos_30d'])} | {fmt(r["reenvios_por_100_informes"])} | "
                     f"{fmt(r['pct_series_com_erro_cadastral'])} | {fmt(r['pct_devedor_nao_informado'])} | {fmt(r['pct_devedor_cnpj_invalido'])} |")
    (ROOT / "reports" / "market_securitizadoras.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
