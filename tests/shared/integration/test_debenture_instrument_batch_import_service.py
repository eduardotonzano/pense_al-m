"""Testes da importacao em lote de debentures (instrumento)."""

import hashlib

import pytest

from pense_alm.shared.entities import (
    EntityType,
    InMemoryEntityRepository,
    InMemoryRelationshipRepository,
    RelationshipType,
)
from pense_alm.shared.integration import (
    DebentureInstrumentBatchImportService,
    DebentureIssuerBatchImportService,
    InstrumentImportReason,
    LegacyDebentureInstrumentReader,
    LegacyDebentureIssuerReader,
)


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_issuers(legacy_database, entities):
    report = DebentureIssuerBatchImportService(
        LegacyDebentureIssuerReader(legacy_database),
        entities,
    ).run()

    assert report.errors == 0


def create_service(
    legacy_database,
    entities=None,
    relationships=None,
):
    entities = entities or InMemoryEntityRepository()
    relationships = relationships or InMemoryRelationshipRepository()

    service = DebentureInstrumentBatchImportService(
        LegacyDebentureInstrumentReader(legacy_database),
        entities,
        relationships,
    )

    return service, entities, relationships


def test_batch_creates_instruments_and_reviews_the_rest(
    legacy_database,
):
    service, entities, relationships = create_service(
        legacy_database
    )
    import_issuers(legacy_database, entities)

    outcome = service.run(batch_size=2)
    report = outcome.report

    assert report.total_read == 4
    assert report.created == 2
    assert report.matched == 0
    assert report.review == 2
    assert report.blocked == 0
    assert report.errors == 0
    assert report.dry_run is False
    assert entities.count(EntityType.DEBENTURE) == 2
    assert relationships.count(RelationshipType.ISSUES) == 2

    reasons = {
        result.legacy_id: result.reason
        for result in outcome.pending
    }

    assert reasons == {
        3: InstrumentImportReason.ISSUER_WITHOUT_CNPJ,
        4: InstrumentImportReason.ISSUER_MISSING,
    }


def test_batch_reexecution_matches_instruments(
    legacy_database,
):
    service, entities, relationships = create_service(
        legacy_database
    )
    import_issuers(legacy_database, entities)

    first = service.run()
    second = service.run()

    assert first.report.created == 2
    assert second.report.created == 0
    assert second.report.matched == 2
    assert second.report.review == 2
    assert second.report.errors == 0
    assert entities.count(EntityType.DEBENTURE) == 2
    assert relationships.count(RelationshipType.ISSUES) == 2


def test_batch_without_issuers_creates_nothing(
    legacy_database,
):
    service, entities, relationships = create_service(
        legacy_database
    )

    outcome = service.run()

    assert outcome.report.created == 0
    assert outcome.report.review == 4
    assert entities.count() == 0
    assert relationships.count() == 0

    reasons = {
        result.legacy_id: result.reason
        for result in outcome.pending
    }

    assert reasons[1] is (
        InstrumentImportReason.ISSUER_NOT_REGISTERED
    )
    assert reasons[2] is (
        InstrumentImportReason.ISSUER_NOT_REGISTERED
    )


def test_batch_records_read_error_and_continues(
    legacy_database_factory,
):
    issuer = (
        1,
        "12345678000199",
        "Empresa Alfa S.A.",
        None,
        "2026-09-20 10:00:00",
        "2026-09-21 12:00:00",
    )
    database_path = legacy_database_factory(
        issuers=(issuer,),
        debentures=(
            (
                1,
                1,
                "ALFA11",
                "BRALFADBS001",
                "active",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
            (
                2,
                1,
                "ALFA12",
                "BR-ALFA-0001",
                "active",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
            (
                3,
                1,
                "ALFA13",
                "BRALFADBS003",
                "active",
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        ),
    )
    service, entities, _ = create_service(database_path)
    import_issuers(database_path, entities)

    report = service.run(batch_size=1).report

    assert report.total_read == 3
    assert report.created == 2
    assert report.errors == 1
    assert entities.count(EntityType.DEBENTURE) == 2

    detail = report.error_details[0]

    assert detail.legacy_id == 2
    assert detail.error_type == "ValueError"


def test_batch_records_import_error_and_continues(
    legacy_database,
):
    class FailingForOne(InMemoryRelationshipRepository):
        def save(self, relationship):
            if relationship.provenance.source_reference == (
                "debenture:1"
            ):
                raise RuntimeError("falha simulada")

            return super().save(relationship)

    service, entities, relationships = create_service(
        legacy_database,
        relationships=FailingForOne(),
    )
    import_issuers(legacy_database, entities)

    report = service.run().report

    assert report.total_read == 4
    assert report.created == 1
    assert report.review == 2
    assert report.errors == 1
    assert report.error_details[0].legacy_id == 1
    assert report.error_details[0].error_type == "RuntimeError"
    assert report.error_details[0].message == "falha simulada"


def test_batch_does_not_change_legacy_database(
    legacy_database,
):
    before = sha256_of(legacy_database)
    service, entities, _ = create_service(legacy_database)
    import_issuers(legacy_database, entities)

    service.run()
    service.run()

    assert sha256_of(legacy_database) == before


def test_batch_labels_dry_run_report(legacy_database):
    service, entities, _ = create_service(legacy_database)
    import_issuers(legacy_database, entities)

    assert service.run(dry_run=True).report.dry_run is True


def test_batch_rejects_non_boolean_dry_run(legacy_database):
    service, _, _ = create_service(legacy_database)

    with pytest.raises(TypeError):
        service.run(dry_run="sim")


def test_batch_rejects_unexpected_reader(legacy_database):
    with pytest.raises(TypeError):
        DebentureInstrumentBatchImportService(
            object(),
            InMemoryEntityRepository(),
            InMemoryRelationshipRepository(),
        )
