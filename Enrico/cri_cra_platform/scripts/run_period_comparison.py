from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect, initialize_database
from credit_assets.services.period_comparison_service import compare_asset

R = "/InformeMensalCRA"
# Indicadores do handoff (saldo, carteira, inadimplência, garantias, caixa,
# pagamentos, situação). Fundo de reserva não existe como campo neste leiaute.
INDICATORS = {
    "saldo_certificados": R + "/DetalhesSeries/totalVlrCertificados",
    "carteira_direitos_creditorios": R + "/Ativo/DireitosCreditorios/@total",
    "a_vencer_sem_atraso": R + "/Ativo/DireitosCreditorios/DirCredAVencerSemParcelasAtraso",
    "a_vencer_com_atraso": R + "/Ativo/DireitosCreditorios/DirCredAVencerComParcelasAtraso",
    "vencidos_nao_pagos": R + "/Ativo/DireitosCreditorios/DirCredVencidosNaoPagos",
    "parcelas_em_atraso": R + "/InfoDireitosCreditoriosAgro/VlrTotalParcelasAtraso",
    "provisao_recuperacao": R + "/Ativo/ProvisaoRecuperacaoDireitosCreditorios",
    "garantias": R + "/InfoDireitosCreditoriosAgro/OutrasInfoDireitosCreditoriosAReceber/VlrTotalGarantias",
    "caixa_equivalentes": R + "/Ativo/CaixaEquivalentes/@total",
    "pagamentos_senior": R + "/FluxoCaixaLiquidoMes/PgtosEfetuadosClasseSenior/@total",
    "patrimonio_liquido": R + "/VlrPatrimonioLiquidoEmissao",
    "maior_devedor_fracao": R + "/InfoDireitosCreditoriosAgro/ConcentracaoEmissaoPorGrupoDevedor/MaiorDevedor",
}
PER_SERIES = {
    "situacao": R + "/DadosGerais/Series/Serie/Situacao",
    "rentabilidade_fracao": R + "/DetalhesSeries/Series/Serie/RentabilidadePeriodo",
    "valor_serie": R + "/DetalhesSeries/Series/Serie/VlrCertificadosPorClasse",
}


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def indicator_series(connection, asset_id: int) -> tuple[list[dict], list[str]]:
    reports = connection.execute(
        """SELECT r.report_id, substr(r.reference_date, 1, 7) AS month, r.reference_date,
                  r.source_version, d.source_document_id
           FROM extracted_reports r JOIN documents d ON d.document_pk = r.document_id
           WHERE r.asset_id = ? AND r.is_current = 1 ORDER BY month""",
        (asset_id,),
    ).fetchall()
    keys = sorted({
        row[0] for row in connection.execute(
            """SELECT DISTINCT v.instance_key FROM extracted_values v
               JOIN extracted_reports r USING (report_id)
               WHERE r.asset_id = ? AND r.is_current = 1 AND v.xml_path = ?
                 AND v.instance_key IS NOT NULL""",
            (asset_id, PER_SERIES["situacao"]),
        )
    }, key=lambda key: int(key) if key.isdigit() else key)
    columns = ["competencia_mes", "reference_date", "source_version", "source_document_id",
               "escala_monetaria", *INDICATORS]
    columns += [f"{name}_serie_{key}" for key in keys for name in PER_SERIES]
    rows = []
    for report in reports:
        values = {
            (v["xml_path"], v["instance_key"]): v
            for v in connection.execute(
                """SELECT xml_path, instance_key, normalized_value, field_state, scale
                   FROM extracted_values WHERE report_id = ?""",
                (report["report_id"],),
            )
        }
        scale_unknown = any(v["scale"] == "unknown" for v in values.values())
        row = {
            "competencia_mes": report["month"],
            "reference_date": report["reference_date"],
            "source_version": report["source_version"],
            "source_document_id": report["source_document_id"],
            "escala_monetaria": "suspeita (fora das comparações R$)" if scale_unknown else "reais",
        }

        def show(value):
            if value is None:
                return ""
            if value["field_state"] == "absent":
                return "[ausente]"
            if value["field_state"] == "present_empty":
                return "[vazio]"
            return value["normalized_value"]

        for name, path in INDICATORS.items():
            row[name] = show(values.get((path, None)))
        for key in keys:
            for name, path in PER_SERIES.items():
                row[f"{name}_serie_{key}"] = show(values.get((path, key)))
        rows.append(row)
    return rows, columns


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cetip", required=True)
    parser.add_argument("--isin", required=True)
    args = parser.parse_args()
    connection = connect(ROOT / "data" / "cri_cra.db")
    initialize_database(connection)
    try:
        asset = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (args.cetip, args.isin),
        ).fetchone()
        if asset is None:
            raise SystemExit("ativo não encontrado")
        summary = compare_asset(connection, asset["asset_id"])
        changes = [dict(row) for row in connection.execute(
            """SELECT current_month, previous_month, replace(xml_path, ?, '') AS campo,
                      instance_key AS serie, data_type, previous_value, current_value,
                      previous_state, current_state, absolute_change, relative_change,
                      comparison_status
               FROM period_comparisons
               WHERE comparison_run_id = ? AND comparison_status IN ('changed', 'state_changed')
               ORDER BY current_month, campo, serie""",
            (R, summary["comparison_run_id"]),
        )]
        stem = args.cetip.lower()
        write_csv(ROOT / "reports" / f"{stem}_mudancas_entre_periodos.csv", changes,
                  list(changes[0]) if changes else ["current_month"])
        rows, columns = indicator_series(connection, asset["asset_id"])
        write_csv(ROOT / "reports" / f"{stem}_serie_indicadores.csv", rows, columns)
    finally:
        connection.close()
    print(json.dumps({**summary, "changed_rows": len(changes), "indicator_months": len(rows)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
