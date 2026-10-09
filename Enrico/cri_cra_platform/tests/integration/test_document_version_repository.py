from __future__ import annotations

import sqlite3

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_version_repository import (
    DocumentVersionRepository,
)


def setup_documents(connection: sqlite3.Connection) -> tuple[int, int]:
    run_id = "document-version-test-run"
    connection.execute(
        """INSERT INTO executions (run_id, started_at, status)
           VALUES (?, '2026-01-01T00:00:00Z', 'running')""",
        (run_id,),
    )
    asset_id = AssetRepository(connection).upsert(
        Asset(
            "CRA-VERSIONS",
            "CRA",
            "Securitizadora",
            "123",
            "1",
            "1",
            isin="BR0000000000",
        )
    )
    document_ids = []
    for source_id in ("versao-1", "versao-2"):
        cursor = connection.execute(
            """INSERT INTO documents (
                source_document_id, asset_id, category, document_name,
                source, source_url, run_id
            ) VALUES (?, ?, 'Informe Mensal', ?, 'Fundos.NET', ?, ?)""",
            (
                source_id,
                asset_id,
                source_id,
                f"https://example.test/{source_id}",
                run_id,
            ),
        )
        document_ids.append(int(cursor.lastrowid))
    connection.commit()
    return document_ids[0], document_ids[1]


def insert_version(repository, document_id, hash_value, *, current=True, source_version="1"):
    return repository.create_version(
        document_id=document_id,
        file_name=f"{document_id}.xml",
        local_file_path=f"data/documents/{document_id}.xml",
        file_format="xml",
        file_size_bytes=20,
        file_hash=hash_value,
        source_url=f"https://example.test/download?id={document_id}",
        source_version=source_version,
        is_current=current,
        validation_status="valid",
    )


def test_version_first_repeat_and_new_hash_updates_current(tmp_path):
    connection = connect(tmp_path / "versions.db")
    initialize_database(connection)
    first_id, _ = setup_documents(connection)
    repository = DocumentVersionRepository(connection)
    old_hash = "a" * 64
    new_hash = "b" * 64

    first_version, first_status = insert_version(repository, first_id, old_hash)
    same_version, same_status = insert_version(repository, first_id, old_hash)
    new_version, new_status = insert_version(
        repository, first_id, new_hash, source_version="2"
    )

    assert first_status == "inserted"
    assert same_status == "unchanged"
    assert same_version == first_version
    assert new_status == "inserted"
    assert new_version != first_version
    assert repository.get_current_version(first_id)["version_id"] == new_version
    rows = repository.list_versions(first_id)
    assert len(rows) == 2
    assert [row["is_current"] for row in rows] == [0, 1]
    assert repository.count_versions(first_id) == 2
    assert repository.find_by_hash(old_hash)[0]["document_id"] == first_id


def test_different_documents_can_reference_same_file_hash(tmp_path):
    connection = connect(tmp_path / "versions.db")
    initialize_database(connection)
    first_id, second_id = setup_documents(connection)
    repository = DocumentVersionRepository(connection)
    shared_hash = "c" * 64

    insert_version(repository, first_id, shared_hash)
    insert_version(repository, second_id, shared_hash)

    assert len(repository.find_by_hash(shared_hash)) == 2
    assert repository.get_current_version(first_id)["file_hash"] == shared_hash
    assert repository.get_current_version(second_id)["file_hash"] == shared_hash


def test_only_valid_hashed_version_can_be_current(tmp_path):
    connection = connect(tmp_path / "versions.db")
    initialize_database(connection)
    first_id, _ = setup_documents(connection)
    repository = DocumentVersionRepository(connection)
    with pytest.raises(ValueError, match="collection_attempts"):
        repository.create_version(
            first_id, None, None, "html", 100, None, None,
            is_current=True, validation_status="html_instead_of_file",
        )


def test_document_versions_reject_operational_failures(tmp_path):
    connection = connect(tmp_path / "versions.db")
    initialize_database(connection)
    first_id, _ = setup_documents(connection)
    repository = DocumentVersionRepository(connection)

    with pytest.raises(ValueError, match="collection_attempts"):
        repository.create_version(
            document_id=first_id,
            file_name=None,
            local_file_path=None,
            file_format=None,
            file_size_bytes=None,
            file_hash=None,
            source_url="https://example.test/download",
            is_current=False,
            validation_status="download_failed",
            error_message="network timeout",
        )
    assert repository.count_versions(first_id) == 0


def test_collection_attempts_migration_is_additive(tmp_path):
    connection = connect(tmp_path / "old-attempts.db")
    initialize_database(connection)
    connection.execute("DROP INDEX ix_collection_attempts_document_id")
    connection.execute("DROP TABLE collection_attempts")
    connection.execute(
        """CREATE TABLE collection_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            asset_id INTEGER,
            source TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            http_status INTEGER,
            error_message TEXT,
            FOREIGN KEY(run_id) REFERENCES executions(run_id),
            FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
        )"""
    )
    connection.commit()

    initialize_database(connection)

    columns = {
        row["name"]: row for row in connection.execute(
            "PRAGMA table_info(collection_attempts)"
        )
    }
    assert {
        "run_id", "asset_id", "source", "started_at", "finished_at",
        "status", "http_status", "error_message", "document_id",
        "attempt_number", "response_content_type", "final_url",
    } <= set(columns)
    index_names = {
        row["name"] for row in connection.execute(
            "PRAGMA index_list(collection_attempts)"
        )
    }
    assert "ix_collection_attempts_document_id" in index_names


def test_upgrade_replaces_old_hash_index_without_losing_documents(tmp_path):
    connection = connect(tmp_path / "old.db")
    initialize_database(connection)
    first_id, second_id = setup_documents(connection)
    connection.execute("DROP INDEX ix_documents_file_hash")
    connection.execute(
        """CREATE UNIQUE INDEX uq_documents_file_hash_nonempty
           ON documents(file_hash)
           WHERE file_hash IS NOT NULL AND file_hash <> ''"""
    )
    connection.commit()

    initialize_database(connection)

    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
    indexes = {
        row["name"]: row["sql"]
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index'"
        )
    }
    assert "uq_documents_file_hash_nonempty" not in indexes
    assert "ix_documents_file_hash" in indexes
    connection.execute(
        "UPDATE documents SET file_hash = ? WHERE document_pk = ?",
        ("d" * 64, first_id),
    )
    connection.execute(
        "UPDATE documents SET file_hash = ? WHERE document_pk = ?",
        ("d" * 64, second_id),
    )
    connection.commit()
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE file_hash = ?", ("d" * 64,)
    ).fetchone()[0] == 2
