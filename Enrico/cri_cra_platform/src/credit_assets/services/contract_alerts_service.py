"""Alertas contratuais: parâmetros aprovados do Termo × fatos reportados.

Só usa ``contract_parameters`` com ``review_status = 'approved'``; parâmetro
ausente ou não aprovado interrompe a regra (nunca é presumido). Fatos vêm de
``reported_facts`` (trecho literal conferido) e de relatórios vigentes do
Informe Mensal. Só fatos com revisão humana aprovada entram nas regras: fato
pendente nunca gera alerta contratual. Toda avaliação é devolvida, inclusive as
conformes, para que a ausência de alerta também seja rastreável.
"""
from __future__ import annotations

import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from credit_assets.cross_checks import normalize
from credit_assets.services.data_quality_alerts_service import upsert_alert

DETECTOR_VERSION = "0.3.0"
# Unidades de fatos convertidas para a unidade do parâmetro (BRL) nas regras de mínimo.
UNIT_FACTORS = {"BRL": Decimal(1), "BRL_mil": Decimal(1000)}


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
           WHERE f.asset_id = ? AND f.review_status = 'approved'""",
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


def _fulfilled(item, facts) -> dict | None:
    """Cumprimento comprovado por fato aprovado: {"fact": nome, "reference_date": data}."""
    condition = item.get("fulfilled_by_fact")
    if not isinstance(condition, dict) or facts is None:
        return None
    rows = facts.get(condition["reference_date"], {}).get(condition["fact"], [])
    return {"fato": condition["fact"], "data_base": condition["reference_date"],
            "fonte": _source(rows[0])} if rows else None


def obligation_deadlines(parameters, rule, today: str, facts=None) -> list[dict]:
    """Prazos de obrigações aprovadas: informa os vencidos ou próximos sem evidência de cumprimento."""
    evaluations = []
    for item in rule["obligations"]:
        try:
            row = parameter_row(parameters, item["parameter"])
        except ParameterNotApproved:
            continue
        due = item.get("due") or row["parameter_value"]
        days = (datetime.fromisoformat(due) - datetime.fromisoformat(today)).days
        proof = _fulfilled(item, facts)
        if proof:
            evaluations.append({
                "month": due[:7], "instance_key": item["parameter"], "compliant": True,
                "message": f"{item['label']}: prazo {due}; cumprimento comprovado por {proof['fato']} ({proof['fonte']}).",
                "evidence": {"parametro": item["parameter"], "prazo": due, **proof},
            })
            continue
        if days > rule["warn_days"] or (
            item.get("fulfilled_by_fact") and not isinstance(item["fulfilled_by_fact"], dict)
        ):
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


def fact_minimum(facts, parameters, rule) -> list[dict]:
    """Soma de fatos ≥ parâmetro mínimo, convertendo a unidade do fato para a do parâmetro (BRL)."""
    evaluations = []
    for date, names in sorted(facts.items()):
        if rule.get("months") and date[5:7] not in rule["months"]:
            continue
        if not all(name in names for name in rule["facts"]):
            continue
        minimum = _parameter(parameters, rule["parameter"], date)
        value = Decimal(0)
        for name in rule["facts"]:
            fact = names[name][0]
            if fact["unit"] not in UNIT_FACTORS:
                raise ValueError(f"unidade {fact['unit']} de {name} sem conversão definida")
            value += Decimal(fact["value"]) * UNIT_FACTORS[fact["unit"]]
        below = value < minimum
        evaluations.append({
            "month": date[:7], "instance_key": None, "compliant": not below,
            "message": (f"{rule['label']}: R$ {value:,.2f} em {date} "
                        f"{'abaixo do' if below else '≥'} mínimo de R$ {minimum:,.2f}."),
            "evidence": {"valor_brl": str(value), "minimo": str(minimum), "data_base": date,
                         "parametro": rule["parameter"],
                         "fontes_fatos": sorted({_source(names[n][0]) for n in rule["facts"]}),
                         "unidades": sorted({names[n][0]["unit"] for n in rule["facts"]}),
                         "fonte_parametro": parameter_row(parameters, rule["parameter"], date)["source_reference"]},
        })
    return evaluations


def fact_flag(facts, parameters, rule) -> list[dict]:
    """Fato aprovado com valor que contradiz uma obrigação aprovada (ex.: garantia "NÃO" constituída)."""
    obligation = parameter_row(parameters, rule["parameter"])
    alert_values = {value.strip().lower() for value in rule["alert_values"]}
    evaluations = []
    for date, names in sorted(facts.items()):
        for name in rule["facts"]:
            for fact in names.get(name, []):
                flagged = str(fact["value"]).strip().lower() in alert_values
                evaluations.append({
                    "month": date[:7], "instance_key": name, "compliant": not flagged,
                    "message": f"{rule['label']}: {name} = {fact['value']!r} em {date} ({_source(fact)}).",
                    "evidence": {"fato": name, "valor": fact["value"], "data_base": date, "fonte": _source(fact),
                                 "parametro": rule["parameter"], "obrigacao": obligation["parameter_value"],
                                 "fonte_parametro": obligation["source_reference"]},
                })
    return evaluations


def informe_registry_vs_terms(connection, asset_id, parameters, rule) -> list[dict]:
    """Dado cadastral do Informe vigente mais recente × parâmetro aprovado do Termo (ou de ata).

    Cada comparação: ``informe_path`` (final do xml_path), ``parameter`` (nome; ``{n}`` = série),
    ``kind`` (date, code ou number). Sem parâmetro aprovado vigente, a comparação é ignorada:
    nunca se presume o valor do Termo. Divergência não diz qual fonte está certa."""

    report = connection.execute(
        """SELECT r.report_id, r.reference_date, d.source_document_id
           FROM extracted_reports r JOIN documents d ON d.document_pk = r.document_id
           WHERE r.asset_id = ? AND r.is_current = 1 AND r.human_review_status = 'approved'
           ORDER BY r.reference_date DESC, r.report_id DESC LIMIT 1""", (asset_id,),
    ).fetchone()
    if report is None:
        return []
    evaluations = []
    for comparison in rule["comparisons"]:
        for row in connection.execute(
            """SELECT xml_path, instance_key, original_value FROM extracted_values
               WHERE report_id = ? AND xml_path LIKE ? AND TRIM(COALESCE(original_value, '')) <> ''""",
            (report["report_id"], "%" + comparison["informe_path"]),
        ).fetchall():
            series = str(row["instance_key"]) if row["instance_key"] is not None else "-"
            if comparison.get("series") and series not in [str(n) for n in comparison["series"]]:
                continue
            name = comparison["parameter"].replace("{n}", series)
            try:
                parameter = parameter_row(parameters, name, report["reference_date"])
            except ParameterNotApproved:
                continue
            informe_value = normalize(row["original_value"], comparison["kind"])
            terms_value = normalize(parameter["parameter_value"], comparison["kind"])
            if informe_value is None or terms_value is None:
                continue
            same = informe_value == terms_value
            evaluations.append({
                "month": report["reference_date"][:7],
                "instance_key": f"{comparison['label']}:{series}",
                "report_id": report["report_id"], "compliant": same,
                "message": (f"{comparison['label']} (série {series}): Informe {report['reference_date'][:7]} traz "
                            f"{row['original_value']!r}; {name} aprovado traz {parameter['parameter_value']!r}."),
                "evidence": {"campo": comparison["label"], "serie": series,
                             "valor_informe": row["original_value"], "valor_termo": parameter["parameter_value"],
                             "parametro": name, "fonte_parametro": parameter["source_reference"],
                             "informe": f"{report['reference_date']} (doc {report['source_document_id']})"},
            })
    return evaluations


def evaluate_asset(connection, asset_id, config, persist: bool = True) -> dict[str, Any]:
    parameters = approved_parameters(connection, asset_id)
    facts = facts_by_date(connection, asset_id)
    rules = config["rules"]
    today = config.get("reference_date") or datetime.now().date().isoformat()
    evaluators = {
        "cessao_fiduciaria_minima": lambda rule: cessao_fiduciaria_minima(facts, parameters, rule),
        "razao_garantia_minima": lambda rule: razao_garantia_minima(facts, parameters, rule),
        "payment_reconciliation": lambda rule: payment_reconciliation(connection, asset_id, facts, rule),
        "trustee_payment_statement": lambda rule: trustee_payment_statement(connection, asset_id, facts, rule),
        "obligation_deadlines": lambda rule: obligation_deadlines(parameters, rule, today, facts),
        "fact_minimum": lambda rule: fact_minimum(facts, parameters, rule),
        "fact_flag": lambda rule: fact_flag(facts, parameters, rule),
        "informe_registry_vs_terms": lambda rule: informe_registry_vs_terms(
            connection, asset_id, parameters, rule),
    }
    evaluations = {}
    for rule_id, rule in rules.items():
        kind = rule.get("type", rule_id)
        if kind not in evaluators:
            raise ValueError(f"regra {rule_id}: tipo {kind} desconhecido")
        evaluations[rule_id] = evaluators[kind](rule)
    if not persist:
        return {"detector_run_id": None, "new": 0, "seen_again": 0,
                "compliant": sum(item["compliant"] for items in evaluations.values() for item in items),
                "evaluations": evaluations}
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
