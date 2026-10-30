"""Confere os dados abertos da CVM contra a nossa extração do XML dos pilotos (só leitura).

Para cada informe vigente dos ativos do catálogo, compara por série os valores que existem nas duas
fontes. Serve para saber se a base da CVM pode ser a fonte do Informe em escala.
Gera reports/cvm_vs_xml.{md,csv}.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# campo do XML (final do xml_path, bloco de séries)  ->  coluna da base da CVM
FIELDS = {
    "QtdCertificadosPorClasse": "Quantidade_Certificados",
    "VlrCertificadosPorClasse": "Valor_Certificados",
    "RentabilidadePeriodo": "Rentabilidade",
    "AmortizacoesRealizadasPeriodo": "Amortizacoes",
    "RendimentosDistribuidosPeriodo": "Rendimentos",
}
TOLERANCE = Decimal("0.01")


def to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value).strip().replace(",", ".")) if str(value).strip() else None
    except InvalidOperation:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=str(ROOT / "data" / "cri_cra.db"))
    parser.add_argument("--cvm", default=str(ROOT / "data" / "cvm_open.db"))
    args = parser.parse_args()
    catalog = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)
    catalog.row_factory = sqlite3.Row
    cvm = sqlite3.connect(f"file:{args.cvm}?mode=ro", uri=True)
    cvm.row_factory = sqlite3.Row

    stats: dict[tuple[str, str], Counter] = defaultdict(Counter)
    samples: list[dict] = []
    rows_out: list[dict] = []
    for asset in catalog.execute("SELECT asset_id, codigo_cetip, isin, tipo_ativo FROM assets WHERE isin IS NOT NULL"):
        kind = asset["tipo_ativo"].lower()
        cert = cvm.execute(
            f"SELECT Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE Codigo_ISIN = ? LIMIT 1",
            (asset["isin"],),
        ).fetchone()
        if cert is None:
            stats[(asset["codigo_cetip"], "ativo")]["ausente_na_cvm"] += 1
            continue
        cvm_rows = {
            (r["Data_Referencia"][:7], str(r["Numero_Serie"]).strip()): r for r in cvm.execute(
                f"SELECT * FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado = ?", (cert[0],))
        }
        reports = catalog.execute(
            "SELECT report_id, reference_date FROM extracted_reports WHERE asset_id = ? AND is_current = 1", (asset["asset_id"],)
        ).fetchall()
        for report in reports:
            month = report["reference_date"][:7]
            for value in catalog.execute(
                """SELECT xml_path, instance_key, original_value FROM extracted_values
                   WHERE report_id = ? AND xml_path LIKE '%DetalhesSeries/Series/Serie/%'""", (report["report_id"],)):
                field = value["xml_path"].rsplit("/", 1)[-1]
                if field not in FIELDS:
                    continue
                key = (month, str(value["instance_key"]).strip())
                counter = stats[(asset["codigo_cetip"], field)]
                if key not in cvm_rows:
                    counter["sem_linha_na_cvm"] += 1
                    continue
                ours, theirs = to_decimal(value["original_value"]), to_decimal(cvm_rows[key][FIELDS[field]])
                if ours is None and theirs is None:
                    counter["ambos_vazios"] += 1
                    continue
                if ours is None or theirs is None:
                    counter["so_um_lado_preenchido"] += 1
                    verdict = "so_um_lado"
                elif abs(ours - theirs) <= TOLERANCE * max(Decimal(1), abs(theirs)) / 100:
                    counter["iguais"] += 1
                    continue
                else:
                    counter["diferentes"] += 1
                    verdict = "diferente"
                row = {"ativo": asset["codigo_cetip"], "mes": month, "serie": value["instance_key"], "campo": field,
                       "xml": value["original_value"], "cvm": cvm_rows[key][FIELDS[field]], "resultado": verdict}
                rows_out.append(row)
    catalog.close(); cvm.close()

    with (ROOT / "reports" / "cvm_vs_xml.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ativo", "mes", "serie", "campo", "xml", "cvm", "resultado"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows_out)
    lines = ["# Base da CVM × nossa extração do XML (pilotos)", "",
             "Compara, por informe vigente e série, os campos que existem nas duas fontes (tolerância de 0,01%). Só leitura.", "",
             "| Ativo | Campo | Iguais | Diferentes | Só um lado | Sem linha na CVM | Ambos vazios |", "|---|---|---|---|---|---|---|"]
    total = Counter()
    for (asset, field), counter in sorted(stats.items()):
        total.update(counter)
        lines.append(f"| {asset} | `{field}` | {counter['iguais']} | {counter['diferentes']} | {counter['so_um_lado_preenchido']} | "
                     f"{counter['sem_linha_na_cvm']} | {counter['ambos_vazios']} |")
    compared = total["iguais"] + total["diferentes"]
    lines += ["", f"**Total comparado:** {compared} valores; iguais {total['iguais']} "
                  f"({100 * total['iguais'] / compared:.1f}%), diferentes {total['diferentes']}, só um lado {total['so_um_lado_preenchido']}."
              if compared else "", "", "Diferenças e casos de um lado só: `reports/cvm_vs_xml.csv`."]
    (ROOT / "reports" / "cvm_vs_xml.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
