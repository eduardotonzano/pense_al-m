import sqlite3

import pytest

from apoio import make_test_cnpj
from fundos.backup import BackupError
from fundos.backup import check_path_length
from fundos.backup import create_backup
from fundos.backup import file_sha256


def test_backup_is_a_valid_copy_with_short_name(db, tmp_path):
    result = create_backup(db.database_path, tmp_path / "bk")

    assert result.path.parent == tmp_path / "bk"
    assert result.path.name.startswith("fundos_")
    assert result.path.suffix == ".sqlite3"
    assert result.sha256 == file_sha256(result.path)
    assert result.size_bytes == result.path.stat().st_size

    copy = sqlite3.connect(result.path)
    try:
        versions = copy.execute("SELECT version FROM schema_migrations").fetchall()
    finally:
        copy.close()

    assert versions == [(1,)]


def test_missing_or_invalid_database_is_refused(tmp_path):
    garbage = tmp_path / "lixo.db"
    garbage.write_bytes(b"isto nao e um banco sqlite" * 10)

    with pytest.raises(BackupError, match="nao encontrado"):
        create_backup(tmp_path / "inexistente.db", tmp_path / "bk")

    with pytest.raises(BackupError, match="nao e valido"):
        create_backup(garbage, tmp_path / "bk")

    assert not (tmp_path / "bk").exists()


def test_database_with_foreign_key_errors_is_refused(db, tmp_path):
    raw = sqlite3.connect(db.database_path)
    try:
        raw.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (999, ?)",
            (make_test_cnpj(1),),
        )
        raw.commit()
    finally:
        raw.close()

    with pytest.raises(BackupError, match="chave estrangeira"):
        create_backup(db.database_path, tmp_path / "bk")


def test_long_backup_path_is_refused_before_creating_anything(db, tmp_path):
    long_dir = tmp_path / ("b" * 255)

    with pytest.raises(BackupError, match="caminho longo") as error:
        create_backup(db.database_path, long_dir)

    assert "--backup-dir" in str(error.value)
    assert not long_dir.exists()

    check_path_length("C:\\bk\\fundos\\fundos_20261027T130000_000000Z.sqlite3")

    with pytest.raises(BackupError, match="caminho longo"):
        check_path_length("C:\\" + "x" * 251)
