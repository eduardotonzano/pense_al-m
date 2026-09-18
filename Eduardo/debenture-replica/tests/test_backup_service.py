import pathlib
import sqlite3

import pytest

from debenture_search.database import Database
from debenture_search.services.backup_service import (
    BackupRecord,
    BackupService,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"


@pytest.fixture
def context(tmp_path):
    database_path = tmp_path / "data" / "debenture.db"
    db = Database(database_path)
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.execute(
            """
            INSERT INTO issuers (cnpj, legal_name)
            VALUES (?, ?)
            """,
            ("12345678000199", "Empresa Original"),
        )
        connection.commit()

    service = BackupService(
        db,
        backup_dir=tmp_path / "backups",
    )

    return {
        "db": db,
        "service": service,
        "tmp_path": tmp_path,
    }


def test_create_backup(context):
    record = context["service"].create_backup()

    assert isinstance(record, BackupRecord)
    assert record.path.exists()
    assert record.size_bytes > 0
    assert len(record.sha256) == 64
    assert context["service"].validate_sqlite(record.path)


def test_backup_contains_original_data(context):
    record = context["service"].create_backup()
    connection = sqlite3.connect(record.path)

    try:
        result = connection.execute(
            "SELECT legal_name FROM issuers"
        ).fetchone()[0]
    finally:
        connection.close()

    assert result == "Empresa Original"


def test_list_backups(context):
    first = context["service"].create_backup()
    second = context["service"].create_backup()
    backups = context["service"].list_backups()

    assert len(backups) == 2
    assert {item.path for item in backups} == {
        first.path,
        second.path,
    }


def test_validate_rejects_missing_file(context):
    with pytest.raises(ValueError, match="nao encontrado"):
        context["service"].validate_sqlite(
            context["tmp_path"] / "ausente.db"
        )


def test_validate_rejects_empty_file(context):
    empty = context["tmp_path"] / "empty.db"
    empty.write_bytes(b"")

    with pytest.raises(ValueError, match="esta vazio"):
        context["service"].validate_sqlite(empty)


def test_validate_rejects_invalid_file(context):
    invalid = context["tmp_path"] / "invalid.db"
    invalid.write_text("nao e sqlite", encoding="utf-8")

    with pytest.raises(ValueError, match="SQLite valido"):
        context["service"].validate_sqlite(invalid)


def test_restore_backup(context):
    service = context["service"]
    backup = service.create_backup()

    with context["db"].transaction() as connection:
        connection.execute(
            "UPDATE issuers SET legal_name = ?",
            ("Empresa Alterada",),
        )

    result = service.restore(backup.path)
    issuer = context["db"].fetch_one(
        "SELECT legal_name FROM issuers"
    )

    assert issuer["legal_name"] == "Empresa Original"
    assert result["restored_from"] == backup.path
    assert result["safety_backup"] is not None


def test_restore_rejects_invalid_backup(context):
    invalid = context["tmp_path"] / "invalid.db"
    invalid.write_text("conteudo invalido", encoding="utf-8")

    with pytest.raises(ValueError, match="SQLite valido"):
        context["service"].restore(invalid)


def test_restore_creates_safety_backup(context):
    backup = context["service"].create_backup()
    result = context["service"].restore(backup.path)

    assert result["safety_backup"] is not None
    assert result["safety_backup"].exists()


def test_prune_keeps_requested_amount(context):
    service = context["service"]

    for _ in range(4):
        service.create_backup()

    removed = service.prune(keep=2)
    remaining = service.list_backups()

    assert len(removed) == 2
    assert len(remaining) == 2


def test_prune_rejects_zero(context):
    with pytest.raises(ValueError, match="maior que zero"):
        context["service"].prune(keep=0)


def test_get_record_returns_metadata(context):
    created = context["service"].create_backup()
    found = context["service"].get_record(created.path)

    assert found.path == created.path
    assert found.size_bytes == created.size_bytes
    assert found.sha256 == created.sha256


def test_backup_does_not_modify_database(context):
    before = context["db"].fetch_one(
        "SELECT COUNT(*) AS total FROM issuers"
    )["total"]

    context["service"].create_backup()

    after = context["db"].fetch_one(
        "SELECT COUNT(*) AS total FROM issuers"
    )["total"]

    assert before == after


def test_database_integrity_after_backup(context):
    context["service"].create_backup()

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
