"""Modelos de requisicoes compartilhadas de coleta."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID, uuid4

from .sources import normalize_required_text


def normalize_mapping(
    value: Mapping[str, Any] | None,
    field_name: str,
) -> Mapping[str, Any]:
    """Normaliza e protege um mapeamento."""

    if value is None:
        return MappingProxyType({})

    if not isinstance(value, Mapping):
        raise TypeError(
            f"{field_name} deve ser um mapeamento."
        )

    normalized = {}

    for key, item in value.items():
        normalized_key = normalize_required_text(
            key,
            f"{field_name}.key",
        )

        normalized[normalized_key] = item

    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    """Solicitacao independente de uma implementacao HTTP."""

    source_id: UUID
    operation: str
    target: str
    parameters: Mapping[str, Any] = field(
        default_factory=dict
    )
    headers: Mapping[str, Any] = field(
        default_factory=dict
    )
    request_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, UUID):
            raise TypeError(
                "source_id deve ser UUID."
            )

        if not isinstance(self.request_id, UUID):
            raise TypeError(
                "request_id deve ser UUID."
            )

        normalized_operation = normalize_required_text(
            self.operation,
            "operation",
        ).upper()

        normalized_target = normalize_required_text(
            self.target,
            "target",
        )

        normalized_parameters = normalize_mapping(
            self.parameters,
            "parameters",
        )
        normalized_headers = normalize_mapping(
            self.headers,
            "headers",
        )

        object.__setattr__(
            self,
            "operation",
            normalized_operation,
        )
        object.__setattr__(
            self,
            "target",
            normalized_target,
        )
        object.__setattr__(
            self,
            "parameters",
            normalized_parameters,
        )
        object.__setattr__(
            self,
            "headers",
            normalized_headers,
        )
