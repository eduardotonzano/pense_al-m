"""Testes do servico de importacao em lote."""

import sqlite3

import pytest

from pense_alm.shared.entities import (
    IdentifierType,
    InMemoryEntityRepository,
)
from pense_alm.shared.integration import (
    DebentureIssuerBatchImportService,
    LegacyDebentureIssuerReader,
)

from ..cnpj_amostras import (
    CNPJ_3,
    CNPJ_4,
    CNPJ_5,
    CNPJ_7,
    CNPJ_ALFA_1,
    com_mascara,
    dv_errado,
)


def set_legacy_cnpj(
    legacy_database_path,
    legacy_id,
    cnpj,
):
    connection = sqlite3.connect(
        legacy_database_path
    )

    try:
        connection.execute(
            "UPDATE issuers SET cnpj = ? WHERE id = ?",
            (
                cnpj,
                legacy_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def legacy_database_path(tmp_path):
    database_path = tmp_path / "legacy_batch.sqlite3"

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE issuers (
                id INTEGER PRIMARY KEY,
                cnpj TEXT,
                legal_name TEXT NOT NULL,
                trade_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO issuers (
                id,
                cnpj,
                legal_name,
                trade_name,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    1,
                    CNPJ_3,
                    "Empresa Alfa S.A.",
                    "Empresa Alfa",
                    "2026-09-20 10:00:00",
                    "2026-09-21 12:00:00",
                ),
                (
                    2,
                    CNPJ_4,
                    "Empresa Beta S.A.",
                    None,
                    "2026-09-20 11:00:00",
                    "2026-09-21 13:00:00",
                ),
                (
                    3,
                    CNPJ_5,
                    "Empresa Gama S.A.",
                    "Empresa Gama",
                    "2026-09-20 12:00:00",
                    "2026-09-21 14:00:00",
                ),
            ),
        )

        connection.commit()
    finally:
        connection.close()

    return database_path


def create_service(
    legacy_database_path,
    repository=None,
):
    target_repository = (
        repository
        or InMemoryEntityRepository()
    )

    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    service = DebentureIssuerBatchImportService(
        reader,
        target_repository,
    )

    return service, target_repository


def test_batch_import_creates_all_entities(
    legacy_database_path,
):
    service, repository = create_service(
        legacy_database_path
    )

    report = service.run(batch_size=2)

    assert report.total_read == 3
    assert report.created == 3
    assert report.matched == 0
    assert report.review == 0
    assert report.blocked == 0
    assert report.errors == 0
    assert report.dry_run is False
    assert repository.count() == 3


def test_batch_reexecution_matches_entities(
    legacy_database_path,
):
    service, repository = create_service(
        legacy_database_path
    )

    first_report = service.run()
    second_report = service.run()

    assert first_report.created == 3
    assert second_report.created == 0
    assert second_report.matched == 3
    assert second_report.errors == 0
    assert repository.count() == 3


def test_batch_imports_and_matches_alphanumeric_cnpj(
    legacy_database_path,
):
    set_legacy_cnpj(
        legacy_database_path,
        2,
        com_mascara(CNPJ_ALFA_1).lower(),
    )

    service, repository = create_service(
        legacy_database_path
    )

    first_report = service.run(batch_size=2)
    second_report = service.run(batch_size=2)

    assert first_report.created == 3
    assert first_report.errors == 0
    assert second_report.matched == 3
    assert second_report.errors == 0
    assert repository.count() == 3

    entity = repository.get_by_identifier(
        IdentifierType.CNPJ,
        CNPJ_ALFA_1,
    )

    assert entity is not None
    assert entity.legal_name == "Empresa Beta S.A."


def test_dry_run_does_not_modify_repository(
    legacy_database_path,
):
    service, repository = create_service(
        legacy_database_path
    )

    report = service.run(
        batch_size=2,
        dry_run=True,
    )

    assert report.total_read == 3
    assert report.created == 3
    assert report.dry_run is True
    assert repository.count() == 0


def test_batch_records_error_and_continues(
    legacy_database_path,
):
    connection = sqlite3.connect(
        legacy_database_path
    )

    try:
        connection.execute(
            """
            UPDATE issuers
            SET created_at = ?
            WHERE id = ?
            """,
            (
                "data-invalida",
                2,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    service, repository = create_service(
        legacy_database_path
    )

    report = service.run(batch_size=1)

    assert report.total_read == 3
    assert report.created == 2
    assert report.matched == 0
    assert report.review == 0
    assert report.blocked == 0
    assert report.errors == 1
    assert repository.count() == 2

    assert len(report.error_details) == 1

    detail = report.error_details[0]

    assert detail.legacy_id == 2
    assert detail.error_type == "ValueError"
    assert detail.message == (
        "Timestamp legado invalido."
    )


INVALID_CNPJS = (
    dv_errado(CNPJ_4),
    dv_errado(CNPJ_ALFA_1),
    "123",
    "11.111.111/1111-11",
)
INVALID_CNPJ_IDS = (
    "dv-numerico",
    "dv-alfanumerico",
    "tamanho",
    "caracteres-iguais",
)


@pytest.mark.parametrize(
    "invalid_cnpj",
    INVALID_CNPJS,
    ids=INVALID_CNPJ_IDS,
)
def test_batch_records_invalid_cnpj_as_record_error_and_continues(
    legacy_database_path,
    invalid_cnpj,
):
    set_legacy_cnpj(
        legacy_database_path,
        2,
        invalid_cnpj,
    )

    service, repository = create_service(
        legacy_database_path
    )

    report = service.run(batch_size=1)

    assert report.total_read == 3
    assert report.created == 2
    assert report.matched == 0
    assert report.review == 0
    assert report.blocked == 0
    assert report.errors == 1
    assert repository.count() == 2

    for valid_cnpj in (CNPJ_3, CNPJ_5):
        assert repository.get_by_identifier(
            IdentifierType.CNPJ,
            valid_cnpj,
        ) is not None

    assert len(report.error_details) == 1

    detail = report.error_details[0]

    assert detail.legacy_id == 2
    assert detail.error_type == "IdentifierValidationError"
    assert invalid_cnpj not in detail.message


def test_batch_dry_run_reports_invalid_cnpj_like_the_real_run(
    legacy_database_path,
):
    set_legacy_cnpj(
        legacy_database_path,
        2,
        dv_errado(CNPJ_4),
    )

    service, repository = create_service(
        legacy_database_path
    )

    simulated = service.run(
        batch_size=1,
        dry_run=True,
    )

    assert repository.count() == 0

    real = service.run(batch_size=1)

    assert repository.count() == 2

    for report in (simulated, real):
        assert report.total_read == 3
        assert report.created == 2
        assert report.errors == 1

    assert simulated.dry_run is True
    assert real.dry_run is False
    assert simulated.error_details == real.error_details
    assert simulated.error_details[0].legacy_id == 2
    assert simulated.error_details[0].message == (
        "CNPJ com digito verificador invalido."
    )


def test_batch_requires_review_for_same_name_without_shared_cnpj(
    legacy_database_path,
):
    from pense_alm.shared.integration import (
        DebentureIssuerAdapter,
        DebentureIssuerRecord,
    )

    repository = InMemoryEntityRepository()

    existing = DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=99,
            legal_name="Empresa Alfa S.A.",
            trade_name="Empresa Alfa",
            cnpj=None,
            created_at="2026-09-19 10:00:00",
            updated_at="2026-09-19 12:00:00",
        )
    )

    repository.save(existing)

    service, repository = create_service(
        legacy_database_path,
        repository=repository,
    )

    report = service.run(batch_size=2)

    assert report.total_read == 3
    assert report.created == 2
    assert report.matched == 0
    assert report.review == 1
    assert report.blocked == 0
    assert report.errors == 0
    assert repository.count() == 3


def test_batch_blocks_same_name_with_conflicting_cnpj(
    legacy_database_path,
):
    from pense_alm.shared.integration import (
        DebentureIssuerAdapter,
        DebentureIssuerRecord,
    )

    repository = InMemoryEntityRepository()

    existing = DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=99,
            legal_name="Empresa Alfa S.A.",
            trade_name="Empresa Alfa",
            cnpj=CNPJ_7,
            created_at="2026-09-19 10:00:00",
            updated_at="2026-09-19 12:00:00",
        )
    )

    repository.save(existing)

    service, repository = create_service(
        legacy_database_path,
        repository=repository,
    )

    report = service.run(batch_size=2)

    assert report.total_read == 3
    assert report.created == 2
    assert report.matched == 0
    assert report.review == 0
    assert report.blocked == 1
    assert report.errors == 0
    assert repository.count() == 3
