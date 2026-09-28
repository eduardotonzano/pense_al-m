"""Modelos do catalogo compartilhado de fontes."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import CollectionSourceType


def normalize_required_text(
    value: str,
    field_name: str,
) -> str:
    """Normaliza um texto obrigatorio."""

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} deve ser texto."
        )

    normalized = " ".join(value.split())

    if not normalized:
        raise ValueError(
            f"{field_name} nao pode ser vazio."
        )

    return normalized


@dataclass(frozen=True, slots=True)
class CollectionSource:
    """Fonte cadastrada no catalogo de coleta."""

    code: str
    name: str
    source_type: CollectionSourceType
    priority: int = 0
    active: bool = True
    source_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def __post_init__(self) -> None:
        normalized_code = normalize_required_text(
            self.code,
            "code",
        )
        normalized_code = "_".join(
            normalized_code.upper().split()
        )

        normalized_name = normalize_required_text(
            self.name,
            "name",
        )

        if not isinstance(
            self.source_type,
            CollectionSourceType,
        ):
            raise TypeError(
                "source_type deve ser CollectionSourceType."
            )

        if (
            isinstance(self.priority, bool)
            or not isinstance(self.priority, int)
        ):
            raise TypeError(
                "priority deve ser inteiro."
            )

        if self.priority < 0:
            raise ValueError(
                "priority nao pode ser negativa."
            )

        if not isinstance(self.active, bool):
            raise TypeError(
                "active deve ser booleano."
            )

        if not isinstance(self.source_id, UUID):
            raise TypeError(
                "source_id deve ser UUID."
            )

        if not isinstance(self.created_at, datetime):
            raise TypeError(
                "created_at deve ser datetime."
            )

        if self.created_at.tzinfo is None:
            raise ValueError(
                "created_at deve possuir timezone."
            )

        object.__setattr__(
            self,
            "code",
            normalized_code,
        )
        object.__setattr__(
            self,
            "name",
            normalized_name,
        )
        object.__setattr__(
            self,
            "created_at",
            self.created_at.astimezone(UTC),
        )
