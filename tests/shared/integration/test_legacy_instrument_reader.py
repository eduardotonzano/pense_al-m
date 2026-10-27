"""Testes do leitor de debentures do banco legado."""

import hashlib
import sqlite3

import pytest

from pense_alm.shared.integration import (
    DebentureInstrumentRecord,
    LegacyDebentureInstrumentReader,
    LegacyInstrumentReadError,
)


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reader_counts_debentures(legacy_database):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    assert reader.count() == 4


def test_reader_returns_records_with_issuer_data(
    legacy_database,
):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    records = list(reader.iter_records())

    assert all(
        isinstance(record, DebentureInstrumentRecord)
        for record in records
    )

    first = records[0]

    assert first.legacy_id == 1
    assert first.asset_code == "ALFA11"
    assert first.isin == "BRALFADBS001"
    assert first.status == "active"
    assert first.issuer_legacy_id == 1
    assert first.issuer_cnpj == "12345678000199"


def test_reader_maps_issuer_without_cnpj(legacy_database):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    record = list(reader.iter_records())[2]

    assert record.asset_code == "SEMC13"
    assert record.isin is None
    assert record.issuer_legacy_id == 3
    assert record.issuer_cnpj is None


def test_reader_maps_debenture_without_issuer(legacy_database):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    record = list(reader.iter_records())[3]

    assert record.asset_code is None
    assert record.isin == "BRSEMEDBS003"
    assert record.issuer_legacy_id is None
    assert record.issuer_cnpj is None


@pytest.mark.parametrize("batch_size", [1, 3, 100])
def test_reader_preserves_deterministic_order(
    legacy_database,
    batch_size,
):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    identifiers = [
        record.legacy_id
        for record in reader.iter_records(
            batch_size=batch_size
        )
    ]

    assert identifiers == [1, 2, 3, 4]


def test_reader_reports_invalid_row_and_continues(
    legacy_database_factory,
):
    # 12 caracteres e maiusculo: passa no CHECK do legado,
    # mas nao e um ISIN alfanumerico.
    database_path = legacy_database_factory(
        issuers=(
            (
                1,
                "12345678000199",
                "Empresa Alfa S.A.",
                None,
                "2026-09-20 10:00:00",
                "2026-09-21 12:00:00",
            ),
        ),
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

    results = list(
        LegacyDebentureInstrumentReader(
            database_path
        ).iter_records(batch_size=2)
    )

    assert len(results) == 3
    assert isinstance(results[0], DebentureInstrumentRecord)
    assert isinstance(results[2], DebentureInstrumentRecord)

    error = results[1]

    assert isinstance(error, LegacyInstrumentReadError)
    assert error.legacy_id == 2
    assert error.error_type == "ValueError"
    assert "isin" in error.message


@pytest.mark.parametrize("batch_size", [0, -1])
def test_reader_rejects_non_positive_batch_size(
    legacy_database,
    batch_size,
):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    with pytest.raises(ValueError):
        list(reader.iter_records(batch_size=batch_size))


def test_reader_rejects_non_integer_batch_size(
    legacy_database,
):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    with pytest.raises(TypeError):
        list(reader.iter_records(batch_size="10"))


def test_reader_rejects_missing_database(tmp_path):
    with pytest.raises(FileNotFoundError):
        LegacyDebentureInstrumentReader(
            tmp_path / "inexistente.sqlite3"
        )


def test_reader_rejects_empty_path():
    with pytest.raises(ValueError):
        LegacyDebentureInstrumentReader("  ")


def test_reader_rejects_unexpected_path_type():
    with pytest.raises(TypeError):
        LegacyDebentureInstrumentReader(123)


def test_reader_connection_is_query_only(legacy_database):
    reader = LegacyDebentureInstrumentReader(legacy_database)

    connection = reader._connect()

    try:
        with pytest.raises(
            sqlite3.OperationalError,
            match="readonly",
        ):
            connection.execute("DELETE FROM debentures")
    finally:
        connection.close()


def test_reader_does_not_change_legacy_database(
    legacy_database,
):
    before = sha256_of(legacy_database)

    reader = LegacyDebentureInstrumentReader(legacy_database)
    reader.count()
    list(reader.iter_records(batch_size=2))

    assert sha256_of(legacy_database) == before
