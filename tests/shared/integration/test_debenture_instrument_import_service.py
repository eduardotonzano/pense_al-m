"""Testes do servico de importacao de debentures (instrumento)."""

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityStatus,
    EntityType,
    IdentifierType,
    InMemoryEntityRepository,
    InMemoryRelationshipRepository,
    MatchDecision,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration import (
    DebentureInstrumentImportService,
    DebentureInstrumentRecord,
    DebentureIssuerAdapter,
    DebentureIssuerRecord,
    EntityImportAction,
    InstrumentImportReason,
)

ALFA_CNPJ = "12345678000199"
BETA_CNPJ = "22345678000198"


def create_record(**overrides):
    values = {
        "legacy_id": 7,
        "asset_code": "ALFA11",
        "isin": "BRALFADBS001",
        "status": "active",
        "issuer_legacy_id": 1,
        "issuer_cnpj": ALFA_CNPJ,
        "created_at": "2026-09-20 10:00:00",
        "updated_at": "2026-09-21 12:00:00",
    }
    values.update(overrides)
    return DebentureInstrumentRecord(**values)


def create_issuer(legacy_id=1, cnpj=ALFA_CNPJ, name=None):
    return DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=legacy_id,
            legal_name=name or f"Empresa {legacy_id} S.A.",
            cnpj=cnpj,
            created_at="2026-09-20 10:00:00",
            updated_at="2026-09-21 12:00:00",
        )
    )


@pytest.fixture
def entities():
    repository = InMemoryEntityRepository()
    repository.save(create_issuer(1, ALFA_CNPJ))
    repository.save(create_issuer(2, BETA_CNPJ))

    return repository


@pytest.fixture
def relationships():
    return InMemoryRelationshipRepository()


@pytest.fixture
def service(entities, relationships):
    return DebentureInstrumentImportService(
        entities,
        relationships,
    )


def instrument_count(entities):
    return entities.count(EntityType.DEBENTURE)


def issues_count(relationships):
    return relationships.count(RelationshipType.ISSUES)


def test_import_creates_instrument_and_issuance(
    service,
    entities,
    relationships,
):
    result = service.import_record(create_record())

    assert result.action is EntityImportAction.CREATED
    assert result.was_created is True
    assert result.relationship_created is True
    assert result.reason is None
    assert result.resolved_entity.entity_type is (
        EntityType.DEBENTURE
    )
    assert result.issuer_entity.cnpj == ALFA_CNPJ
    assert instrument_count(entities) == 1
    assert issues_count(relationships) == 1

    relationship = result.relationship

    assert relationship.source_entity_id == (
        result.issuer_entity.entity_id
    )
    assert relationship.target_entity_id == (
        result.resolved_entity.entity_id
    )
    assert entities.get_by_identifier(
        IdentifierType.ISIN,
        "BRALFADBS001",
    ) == result.resolved_entity


def test_import_is_idempotent(
    service,
    entities,
    relationships,
):
    first = service.import_record(create_record())
    second = service.import_record(create_record())

    assert first.was_created is True
    assert second.was_matched is True
    assert second.relationship_created is False
    assert second.reason is None
    assert second.resolved_entity == first.resolved_entity
    assert second.match_result.decision is (
        MatchDecision.AUTO_MATCH
    )
    assert second.unmerged_identifiers == ()
    assert instrument_count(entities) == 1
    assert issues_count(relationships) == 1
    assert entities.count() == 3


def test_import_matches_existing_by_isin(
    service,
    entities,
    relationships,
):
    first = service.import_record(
        create_record(legacy_id=7, asset_code=None)
    )
    second = service.import_record(
        create_record(legacy_id=8)
    )

    assert second.was_matched is True
    assert second.resolved_entity == first.resolved_entity
    assert second.unmerged_identifiers == (
        "asset_code:ALFA11",
    )
    assert instrument_count(entities) == 1
    assert issues_count(relationships) == 1


def test_import_matches_existing_by_asset_code(
    service,
    entities,
):
    first = service.import_record(
        create_record(legacy_id=7, isin=None)
    )
    second = service.import_record(
        create_record(legacy_id=8)
    )

    assert second.was_matched is True
    assert second.resolved_entity == first.resolved_entity
    assert second.unmerged_identifiers == (
        "isin:BRALFADBS001",
    )
    assert instrument_count(entities) == 1


def test_import_does_not_update_existing_entity(
    service,
    entities,
):
    first = service.import_record(create_record())
    second = service.import_record(
        create_record(status="inactive")
    )

    assert second.was_matched is True
    assert first.resolved_entity.status is EntityStatus.ACTIVE
    assert second.resolved_entity.status is EntityStatus.ACTIVE
    assert entities.get_by_id(
        first.resolved_entity.entity_id
    ).status is EntityStatus.ACTIVE


def test_two_candidates_are_blocked_and_nothing_is_saved(
    service,
    entities,
    relationships,
):
    service.import_record(
        create_record(legacy_id=7, isin=None)
    )
    service.import_record(
        create_record(
            legacy_id=8,
            asset_code=None,
            isin="BRBETADBS002",
        )
    )

    entities_before = entities.count()
    issues_before = issues_count(relationships)

    result = service.import_record(
        create_record(
            legacy_id=9,
            asset_code="ALFA11",
            isin="BRBETADBS002",
        )
    )

    assert result.action is EntityImportAction.BLOCKED
    assert result.was_blocked is True
    assert result.reason is (
        InstrumentImportReason.CONFLICTING_CANDIDATES
    )
    assert result.relationship is None
    assert entities.count() == entities_before
    assert issues_count(relationships) == issues_before


def test_divergent_isin_for_same_asset_code_is_blocked(
    service,
    entities,
    relationships,
):
    service.import_record(create_record())

    result = service.import_record(
        create_record(
            legacy_id=8,
            asset_code="ALFA11",
            isin="BRZZZZDBS999",
        )
    )

    assert result.was_blocked is True
    assert result.reason is (
        InstrumentImportReason.IDENTIFIER_CONFLICT
    )
    assert result.match_result.decision is MatchDecision.BLOCKED
    assert instrument_count(entities) == 1
    assert issues_count(relationships) == 1
    assert entities.get_by_identifier(
        IdentifierType.ISIN,
        "BRZZZZDBS999",
    ) is None


def test_changed_identifiers_for_same_legacy_id_do_not_overwrite(
    service,
    entities,
):
    first = service.import_record(create_record())

    result = service.import_record(
        create_record(
            asset_code="OUTRO99",
            isin="BROUTRODBS99",
        )
    )

    assert result.was_blocked is True
    assert result.reason is (
        InstrumentImportReason.IDENTIFIER_CONFLICT
    )
    assert result.resolved_entity == first.resolved_entity

    stored = entities.get_by_id(first.resolved_entity.entity_id)

    assert stored == first.resolved_entity
    assert instrument_count(entities) == 1


def test_identifier_owned_by_non_instrument_is_blocked(
    service,
    entities,
    relationships,
):
    provenance = DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste",
    )
    entities.save(
        Entity(
            legal_name="Empresa Qualquer S.A.",
            entity_type=EntityType.COMPANY,
            provenance=provenance,
            identifiers=(
                EntityIdentifier(
                    identifier_type=IdentifierType.ASSET_CODE,
                    value="ALFA11",
                    provenance=provenance,
                ),
            ),
        )
    )

    result = service.import_record(create_record())

    assert result.was_blocked is True
    assert result.reason is (
        InstrumentImportReason.NOT_AN_INSTRUMENT
    )
    assert instrument_count(entities) == 0
    assert issues_count(relationships) == 0


def test_instrument_of_another_issuer_is_blocked(
    service,
    entities,
    relationships,
):
    first = service.import_record(create_record())

    result = service.import_record(
        create_record(
            issuer_legacy_id=2,
            issuer_cnpj=BETA_CNPJ,
        )
    )

    assert result.was_blocked is True
    assert result.reason is InstrumentImportReason.ISSUER_MISMATCH
    assert issues_count(relationships) == 1
    assert relationships.list_by_target(
        first.resolved_entity.entity_id
    )[0].source_entity_id == first.issuer_entity.entity_id


def test_record_without_issuer_goes_to_review(
    service,
    entities,
    relationships,
):
    entities_before = entities.count()

    result = service.import_record(
        create_record(
            issuer_legacy_id=None,
            issuer_cnpj=None,
        )
    )

    assert result.action is EntityImportAction.REVIEW
    assert result.requires_review is True
    assert result.reason is InstrumentImportReason.ISSUER_MISSING
    assert entities.count() == entities_before
    assert issues_count(relationships) == 0


def test_issuer_without_cnpj_goes_to_review(
    service,
    entities,
    relationships,
):
    entities_before = entities.count()

    result = service.import_record(
        create_record(issuer_cnpj=None)
    )

    assert result.requires_review is True
    assert result.reason is (
        InstrumentImportReason.ISSUER_WITHOUT_CNPJ
    )
    assert entities.count() == entities_before
    assert issues_count(relationships) == 0


def test_unregistered_issuer_goes_to_review_and_is_not_created(
    service,
    entities,
    relationships,
):
    entities_before = entities.count()

    result = service.import_record(
        create_record(
            issuer_legacy_id=3,
            issuer_cnpj="32345678000197",
        )
    )

    assert result.requires_review is True
    assert result.reason is (
        InstrumentImportReason.ISSUER_NOT_REGISTERED
    )
    assert entities.count() == entities_before
    assert entities.get_by_identifier(
        IdentifierType.CNPJ,
        "32345678000197",
    ) is None
    assert issues_count(relationships) == 0


def test_name_similarity_never_links_an_entity(
    service,
    entities,
    relationships,
):
    provenance = DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste",
    )
    company = Entity(
        legal_name="ALFA11",
        entity_type=EntityType.COMPANY,
        provenance=provenance,
    )
    entities.save(company)

    result = service.import_record(create_record())

    assert result.was_created is True
    assert result.resolved_entity.entity_id != company.entity_id
    assert entities.get_by_id(company.entity_id) == company
    assert instrument_count(entities) == 1


def test_issuer_of_any_entity_type_is_accepted(
    relationships,
):
    entities = InMemoryEntityRepository()
    provenance = DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Teste",
    )
    bank = Entity(
        legal_name="Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        provenance=provenance,
        identifiers=(
            EntityIdentifier(
                identifier_type=IdentifierType.CNPJ,
                value=ALFA_CNPJ,
                provenance=provenance,
                is_primary=True,
            ),
        ),
    )
    entities.save(bank)

    result = DebentureInstrumentImportService(
        entities,
        relationships,
    ).import_record(create_record())

    assert result.was_created is True
    assert result.issuer_entity == bank
    assert result.relationship.source_entity_id == bank.entity_id


def test_missing_relationship_is_repaired_on_rerun(
    entities,
    relationships,
):
    first = DebentureInstrumentImportService(
        entities,
        relationships,
    ).import_record(create_record())

    fresh_relationships = InMemoryRelationshipRepository()

    second = DebentureInstrumentImportService(
        entities,
        fresh_relationships,
    ).import_record(create_record())

    assert second.was_matched is True
    assert second.relationship_created is True
    assert second.resolved_entity == first.resolved_entity
    assert issues_count(fresh_relationships) == 1
    assert instrument_count(entities) == 1


def test_partial_failure_is_completed_on_rerun(entities):
    class FailingOnce(InMemoryRelationshipRepository):
        def __init__(self):
            super().__init__()
            self.failed = False

        def save(self, relationship):
            if not self.failed:
                self.failed = True
                raise RuntimeError("falha simulada")

            return super().save(relationship)

    relationships = FailingOnce()
    service = DebentureInstrumentImportService(
        entities,
        relationships,
    )

    with pytest.raises(RuntimeError):
        service.import_record(create_record())

    assert instrument_count(entities) == 1
    assert issues_count(relationships) == 0

    result = service.import_record(create_record())

    assert result.was_matched is True
    assert result.relationship_created is True
    assert instrument_count(entities) == 1
    assert issues_count(relationships) == 1


def test_blocked_and_review_results_require_a_reason(
    service,
):
    from pense_alm.shared.integration import (
        InstrumentImportResult,
    )

    incoming = service.import_record(
        create_record()
    ).incoming_entity

    with pytest.raises(ValueError):
        InstrumentImportResult(
            action=EntityImportAction.REVIEW,
            legacy_id=1,
            incoming_entity=incoming,
        )

    with pytest.raises(ValueError):
        InstrumentImportResult(
            action=EntityImportAction.CREATED,
            legacy_id=1,
            incoming_entity=incoming,
            reason=InstrumentImportReason.ISSUER_MISSING,
        )


@pytest.mark.parametrize(
    "entity_repository",
    [object(), None],
)
def test_service_validates_entity_repository(
    entity_repository,
    relationships,
):
    with pytest.raises(TypeError):
        DebentureInstrumentImportService(
            entity_repository,
            relationships,
        )


def test_service_validates_relationship_repository(entities):
    with pytest.raises(TypeError):
        DebentureInstrumentImportService(entities, object())
