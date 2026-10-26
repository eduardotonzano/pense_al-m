"""Normalização determinística de valores XML conforme a mapping_version.

Nunca adivinha: texto fora do formato esperado vira ``invalid`` (com o
literal preservado), vazio continua vazio e zero só existe para campos
numéricos. Valores monetários não são multiplicados por escala.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

SEMANTIC_NORMALIZER_VERSION = "0.1.0"
_DECIMAL = re.compile(r"-?\d+(\.\d+)?")
_INTEGER = re.compile(r"-?\d+")
_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def normalize(raw_text: str | None, rule: dict[str, Any]) -> dict[str, Any]:
    data_type = rule.get("data_type")
    result: dict[str, Any] = {
        "normalized_value": None,
        "data_type": data_type,
        "unit": rule.get("unit"),
        "currency": rule.get("currency"),
        "scale": rule.get("scale"),
        "automatic_validation_status": "valid",
        "problem": None,
    }
    if raw_text is None:
        return {**result, "field_state": "absent"}
    text = raw_text.strip()
    if not text:
        return {**result, "field_state": "present_empty"}

    if data_type in ("decimal", "integer"):
        pattern = _DECIMAL if data_type == "decimal" else _INTEGER
        if not pattern.fullmatch(text):
            return {
                **result, "field_state": "invalid", "automatic_validation_status": "invalid",
                "problem": f"esperado {data_type} com ponto decimal, recebido {text!r}",
            }
        number = Decimal(text)
        return {
            **result,
            "normalized_value": str(number),
            "field_state": "zero" if number == 0 else "present_value",
        }
    if data_type == "date":
        match = _DATE.fullmatch(text)
        try:
            if not match:
                raise ValueError
            date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return {
                **result, "field_state": "invalid", "automatic_validation_status": "invalid",
                "problem": f"data fora de AAAA-MM-DD válida: {text!r}",
            }
        return {**result, "normalized_value": text, "field_state": "present_value"}
    if data_type in ("identifier", "text"):
        return {**result, "normalized_value": raw_text, "field_state": "present_value"}
    raise ValueError(f"data_type não suportado: {data_type!r}")


def is_monetary(rule: dict[str, Any]) -> bool:
    return rule.get("data_type") == "decimal" and rule.get("currency") is not None
