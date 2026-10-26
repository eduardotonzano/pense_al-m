"""Alertas contratuais: parâmetros aprovados do Termo × fatos reportados.

Só usa ``contract_parameters`` com ``review_status = 'approved'``; parâmetro
ausente ou não aprovado interrompe a regra (nunca é presumido). Fatos vêm de
``reported_facts`` (trecho literal conferido) e de relatórios vigentes do
Informe Mensal. Toda avaliação é devolvida, inclusive as conformes, para que a
ausência de alerta também seja rastreável.
"""
from __future__ import annotations

import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from credit_assets.services.data_quality_alerts_service import upsert_alert

DETECTOR_VERSION = "0.1.0"


class ParameterNotApproved(ValueError):
    pass


def approved_parameters(connection, asset_id) -> dict[str, sqlite3.Row]:
    return {
        row["parameter_name"]: row
        for row in connection.execute(
            """SELECT parameter_name, parameter_value, unit, source_reference
               FROM contract_parameters WHERE asset_id = ? AND review_status = 'approved'""",
            (asset_id,),
        )
    }


def _parameter(parameters, name) -> Decimal:
    if name not in parameters:
        raise ParameterNotApproved(f"parâmetro {name} ausente ou não aprovado")
    return Decimal(parameters[name]["parameter_value"])


def facts_by_date(connection, asset_id) -> dict[str, dict[str, list[sqlite3.Row]]]:
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in connection.execute(
        """SELECT f.fact_name, f.reference_date, f.value, f.unit, f.page_number, d.source_document_id
           FROM reported_facts f
           JOIN document_versions v ON v.version_id = f.document_version_id
           JOIN documents d ON d.document_pk = v.document_id
           WHERE f.asset_id = ? AND f.review_status <> 'rejected'""",
        (asset_id,),
    ):
        grouped[row["reference_date"]][row["fact_name"]].append(row)
    return grouped


def _source(row) -> str:
    return f"{row['source_document_id']} p.{row['page_number']}"


def cessao_fiduciaria_minima(facts, parameters, rule) -> list[dict]:
    minimum = _parameter(parameters, rule["parameter"])
    evaluations = []
    for date, names in sorted(facts.items()):
        if date[5:7] not in rule["months"] or rule["fact"] not in names:
            continue
        row = names[rule["fact"]][0]
        value = Decimal(row["value"])
        evaluations.append({
            "month": date[:7], "instance_key": None, "compliant": value >= minimum,
            "message": f"Cessão Fiduciária R$ {value:,.2f} em {date} {'≥' if value >= minimum else 'abaixo do'} mínimo de R$ {minimum:,.2f}.",
            "evidence": {"valor": str(value), "minimo": str(minimum), "data_base": date,
                         "fonte_fato": _source(row),
                         "fonte_parametro": parameters[rule["parameter"]]["source_reference"]},
        })
    return evaluations


def razao_garantia_minima(facts, parameters, rule) -> list[dict]:
    evaluations = []
    for date, names in sorted(facts.items()):
        needed = rule["numerator_facts"] + [rule["denominator_fact"]]
        if not all(name in names for name in needed):
            continue
        parameter_name = rule["parameters"]["01-08" if int(date[5:7]) <= 8 else "09-12"]
        minimum = _parameter(parameters, parameter_name)
        numerator = sum((Decimal(names[n][0]["value"]) for n in rule["numerator_facts"]), Decimal(0))
        denominator = Decimal(names[rule["denominator_fact"]][0]["value"])
        ratio = numerator / denominator
        evaluations.append({
            "month": date[:7], "instance_key": None, "compliant": ratio >= minimum,
            "message": f"Razão de Garantia {ratio:.2%} em {date} (mínimo {minimum:.0%}).",
            "evidence": {"razao": str(ratio.quantize(Decimal('0.0001'))), "minimo": str(minimum),
                         "numerador": str(numerator), "denominador": str(denominator), "data_base": date,
                         "fontes": sorted({_source(names[n][0]) for n in needed}),
                         "parametro": parameter_name},
        })
    return evaluations


def _informe_amount(connection, asset_id, month, path) -> tuple[Decimal | None, Any]:
    row = connection.execute(
        """SELECT v.normalized_value, v.scale, r.report_id
           FROM extracted_reports r JOIN extracted_values v USING (report_id)
           WHERE r.asset_id = ? AND r.is_current = 1 AND substr(r.reference_date, 1, 7) = ?
             AND v.xml_path = ? AND v.mapping_status = 'mapped'""",
        (asset_id, month, path),
    ).fetchone()
    if row is None or row["normalized_value"] is None or row["scale"] == "unknown":
        return None, None
    return Decimal(row["normalized_value"]), row["report_id"]


def payment_reconciliation(connection, asset_id, facts, rule) -> list[dict]:
    paid_by_month: dict[str, list] = defaultdict(list)
    for date, names in facts.items():
        for row in names.get(rule["fact"], []):
            paid_by_month[date[:7]].append(row)
    tolerance = Decimal(rule["tolerance_brl"])
    evaluations = []
    for month in rule["coverage_months"]:
        informe, report_id = _informe_amount(connection, asset_id, month, rule["informe_path"])
        if informe is None:
            continue
        announced = sum((Decimal(r["value"]) for r in paid_by_month.get(month, [])), Decimal(0))
        compliant = abs(informe - announced) <= tolerance
        evaluations.append({
            "month": month, "instance_key": None, "report_id": report_id, "compliant": compliant,
            "message": (
                f"Pagamentos {month}: Informe R$ {informe:,.2f} × comunicados R$ {announced:,.2f}"
                + ("" if compliant else f" (diferença R$ {informe - announced:,.2f}).")
            ),
            "evidence": {"informe": str(informe), "comunicados": str(announced),
                         "fontes_comunicados": sorted(_source(r) for r in paid_by_month.get(month, []))},
        })
    return evaluations


def trustee_payment_statement(connection, asset_id, facts, rule) -> list[dict]:
    evaluations = []
    for date, names in sorted(facts.items()):
        for row in names.get(rule["fact"], []):
            if row["value"] != "nenhum":
                continue
            year = date[:4]
            total = Decimal(0)
            for month in range(1, 13):
                amount, _ = _informe_amount(connection, asset_id, f"{year}-{month:02d}", rule["informe_path"])
                total += amount or 0
            evaluations.append({
                "month": f"{year}-12", "instance_key": None, "compliant": total == 0,
                "message": f"AF declara nenhum pagamento em {year}; Informes vigentes somam R$ {total:,.2f}.",
                "evidence": {"fonte_af": _source(row), "soma_informes": str(total), "exercicio": year},
            })
    return evaluations


def evaluate_asset(connection, asset_id, config) -> dict[str, Any]:
    parameters = approved_parameters(connection, asset_id)
    facts = facts_by_date(connection, asset_id)
    rules = config["rules"]
    evaluations = {
        "cessao_fiduciaria_minima": cessao_fiduciaria_minima(facts, parameters, rules["cessao_fiduciaria_minima"]),
        "razao_garantia_minima": razao_garantia_minima(facts, parameters, rules["razao_garantia_minima"]),
        "payment_reconciliation": payment_reconciliation(connection, asset_id, facts, rules["payment_reconciliation"]),
        "trustee_payment_statement": trustee_payment_statement(connection, asset_id, facts, rules["trustee_payment_statement"]),
    }
    run_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    counts = {"new": 0, "seen_again": 0, "compliant": 0}
    with connection:
        for rule_id, items in evaluations.items():
            for item in items:
                if item["compliant"]:
                    counts["compliant"] += 1
                    continue
                status = upsert_alert(connection, "contractual", rule_id, config["rules_version"],
                                      DETECTOR_VERSION, asset_id, item, rules[rule_id]["severity"], run_id, now)
                counts[status] += 1
    return {"detector_run_id": run_id, **counts, "evaluations": evaluations}
