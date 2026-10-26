"""Testes do repositorio SQLite de entidades."""

from dataclasses import replace

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    DuplicateEntityError,
    Entity,
    EntityIdentifier,
    EntityType,
    IdentifierType,
    RepositoryValidationError,
    SourceType,
)
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
)


@pytest.fixture
def provenance():
    return DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )


@pytest.fixture
def repository(tmp_path):
    database_path = (
        tmp_path
        / "sqlite_entity_repository.sqlite3"
    )

    manager = SQLiteConnectionManager(database_path)

    return SQLiteEntityRepository(manager)


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


def test_repository_saves_and_loads_entity(
    repository,
    provenance,
):
    entity = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
        cnpj="12.345.678/0001-90",
    )

    repository.save(entity)

    restored = repository.get_by_id(
        entity.entity_id
    )

    assert restored == entity
    assert restored is not entity


def test_repository_returns_none_when_missing(
    repository,
):
    from uuid import uuid4

    assert repository.get_by_id(uuid4()) is None


def test_repository_finds_by_formatted_identifier(
    repository,
    provenance,
):
    entity = create_entity(
        provenance,
        "Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        cnpj="12.345.678/0001-90",
    )

    repository.save(entity)

    restored = repository.get_by_identifier(
        IdentifierType.CNPJ,
        "12345678000190",
    )

    assert restored == entity


def test_repository_rejects_duplicate_identifier(
    repository,
    provenance,
):
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
    repository,
    provenance,
):
    entity = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
    )

    repository.save(entity)
    repository.save(entity)

    assert repository.count() == 1


def test_repository_updates_identifier_index(
    repository,
    provenance,
):
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
    ) == updated


def test_repository_lists_in_name_order(
    repository,
    provenance,
):
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

    assert repository.list_all() == (
        alpha,
        beta,
    )


def test_repository_filters_and_counts_type(
    repository,
    provenance,
):
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

    assert repository.list_all(
        EntityType.BANK
    ) == (bank,)

    assert repository.count(
        EntityType.BANK
    ) == 1

    assert repository.count() == 2


def test_repository_reports_existence(
    repository,
    provenance,
):
    entity = create_entity(
        provenance,
        "Empresa Exemplo S.A.",
    )

    assert repository.exists(entity.entity_id) is False

    repository.save(entity)

    assert repository.exists(entity.entity_id) is True


@pytest.mark.parametrize(
    "operation",
    [
        lambda repository: repository.save("invalid"),
        lambda repository: repository.get_by_id("invalid"),
        lambda repository: repository.exists("invalid"),
        lambda repository: repository.list_all("invalid"),
        lambda repository: repository.count("invalid"),
    ],
)
def test_repository_rejects_invalid_input(
    repository,
    operation,
):
    with pytest.raises(RepositoryValidationError):
        operation(repository)


def create_instrument(provenance, legal_name, isin, asset_code):
    return Entity(
        legal_name=legal_name,
        entity_type=EntityType.DEBENTURE,
        provenance=provenance,
        identifiers=(
            EntityIdentifier(
                identifier_type=IdentifierType.ASSET_CODE,
                value=asset_code,
                provenance=provenance,
                is_primary=True,
            ),
            EntityIdentifier(
                identifier_type=IdentifierType.ISIN,
                value=isin,
                provenance=provenance,
                is_primary=True,
            ),
        ),
    )


def test_repository_round_trips_instrument_entity(
    repository,
    provenance,
):
    instrument = create_instrument(
        provenance,
        "ALFA11",
        "BRALFADBS001",
        "ALFA11",
    )

    repository.save(instrument)

    restored = repository.get_by_id(instrument.entity_id)

    assert restored == instrument
    assert restored.entity_type is EntityType.DEBENTURE
    assert (
        repository.get_by_identifier(
            IdentifierType.ISIN,
            "bralfadbs001",
        )
        == instrument
    )
    assert (
        repository.get_by_identifier(
            IdentifierType.ASSET_CODE,
            "alfa11",
        )
        == instrument
    )
    assert repository.list_all(EntityType.DEBENTURE) == (
        instrument,
    )


def test_repository_rejects_isin_owned_by_other_entity(
    repository,
    provenance,
):
    first = create_instrument(
        provenance,
        "ALFA11",
        "BRALFADBS001",
        "ALFA11",
    )
    second = create_instrument(
        provenance,
        "ALFA12",
        "BRALFADBS001",
        "ALFA12",
    )

    repository.save(first)

    with pytest.raises(DuplicateEntityError):
        repository.save(second)

    assert repository.count(EntityType.DEBENTURE) == 1
