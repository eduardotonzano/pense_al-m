from __future__ import annotations

from pathlib import Path

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    MigrationError,
    PendingMigrationsError,
    apply_pending,
    discover_migrations,
    ensure_schema_current,
    pending_migrations,
    read_applied_versions,
    schema_snapshot,
    schema_warnings,
    split_statements,
    verify_state,
)


NOTE_SQL = "ALTER TABLE documents ADD COLUMN note TEXT;\n"


def write_migrations(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    for name, sql in files.items():
        (directory / name).write_text(sql, encoding="utf-8")

    return directory


def create_database(tmp_path: Path):
    """Banco existente, sem nenhuma migration aplicada."""

    empty = write_migrations(tmp_path / "empty_migrations", {})
    connection = connect(tmp_path / "cri_cra.db")
    initialize_database(connection, migrations_dir=empty)
    connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('TST0001', 'CRA', 'S', '1', '1', '1', 'now', 'now')"""
    )
    connection.commit()
    return connection


def columns(connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_discover_migrations_orders_and_ignores_other_files(tmp_path):
    folder = write_migrations(
        tmp_path / "m",
        {
            "010_ten.sql": "",
            "002_two.sql": "",
            "README.md": "",
            "003_Bad.sql": "",
            "004-bad.sql": "",
        },
    )

    found = discover_migrations(folder)

    assert [(item.version, item.name) for item in found] == [
        (2, "two"),
        (10, "ten"),
    ]


def test_discover_migrations_rejects_duplicate_numbers(tmp_path):
    folder = write_migrations(tmp_path / "m", {"002_a.sql": "", "002_b.sql": ""})

    with pytest.raises(MigrationError, match="mesmo numero"):
        discover_migrations(folder)


def test_discover_migrations_rejects_missing_folder(tmp_path):
    with pytest.raises(MigrationError, match="nao encontrada"):
        discover_migrations(tmp_path / "nope")


def test_default_migrations_folder_exists_and_is_numbered():
    found = discover_migrations()

    versions = [item.version for item in found]
    assert versions == sorted(set(versions))


def test_split_statements():
    sql = (
        "CREATE TABLE t (\n"
        " a INTEGER,\n"
        " b TEXT\n"
        ");\n"
        "-- comentario\n"
        "INSERT INTO t VALUES (1, 'a;b');\n"
    )

    statements = split_statements(sql)

    assert len(statements) == 2
    assert statements[1].endswith("VALUES (1, 'a;b');")


def test_split_statements_rejects_incomplete_script():
    with pytest.raises(MigrationError, match="incompleta"):
        split_statements("CREATE TABLE t (a INTEGER")


def test_read_applied_versions_without_table_is_empty(tmp_path):
    connection = create_database(tmp_path)

    assert read_applied_versions(connection) == {}


def test_initialize_database_applies_migrations_to_a_new_database(tmp_path):
    folder = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    connection = connect(tmp_path / "new.db")

    initialize_database(connection, migrations_dir=folder)

    assert "note" in columns(connection, "documents")
    assert read_applied_versions(connection) == {1: "add_note"}


def test_initialize_database_leaves_an_existing_database_alone(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})

    initialize_database(connection, migrations_dir=folder)

    assert "note" not in columns(connection, "documents")
    assert [item.version for item in pending_migrations(connection, folder)] == [1]


def test_ensure_schema_current_demands_apply_migration(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(
        tmp_path / "m",
        {"001_add_note.sql": NOTE_SQL, "002_other.sql": "SELECT 1;\n"},
    )

    with pytest.raises(PendingMigrationsError) as error:
        ensure_schema_current(connection, folder)

    assert "001, 002" in str(error.value)
    assert "apply_migration.py" in str(error.value)


def test_ensure_schema_current_passes_when_everything_is_applied(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    apply_pending(connection, pending_migrations(connection, folder))

    ensure_schema_current(connection, folder)

    assert pending_migrations(connection, folder) == []


def test_apply_pending_registers_versions_and_keeps_data(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})

    applied = apply_pending(connection, pending_migrations(connection, folder))

    assert [item.version for item in applied] == [1]
    assert read_applied_versions(connection) == {1: "add_note"}
    assert "note" in columns(connection, "documents")
    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.in_transaction is False


def test_apply_pending_with_nothing_pending_does_nothing(tmp_path):
    connection = create_database(tmp_path)

    assert apply_pending(connection, []) == []
    assert read_applied_versions(connection) == {}


def test_apply_pending_rolls_back_when_a_statement_fails(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(
        tmp_path / "m",
        {"001_broken.sql": NOTE_SQL + "INSERT INTO missing_table VALUES (1);\n"},
    )

    with pytest.raises(Exception, match="missing_table"):
        apply_pending(connection, pending_migrations(connection, folder))

    assert "note" not in columns(connection, "documents")
    assert read_applied_versions(connection) == {}
    assert connection.in_transaction is False


def test_apply_pending_rolls_back_when_a_column_is_removed(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(
        tmp_path / "m",
        {"001_drop.sql": "ALTER TABLE assets DROP COLUMN devedor;\n"},
    )

    with pytest.raises(MigrationError, match="Coluna removida: assets.devedor"):
        apply_pending(connection, pending_migrations(connection, folder))

    assert "devedor" in columns(connection, "assets")
    assert read_applied_versions(connection) == {}


def test_apply_pending_rolls_back_when_rows_are_deleted(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(tmp_path / "m", {"001_wipe.sql": "DELETE FROM assets;\n"})

    with pytest.raises(MigrationError, match="Contagem alterada em assets"):
        apply_pending(connection, pending_migrations(connection, folder))

    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_apply_pending_rolls_back_when_an_index_is_removed(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(
        tmp_path / "m",
        {"001_drop_index.sql": "DROP INDEX ix_documents_file_hash;\n"},
    )

    with pytest.raises(MigrationError, match="Indice removido: ix_documents_file_hash"):
        apply_pending(connection, pending_migrations(connection, folder))

    names = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "ix_documents_file_hash" in names


def test_apply_pending_rejects_a_migration_that_registers_another_name(tmp_path):
    connection = create_database(tmp_path)
    folder = write_migrations(
        tmp_path / "m",
        {
            "001_right.sql": "INSERT INTO schema_migrations (version, name) "
            "VALUES (1, 'other');\n"
        },
    )

    with pytest.raises(MigrationError, match="registrou outro nome"):
        apply_pending(connection, pending_migrations(connection, folder))

    assert read_applied_versions(connection) == {}


def test_verify_state_accepts_an_untouched_database(tmp_path):
    connection = create_database(tmp_path)

    assert verify_state(connection, schema_snapshot(connection), {}) == []


def test_verify_state_detects_foreign_key_errors(tmp_path):
    connection = create_database(tmp_path)
    before = schema_snapshot(connection)
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name,
            source, source_url, run_id
        ) VALUES ('x', 999, 'Outro', 'n', 'Fundos.NET', 'u', 'no-such-run')"""
    )
    connection.commit()

    problems = verify_state(connection, before, {})

    assert any("foreign_key_check encontrou" in item for item in problems)


def test_schema_warnings_flags_legacy_cetip_not_null(tmp_path):
    connection = create_database(tmp_path)
    assert schema_warnings(connection) == []

    legacy = connect(tmp_path / "legacy.db")
    legacy.execute(
        """CREATE TABLE assets (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_cetip TEXT NOT NULL UNIQUE
        )"""
    )

    warnings = schema_warnings(legacy)

    assert len(warnings) == 1
    assert "codigo_cetip" in warnings[0]
