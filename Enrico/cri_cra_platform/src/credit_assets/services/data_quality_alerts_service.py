"""Alertas de qualidade de dado sobre os relatórios vigentes.

Regras determinísticas e versionadas em config/alert_rules; nenhuma usa
limite contratual. Valores monetários com escala suspeita não entram em
regras numéricas. Cada alerta guarda a evidência (caminhos, valores e
report_id) e é identificado por um fingerprint, para não duplicar entre
execuções nem reabrir alertas descartados.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from statistics import median
from typing import Any

DETECTOR_VERSION = "0.1.0"
ZERO_STATES = ("zero", "present_empty", "absent")


def _current_reports(connection, asset_id):
    return connection.execute(
        """SELECT report_id, substr(reference_date, 1, 7) AS month
           FROM extracted_reports WHERE asset_id = ? AND is_current = 1 ORDER BY month""",
        (asset_id,),
    ).fetchall()


def _values(connection, report_id) -> dict[tuple[str, str | None], sqlite3.Row]:
    return {
        (row["xml_path"], row["instance_key"]): row
        for row in connection.execute(
            """SELECT xml_path, instance_key, instance_index, normalized_value,
                      original_value, field_state, scale
               FROM extracted_values WHERE report_id = ? AND mapping_status = 'mapped'""",
            (report_id,),
        )
    }


def _by_path(values, path):
    return [row for (row_path, _), row in values.items() if row_path == path]


def _number(row) -> Decimal | None:
    if row is None or row["field_state"] not in ("present_value", "zero"):
        return None
    return Decimal(row["normalized_value"])


def status_vs_delinquency(months, rule) -> list[dict]:
    alerts = []
    for month in months:
        values = month["values"]
        statuses = {row["normalized_value"] for row in _by_path(values, rule["status_path"])}
        amounts = {
            path: (rows[0]["normalized_value"] if rows else None, rows[0]["field_state"] if rows else "absent")
            for path in rule["delinquency_paths"]
            for rows in [_by_path(values, path)]
        }
        all_zero = all(state in ZERO_STATES for _, state in amounts.values())
        if "Em atraso" in statuses and all_zero:
            message = "Situação 'Em atraso' com todos os campos de atraso zerados ou vazios."
        elif statuses == {"Adimplente"} and not all_zero:
            message = "Todas as séries 'Adimplente', mas há valores em campos de atraso."
        else:
            continue
        alerts.append({
            "report_id": month["report_id"], "month": month["month"], "instance_key": None,
            "message": message,
            "evidence": {"situacao": sorted(statuses), "campos_atraso": amounts},
        })
    return alerts


def balance_reconciliation(months, rule) -> list[dict]:
    alerts = []
    tolerance = Decimal(rule["tolerance"])
    for previous, current in zip(months, months[1:]):
        series = _number(_by_path(current["values"], rule["series_count_path"])[0]) if _by_path(current["values"], rule["series_count_path"]) else None
        if series != 1:
            continue
        rows = {
            "saldo_anterior": (_by_path(previous["values"], rule["balance_path"]) or [None])[0],
            "saldo": (_by_path(current["values"], rule["balance_path"]) or [None])[0],
            "rentabilidade": (_by_path(current["values"], rule["return_path"]) or [None])[0],
            "pagamentos": (_by_path(current["values"], rule["payments_path"]) or [None])[0],
        }
        if any(row is not None and row["scale"] == "unknown" for row in rows.values()):
            continue
        numbers = {name: _number(row) for name, row in rows.items()}
        if any(value is None for value in numbers.values()) or numbers["saldo_anterior"] == 0:
            continue
        expected = numbers["saldo_anterior"] * (1 + numbers["rentabilidade"]) - numbers["pagamentos"]
        residual = (numbers["saldo"] - expected) / numbers["saldo_anterior"]
        if abs(residual) > tolerance:
            alerts.append({
                "report_id": current["report_id"], "month": current["month"], "instance_key": None,
                "message": (
                    f"Saldo {numbers['saldo']} difere do esperado {expected:.2f} "
                    f"(resíduo {residual:.4%} do saldo anterior; tolerância {tolerance:.2%})."
                ),
                "evidence": {name: str(value) for name, value in numbers.items()}
                | {"esperado": f"{expected:.2f}", "residuo": str(residual.quantize(Decimal('0.000001'))),
                   "mes_anterior": previous["month"]},
            })
    return alerts


def return_outlier(months, rule) -> list[dict]:
    alerts = []
    threshold = Decimal(rule["robust_z_threshold"])
    history: dict[str | None, list[tuple[dict, Decimal]]] = {}
    for month in months:
        for row in _by_path(month["values"], rule["return_path"]):
            value = _number(row)
            if value is not None:
                history.setdefault(row["instance_key"], []).append((month, value))
    for key, points in history.items():
        if len(points) < rule["minimum_months"]:
            continue
        returns = [value for _, value in points]
        center = median(returns)
        mad = median(abs(value - center) for value in returns)
        if mad == 0:
            continue
        scale = Decimal("1.4826") * mad
        for month, value in points:
            z = abs(value - center) / scale
            if z > threshold:
                alerts.append({
                    "report_id": month["report_id"], "month": month["month"], "instance_key": key,
                    "message": (
                        f"Rentabilidade {value} (série {key}) fora do histórico: mediana {center}, "
                        f"desvio robusto {z:.1f} > {threshold}."
                    ),
                    "evidence": {"rentabilidade": str(value), "mediana": str(center),
                                 "mad": str(mad), "desvio_robusto": f"{z:.2f}",
                                 "meses_no_historico": len(points)},
                })
    return alerts


def key_party_changed(months, rule) -> list[dict]:
    alerts = []
    for previous, current in zip(months, months[1:]):
        for path in rule["paths"]:
            before = sorted(r["normalized_value"] for r in _by_path(previous["values"], path) if r["normalized_value"])
            after = sorted(r["normalized_value"] for r in _by_path(current["values"], path) if r["normalized_value"])
            if before and after and before != after:
                alerts.append({
                    "report_id": current["report_id"], "month": current["month"], "instance_key": None,
                    "message": f"{path.rsplit('/', 2)[-2]} com mais de 20% mudou: {before} -> {after}.",
                    "evidence": {"caminho": path, "antes": before, "depois": after,
                                 "mes_anterior": previous["month"]},
                })
    return alerts


DETECTORS = {
    "status_vs_delinquency": status_vs_delinquency,
    "balance_reconciliation": balance_reconciliation,
    "return_outlier": return_outlier,
    "key_party_changed": key_party_changed,
}


def detect_asset(connection: sqlite3.Connection, asset_id: int, config: dict[str, Any]) -> dict[str, Any]:
    months = [
        {"report_id": row["report_id"], "month": row["month"],
         "values": _values(connection, row["report_id"])}
        for row in _current_reports(connection, asset_id)
    ]
    run_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    counts = {"new": 0, "seen_again": 0}
    by_rule: dict[str, int] = {}
    with connection:
        for rule_id, detector in DETECTORS.items():
            rule = config["rules"].get(rule_id)
            if not rule:
                continue
            for alert in detector(months, rule):
                evidence = json.dumps(alert["evidence"], ensure_ascii=False, sort_keys=True, default=str)
                fingerprint = hashlib.sha256(
                    "|".join([rule_id, str(asset_id), alert["month"], str(alert["instance_key"]), evidence]).encode()
                ).hexdigest()
                by_rule[rule_id] = by_rule.get(rule_id, 0) + 1
                updated = connection.execute(
                    "UPDATE data_quality_alerts SET last_seen_run_id = ? WHERE fingerprint = ?",
                    (run_id, fingerprint),
                ).rowcount
                if updated:
                    counts["seen_again"] += 1
                    continue
                connection.execute(
                    """INSERT INTO data_quality_alerts (
                        fingerprint, rule_id, rules_version, detector_version, asset_id,
                        report_id, competencia_mes, instance_key, severity, message,
                        evidence_json, first_seen_run_id, last_seen_run_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (fingerprint, rule_id, config["rules_version"], DETECTOR_VERSION, asset_id,
                     alert["report_id"], alert["month"], alert["instance_key"], rule["severity"],
                     alert["message"], evidence, run_id, run_id, now),
                )
                counts["new"] += 1
    return {"detector_run_id": run_id, "months": len(months), **counts, "by_rule": by_rule}
