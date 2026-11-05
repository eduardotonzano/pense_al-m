"""Identificadores da Shared Entity Layer."""

import re
from dataclasses import dataclass

from .enums import IdentifierType
from .exceptions import IdentifierValidationError
from .provenance import DataProvenance


_CNPJ_SEPARATORS = str.maketrans("", "", "./-")
_CNPJ_FORMAT = re.compile(r"[0-9A-Z]{12}[0-9]{2}")
_CNPJ_FIRST_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_SECOND_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _cnpj_check_digit(
    values: list[int],
    weights: tuple[int, ...],
) -> int:
    remainder = sum(
        value * weight
        for value, weight in zip(values, weights)
    ) % 11

    return 0 if remainder < 2 else 11 - remainder


def normalize_cnpj(value: str) -> str:
    """Normaliza e valida o CNPJ numerico ou alfanumerico.

    Regra da IN RFB 2.229/2024 (ADR-011): remove so ponto, barra e
    hifen e poe em maiusculas; exige 14 caracteres ASCII, os 12
    primeiros em [0-9A-Z] e os 2 ultimos numericos; recusa sequencia
    de caracteres iguais e valida os dois digitos verificadores, com
    cada caractere valendo ord(c) - 48. Para CNPJ so numerico o
    resultado e o do calculo classico. Nunca completa zeros a
    esquerda (11 digitos pode ser CPF). As mensagens de erro nunca
    repetem o valor recebido.
    """

    if not isinstance(value, str):
        raise IdentifierValidationError(
            "CNPJ deve ser texto."
        )

    format_message = (
        "CNPJ deve ter 14 caracteres: os 12 primeiros em "
        "[0-9A-Z] e os 2 ultimos numericos."
    )

    candidate = value.strip()

    # isascii antes de upper: o i sem ponto (U+0131) vira "I" em
    # maiusculas e passaria por uma letra ASCII.
    if not candidate.isascii():
        raise IdentifierValidationError(format_message)

    candidate = candidate.translate(_CNPJ_SEPARATORS).upper()

    if _CNPJ_FORMAT.fullmatch(candidate) is None:
        raise IdentifierValidationError(format_message)

    if len(set(candidate)) == 1:
        raise IdentifierValidationError(
            "CNPJ nao pode possuir todos os caracteres iguais."
        )

    values = [ord(character) - 48 for character in candidate[:12]]
    first = _cnpj_check_digit(values, _CNPJ_FIRST_WEIGHTS)
    second = _cnpj_check_digit(
        values + [first],
        _CNPJ_SECOND_WEIGHTS,
    )

    if candidate[12:] != f"{first}{second}":
        raise IdentifierValidationError(
            "CNPJ com digito verificador invalido."
        )

    return candidate


def normalize_identifier(
    identifier_type: IdentifierType,
    value: str,
) -> str:
    """Normaliza um identificador de acordo com o seu tipo."""

    if not isinstance(value, str):
        raise IdentifierValidationError(
            "O valor do identificador deve ser texto."
        )

    normalized = value.strip()

    if not normalized:
        raise IdentifierValidationError(
            "O identificador nao pode ser vazio."
        )

    if identifier_type is IdentifierType.CNPJ:
        return normalize_cnpj(normalized)

    return normalized.upper()


@dataclass(frozen=True, slots=True)
class EntityIdentifier:
    """Identificador associado a uma entidade."""

    identifier_type: IdentifierType
    value: str
    provenance: DataProvenance
    is_primary: bool = False

    def __post_init__(self) -> None:
        normalized = normalize_identifier(
            self.identifier_type,
            self.value,
        )
        object.__setattr__(self, "value", normalized)

    @property
    def canonical_key(self) -> str:
        """Chave estavel para matching e deduplicacao."""

        return f"{self.identifier_type.value}:{self.value}"
