"""Comparação de campos entre competências vigentes consecutivas.

Usa somente relatórios ``is_current = 1`` e valores ``mapped``. Valores
monetários com ``scale = 'unknown'`` (escala suspeita) nunca entram em
diferenças numéricas: viram ``excluded_scale_unknown``. Não aplica limites
nem gera alertas.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

COMPARATOR_VERSION = "0.1.0"
NUMERIC_TYPES = ("decimal", "integer")
VALUE_STATES = ("present_value", "zero")


def _months_between(previous: str, current: str) -> int:
    py, pm = map(int, previous.split("-"))
    cy, cm = map(int, current.split("-"))
    return (cy - py) * 12 + (cm - pm)


def current_series(connection: sqlite3.Connection, asset_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT report_id, substr(reference_date, 1, 7) AS month
           FROM extracted_reports
           WHERE asset_id = ? AND is_current = 1
           ORDER BY month""",
        (asset_id,),
    ).fetchall()


def _values(connection, report_id) -> dict[tuple, sqlite3.Row]:
    return {
        (row["xml_path"], row["instance_key"] if row["instance_key"] is not None else f"#{row['instance_index']}"): row
        for row in connection.execute(
            """SELECT xml_path, instance_key, instance_index, data_type, field_state,
                      normalized_value, scale
               FROM extracted_values
               WHERE report_id = ? AND mapping_status = 'mapped'""",
            (report_id,),
        )
    }


def compare_pair(previous: sqlite3.Row | None, current: sqlite3.Row | None) -> dict[str, Any]:
    reference = current or previous
    result = {
        "data_type": reference["data_type"],
        "previous_value": previous["normalized_value"] if previous else None,
        "current_value": current["normalized_value"] if current else None,
        "previous_state": previous["field_state"] if previous else None,
        "current_state": current["field_state"] if current else None,
        "absolute_change": None,
        "relative_change": None,
    }
    if previous is None or current is None:
        return {**result, "comparison_status": "only_one_side"}
    if "unknown" in (previous["scale"], current["scale"]):
        return {**result, "comparison_status": "excluded_scale_unknown"}
    if reference["data_type"] in NUMERIC_TYPES and {
        previous["field_state"], current["field_state"]
    } <= set(VALUE_STATES):
        before = Decimal(previous["normalized_value"])
        after = Decimal(current["normalized_value"])
        change = after - before
        result["absolute_change"] = str(change)
        if before != 0:
            result["relative_change"] = str((change / before).quantize(Decimal("0.000001")))
        return {**result, "comparison_status": "unchanged" if change == 0 else "changed"}
    if previous["field_state"] != current["field_state"]:
        return {**result, "comparison_status": "state_changed"}
    same = previous["normalized_value"] == current["normalized_value"]
    return {**result, "comparison_status": "unchanged" if same else "changed"}


def compare_asset(connection: sqlite3.Connection, asset_id: int) -> dict[str, Any]:
    series = current_series(connection, asset_id)
    run_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    counts: dict[str, int] = {}
    with connection:
        for previous_report, current_report in zip(series, series[1:]):
            before = _values(connection, previous_report["report_id"])
            after = _values(connection, current_report["report_id"])
            for key in sorted(set(before) | set(after)):
                result = compare_pair(before.get(key), after.get(key))
                counts[result["comparison_status"]] = counts.get(result["comparison_status"], 0) + 1
                connection.execute(
                    """INSERT INTO period_comparisons (
                        comparison_run_id, comparator_version, created_at, asset_id,
                        xml_path, instance_key, data_type, previous_report_id,
                        current_report_id, previous_month, current_month, months_between,
                        previous_value, current_value, previous_state, current_state,
                        absolute_change, relative_change, comparison_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id, COMPARATOR_VERSION, created_at, asset_id, key[0],
                        None if key[1].startswith("#") else key[1], result["data_type"],
                        previous_report["report_id"], current_report["report_id"],
                        previous_report["month"], current_report["month"],
                        _months_between(previous_report["month"], current_report["month"]),
                        result["previous_value"], result["current_value"],
                        result["previous_state"], result["current_state"],
                        result["absolute_change"], result["relative_change"],
                        result["comparison_status"],
                    ),
                )
    gaps = [
        (a["month"], b["month"]) for a, b in zip(series, series[1:])
        if _months_between(a["month"], b["month"]) != 1
    ]
    return {
        "comparison_run_id": run_id,
        "months": len(series),
        "pairs": max(len(series) - 1, 0),
        "gaps": gaps,
        "counts": counts,
    }
