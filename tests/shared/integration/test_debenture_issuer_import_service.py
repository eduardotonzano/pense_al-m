"""Testes do servico de importacao de emissores."""

from pense_alm.shared.entities import (
    Entity,
    EntityType,
    InMemoryEntityRepository,
    MatchDecision,
)
from pense_alm.shared.integration import (
    DebentureIssuerImportService,
    DebentureIssuerRecord,
    EntityImportAction,
)


def create_record(**overrides):
    values = {
        "legacy_id": 42,
        "legal_name": "Empresa Brasileira S.A.",
        "trade_name": "Empresa Brasileira",
        "cnpj": "12.345.678/0001-99",
        "created_at": "2026-09-20 10:00:00",
        "updated_at": "2026-09-21 12:30:00",
    }
    values.update(overrides)
    return DebentureIssuerRecord(**values)


def test_import_creates_new_entity():
    repository = InMemoryEntityRepository()
    service = DebentureIssuerImportService(repository)

    result = service.import_record(create_record())

    assert result.action is EntityImportAction.CREATED
    assert result.was_created is True
    assert result.resolved_entity is not None
    assert repository.count() == 1


def test_repeated_cnpj_matches_existing_entity():
    repository = InMemoryEntityRepository()
    service = DebentureIssuerImportService(repository)

    first = service.import_record(
        create_record(legacy_id=42)
    )
    second = service.import_record(
        create_record(
            legacy_id=43,
            legal_name="Nome Diferente S.A.",
        )
    )

    assert first.was_created is True
    assert second.was_matched is True
    assert second.action is EntityImportAction.MATCHED
    assert second.match_result is not None
    assert second.match_result.decision is (
        MatchDecision.AUTO_MATCH
    )
    assert second.resolved_entity == first.resolved_entity
    assert repository.count() == 1


def test_same_name_without_cnpj_requires_review():
    repository = InMemoryEntityRepository()
    service = DebentureIssuerImportService(repository)

    first = service.import_record(
        create_record(
            legacy_id=42,
            cnpj=None,
        )
    )
    second = service.import_record(
        create_record(
            legacy_id=43,
            cnpj=None,
        )
    )

    assert first.was_created is True
    assert second.requires_review is True
    assert second.action is EntityImportAction.REVIEW
    assert second.match_result is not None
    assert second.match_result.decision is MatchDecision.REVIEW
    assert repository.count() == 1


def test_different_name_without_cnpj_creates_entity():
    repository = InMemoryEntityRepository()
    service = DebentureIssuerImportService(repository)

    service.import_record(
        create_record(
            legacy_id=42,
            cnpj=None,
        )
    )

    result = service.import_record(
        create_record(
            legacy_id=43,
            legal_name="Outra Empresa S.A.",
            trade_name=None,
            cnpj=None,
        )
    )

    assert result.was_created is True
    assert repository.count() == 2


def test_import_preserves_existing_entity_data():
    repository = InMemoryEntityRepository()
    service = DebentureIssuerImportService(repository)

    first = service.import_record(
        create_record(
            legal_name="Nome Original S.A.",
        )
    )

    second = service.import_record(
        create_record(
            legacy_id=99,
            legal_name="Nome Atualizado S.A.",
        )
    )

    assert second.was_matched is True
    assert second.resolved_entity == first.resolved_entity
    assert second.resolved_entity.legal_name == (
        "Nome Original S.A."
    )


def test_service_only_compares_companies():
    from pense_alm.shared.entities import (
        DataProvenance,
        SourceType,
    )

    repository = InMemoryEntityRepository()

    unrelated = Entity(
        legal_name="Empresa Brasileira S.A.",
        entity_type=EntityType.FIDC,
        provenance=DataProvenance(
            source_type=SourceType.MANUAL,
            source_name="Teste",
        ),
    )

    repository.save(unrelated)

    service = DebentureIssuerImportService(repository)

    result = service.import_record(
        create_record(
            cnpj=None,
        )
    )

    assert result.was_created is True
    assert result.resolved_entity is not None
    assert result.resolved_entity.entity_type is EntityType.COMPANY
    assert repository.count() == 2
