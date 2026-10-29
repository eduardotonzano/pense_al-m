"""Histórico mês a mês de uma emissão no Informe Mensal da CVM (só leitura de data/cvm_open.db).

Uso: market_asset_history.py --isin BRECOACRALJ8   (ou --certificado <código>)
Mostra, por série e mês, situação, saldo, amortização, rendimentos, rentabilidade, vencimento, taxa e rating,
e marca os eventos de crédito entre meses. Gera reports/historico_<código>.md.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.market_checks import balance_is_suspect, money
from credit_assets.market_events import compare


def main() -> int:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--isin")
    target.add_argument("--certificado")
    parser.add_argument("--database", default=str(ROOT / "data" / "cvm_open.db"))
    parser.add_argument("--months", type=int, default=24)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    found = None
    for kind in ("cra", "cri"):
        if args.isin:
            row = connection.execute(
                f"SELECT CNPJ_Emissora, Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE Codigo_ISIN = ? "
                "ORDER BY Data_Referencia DESC LIMIT 1", (args.isin.upper(),)).fetchone()
        else:
            row = connection.execute(
                f"SELECT CNPJ_Emissora, Codigo_Identificacao_Certificado FROM {kind}_classe_vigente "
                "WHERE Codigo_Identificacao_Certificado = ? LIMIT 1", (args.certificado,)).fetchone()
        if row:
            found = (kind, row["CNPJ_Emissora"], row["Codigo_Identificacao_Certificado"])
            break
    if found is None:
        print("emissão não encontrada na base da CVM")
        return 1
    kind, cnpj, cert = found
    # inclui códigos-irmãos: outros certificados da mesma securitizadora com algum ISIN em comum
    isins = [r[0] for r in connection.execute(
        f"SELECT DISTINCT Codigo_ISIN FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado = ? AND Codigo_ISIN <> ''", (cert,))]
    codes = {cert} | {r[0] for r in connection.execute(
        f"SELECT DISTINCT Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE CNPJ_Emissora = ? AND Codigo_ISIN IN "
        f"({','.join('?' * len(isins))})", (cnpj, *isins))} if isins else {cert}
    rows = [dict(r) for r in connection.execute(
        f"SELECT * FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado IN ({','.join('?' * len(codes))}) "
        "ORDER BY Codigo_ISIN, Numero_Serie, Data_Referencia", tuple(codes))]
    geral = connection.execute(
        f"SELECT Companhia_Emissora, Nome_Emissao, Numero_Emissao, Data_Emissao FROM {kind}_geral_vigente "
        f"WHERE Codigo_Identificacao_Certificado IN ({','.join('?' * len(codes))}) ORDER BY Data_Referencia DESC LIMIT 1",
        tuple(codes)).fetchone()
    connection.close()

    lines = [f"# Histórico do Informe Mensal: {cert} ({kind.upper()})", "",
             f"{geral['Companhia_Emissora']} | {geral['Nome_Emissao']} | emissão {geral['Numero_Emissao']} de {geral['Data_Emissao']}" if geral else "",
             f"Códigos do certificado na base: {', '.join(sorted(codes))}. Fonte: dados abertos da CVM (versão vigente de cada mês).", ""]
    by_series: dict[str, list[dict]] = {}
    for row in rows:
        key = row["Codigo_ISIN"] or f"série {row['Numero_Serie']}"
        by_series.setdefault(key, [])
        # um registro por mês (o código-irmão pode repetir o mesmo mês)
        if not by_series[key] or by_series[key][-1]["Data_Referencia"] != row["Data_Referencia"]:
            by_series[key].append(row)
    rentab = "Rentabilidade"
    for key, series in by_series.items():
        series = series[-args.months:]
        first = series[-1]
        lines += [f"## {key} (série {first['Numero_Serie']}, {first.get('Classe') or '-'})", "",
                  "| Mês | Situação | Saldo (R$ mi) | Amortização | Rendimentos | Rentab. | Vencimento | Taxa | Rating | Eventos |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        previous = None
        for row in series:
            events = ", ".join(compare(previous, row)) if previous else ""
            balance = money(row.get("Valor_Certificados"))
            shown = f"{balance / 1_000_000:,.2f}" + (" ⚠" if balance_is_suspect(row) else "")
            lines.append(f"| {row['Data_Referencia'][:7]} | {row.get('Situacao') or '-'} | {shown} | "
                         f"{money(row.get('Amortizacoes')):,.0f} | {money(row.get('Rendimentos')):,.0f} | {row.get(rentab) or '-'} | "
                         f"{(row.get('Data_Vencimento') or '-')[:10]} | {row.get('Taxa_Juros') or '-'} | "
                         f"{row.get('Classificacao_Risco_Atual') or '-'} | {events} |")
            previous = row
        lines.append("")
    lines.append("⚠ = saldo mais de 20 vezes o integralizado (provável erro de preenchimento).")
    out = ROOT / "reports" / f"historico_{cert.lower()}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:30]))
    print(f"... gravado em {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
