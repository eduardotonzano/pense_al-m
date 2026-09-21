"""Relacionamentos direcionais entre entidades."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import (
    RelationshipStatus,
    RelationshipType,
)
from .exceptions import EntityValidationError
from .provenance import DataProvenance


def normalize_relationship_notes(
    value: str | None,
) -> str | None:
    """Normaliza observacoes opcionais do relacionamento."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise EntityValidationError(
            "notes deve ser texto."
        )

    normalized = " ".join(value.split())

    return normalized or None


@dataclass(frozen=True, slots=True)
class EntityRelationship:
    """Conexao direcionada e temporal entre duas entidades."""

    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    provenance: DataProvenance

    relationship_id: UUID = field(default_factory=uuid4)
    status: RelationshipStatus = RelationshipStatus.UNKNOWN
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence_score: int = 100
    notes: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def __post_init__(self) -> None:
        if not isinstance(self.source_entity_id, UUID):
            raise EntityValidationError(
                "source_entity_id deve ser um UUID."
            )

        if not isinstance(self.target_entity_id, UUID):
            raise EntityValidationError(
                "target_entity_id deve ser um UUID."
            )

        if self.source_entity_id == self.target_entity_id:
            raise EntityValidationError(
                "Uma entidade nao pode se relacionar consigo mesma."
            )

        if not isinstance(
            self.relationship_type,
            RelationshipType,
        ):
            raise EntityValidationError(
                "relationship_type invalido."
            )

        if not isinstance(self.status, RelationshipStatus):
            raise EntityValidationError(
                "status do relacionamento invalido."
            )

        if not isinstance(self.provenance, DataProvenance):
            raise EntityValidationError(
                "provenance deve ser DataProvenance."
            )

        if not 0 <= self.confidence_score <= 100:
            raise EntityValidationError(
                "confidence_score deve estar entre 0 e 100."
            )

        self._validate_datetime(
            self.valid_from,
            "valid_from",
        )
        self._validate_datetime(
            self.valid_to,
            "valid_to",
        )
        self._validate_datetime(
            self.created_at,
            "created_at",
        )

        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to < self.valid_from
        ):
            raise EntityValidationError(
                "valid_to nao pode ser anterior a valid_from."
            )

        object.__setattr__(
            self,
            "notes",
            normalize_relationship_notes(self.notes),
        )

    @staticmethod
    def _validate_datetime(
        value: datetime | None,
        field_name: str,
    ) -> None:
        if value is not None and value.tzinfo is None:
            raise EntityValidationError(
                f"{field_name} deve possuir timezone."
            )

    @property
    def canonical_key(self) -> str:
        """Chave estavel para deduplicacao e idempotencia."""

        return (
            f"{self.source_entity_id}:"
            f"{self.relationship_type.value}:"
            f"{self.target_entity_id}"
        )

    @property
    def is_open_ended(self) -> bool:
        """Indica se o relacionamento nao possui data final."""

        return self.valid_to is None

    def is_active_at(
        self,
        reference_datetime: datetime,
    ) -> bool:
        """Informa se a relacao estava ativa em uma data."""

        if not isinstance(reference_datetime, datetime):
            raise EntityValidationError(
                "reference_datetime deve ser datetime."
            )

        if reference_datetime.tzinfo is None:
            raise EntityValidationError(
                "reference_datetime deve possuir timezone."
            )

        if self.status is not RelationshipStatus.ACTIVE:
            return False

        if (
            self.valid_from is not None
            and reference_datetime < self.valid_from
        ):
            return False

        if (
            self.valid_to is not None
            and reference_datetime > self.valid_to
        ):
            return False

        return True

    @property
    def is_active(self) -> bool:
        """Indica se a relacao esta ativa no momento atual."""

        return self.is_active_at(datetime.now(UTC))
