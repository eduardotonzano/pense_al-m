from __future__ import annotations

import hashlib
import sqlite3

import pytest

from credit_assets.database.asset_migrations import (
    AssetMigrationConflict,
    migrate_cafe_brasil_duplicate_asset,
)
from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository


def _seed_duplicate_assets(connection: sqlite3.Connection) -> tuple[int, int]:
    repository = AssetRepository(connection)
    canonical_id = repository.upsert(
        Asset(
            "CRA022009VM",
            "CRA",
            "Eco Securitizadora",
            "10.753.164/0001-43",
            "190",
            "unica",
            "Cafe Brasil",
            "01.486.546/0001-67",
            "BRECOACRABX0",
        )
    )
    duplicate_id = repository.upsert(
        Asset(
            "BRECOACRABX0",
            "CRA",
            "Eco Securitizadora",
            "10.753.164/0001-43",
            "190",
            "1",
            "Cafe Brasil",
            "01.486.546/0001-67",
            "BRRBRACRIP13",
        )
    )
    connection.execute("DROP INDEX uq_assets_isin_normalized_nonempty")
    connection.execute(
        "UPDATE assets SET isin = ? WHERE asset_id = ?",
        ("BRECOACRABX0", duplicate_id),
    )
    connection.commit()
    return canonical_id, duplicate_id


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


def test_migration_preserves_documents_versions_attempts_and_removes_empty_duplicate(
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
    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE asset_id = ?", (duplicate_id,)
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE asset_id = ?", (canonical_id,)
    ).fetchone()[0] == 2
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
    assert (tmp_path / "equivalent.pdf").is_file()
    assert (tmp_path / "unique.pdf").is_file()


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
