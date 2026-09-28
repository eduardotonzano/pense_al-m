"""Proveniencia dos dados da Shared Entity Layer."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .enums import SourceType, ValidationStatus
from .exceptions import ProvenanceValidationError


_SOURCE_PRIORITIES = {
    SourceType.BACEN: 1,
    SourceType.CVM: 2,
    SourceType.ANBIMA: 3,
    SourceType.SPECIALIZED: 4,
    SourceType.INSTITUTIONAL: 5,
    SourceType.MANUAL: 6,
}


@dataclass(frozen=True, slots=True)
class DataProvenance:
    """Registra a origem e o estado de validacao de um dado."""

    source_type: SourceType
    source_name: str
    source_reference: str | None = None
    collected_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    reference_date: datetime | None = None
    validation_status: ValidationStatus = ValidationStatus.PENDING
    confidence_score: int = 100

    def __post_init__(self) -> None:
        source_name = self.source_name.strip()

        if not source_name:
            raise ProvenanceValidationError(
                "source_name nao pode ser vazio."
            )

        if not 0 <= self.confidence_score <= 100:
            raise ProvenanceValidationError(
                "confidence_score deve estar entre 0 e 100."
            )

        if self.collected_at.tzinfo is None:
            raise ProvenanceValidationError(
                "collected_at deve possuir timezone."
            )

        if (
            self.reference_date is not None
            and self.reference_date.tzinfo is None
        ):
            raise ProvenanceValidationError(
                "reference_date deve possuir timezone."
            )

        object.__setattr__(self, "source_name", source_name)

        if self.source_reference is not None:
            reference = self.source_reference.strip()
            object.__setattr__(
                self,
                "source_reference",
                reference or None,
            )

    @property
    def source_priority(self) -> int:
        """Retorna a prioridade institucional da fonte."""

        return _SOURCE_PRIORITIES[self.source_type]
