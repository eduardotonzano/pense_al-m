"""Identificadores da Shared Entity Layer."""

from dataclasses import dataclass
from re import sub

from .enums import IdentifierType
from .exceptions import IdentifierValidationError
from .provenance import DataProvenance


def normalize_cnpj(value: str) -> str:
    """Remove formatacao e valida a estrutura basica do CNPJ."""

    normalized = sub(r"\D", "", value)

    if len(normalized) != 14:
        raise IdentifierValidationError(
            "CNPJ deve possuir 14 digitos."
        )

    if len(set(normalized)) == 1:
        raise IdentifierValidationError(
            "CNPJ nao pode possuir todos os digitos iguais."
        )

    return normalized


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
