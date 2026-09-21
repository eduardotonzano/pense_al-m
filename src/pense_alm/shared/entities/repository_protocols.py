"""Contratos de persistencia da Shared Entity Layer."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from .enums import (
    EntityType,
    IdentifierType,
    RelationshipType,
)
from .models import Entity
from .relationships import EntityRelationship


class EntityRepository(Protocol):
    """Contrato para armazenamento e consulta de entidades."""

    def save(self, entity: Entity) -> Entity:
        """Salva uma entidade."""

        ...

    def get_by_id(self, entity_id: UUID) -> Entity | None:
        """Localiza uma entidade pelo identificador interno."""

        ...

    def get_by_identifier(
        self,
        identifier_type: IdentifierType,
        value: str,
    ) -> Entity | None:
        """Localiza uma entidade por identificador oficial."""

        ...

    def list_all(
        self,
        entity_type: EntityType | None = None,
    ) -> tuple[Entity, ...]:
        """Lista entidades, opcionalmente filtradas por tipo."""

        ...

    def exists(self, entity_id: UUID) -> bool:
        """Indica se uma entidade existe."""

        ...

    def count(
        self,
        entity_type: EntityType | None = None,
    ) -> int:
        """Conta entidades, opcionalmente por tipo."""

        ...


class RelationshipRepository(Protocol):
    """Contrato para armazenamento de relacionamentos."""

    def save(
        self,
        relationship: EntityRelationship,
    ) -> EntityRelationship:
        """Salva um relacionamento."""

        ...

    def get_by_id(
        self,
        relationship_id: UUID,
    ) -> EntityRelationship | None:
        """Localiza um relacionamento pelo UUID."""

        ...

    def get_by_canonical_key(
        self,
        canonical_key: str,
    ) -> EntityRelationship | None:
        """Localiza uma relacao pela chave canonica."""

        ...

    def list_by_source(
        self,
        source_entity_id: UUID,
    ) -> tuple[EntityRelationship, ...]:
        """Lista relacoes originadas por uma entidade."""

        ...

    def list_by_target(
        self,
        target_entity_id: UUID,
    ) -> tuple[EntityRelationship, ...]:
        """Lista relacoes destinadas a uma entidade."""

        ...

    def list_active_at(
        self,
        reference_datetime: datetime,
        relationship_type: RelationshipType | None = None,
    ) -> tuple[EntityRelationship, ...]:
        """Lista relacionamentos ativos em determinada data."""

        ...

    def count(
        self,
        relationship_type: RelationshipType | None = None,
    ) -> int:
        """Conta relacionamentos, opcionalmente por tipo."""

        ...
