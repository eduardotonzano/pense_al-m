"""Testes do backup de bancos SQLite."""

import hashlib
import sqlite3

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityType,
    SourceType,
)
from pense_alm.shared.persistence import (
    SQLiteBackup,
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    create_sqlite_backup,
)


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def populated_database(tmp_path):
    database_path = tmp_path / "origem.sqlite3"
    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(database_path)
    )
    repository.save(
        Entity(
            legal_name="Empresa Exemplo S.A.",
            entity_type=EntityType.COMPANY,
            provenance=DataProvenance(
                source_type=SourceType.MANUAL,
                source_name="Teste",
            ),
        )
    )

    return database_path


def test_backup_creates_valid_copy(
    populated_database,
    tmp_path,
):
    backup = create_sqlite_backup(
        populated_database,
        tmp_path / "backups",
    )

    assert isinstance(backup, SQLiteBackup)
    assert backup.path.parent == tmp_path / "backups"
    assert backup.path.name.startswith("origem_")
    assert backup.path.suffix == ".sqlite3"
    assert backup.size_bytes == backup.path.stat().st_size
    assert backup.sha256 == sha256_of(backup.path)

    restored = SQLiteEntityRepository(
        SQLiteConnectionManager(backup.path)
    )

    assert restored.count() == 1


def test_backup_matches_source_rows(
    populated_database,
    tmp_path,
):
    backup = create_sqlite_backup(
        populated_database,
        tmp_path / "backups",
    )

    def row_counts(path):
        connection = sqlite3.connect(path)

        try:
            return {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in (
                    "entities",
                    "entity_identifiers",
                    "entity_relationships",
                    "data_provenance",
                )
            }
        finally:
            connection.close()

    assert row_counts(backup.path) == row_counts(
        populated_database
    )


def test_backup_does_not_change_source(
    populated_database,
    tmp_path,
):
    before = sha256_of(populated_database)

    create_sqlite_backup(
        populated_database,
        tmp_path / "backups",
    )

    assert sha256_of(populated_database) == before


def test_backup_creates_missing_directory(
    populated_database,
    tmp_path,
):
    target_dir = tmp_path / "novo" / "backups"

    backup = create_sqlite_backup(
        populated_database,
        target_dir,
    )

    assert target_dir.is_dir()
    assert backup.path.is_file()


def test_backups_have_distinct_names(
    populated_database,
    tmp_path,
):
    first = create_sqlite_backup(
        populated_database,
        tmp_path / "backups",
    )
    second = create_sqlite_backup(
        populated_database,
        tmp_path / "backups",
    )

    assert first.path != second.path
    assert len(list((tmp_path / "backups").iterdir())) == 2


def test_backup_rejects_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_sqlite_backup(
            tmp_path / "inexistente.sqlite3",
            tmp_path / "backups",
        )

    assert not (tmp_path / "backups").exists()


def test_backup_of_invalid_file_leaves_no_partial_copy(
    tmp_path,
):
    broken = tmp_path / "quebrado.sqlite3"
    broken.write_bytes(b"isto nao e um banco sqlite" * 100)

    with pytest.raises(sqlite3.DatabaseError):
        create_sqlite_backup(broken, tmp_path / "backups")

    assert list((tmp_path / "backups").iterdir()) == []
