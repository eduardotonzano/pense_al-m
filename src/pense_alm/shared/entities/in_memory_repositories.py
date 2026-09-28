"""Implementacoes em memoria dos repositorios."""

from datetime import datetime
from uuid import UUID

from .enums import (
    EntityType,
    IdentifierType,
    RelationshipType,
)
from .exceptions import (
    DuplicateEntityError,
    DuplicateRelationshipError,
    RepositoryValidationError,
)
from .identifiers import normalize_identifier
from .models import Entity
from .relationships import EntityRelationship


class InMemoryEntityRepository:
    """Repositorio de entidades para testes e prototipos."""

    def __init__(self) -> None:
        self._entities: dict[UUID, Entity] = {}
        self._identifier_index: dict[str, UUID] = {}

    def save(self, entity: Entity) -> Entity:
        if not isinstance(entity, Entity):
            raise RepositoryValidationError(
                "entity deve ser uma instancia de Entity."
            )

        existing = self._entities.get(entity.entity_id)

        for identifier in entity.identifiers:
            owner_id = self._identifier_index.get(
                identifier.canonical_key
            )

            if (
                owner_id is not None
                and owner_id != entity.entity_id
            ):
                raise DuplicateEntityError(
                    "O identificador ja pertence a outra entidade: "
                    f"{identifier.canonical_key}."
                )

        if existing is not None:
            old_keys = {
                identifier.canonical_key
                for identifier in existing.identifiers
            }
            new_keys = {
                identifier.canonical_key
                for identifier in entity.identifiers
            }

            for removed_key in old_keys - new_keys:
                self._identifier_index.pop(removed_key, None)

        self._entities[entity.entity_id] = entity

        for identifier in entity.identifiers:
            self._identifier_index[
                identifier.canonical_key
            ] = entity.entity_id

        return entity

    def get_by_id(self, entity_id: UUID) -> Entity | None:
        if not isinstance(entity_id, UUID):
            raise RepositoryValidationError(
                "entity_id deve ser UUID."
            )

        return self._entities.get(entity_id)

    def get_by_identifier(
        self,
        identifier_type: IdentifierType,
        value: str,
    ) -> Entity | None:
        if not isinstance(identifier_type, IdentifierType):
            raise RepositoryValidationError(
                "identifier_type invalido."
            )

        normalized = normalize_identifier(
            identifier_type,
            value,
        )
        canonical_key = (
            f"{identifier_type.value}:{normalized}"
        )

        entity_id = self._identifier_index.get(canonical_key)

        if entity_id is None:
            return None

        return self._entities[entity_id]

    def list_all(
        self,
        entity_type: EntityType | None = None,
    ) -> tuple[Entity, ...]:
        if (
            entity_type is not None
            and not isinstance(entity_type, EntityType)
        ):
            raise RepositoryValidationError(
                "entity_type invalido."
            )

        entities = tuple(self._entities.values())

        if entity_type is not None:
            entities = tuple(
                entity
                for entity in entities
                if entity.entity_type is entity_type
            )

        return tuple(
            sorted(
                entities,
                key=lambda entity: (
                    entity.legal_name.casefold(),
                    str(entity.entity_id),
                ),
            )
        )

    def exists(self, entity_id: UUID) -> bool:
        if not isinstance(entity_id, UUID):
            raise RepositoryValidationError(
                "entity_id deve ser UUID."
            )

        return entity_id in self._entities

    def count(
        self,
        entity_type: EntityType | None = None,
    ) -> int:
        return len(self.list_all(entity_type))


class InMemoryRelationshipRepository:
    """Repositorio de relacionamentos para testes."""

    def __init__(self) -> None:
        self._relationships: dict[
            UUID,
            EntityRelationship,
        ] = {}
        self._canonical_index: dict[str, UUID] = {}

    def save(
        self,
        relationship: EntityRelationship,
    ) -> EntityRelationship:
        if not isinstance(
            relationship,
            EntityRelationship,
        ):
            raise RepositoryValidationError(
                "relationship deve ser EntityRelationship."
            )

        owner_id = self._canonical_index.get(
            relationship.canonical_key
        )

        if (
            owner_id is not None
            and owner_id != relationship.relationship_id
        ):
            raise DuplicateRelationshipError(
                "O relacionamento ja existe: "
                f"{relationship.canonical_key}."
            )

        existing = self._relationships.get(
            relationship.relationship_id
        )

        if (
            existing is not None
            and existing.canonical_key
            != relationship.canonical_key
        ):
            self._canonical_index.pop(
                existing.canonical_key,
                None,
            )

        self._relationships[
            relationship.relationship_id
        ] = relationship

        self._canonical_index[
            relationship.canonical_key
        ] = relationship.relationship_id

        return relationship

    def get_by_id(
        self,
        relationship_id: UUID,
    ) -> EntityRelationship | None:
        if not isinstance(relationship_id, UUID):
            raise RepositoryValidationError(
                "relationship_id deve ser UUID."
            )

        return self._relationships.get(relationship_id)

    def get_by_canonical_key(
        self,
        canonical_key: str,
    ) -> EntityRelationship | None:
        if not isinstance(canonical_key, str):
            raise RepositoryValidationError(
                "canonical_key deve ser texto."
            )

        normalized_key = canonical_key.strip()

        if not normalized_key:
            raise RepositoryValidationError(
                "canonical_key nao pode ser vazia."
            )

        relationship_id = self._canonical_index.get(
            normalized_key
        )

        if relationship_id is None:
            return None

        return self._relationships[relationship_id]

    def list_by_source(
        self,
        source_entity_id: UUID,
        ) -> tuple[EntityRelationship, ...]:
        self._validate_entity_id(source_entity_id)

        return self._sort_relationships(
            relationship
            for relationship in self._relationships.values()
            if relationship.source_entity_id
            == source_entity_id
        )

    def list_by_target(
        self,
        target_entity_id: UUID,
    ) -> tuple[EntityRelationship, ...]:
        self._validate_entity_id(target_entity_id)

        return self._sort_relationships(
            relationship
            for relationship in self._relationships.values()
            if relationship.target_entity_id
            == target_entity_id
        )

    def list_active_at(
        self,
        reference_datetime: datetime,
        relationship_type: RelationshipType | None = None,
    ) -> tuple[EntityRelationship, ...]:
        if not isinstance(reference_datetime, datetime):
            raise RepositoryValidationError(
                "reference_datetime deve ser datetime."
            )

        if reference_datetime.tzinfo is None:
            raise RepositoryValidationError(
                "reference_datetime deve possuir timezone."
            )

        if (
            relationship_type is not None
            and not isinstance(
                relationship_type,
                RelationshipType,
            )
        ):
            raise RepositoryValidationError(
                "relationship_type invalido."
            )

        return self._sort_relationships(
            relationship
            for relationship in self._relationships.values()
            if relationship.is_active_at(reference_datetime)
            and (
                relationship_type is None
                or relationship.relationship_type
                is relationship_type
            )
        )

    def count(
        self,
        relationship_type: RelationshipType | None = None,
    ) -> int:
        if (
            relationship_type is not None
            and not isinstance(
                relationship_type,
                RelationshipType,
            )
        ):
            raise RepositoryValidationError(
                "relationship_type invalido."
            )

        return sum(
            1
            for relationship in self._relationships.values()
            if (
                relationship_type is None
                or relationship.relationship_type
                is relationship_type
        )
        )

    @staticmethod
    def _validate_entity_id(entity_id: UUID) -> None:
        if not isinstance(entity_id, UUID):
            raise RepositoryValidationError(
                "entity_id deve ser UUID."
            )

    @staticmethod
    def _sort_relationships(
        relationships,
    ) -> tuple[EntityRelationship, ...]:
        return tuple(
            sorted(
                relationships,
                key=lambda relationship: (
                    relationship.relationship_type.value,
                    str(relationship.source_entity_id),
                    str(relationship.target_entity_id),
                ),
            )
        )
