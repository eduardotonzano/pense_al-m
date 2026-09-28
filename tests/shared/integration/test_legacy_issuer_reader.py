"""Testes do leitor legado de emissores."""

import sqlite3

import pytest

from pense_alm.shared.integration import (
    DebentureIssuerRecord,
    LegacyDebentureIssuerReader,
)


@pytest.fixture
def legacy_database_path(tmp_path):
    database_path = tmp_path / "legacy_debenture.sqlite3"

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


def test_reader_counts_issuers(
    legacy_database_path,
):
    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    assert reader.count() == 3


def test_reader_returns_intermediate_records(
    legacy_database_path,
):
    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    records = tuple(reader.iter_records())

    assert len(records) == 3
    assert all(
        isinstance(record, DebentureIssuerRecord)
        for record in records
    )


def test_reader_preserves_deterministic_order(
    legacy_database_path,
):
    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    records = tuple(
        reader.iter_records(batch_size=2)
    )

    assert [
        record.legacy_id
        for record in records
    ] == [1, 2, 3]


def test_reader_maps_optional_trade_name(
    legacy_database_path,
):
    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    records = tuple(reader.iter_records())

    assert records[1].trade_name is None


def test_reader_rejects_invalid_batch_size(
    legacy_database_path,
):
    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    with pytest.raises(
        ValueError,
        match="maior que zero",
    ):
        tuple(reader.iter_records(batch_size=0))


def test_reader_rejects_missing_database(
    tmp_path,
):
    missing_path = tmp_path / "missing.sqlite3"

    with pytest.raises(FileNotFoundError):
        LegacyDebentureIssuerReader(missing_path)


def test_reader_connection_is_query_only(
    legacy_database_path,
):
    reader = LegacyDebentureIssuerReader(
        legacy_database_path
    )

    connection = reader._connect()

    try:
        with pytest.raises(
            sqlite3.OperationalError,
            match="readonly",
        ):
            connection.execute(
                """
                INSERT INTO issuers (
                    cnpj,
                    legal_name,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "42345678000196",
                    "Empresa Bloqueada S.A.",
                    "2026-09-20 13:00:00",
                    "2026-09-21 15:00:00",
                ),
            )
    finally:
        connection.close()
