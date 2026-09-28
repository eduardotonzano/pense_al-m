"""Erros auditaveis da camada compartilhada de coleta."""

from dataclasses import dataclass
from uuid import UUID

from .sources import normalize_required_text


@dataclass(frozen=True, slots=True)
class CollectionError:
    """Falha ocorrida durante uma execucao de coleta."""

    error_type: str
    message: str
    retryable: bool
    category: str
    run_id: UUID | None = None
    request_id: UUID | None = None
    item_reference: str | None = None
    http_status: int | None = None
    attempt: int = 1

    def __post_init__(self) -> None:
        normalized_error_type = normalize_required_text(
            self.error_type,
            "error_type",
        )

        normalized_message = normalize_required_text(
            self.message,
            "message",
        )

        normalized_category = normalize_required_text(
            self.category,
            "category",
        ).lower()

        optional_uuid_fields = (
            "run_id",
            "request_id",
        )

        for field_name in optional_uuid_fields:
            value = getattr(self, field_name)

            if (
                value is not None
                and not isinstance(value, UUID)
            ):
                raise TypeError(
                    f"{field_name} deve ser UUID ou None."
                )

        if not isinstance(self.retryable, bool):
            raise TypeError(
                "retryable deve ser booleano."
            )

        normalized_item_reference = None

        if self.item_reference is not None:
            normalized_item_reference = (
                normalize_required_text(
                    self.item_reference,
                    "item_reference",
                )
            )

        if self.http_status is not None:
            if (
                isinstance(self.http_status, bool)
                or not isinstance(self.http_status, int)
            ):
                raise TypeError(
                    "http_status deve ser inteiro."
                )

            if not 100 <= self.http_status <= 599:
                raise ValueError(
                    "http_status deve ficar entre 100 e 599."
                )

        if (
            isinstance(self.attempt, bool)
            or not isinstance(self.attempt, int)
        ):
            raise TypeError(
                "attempt deve ser inteiro."
            )

        if self.attempt <= 0:
            raise ValueError(
                "attempt deve ser maior que zero."
            )

        object.__setattr__(
            self,
            "error_type",
            normalized_error_type,
        )
        object.__setattr__(
            self,
            "message",
            normalized_message,
        )
        object.__setattr__(
            self,
            "category",
            normalized_category,
        )
        object.__setattr__(
            self,
            "item_reference",
            normalized_item_reference,
        )
