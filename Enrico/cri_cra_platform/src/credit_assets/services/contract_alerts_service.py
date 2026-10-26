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


def approved_parameters(connection, asset_id) -> dict[str, list[sqlite3.Row]]:
    grouped: dict[str, list] = defaultdict(list)
    for row in connection.execute(
        """SELECT parameter_name, parameter_value, unit, source_reference, valid_from, valid_to
           FROM contract_parameters WHERE asset_id = ? AND review_status = 'approved'""",
        (asset_id,),
    ):
        grouped[row["parameter_name"]].append(row)
    return grouped


def parameter_row(parameters, name, date: str | None = None):
    """Parâmetro aprovado vigente na data (valid_from/valid_to inclusivos; nulos = sem limite)."""
    rows = parameters.get(name) or []
    if isinstance(rows, dict) or hasattr(rows, "keys"):
        rows = [rows]
    valid = [
        row for row in rows
        if date is None
        or ((row.get("valid_from") if isinstance(row, dict) else row["valid_from"]) or "0000") <= date
        <= ((row.get("valid_to") if isinstance(row, dict) else row["valid_to"]) or "9999")
    ]
    if not valid:
        raise ParameterNotApproved(f"parâmetro {name} ausente, não aprovado ou fora de vigência em {date}")
    if len(valid) > 1:
        raise ParameterNotApproved(f"parâmetro {name} com mais de uma versão vigente em {date}")
    return valid[0]


def _parameter(parameters, name, date: str | None = None) -> Decimal:
    return Decimal(parameter_row(parameters, name, date)["parameter_value"])


def _is_valid(parameters, name, date) -> bool:
    try:
        parameter_row(parameters, name, date)
        return True
    except ParameterNotApproved:
        return False


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
    variants = rule.get("variants") or [{"parameter": rule["parameter"], "facts": [rule["fact"]]}]
    evaluations = []
    for date, names in sorted(facts.items()):
        if date[5:7] not in rule["months"]:
            continue
        variant = next((v for v in variants if _is_valid(parameters, v["parameter"], date)), None)
        if variant is None:
            raise ParameterNotApproved(f"nenhum parâmetro de cessão mínima vigente em {date}")
        if not all(name in names for name in variant["facts"]):
            continue
        minimum = _parameter(parameters, variant["parameter"], date)
        value = sum((Decimal(names[n][0]["value"]) for n in variant["facts"]), Decimal(0))
        label = " + ".join(variant["facts"])
        evaluations.append({
            "month": date[:7], "instance_key": None, "compliant": value >= minimum,
            "message": f"{label} = R$ {value:,.2f} em {date} {'≥' if value >= minimum else 'abaixo do'} mínimo de R$ {minimum:,.2f}.",
            "evidence": {"valor": str(value), "minimo": str(minimum), "data_base": date,
                         "parametro": variant["parameter"],
                         "fontes_fatos": sorted({_source(names[n][0]) for n in variant["facts"]}),
                         "fonte_parametro": parameter_row(parameters, variant["parameter"], date)["source_reference"]},
        })
    return evaluations


def razao_garantia_minima(facts, parameters, rule) -> list[dict]:
    evaluations = []
    for date, names in sorted(facts.items()):
        needed = rule["numerator_facts"] + [rule["denominator_fact"]]
        if not all(name in names for name in needed):
            continue
        parameter_name = rule["parameters"]["01-08" if int(date[5:7]) <= 8 else "09-12"]
        minimum = _parameter(parameters, parameter_name, date)
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


def obligation_deadlines(parameters, rule, today: str) -> list[dict]:
    """Prazos de obrigações aprovadas: informa os vencidos ou próximos sem evidência de cumprimento."""
    evaluations = []
    for item in rule["obligations"]:
        try:
            row = parameter_row(parameters, item["parameter"])
        except ParameterNotApproved:
            continue
        due = item.get("due") or row["parameter_value"]
        days = (datetime.fromisoformat(due) - datetime.fromisoformat(today)).days
        if days > rule["warn_days"] or item.get("fulfilled_by_fact"):
            continue
        evaluations.append({
            "month": due[:7], "instance_key": item["parameter"], "compliant": False,
            "message": (
                f"{item['label']}: prazo {due} ({'vencido há ' + str(-days) if days < 0 else 'em ' + str(days)} dias); "
                "cumprimento não verificado nos documentos baixados."
            ),
            "evidence": {"parametro": item["parameter"], "valor": row["parameter_value"], "prazo": due,
                         "fonte": row["source_reference"], "referencia": today},
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
    if "obligation_deadlines" in rules:
        evaluations["obligation_deadlines"] = obligation_deadlines(
            parameters, rules["obligation_deadlines"], config.get("reference_date") or datetime.now().date().isoformat()
        )
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
