"""Contratos publicos da Shared Entity Layer."""

from .enums import (
    EntityStatus,
    EntityType,
    IdentifierType,
    MatchDecision,
    MatchStrength,
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
from .matching import (
    EntityMatcher,
    EntityMatchResult,
    normalize_matching_name,
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
    "EntityMatcher",
    "EntityMatchResult",
    "EntityStatus",
    "EntityType",
    "EntityValidationError",
    "IdentifierType",
    "IdentifierValidationError",
    "MatchDecision",
    "MatchStrength",
    "ProvenanceValidationError",
    "SourceType",
    "ValidationStatus",
    "normalize_cnpj",
    "normalize_identifier",
    "normalize_matching_name",
    "normalize_name",
    "normalize_optional_text",
]
