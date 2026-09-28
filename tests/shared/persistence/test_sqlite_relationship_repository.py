"""Testes do repositorio SQLite de relacionamentos."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    DuplicateRelationshipError,
    Entity,
    EntityRelationship,
    EntityType,
    RelationshipStatus,
    RelationshipType,
    RepositoryValidationError,
    SourceType,
)
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)


@pytest.fixture
def provenance():
    return DataProvenance(
        source_type=SourceType.CVM,
        source_name="CVM",
    )


@pytest.fixture
def repositories(tmp_path):
    database_path = (
        tmp_path
        / "sqlite_relationship_repository.sqlite3"
    )

    manager = SQLiteConnectionManager(database_path)

    entity_repository = SQLiteEntityRepository(
        manager
    )
    relationship_repository = (
        SQLiteRelationshipRepository(manager)
    )

    return (
        entity_repository,
        relationship_repository,
    )


def create_entity(
    provenance,
    legal_name,
    entity_type=EntityType.COMPANY,
):
    return Entity(
        legal_name=legal_name,
        entity_type=entity_type,
        provenance=provenance,
    )


def create_relationship(
    provenance,
    source_entity_id,
    target_entity_id,
    relationship_type=RelationshipType.CONTROLS,
    status=RelationshipStatus.ACTIVE,
    valid_from=None,
    valid_to=None,
):
    return EntityRelationship(
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        provenance=provenance,
        status=status,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def save_entities(
    entity_repository,
    provenance,
):
    source = create_entity(
        provenance,
        "Holding Exemplo S.A.",
        EntityType.HOLDING,
    )
    target = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
        EntityType.COMPANY,
    )

    entity_repository.save(source)
    entity_repository.save(target)

    return source, target


def test_repository_saves_and_loads_relationship(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source, target = save_entities(
        entity_repository,
        provenance,
    )

    relationship = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )

    repository.save(relationship)

    restored = repository.get_by_id(
        relationship.relationship_id
    )

    assert restored == relationship
    assert restored is not relationship


def test_repository_returns_none_when_missing(
    repositories,
):
    _, repository = repositories

    assert repository.get_by_id(uuid4()) is None


def test_repository_finds_by_canonical_key(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source, target = save_entities(
        entity_repository,
        provenance,
    )

    relationship = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )

    repository.save(relationship)

    restored = repository.get_by_canonical_key(
        relationship.canonical_key
    )

    assert restored == relationship


def test_repository_requires_existing_entities(
    repositories,
    provenance,
):
    _, repository = repositories

    relationship = create_relationship(
        provenance,
        uuid4(),
        uuid4(),
    )

    with pytest.raises(RepositoryValidationError):
        repository.save(relationship)

    assert repository.count() == 0


def test_repository_rejects_duplicate_relationship(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source, target = save_entities(
        entity_repository,
        provenance,
    )

    first = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )
    duplicate = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )

    repository.save(first)

    with pytest.raises(DuplicateRelationshipError):
        repository.save(duplicate)

    assert repository.count() == 1


def test_saving_same_relationship_is_idempotent(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source, target = save_entities(
        entity_repository,
        provenance,
    )

    relationship = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )

    repository.save(relationship)
    repository.save(relationship)

    assert repository.count() == 1


def test_repository_updates_relationship(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source, target = save_entities(
        entity_repository,
        provenance,
    )

    original = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )

    repository.save(original)

    updated = replace(
        original,
        notes="Controle confirmado",
        confidence_score=95,
    )

    repository.save(updated)

    restored = repository.get_by_id(
        original.relationship_id
    )

    assert restored == updated
    assert repository.count() == 1


def test_repository_lists_by_source(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source = create_entity(
        provenance,
        "Holding Exemplo S.A.",
        EntityType.HOLDING,
    )
    first_target = create_entity(
        provenance,
        "Empresa Alfa S.A.",
    )
    second_target = create_entity(
        provenance,
        "Empresa Beta S.A.",
    )

    for entity in (
        source,
        first_target,
        second_target,
    ):
        entity_repository.save(entity)

    first = create_relationship(
        provenance,
        source.entity_id,
        first_target.entity_id,
    )
    second = create_relationship(
        provenance,
        source.entity_id,
        second_target.entity_id,
        RelationshipType.GUARANTEES,
    )

    repository.save(first)
    repository.save(second)

    assert set(
        repository.list_by_source(source.entity_id)
    ) == {first, second}


def test_repository_lists_by_target(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source, target = save_entities(
        entity_repository,
        provenance,
    )

    second_source = create_entity(
        provenance,
        "Gestora Exemplo S.A.",
        EntityType.ASSET_MANAGER,
    )
    entity_repository.save(second_source)

    first = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
    )
    second = create_relationship(
        provenance,
        second_source.entity_id,
        target.entity_id,
        RelationshipType.MANAGES,
    )

    repository.save(first)
    repository.save(second)

    assert set(
        repository.list_by_target(target.entity_id)
    ) == {first, second}


def test_repository_lists_active_at_date(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source = create_entity(
        provenance,
        "Holding Exemplo S.A.",
        EntityType.HOLDING,
    )
    target = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
    )
    second_target = create_entity(
        provenance,
        "Empresa Encerrada S.A.",
    )
    pending_target = create_entity(
        provenance,
        "Empresa em Revisao S.A.",
    )

    for entity in (
        source,
        target,
        second_target,
        pending_target,
    ):
        entity_repository.save(entity)

    reference = datetime(
        2026,
        6,
        30,
        tzinfo=UTC,
    )

    active = create_relationship(
        provenance,
        source.entity_id,
        target.entity_id,
        valid_from=reference - timedelta(days=30),
        valid_to=reference + timedelta(days=30),
    )

    expired = create_relationship(
        provenance,
        source.entity_id,
        second_target.entity_id,
        relationship_type=RelationshipType.GUARANTEES,
        valid_from=reference - timedelta(days=60),
        valid_to=reference - timedelta(days=1),
    )

    pending = create_relationship(
        provenance,
        source.entity_id,
        pending_target.entity_id,
        relationship_type=RelationshipType.MANAGES,
        status=RelationshipStatus.PENDING_REVIEW,
    )

    repository.save(active)
    repository.save(expired)
    repository.save(pending)

    assert repository.list_active_at(reference) == (
        active,
    )


def test_repository_filters_active_type(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source = create_entity(
        provenance,
        "Holding Exemplo S.A.",
        EntityType.HOLDING,
    )
    controlled = create_entity(
        provenance,
        "Empresa Controlada S.A.",
    )
    managed = create_entity(
        provenance,
        "FIDC Exemplo",
        EntityType.FIDC,
    )

    for entity in (
        source,
        controlled,
        managed,
    ):
        entity_repository.save(entity)

    controls = create_relationship(
        provenance,
        source.entity_id,
        controlled.entity_id,
        RelationshipType.CONTROLS,
    )

    manages = create_relationship(
        provenance,
        source.entity_id,
        managed.entity_id,
        RelationshipType.MANAGES,
    )

    repository.save(controls)
    repository.save(manages)

    reference = datetime.now(UTC)

    assert repository.list_active_at(
        reference,
        RelationshipType.MANAGES,
    ) == (manages,)


def test_repository_counts_type(
    repositories,
    provenance,
):
    entity_repository, repository = repositories

    source = create_entity(
        provenance,
        "Holding Exemplo S.A.",
        EntityType.HOLDING,
    )
    first_target = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
    )
    second_target = create_entity(
        provenance,
        "FIDC Exemplo",
        EntityType.FIDC,
    )

    for entity in (
        source,
        first_target,
        second_target,
    ):
        entity_repository.save(entity)

    repository.save(
        create_relationship(
            provenance,
            source.entity_id,
            first_target.entity_id,
            RelationshipType.CONTROLS,
        )
    )

    repository.save(
        create_relationship(
            provenance,
            source.entity_id,
            second_target.entity_id,
            RelationshipType.MANAGES,
        )
    )

    assert repository.count() == 2
    assert repository.count(
        RelationshipType.MANAGES
    ) == 1


@pytest.mark.parametrize(
    "operation",
    [
        lambda repository: repository.save("invalid"),
        lambda repository: repository.get_by_id("invalid"),
        lambda repository: repository.get_by_canonical_key(" "),
        lambda repository: repository.list_by_source("invalid"),
        lambda repository: repository.list_by_target("invalid"),
        lambda repository: repository.list_active_at(
            datetime(2026, 1, 1)
        ),
        lambda repository: repository.count("invalid"),
    ],
)
def test_repository_rejects_invalid_input(
    repositories,
    operation,
):
    _, repository = repositories

    with pytest.raises(RepositoryValidationError):
        operation(repository)
