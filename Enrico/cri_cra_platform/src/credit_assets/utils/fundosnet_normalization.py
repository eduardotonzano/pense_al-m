from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"\bS\s*\.?\s*A\s*\.?\b", "SA", value, flags=re.IGNORECASE)
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(
        re.sub(r"[^A-Z0-9]+", " ", without_accents.upper()).split()
    )


def normalize_company_name(value: str | None) -> str:
    tokens = normalize_text(value).split()
    return " ".join(tokens)


def equivalent_names(left: str | None, right: str | None) -> bool:
    return normalize_company_name(left) == normalize_company_name(right)


def product_type_id(value: str) -> int:
    normalized = normalize_text(value)
    if normalized == "CRI":
        return 5
    if normalized == "CRA":
        return 6
    raise ValueError(f"Tipo de ativo inválido: {value}")
