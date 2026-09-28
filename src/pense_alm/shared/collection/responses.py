"""Modelo da resposta obtida por um coletor."""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID, uuid4

from .requests import normalize_mapping
from .sources import normalize_required_text


@dataclass(frozen=True, slots=True)
class CollectedResponse:
    """Resposta bruta retornada por uma fonte externa."""

    request_id: UUID
    source_id: UUID
    payload: bytes
    status_code: int | None = None
    content_type: str | None = None
    response_url: str | None = None
    headers: Mapping[str, Any] = field(
        default_factory=dict
    )
    collected_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    response_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise TypeError(
                "request_id deve ser UUID."
            )

        if not isinstance(self.source_id, UUID):
            raise TypeError(
                "source_id deve ser UUID."
            )

        if not isinstance(self.response_id, UUID):
            raise TypeError(
                "response_id deve ser UUID."
            )

        normalized_payload = self._normalize_payload(
            self.payload
        )

        if self.status_code is not None:
            if (
                isinstance(self.status_code, bool)
                or not isinstance(self.status_code, int)
            ):
                raise TypeError(
                    "status_code deve ser inteiro."
                )

            if not 100 <= self.status_code <= 599:
                raise ValueError(
                    "status_code deve ficar entre 100 e 599."
                )

        normalized_content_type = (
            self._normalize_optional_text(
                self.content_type,
                "content_type",
            )
        )

        normalized_response_url = (
            self._normalize_optional_text(
                self.response_url,
                "response_url",
            )
        )

        normalized_headers = normalize_mapping(
            self.headers,
            "headers",
        )

        if not isinstance(self.collected_at, datetime):
            raise TypeError(
                "collected_at deve ser datetime."
            )

        if self.collected_at.tzinfo is None:
            raise ValueError(
                "collected_at deve possuir timezone."
            )

        object.__setattr__(
            self,
            "payload",
            normalized_payload,
        )
        object.__setattr__(
            self,
            "content_type",
            normalized_content_type,
        )
        object.__setattr__(
            self,
            "response_url",
            normalized_response_url,
        )
        object.__setattr__(
            self,
            "headers",
            normalized_headers,
        )
        object.__setattr__(
            self,
            "collected_at",
            self.collected_at.astimezone(UTC),
        )

    @staticmethod
    def _normalize_payload(
        value: bytes | bytearray | str,
    ) -> bytes:
        if isinstance(value, str):
            normalized = value.encode("utf-8")
        elif isinstance(value, bytes):
            normalized = value
        elif isinstance(value, bytearray):
            normalized = bytes(value)
        else:
            raise TypeError(
                "payload deve ser texto ou bytes."
            )

        if not normalized:
            raise ValueError(
                "payload nao pode ser vazio."
            )

        return normalized

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

    @property
    def payload_sha256(self) -> str:
        """Retorna o SHA-256 do payload."""

        return hashlib.sha256(
            self.payload
        ).hexdigest()

    @property
    def size_bytes(self) -> int:
        """Retorna o tamanho do payload."""

        return len(self.payload)

    @property
    def text(self) -> str:
        """Decodifica o payload como UTF-8."""

        return self.payload.decode("utf-8")
