"""Contratos publicos da Shared Entity Layer."""

from .enums import (
    EntityStatus,
    EntityType,
    IdentifierType,
    SourceType,
    ValidationStatus,
)
from .exceptions import (
    DuplicateEntityError,
    EntityLayerError,
    EntityValidationError,
    IdentifierValidationError,
    ProvenanceValidationError,
)
from .identifiers import (
    EntityIdentifier,
    normalize_cnpj,
    normalize_identifier,
)
from .models import (
    Entity,
    normalize_name,
    normalize_optional_text,
)
from .provenance import DataProvenance

__all__ = [
    "DataProvenance",
    "DuplicateEntityError",
    "Entity",
    "EntityIdentifier",
    "EntityLayerError",
    "EntityStatus",
    "EntityType",
    "EntityValidationError",
    "IdentifierType",
    "IdentifierValidationError",
    "ProvenanceValidationError",
    "SourceType",
    "ValidationStatus",
    "normalize_cnpj",
    "normalize_identifier",
    "normalize_name",
    "normalize_optional_text",
]
