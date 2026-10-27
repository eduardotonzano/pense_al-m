from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from credit_assets.database.backup import BackupError, create_backup, file_sha256
from credit_assets.database.connection import connect, initialize_database


def create_database(tmp_path: Path, name: str = "cri_cra.db") -> Path:
    path = tmp_path / name
    connection = connect(path)
    initialize_database(connection)
    connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('BKP0001', 'CRI', 'S', '1', '1', '1', 'now', 'now')"""
    )
    connection.commit()
    connection.close()
    return path


def asset_codes(path: Path) -> list[str]:
    connection = sqlite3.connect(path)

    try:
        return [row[0] for row in connection.execute("SELECT codigo_cetip FROM assets")]
    finally:
        connection.close()


def test_backup_copies_data_into_a_backups_folder_next_to_the_database(tmp_path):
    database = create_database(tmp_path)

    result = create_backup(database)

    assert result.path.parent == tmp_path / "backups"
    assert result.path.name.startswith("cri_cra_")
    assert result.path.suffix == ".sqlite3"
    assert asset_codes(result.path) == ["BKP0001"]
    assert result.size_bytes == result.path.stat().st_size
    assert result.sha256 == file_sha256(result.path)


def test_backup_uses_the_given_folder_and_unique_names(tmp_path):
    database = create_database(tmp_path)
    folder = tmp_path / "saved" / "nested"

    first = create_backup(database, folder)
    second = create_backup(database, folder, prefix="outro")

    assert first.path.parent == folder
    assert second.path.name.startswith("outro_")
    assert first.path != second.path


def test_backup_does_not_modify_the_source(tmp_path):
    database = create_database(tmp_path)
    before = file_sha256(database)

    create_backup(database)

    assert file_sha256(database) == before


def test_backup_of_a_wal_database_includes_committed_rows(tmp_path):
    database = create_database(tmp_path)
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('BKP0002', 'CRI', 'S', '1', '2', '1', 'now', 'now')"""
    )
    connection.commit()

    result = create_backup(database)
    connection.close()

    assert asset_codes(result.path) == ["BKP0001", "BKP0002"]


def test_backup_refuses_a_missing_database(tmp_path):
    with pytest.raises(BackupError, match="Banco nao encontrado"):
        create_backup(tmp_path / "missing.db")

    assert not (tmp_path / "backups").exists()


def test_backup_refuses_a_file_that_is_not_a_database(tmp_path):
    path = tmp_path / "garbage.db"
    path.write_bytes(b"isto nao e um banco sqlite" * 10)

    with pytest.raises(BackupError):
        create_backup(path)

    assert not list((tmp_path / "backups").glob("*.sqlite3"))


def test_backup_refuses_a_database_with_foreign_key_errors(tmp_path):
    database = create_database(tmp_path)
    connection = sqlite3.connect(database)
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name,
            source, source_url, run_id
        ) VALUES ('x', 999, 'Outro', 'n', 'Fundos.NET', 'u', 'no-such-run')"""
    )
    connection.commit()
    connection.close()

    with pytest.raises(BackupError, match="chave estrangeira"):
        create_backup(database)

    assert not list((tmp_path / "backups").glob("*.sqlite3"))
