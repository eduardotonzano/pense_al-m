"""Série histórica das demonstrações financeiras do Patrimônio Separado, com confronto com o Informe Mensal.

Lê os fatos reportados (aprovados; com ``--include-pending`` também os pendentes, marcados) e agrupa
nomes equivalentes por ``config/fact_aliases.json``. Para cada data-base de DF, procura o Informe
Mensal vigente da mesma competência e compara os indicadores que têm contrapartida no Informe
(DF em milhares de reais, como publicada; Informe em reais). Só leitura: nada é gravado no banco.

    python scripts/export_df_history.py --cetip CRA022009VM [--include-pending]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--include-pending", action="store_true")
    parser.add_argument("--aliases", type=Path, default=ROOT / "config" / "fact_aliases.json")
    args = parser.parse_args()
    config = json.loads(args.aliases.read_text(encoding="utf-8"))
    tolerance = Decimal(config["comparison_tolerance_brl_mil"])
    statuses = ("approved", "pending") if args.include_pending else ("approved",)
    connection = connect(ROOT / "data" / "cri_cra.db")
    try:
        asset = connection.execute(
            "SELECT asset_id, tipo_ativo FROM assets WHERE codigo_cetip = ?", (args.cetip,)
        ).fetchone()
        if asset is None:
            raise SystemExit("ativo não encontrado")
        facts = connection.execute(
            f"""SELECT f.fact_id, f.fact_name, f.reference_date, f.value, f.unit, f.review_status,
                       f.page_number, d.source_document_id
                FROM reported_facts f
                JOIN document_versions v ON v.version_id = f.document_version_id
                JOIN documents d ON d.document_pk = v.document_id
                WHERE f.asset_id = ? AND f.unit = 'BRL_mil'
                  AND f.review_status IN ({','.join('?' * len(statuses))})""",
            (asset["asset_id"], *statuses),
        ).fetchall()
        rows: dict[tuple[str, str], dict] = {}
        for indicator, names in config["indicators"].items():
            for fact in facts:
                if fact["fact_name"] not in names:
                    continue
                key = (fact["reference_date"], indicator)
                rank = names.index(fact["fact_name"])
                current = rows.get(key)
                if current and current["_rank"] <= rank:
                    continue
                rows[key] = {
                    "_rank": rank, "data_base": fact["reference_date"], "indicador": indicator,
                    "valor_df_mil": fact["value"], "fato": fact["fact_name"], "fact_id": fact["fact_id"],
                    "revisao": fact["review_status"],
                    "fonte": f"doc {fact['source_document_id']} p.{fact['page_number']}",
                }
        counterparts = config["informe_counterparts"].get(asset["tipo_ativo"], {})
        for row in rows.values():
            path = counterparts.get(row["indicador"])
            row.update(informe_competencia="", valor_informe_reais="", diferenca_mil="", confronto="")
            if not path:
                continue
            report = connection.execute(
                """SELECT r.report_id, r.reference_date FROM extracted_reports r
                   WHERE r.asset_id = ? AND r.is_current = 1 AND substr(r.reference_date, 1, 7) = ?""",
                (asset["asset_id"], row["data_base"][:7]),
            ).fetchone()
            if report is None:
                row["confronto"] = "sem Informe vigente na competência"
                continue
            value = connection.execute(
                """SELECT normalized_value, field_state, scale FROM extracted_values
                   WHERE report_id = ? AND xml_path = ? AND instance_key IS NULL""",
                (report["report_id"], path),
            ).fetchone()
            row["informe_competencia"] = report["reference_date"]
            if value is None or value["field_state"] not in ("present_value", "zero"):
                row["confronto"] = f"campo do Informe {value['field_state'] if value else 'ausente'}"
                continue
            informe = _decimal(value["normalized_value"])
            df_value = _decimal(row["valor_df_mil"])
            row["valor_informe_reais"] = str(informe)
            if informe is None or df_value is None:
                row["confronto"] = "valor não numérico"
                continue
            if value["scale"] == "unknown":
                # Regra do projeto: valor com escala suspeita não entra em comparação numérica.
                row["confronto"] = "não comparado: escala do Informe suspeita"
                continue
            difference = (informe / 1000 - df_value).quantize(Decimal("0.001"))
            row["diferenca_mil"] = str(difference)
            row["confronto"] = "confere" if abs(difference) <= tolerance else "diverge"
    finally:
        connection.close()
    ordered = sorted(rows.values(), key=lambda item: (item["data_base"], list(config["indicators"]).index(item["indicador"])))
    columns = ["data_base", "indicador", "valor_df_mil", "revisao", "fato", "fact_id", "fonte",
               "informe_competencia", "valor_informe_reais", "diferenca_mil", "confronto"]
    stem = args.cetip.lower()
    with (ROOT / "reports" / f"{stem}_df_historico.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)
    dates = sorted({row["data_base"] for row in ordered})
    lines = [f"# Série histórica das DFs do Patrimônio Separado: {args.cetip}", "",
             "Gerado por `scripts/export_df_history.py` a partir dos fatos reportados "
             + ("aprovados e pendentes (pendentes marcados com *)" if args.include_pending else "aprovados")
             + "; valores em milhares de reais, como publicados. Nomes equivalentes agrupados por "
             "`config/fact_aliases.json`. Coluna de confronto: Informe Mensal vigente da mesma competência, "
             f"tolerância de {tolerance} mil.", "",
             "| Indicador | " + " | ".join(dates) + " |", "|---|" + "---|" * len(dates)]
    for indicator in config["indicators"]:
        cells = []
        for date in dates:
            row = rows.get((date, indicator))
            if not row:
                cells.append("")
                continue
            mark = "*" if row["revisao"] == "pending" else ""
            check = {"confere": " ✓", "diverge": " ≠", "não": " ?"}.get(row["confronto"].split(" ")[0], "")
            cells.append(f"{row['valor_df_mil']}{mark}{check}")
        if any(cells):
            lines.append(f"| {indicator} | " + " | ".join(cells) + " |")
    divergent = [row for row in ordered if row["confronto"].startswith("diverge")]
    lines += ["", "✓ confere com o Informe; ≠ diverge do Informe; ? não comparado (escala do Informe suspeita). "
              "Detalhe no CSV.", "",
              f"## Divergências com o Informe ({len(divergent)})", ""]
    lines += [f"- {row['data_base']} {row['indicador']}: DF {row['valor_df_mil']} mil ({row['fonte']}) × Informe "
              f"{row['valor_informe_reais']} reais (diferença {row['diferenca_mil']} mil){'' if row['revisao'] == 'approved' else ' — fato pendente'}"
              for row in divergent] or ["- nenhuma"]
    (ROOT / "reports" / f"{stem}_df_historico.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"linhas": len(ordered), "datas": dates, "divergencias": len(divergent)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
