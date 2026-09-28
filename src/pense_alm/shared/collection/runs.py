"""Execucoes auditaveis da camada de coleta."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import CollectionRunStatus


@dataclass(frozen=True, slots=True)
class CollectionRun:
    """Representa uma execucao de coleta."""

    source_id: UUID
    requested_items: int
    status: CollectionRunStatus = (
        CollectionRunStatus.RUNNING
    )
    successful_items: int = 0
    failed_items: int = 0
    started_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    finished_at: datetime | None = None
    run_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, UUID):
            raise TypeError(
                "source_id deve ser UUID."
            )

        if not isinstance(self.run_id, UUID):
            raise TypeError(
                "run_id deve ser UUID."
            )

        if not isinstance(
            self.status,
            CollectionRunStatus,
        ):
            raise TypeError(
                "status deve ser CollectionRunStatus."
            )

        counter_fields = (
            "requested_items",
            "successful_items",
            "failed_items",
        )

        for field_name in counter_fields:
            value = getattr(self, field_name)

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
            ):
                raise TypeError(
                    f"{field_name} deve ser inteiro."
                )

            if value < 0:
                raise ValueError(
                    f"{field_name} nao pode ser negativo."
                )

        processed_items = (
            self.successful_items
            + self.failed_items
        )

        if processed_items > self.requested_items:
            raise ValueError(
                "O total processado nao pode exceder "
                "requested_items."
            )

        if not isinstance(self.started_at, datetime):
            raise TypeError(
                "started_at deve ser datetime."
            )

        if self.started_at.tzinfo is None:
            raise ValueError(
                "started_at deve possuir timezone."
            )

        if (
            self.finished_at is not None
            and not isinstance(
                self.finished_at,
                datetime,
            )
        ):
            raise TypeError(
                "finished_at deve ser datetime ou None."
            )

        normalized_started_at = (
            self.started_at.astimezone(UTC)
        )

        normalized_finished_at = None

        if self.finished_at is not None:
            if self.finished_at.tzinfo is None:
                raise ValueError(
                    "finished_at deve possuir timezone."
                )

            normalized_finished_at = (
                self.finished_at.astimezone(UTC)
            )

            if (
                normalized_finished_at
                < normalized_started_at
            ):
                raise ValueError(
                    "finished_at nao pode ser anterior "
                    "a started_at."
                )

        if (
            self.status is CollectionRunStatus.RUNNING
            and normalized_finished_at is not None
        ):
            raise ValueError(
                "Uma execucao running nao pode possuir "
                "finished_at."
            )

        if (
            self.status is not CollectionRunStatus.RUNNING
            and normalized_finished_at is None
        ):
            raise ValueError(
                "Uma execucao finalizada deve possuir "
                "finished_at."
            )

        if (
            self.status is CollectionRunStatus.SUCCESS
            and self.failed_items != 0
        ):
            raise ValueError(
                "Uma execucao success nao pode possuir "
                "failed_items."
            )

        if (
            self.status is CollectionRunStatus.FAILED
            and self.failed_items == 0
        ):
            raise ValueError(
                "Uma execucao failed deve registrar "
                "ao menos uma falha."
            )

        object.__setattr__(
            self,
            "started_at",
            normalized_started_at,
        )
        object.__setattr__(
            self,
            "finished_at",
            normalized_finished_at,
        )
