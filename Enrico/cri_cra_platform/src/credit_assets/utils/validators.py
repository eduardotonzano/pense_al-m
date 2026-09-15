import re

def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")

def validate_asset_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"CRI", "CRA"}:
        raise ValueError(f"Tipo de ativo inválido: {value}")
    return normalized
