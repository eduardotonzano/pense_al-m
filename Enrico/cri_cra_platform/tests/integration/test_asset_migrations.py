from __future__ import annotations

import hashlib
import sqlite3

import pytest

from credit_assets.database.asset_migrations import (
    AssetMigrationConflict,
    migrate_cafe_brasil_duplicate_asset,
)
from credit_assets.database.connection import connect, initialize_database


def _seed_duplicate_assets(
    connection: sqlite3.Connection,
    *,
    canonical_isin: str | None = None,
    duplicate_cetip: str = "BRECOACRABX0",
    duplicate_isin: str = "BRECOACRABX0",
    duplicate_type: str = "CRA",
    duplicate_securitizer: str = "Eco Securitizadora",
    duplicate_issue: str = "190",
    duplicate_series: str = "1",
    duplicate_debtor: str = "Cafe Brasil",
) -> tuple[int, int]:
    connection.execute("DROP INDEX uq_assets_isin_normalized_nonempty")
    connection.execute("DROP INDEX uq_assets_codigo_cetip_normalized_nonempty")
    canonical_cursor = connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, devedor, cnpj_devedor, isin, created_at, updated_at
        ) VALUES ('CRA022009VM', 'CRA', 'Eco Securitizadora', '10.753.164/0001-43',
                  '190', 'unica', 'Cafe Brasil', '01.486.546/0001-67', ?, 'now', 'now')""",
        (canonical_isin,),
    )
    duplicate_cursor = connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, devedor, cnpj_devedor, isin, created_at, updated_at
        ) VALUES (?, ?, ?, '10.753.164/0001-43', ?, ?, ?, '01.486.546/0001-67',
                  ?, 'now', 'now')""",
        (
            duplicate_cetip,
            duplicate_type,
            duplicate_securitizer,
            duplicate_issue,
            duplicate_series,
            duplicate_debtor,
            duplicate_isin,
        ),
    )
    connection.commit()
    return int(canonical_cursor.lastrowid), int(duplicate_cursor.lastrowid)


def _insert_document(
    connection: sqlite3.Connection,
    asset_id: int,
    source_document_id: str,
    *,
    source_url: str,
    category: str = "Informe Mensal",
    reference_date: str = "2026-01-01",
    collected_at: str = "2026-01-02T00:00:00Z",
) -> int:
    return int(
        connection.execute(
            """INSERT INTO documents (
                source_document_id, asset_id, category, document_name,
                reference_date, publication_date, source, source_url, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'Fundos.NET', ?, ?)""",
            (
                source_document_id,
                asset_id,
                category,
                source_document_id,
                reference_date,
                "2026-01-02",
                source_url,
                collected_at,
            ),
        ).lastrowid
    )


def _insert_version(
    connection: sqlite3.Connection,
    document_id: int,
    file_path,
    contents: bytes,
) -> None:
    file_path.write_bytes(contents)
    connection.execute(
        """INSERT INTO document_versions (
            document_id, file_name, local_file_path, file_format,
            file_size_bytes, file_hash, downloaded_at, source_url,
            is_current, validation_status
        ) VALUES (?, ?, ?, 'pdf', ?, ?, '2026-01-03', ?, 1, 'valid')""",
        (
            document_id,
            file_path.name,
            str(file_path),
            len(contents),
            hashlib.sha256(contents).hexdigest(),
            f"https://example.test/{file_path.name}",
        ),
    )


def test_migration_accepts_null_isin_and_moves_document_and_attempt_references(
    tmp_path,
):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    canonical_id, duplicate_id = _seed_duplicate_assets(connection)
    run_id = "migration-run"
    connection.execute(
        """INSERT INTO executions (run_id, started_at, status)
           VALUES (?, '2026-01-01', 'success')""",
        (run_id,),
    )

    canonical_document = _insert_document(
        connection,
        canonical_id,
        "doc-equivalent-canonical",
        source_url="https://example.test/equivalent",
    )
    duplicate_equivalent = _insert_document(
        connection,
        duplicate_id,
        "doc-equivalent-duplicate",
        source_url="https://example.test/equivalent",
        collected_at="2026-01-04T00:00:00Z",
    )
    duplicate_only = _insert_document(
        connection,
        duplicate_id,
        "doc-unique",
        source_url="https://example.test/unique",
    )
    _insert_version(
        connection,
        duplicate_equivalent,
        tmp_path / "equivalent.pdf",
        b"%PDF-equivalent",
    )
    _insert_version(
        connection,
        duplicate_only,
        tmp_path / "unique.pdf",
        b"%PDF-unique",
    )
    for document_id in (duplicate_equivalent, duplicate_only):
        connection.execute(
            """INSERT INTO collection_attempts (
                run_id, asset_id, document_id, source, started_at, status
            ) VALUES (?, ?, ?, 'Fundos.NET', '2026-01-01', 'success')""",
            (run_id, duplicate_id, document_id),
        )
    connection.execute(
        """INSERT INTO alerts (
            run_id, asset_id, alert_type, severity, message, created_at
        ) VALUES (?, ?, 'type', 'low', 'message', '2026-01-01')""",
        (run_id, duplicate_id),
    )
    connection.commit()

    result = migrate_cafe_brasil_duplicate_asset(connection)
    initialize_database(connection)

    assert result["canonical_asset_id"] == canonical_id
    assert result["documents_migrated"] == 1
    assert result["equivalent_documents_merged"] == 1
    assert result["document_versions_preserved"] == 2
    assert result["collection_attempts_migrated"] == 2
    assert result["alerts_migrated"] == 1
    assert result["duplicate_asset_removed"] is True
    canonical = connection.execute(
        "SELECT codigo_cetip, isin, emissao, serie FROM assets WHERE asset_id = ?",
        (canonical_id,),
    ).fetchone()
    assert tuple(canonical) == ("CRA022009VM", "BRECOACRABX0", "190", "1")
    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE asset_id = ?", (duplicate_id,)
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE asset_id = ?", (canonical_id,)
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE asset_id = ?", (duplicate_id,)
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE source_url = 'https://example.test/equivalent'"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM document_versions"
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM document_versions WHERE is_current = 1"
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM collection_attempts WHERE asset_id = ?",
        (canonical_id,),
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM collection_attempts WHERE document_id = ?",
        (canonical_document,),
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM alerts WHERE asset_id = ?", (canonical_id,)
    ).fetchone()[0] == 1
    indexes = {
        row["name"]
        for row in connection.execute("PRAGMA index_list(assets)")
    }
    assert {
        "uq_assets_isin_normalized_nonempty",
        "uq_assets_codigo_cetip_normalized_nonempty",
    } <= indexes
    assert (tmp_path / "equivalent.pdf").is_file()
    assert (tmp_path / "unique.pdf").is_file()


@pytest.mark.parametrize("canonical_isin", ["", "BRECOACRABX0"])
def test_migration_accepts_empty_or_matching_canonical_isin(tmp_path, canonical_isin):
    connection = connect(tmp_path / f"assets-{canonical_isin or 'empty'}.db")
    initialize_database(connection)
    canonical_id, _ = _seed_duplicate_assets(
        connection, canonical_isin=canonical_isin
    )

    result = migrate_cafe_brasil_duplicate_asset(connection)

    assert result["canonical_asset_id"] == canonical_id
    assert connection.execute(
        "SELECT isin FROM assets WHERE asset_id = ?", (canonical_id,)
    ).fetchone()[0] == "BRECOACRABX0"


def test_migration_rejects_canonical_with_different_nonempty_isin(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    canonical_id, duplicate_id = _seed_duplicate_assets(
        connection, canonical_isin="BRRBRACRIP13"
    )

    with pytest.raises(AssetMigrationConflict, match="ISIN incompatível"):
        migrate_cafe_brasil_duplicate_asset(connection)

    assert connection.execute(
        "SELECT isin FROM assets WHERE asset_id = ?", (canonical_id,)
    ).fetchone()[0] == "BRRBRACRIP13"
    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE asset_id = ?", (duplicate_id,)
    ).fetchone()[0] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duplicate_cetip", "OTHER-CETIP"),
        ("duplicate_isin", "BRRBRACRIP13"),
        ("duplicate_type", "CRI"),
        ("duplicate_securitizer", "Other Securitizadora"),
        ("duplicate_issue", "191"),
        ("duplicate_series", "2"),
        ("duplicate_debtor", "Other Debtor"),
    ],
)
def test_migration_rejects_incompatible_duplicate(tmp_path, field, value):
    connection = connect(tmp_path / f"assets-{field}.db")
    initialize_database(connection)
    canonical_id, duplicate_id = _seed_duplicate_assets(
        connection, **{field: value}
    )

    with pytest.raises(AssetMigrationConflict):
        migrate_cafe_brasil_duplicate_asset(connection)

    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE asset_id IN (?, ?)",
        (canonical_id, duplicate_id),
    ).fetchone()[0] == 2


def test_migration_rejects_multiple_duplicates_by_isin(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    canonical_id, duplicate_id = _seed_duplicate_assets(connection)
    second_duplicate = connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, devedor, cnpj_devedor, isin, created_at, updated_at
        ) VALUES ('BRECOACRABX0', 'CRA', 'Eco Securitizadora',
                  '10.753.164/0001-43', '190', '1', 'Cafe Brasil',
                  '01.486.546/0001-67', 'BRECOACRABX0', 'now', 'now')"""
    ).lastrowid
    connection.commit()

    with pytest.raises(AssetMigrationConflict, match="exatamente um duplicado"):
        migrate_cafe_brasil_duplicate_asset(connection)

    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE asset_id IN (?, ?, ?)",
        (canonical_id, duplicate_id, second_duplicate),
    ).fetchone()[0] == 3


def test_migration_rolls_back_on_document_metadata_conflict(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    canonical_id, duplicate_id = _seed_duplicate_assets(connection)
    _insert_document(
        connection,
        canonical_id,
        "doc-conflict-canonical",
        source_url="https://example.test/doc",
    )
    _insert_document(
        connection,
        duplicate_id,
        "doc-conflict-duplicate",
        source_url="https://example.test/doc",
        category="Ata/Edital",
    )
    connection.commit()

    with pytest.raises(AssetMigrationConflict, match="category"):
        migrate_cafe_brasil_duplicate_asset(connection)

    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE asset_id IN (?, ?)",
        (canonical_id, duplicate_id),
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE asset_id = ?", (duplicate_id,)
    ).fetchone()[0] == 1
