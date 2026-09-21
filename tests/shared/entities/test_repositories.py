"""Testes dos repositorios em memoria."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    DuplicateEntityError,
    DuplicateRelationshipError,
    Entity,
    EntityIdentifier,
    EntityRelationship,
    EntityType,
    IdentifierType,
    InMemoryEntityRepository,
    InMemoryRelationshipRepository,
    RelationshipStatus,
    RelationshipType,
    RepositoryValidationError,
    SourceType,
)


@pytest.fixture
def provenance():
    return DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )


def create_entity(
    provenance,
    legal_name,
    entity_type=EntityType.COMPANY,
    cnpj=None,
):
    identifiers = ()

    if cnpj is not None:
        identifiers = (
            EntityIdentifier(
                identifier_type=IdentifierType.CNPJ,
                value=cnpj,
                provenance=provenance,
                is_primary=True,
            ),
        )

    return Entity(
        legal_name=legal_name,
        entity_type=entity_type,
        provenance=provenance,
        identifiers=identifiers,
    )


def create_relationship(
    provenance,
    source_entity_id=None,
    target_entity_id=None,
    relationship_type=RelationshipType.CONTROLS,
    status=RelationshipStatus.ACTIVE,
    valid_from=None,
    valid_to=None,
):
    return EntityRelationship(
        source_entity_id=source_entity_id or uuid4(),
        target_entity_id=target_entity_id or uuid4(),
        relationship_type=relationship_type,
        provenance=provenance,
        status=status,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def test_entity_repository_saves_and_gets_entity(
    provenance,
):
    repository = InMemoryEntityRepository()
    entity = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
    )

    saved = repository.save(entity)

    assert saved is entity
    assert repository.get_by_id(entity.entity_id) is entity
    assert repository.exists(entity.entity_id) is True
    assert repository.count() == 1


def test_entity_repository_returns_none_when_missing():
    repository = InMemoryEntityRepository()

    assert repository.get_by_id(uuid4()) is None
    assert repository.exists(uuid4()) is False


def test_entity_repository_finds_formatted_cnpj(
    provenance,
):
    repository = InMemoryEntityRepository()
    entity = create_entity(
        provenance,
        "Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        cnpj="12.345.678/0001-90",
    )

    repository.save(entity)

    found = repository.get_by_identifier(
        IdentifierType.CNPJ,
        "12345678000190",
    )

    assert found is entity


def test_duplicate_identifier_is_rejected(
    provenance,
):
    repository = InMemoryEntityRepository()

    first = create_entity(
        provenance,
        "Empresa Alfa S.A.",
        cnpj="12.345.678/0001-90",
    )
    second = create_entity(
        provenance,
        "Empresa Beta S.A.",
        cnpj="12.345.678/0001-90",
    )

    repository.save(first)

    with pytest.raises(DuplicateEntityError):
        repository.save(second)

    assert repository.count() == 1


def test_saving_same_entity_is_idempotent(
    provenance,
):
    repository = InMemoryEntityRepository()
    entity = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
    )

    repository.save(entity)
    repository.save(entity)

    assert repository.count() == 1


def test_entity_repository_updates_identifier_index(
    provenance,
):
    repository = InMemoryEntityRepository()

    original = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
        cnpj="12.345.678/0001-90",
    )
    repository.save(original)

    replacement_identifier = EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value="98.765.432/0001-10",
        provenance=provenance,
        is_primary=True,
    )
    updated = replace(
        original,
        identifiers=(replacement_identifier,),
    )

    repository.save(updated)

    assert repository.get_by_identifier(
        IdentifierType.CNPJ,
        "12345678000190",
    ) is None
    assert repository.get_by_identifier(
        IdentifierType.CNPJ,
        "98765432000110",
    ) is updated


def test_entity_repository_lists_in_name_order(
    provenance,
):
    repository = InMemoryEntityRepository()

    beta = create_entity(
        provenance,
        "Empresa Beta S.A.",
    )
    alpha = create_entity(
        provenance,
        "Empresa Alfa S.A.",
    )

    repository.save(beta)
    repository.save(alpha)

    assert repository.list_all() == (alpha, beta)


def test_entity_repository_filters_and_counts_type(
    provenance,
):
    repository = InMemoryEntityRepository()

    bank = create_entity(
        provenance,
        "Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
    )
    company = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
        entity_type=EntityType.COMPANY,
    )

    repository.save(bank)
    repository.save(company)

    assert repository.list_all(EntityType.BANK) == (bank,)
    assert repository.count(EntityType.BANK) == 1
    assert repository.count() == 2


@pytest.mark.parametrize(
    "operation",
    [
        lambda repository: repository.save("invalid"),
        lambda repository: repository.get_by_id("invalid"),
        lambda repository: repository.exists("invalid"),
        lambda repository: repository.list_all("invalid"),
    ],
)
def test_entity_repository_rejects_invalid_input(
    operation,
):
    repository = InMemoryEntityRepository()

    with pytest.raises(RepositoryValidationError):
        operation(repository)


def test_relationship_repository_saves_and_gets(
    provenance,
):
    repository = InMemoryRelationshipRepository()
    relationship = create_relationship(provenance)

    saved = repository.save(relationship)

    assert saved is relationship
    assert repository.get_by_id(
        relationship.relationship_id
    ) is relationship
    assert repository.get_by_canonical_key(
        relationship.canonical_key
    ) is relationship
    assert repository.count() == 1


def test_relationship_save_is_idempotent(
    provenance,
):
    repository = InMemoryRelationshipRepository()
    relationship = create_relationship(provenance)

    repository.save(relationship)
    repository.save(relationship)

    assert repository.count() == 1


def test_duplicate_relationship_is_rejected(
    provenance,
):
    repository = InMemoryRelationshipRepository()

    source_id = uuid4()
    target_id = uuid4()

    first = create_relationship(
        provenance,
        source_entity_id=source_id,
        target_entity_id=target_id,
    )
    duplicate = create_relationship(
        provenance,
        source_entity_id=source_id,
        target_entity_id=target_id,
    )

    repository.save(first)

    with pytest.raises(DuplicateRelationshipError):
        repository.save(duplicate)

    assert repository.count() == 1


def test_relationship_repository_lists_by_source(
    provenance,
):
    repository = InMemoryRelationshipRepository()

    source_id = uuid4()
    first = create_relationship(
        provenance,
        source_entity_id=source_id,
    )
    second = create_relationship(
        provenance,
        source_entity_id=source_id,
        relationship_type=RelationshipType.GUARANTEES,
    )
    unrelated = create_relationship(provenance)

    repository.save(first)
    repository.save(second)
    repository.save(unrelated)

    result = repository.list_by_source(source_id)

    assert set(result) == {first, second}


def test_relationship_repository_lists_by_target(
    provenance,
):
    repository = InMemoryRelationshipRepository()

    target_id = uuid4()
    first = create_relationship(
        provenance,
        target_entity_id=target_id,
    )
    second = create_relationship(
        provenance,
        target_entity_id=target_id,
        relationship_type=RelationshipType.MANAGES,
    )

    repository.save(first)
    repository.save(second)

    result = repository.list_by_target(target_id)

    assert set(result) == {first, second}


def test_relationship_repository_lists_only_active(
    provenance,
):
    repository = InMemoryRelationshipRepository()
    reference = datetime(2026, 1, 15, tzinfo=UTC)

    active = create_relationship(
        provenance,
        valid_from=reference - timedelta(days=10),
        valid_to=reference + timedelta(days=10),
    )
    expired = create_relationship(
        provenance,
        relationship_type=RelationshipType.GUARANTEES,
        valid_from=reference - timedelta(days=20),
        valid_to=reference - timedelta(days=1),
    )
    pending = create_relationship(
        provenance,
        relationship_type=RelationshipType.MANAGES,
        status=RelationshipStatus.PENDING_REVIEW,
    )

    repository.save(active)
    repository.save(expired)
    repository.save(pending)

    assert repository.list_active_at(reference) == (active,)


def test_relationship_repository_filters_active_type(
    provenance,
):
    repository = InMemoryRelationshipRepository()
    reference = datetime(2026, 1, 15, tzinfo=UTC)

    controls = create_relationship(
        provenance,
        relationship_type=RelationshipType.CONTROLS,
    )
    manages = create_relationship(
        provenance,
        relationship_type=RelationshipType.MANAGES,
    )

    repository.save(controls)
    repository.save(manages)

    result = repository.list_active_at(
        reference,
        RelationshipType.MANAGES,
    )

    assert result == (manages,)


def test_relationship_repository_counts_type(
    provenance,
):
    repository = InMemoryRelationshipRepository()

    repository.save(
        create_relationship(
            provenance,
            relationship_type=RelationshipType.CONTROLS,
        )
    )
    repository.save(
        create_relationship(
            provenance,
            relationship_type=RelationshipType.MANAGES,
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
def test_relationship_repository_rejects_invalid_input(
    operation,
):
    repository = InMemoryRelationshipRepository()

    with pytest.raises(RepositoryValidationError):
        operation(repository)
