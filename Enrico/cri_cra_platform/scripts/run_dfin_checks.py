"""Sinais das DFs dos patrimônios separados no mercado inteiro (só leitura de data/cvm_dfin.db e data/cvm_open.db).

Por certificado: opinião do auditor da DF mais recente (ressalva, abstenção, adversa), piora em relação à anterior,
entrega depois de 90 dias da data-base e emissões com Informe recente e saldo, mas sem DF nos últimos 15 meses.
Só conta emissões vivas (Informe na competência de referência com saldo); as demais ficam fora da contagem.
O prazo de 90 dias é parâmetro de triagem, não a regra da norma; a distribuição dos dias de entrega sai no relatório.
Gera reports/market_dfin.{md,csv}. Rodar depois de ingest_cvm_dfin.py --commit.
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

from credit_assets.dfin_checks import delivery_days, latest_by_certificate, signals
from credit_assets.market_checks import fold, reference_competence, trusted_balance

LABELS = {"df_com_ressalva": "DF com ressalva", "df_abstencao_ou_adversa": "DF com abstenção ou opinião adversa",
          "opiniao_piorou": "Opinião piorou em relação à DF anterior", "df_entregue_apos_prazo": "DF entregue mais de 90 dias após a data-base (parâmetro de triagem, não a regra da norma)",
          "sem_df_recente": "Informe recente e saldo, mas sem DF nos últimos 15 meses"}

DELAY_BANDS = [(90, "até 90"), (120, "91 a 120"), (180, "121 a 180"), (10**6, "mais de 180")]


def months_before(month: str, n: int) -> str:
    year, mon = int(month[:4]), int(month[5:7]) - n
    while mon <= 0:
        year, mon = year - 1, mon + 12
    return f"{year:04d}-{mon:02d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dfin", default=str(ROOT / "data" / "cvm_dfin.db"))
    parser.add_argument("--cvm", default=str(ROOT / "data" / "cvm_open.db"))
    args = parser.parse_args()
    if not Path(args.dfin).is_file():
        print("data/cvm_dfin.db não existe: rode scripts/ingest_cvm_dfin.py --dry-run e depois --commit")
        return 2
    dfin = sqlite3.connect(f"file:{args.dfin}?mode=ro", uri=True)
    dfin.row_factory = sqlite3.Row
    cvm = sqlite3.connect(f"file:{args.cvm}?mode=ro", uri=True)
    cvm.row_factory = sqlite3.Row
    out_rows, summary = [], {}
    for kind in ("cra", "cri"):
        rows = [dict(r) for r in dfin.execute(
            f"SELECT t.* FROM dfin_{kind} t JOIN source_files f ON f.file_id = t._file_id WHERE f.is_current = 1")]
        history = latest_by_certificate(rows)
        counts = {r[0]: r[1] for r in cvm.execute(
            f"SELECT Data_Referencia, COUNT(DISTINCT Codigo_Identificacao_Certificado) FROM {kind}_geral_vigente GROUP BY 1")}
        reference = reference_competence(counts)
        current = {}
        for r in cvm.execute(f"SELECT * FROM {kind}_classe_vigente WHERE Data_Referencia = ?", (reference,)):
            r = dict(r)
            item = current.setdefault(r["Codigo_Identificacao_Certificado"], {"saldo": Decimal(0), "atraso": False,
                                                                                "emissora": r["CNPJ_Emissora"]})
            item["saldo"] += trusted_balance(r)
            item["atraso"] = item["atraso"] or fold(r.get("Situacao")) == "em atraso"
        emitted = {r[0]: (r[1] or "")[:7] for r in cvm.execute(
            f"SELECT Codigo_Identificacao_Certificado, MIN(Data_Emissao) FROM {kind}_geral_vigente GROUP BY 1")}
        names = {r[0]: r[1] for r in cvm.execute(
            f"SELECT Codigo_Identificacao_Certificado, Nome_Emissao FROM {kind}_geral_vigente WHERE Data_Referencia = ?", (reference,))}
        limit = months_before(reference[:7], 15)
        found, delays, outside = Counter(), Counter(), 0
        for cert, items in history.items():
            info = current.get(cert)
            if not info or info["saldo"] <= 0:
                outside += 1
                continue
            last = items[0]
            days = delivery_days(last.get("Data_Referencia") or "", last.get("Data_Entrega") or "")
            if days is not None:
                delays[next(label for limit_days, label in DELAY_BANDS if days <= limit_days)] += 1
            flags = signals(items)
            if not flags:
                continue
            for flag in flags:
                found[flag] += 1
            out_rows.append({"tipo": kind.upper(), "certificado": cert, "emissao": names.get(cert, last.get("Nome_Certificado", ""))[:70],
                             "securitizadora": last.get("Nome_Emissora", ""), "data_base": last.get("Data_Referencia", "")[:10],
                             "entrega": last.get("Data_Entrega", "")[:10], "parecer": last.get("Parecer_Auditor", ""),
                             "sinais": "; ".join(flags), "saldo_brl": f"{info.get('saldo', Decimal(0)):.2f}",
                             "em_atraso": int(bool(info.get("atraso"))), "link": last.get("Link_Download", "")})
        for cert, info in current.items():
            if info["saldo"] <= 0 or (emitted.get(cert) or "9999") > limit:
                continue
            recent = [h for h in history.get(cert, []) if (h.get("Data_Referencia") or "")[:7] >= limit]
            if not recent:
                found["sem_df_recente"] += 1
                out_rows.append({"tipo": kind.upper(), "certificado": cert, "emissao": names.get(cert, "")[:70], "securitizadora": "",
                                 "data_base": (history.get(cert) or [{}])[0].get("Data_Referencia", "")[:10], "entrega": "",
                                 "parecer": "", "sinais": "sem_df_recente", "saldo_brl": f"{info['saldo']:.2f}",
                                 "em_atraso": int(info["atraso"]), "link": ""})
        summary[kind] = {"dfs": len(rows), "certificados": len(history), "referencia": reference[:7], "sinais": found,
                         "fora": outside, "prazos": delays}
    dfin.close()
    cvm.close()

    fields = ["tipo", "certificado", "emissao", "securitizadora", "data_base", "entrega", "parecer", "sinais", "saldo_brl", "em_atraso", "link"]
    with (ROOT / "reports" / "market_dfin.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(out_rows)
    lines = ["# Demonstrações financeiras dos patrimônios separados (CRA e CRI)", "",
             "Fonte: índice de DFs dos dados abertos da CVM (opinião do auditor como informada) e Informe Mensal. Triagem: ler o relatório do auditor.", ""]
    for kind, info in summary.items():
        lines += [f"## {kind.upper()}", "", f"- {info['dfs']} DFs de {info['certificados']} certificados; Informe de referência {info['referencia']}.",
                  f"- {info['certificados'] - info['fora']} com Informe e saldo na referência (contados abaixo); {info['fora']} encerrados ou sem "
                  "Informe recente ficam fora.", "", "| Sinal (emissões vivas) | Certificados |", "|---|---|"]
        lines += [f"| {LABELS[k]} | {info['sinais'].get(k, 0)} |" for k in LABELS]
        lines += ["", "| Dias entre a data-base e a entrega da DF mais recente | Certificados |", "|---|---|"]
        lines += [f"| {label} | {info['prazos'].get(label, 0)} |" for _, label in DELAY_BANDS]
        lines.append("")
    serious = [r for r in out_rows if "ressalva" in r["sinais"] or "abstencao" in r["sinais"]]
    serious.sort(key=lambda r: -Decimal(r["saldo_brl"]))
    lines += ["## DFs com ressalva, abstenção ou opinião adversa (maior saldo primeiro)", "",
              "| Tipo | Certificado | Emissão | Data-base | Parecer | Em atraso | Saldo (R$ mi) | DF |", "|---|---|---|---|---|---|---|---|"]
    for r in serious[:60]:
        lines.append(f"| {r['tipo']} | {r['certificado']} | {r['emissao'][:50]} | {r['data_base']} | {r['parecer']} | "
                     f"{'sim' if r['em_atraso'] else ''} | {Decimal(r['saldo_brl']) / 1_000_000:,.1f} | [abrir]({r['link']}) |")
    (ROOT / "reports" / "market_dfin.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
