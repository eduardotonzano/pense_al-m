"""Registros brutos preservados pela camada de coleta."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import RawRecordStatus
from .sources import normalize_required_text


@dataclass(frozen=True, slots=True)
class RawCollectionRecord:
    """Conteudo bruto preservado antes do processamento."""

    source_id: UUID
    payload: bytes
    payload_sha256: str
    collected_at: datetime
    status: RawRecordStatus = RawRecordStatus.PENDING
    collection_run_id: UUID | None = None
    request_id: UUID | None = None
    response_id: UUID | None = None
    content_type: str | None = None
    http_status: int | None = None
    parser_version: str | None = None
    processing_error: str | None = None
    raw_record_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        uuid_fields = (
            "source_id",
            "raw_record_id",
        )

        for field_name in uuid_fields:
            if not isinstance(
                getattr(self, field_name),
                UUID,
            ):
                raise TypeError(
                    f"{field_name} deve ser UUID."
                )

        optional_uuid_fields = (
            "collection_run_id",
            "request_id",
            "response_id",
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

        if not isinstance(self.payload, bytes):
            raise TypeError(
                "payload deve ser bytes."
            )

        if not self.payload:
            raise ValueError(
                "payload nao pode ser vazio."
            )

        normalized_hash = normalize_required_text(
            self.payload_sha256,
            "payload_sha256",
        ).lower()

        if (
            len(normalized_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in normalized_hash
            )
        ):
            raise ValueError(
                "payload_sha256 deve ser um SHA-256 valido."
            )

        if not isinstance(self.status, RawRecordStatus):
            raise TypeError(
                "status deve ser RawRecordStatus."
            )

        if not isinstance(self.collected_at, datetime):
            raise TypeError(
                "collected_at deve ser datetime."
            )

        if self.collected_at.tzinfo is None:
            raise ValueError(
                "collected_at deve possuir timezone."
            )

        normalized_content_type = (
            self._normalize_optional_text(
                self.content_type,
                "content_type",
            )
        )

        normalized_parser_version = (
            self._normalize_optional_text(
                self.parser_version,
                "parser_version",
            )
        )

        normalized_processing_error = (
            self._normalize_optional_text(
                self.processing_error,
                "processing_error",
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
            self.status is RawRecordStatus.FAILED
            and normalized_processing_error is None
        ):
            raise ValueError(
                "Um registro failed deve possuir "
                "processing_error."
            )

        if (
            self.status is not RawRecordStatus.FAILED
            and normalized_processing_error is not None
        ):
            raise ValueError(
                "processing_error somente pode ser informado "
                "para registros failed."
            )

        object.__setattr__(
            self,
            "payload_sha256",
            normalized_hash,
        )
        object.__setattr__(
            self,
            "collected_at",
            self.collected_at.astimezone(UTC),
        )
        object.__setattr__(
            self,
            "content_type",
            normalized_content_type,
        )
        object.__setattr__(
            self,
            "parser_version",
            normalized_parser_version,
        )
        object.__setattr__(
            self,
            "processing_error",
            normalized_processing_error,
        )

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
        field_name: str,
    ) -> str | None:
        if value is None:
            return None

        return normalize_required_text(
            value,
            field_name,
        )
