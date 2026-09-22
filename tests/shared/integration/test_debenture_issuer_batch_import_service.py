"""Testes do servico de importacao em lote."""

import sqlite3

import pytest

from pense_alm.shared.entities import (
    InMemoryEntityRepository,
)
from pense_alm.shared.integration import (
    DebentureIssuerBatchImportService,
    LegacyDebentureIssuerReader,
)


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
                    "12345678000199",
                    "Empresa Alfa S.A.",
                    "Empresa Alfa",
                    "2026-09-20 10:00:00",
                    "2026-09-21 12:00:00",
                ),
                (
                    2,
                    "22345678000198",
                    "Empresa Beta S.A.",
                    None,
                    "2026-09-20 11:00:00",
                    "2026-09-21 13:00:00",
                ),
                (
                    3,
                    "32345678000197",
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
