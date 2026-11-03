from __future__ import annotations

import re

_CNPJ_TEXT = re.compile(r"[\d.\-/\s]*")
_CNPJ_WEIGHTS = (
    (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
    (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
)

def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")

def _cnpj_check_digit(digits: str, weights: tuple[int, ...]) -> str:
    remainder = sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 11
    return "0" if remainder < 2 else str(11 - remainder)

def is_valid_cnpj(value: str | None) -> bool:
    """CNPJ de 14 digitos, nao repetido, com os dois digitos verificadores (modulo 11).

    Aceita so digitos, ponto, barra, hifen e espaco: letras e outros simbolos
    reprovam em vez de serem descartados. CPF (11 digitos) tambem reprova.
    """
    if value is None or not _CNPJ_TEXT.fullmatch(value):
        return False
    digits = only_digits(value)
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    first = _cnpj_check_digit(digits[:12], _CNPJ_WEIGHTS[0])
    second = _cnpj_check_digit(digits[:12] + first, _CNPJ_WEIGHTS[1])
    return digits[12:] == first + second

def normalize_cnpj(value: str | None) -> str | None:
    """Os 14 digitos do CNPJ valido, ou None. Nunca corrige nem completa."""
    return only_digits(value) if is_valid_cnpj(value) else None

def format_cnpj(digits: str) -> str:
    """NN.NNN.NNN/NNNN-NN, o formato do ativos_piloto.csv."""
    if len(digits) != 14 or not digits.isdigit():
        raise ValueError(f"CNPJ precisa ter 14 digitos: {digits!r}")
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"

def validate_asset_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"CRI", "CRA"}:
        raise ValueError(f"Tipo de ativo inválido: {value}")
    return normalized
