"""Contratos publicos da Shared Entity Layer."""

from .enums import (
    EntityStatus,
    EntityType,
    IdentifierType,
    MatchDecision,
    MatchStrength,
    RelationshipStatus,
    RelationshipType,
    SourceType,
    ValidationStatus,
)
from .exceptions import (
    DuplicateEntityError,
    DuplicateRelationshipError,
    EntityLayerError,
    EntityNotFoundError,
    EntityValidationError,
    IdentifierValidationError,
    ProvenanceValidationError,
    RelationshipNotFoundError,
    RepositoryValidationError,
)
from .identifiers import (
    EntityIdentifier,
    normalize_cnpj,
    normalize_identifier,
)
from .in_memory_repositories import (
    InMemoryEntityRepository,
    InMemoryRelationshipRepository,
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
from .relationships import (
    EntityRelationship,
    normalize_relationship_notes,
)
from .repository_protocols import (
    EntityRepository,
    RelationshipRepository,
)

__all__ = [
    "DataProvenance",
    "DuplicateEntityError",
    "DuplicateRelationshipError",
    "Entity",
    "EntityIdentifier",
    "EntityLayerError",
    "EntityMatcher",
    "EntityMatchResult",
    "EntityNotFoundError",
    "EntityRelationship",
    "EntityRepository",
    "EntityStatus",
    "EntityType",
    "EntityValidationError",
    "IdentifierType",
    "IdentifierValidationError",
    "InMemoryEntityRepository",
    "InMemoryRelationshipRepository",
    "MatchDecision",
    "MatchStrength",
    "ProvenanceValidationError",
    "RelationshipNotFoundError",
    "RelationshipRepository",
    "RelationshipStatus",
    "RelationshipType",
    "RepositoryValidationError",
    "SourceType",
    "ValidationStatus",
    "normalize_cnpj",
    "normalize_identifier",
    "normalize_matching_name",
    "normalize_name",
    "normalize_optional_text",
    "normalize_relationship_notes",
]
