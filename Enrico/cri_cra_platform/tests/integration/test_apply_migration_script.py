from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from credit_assets.database.backup import file_sha256
from credit_assets.database.connection import connect, initialize_database


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
NOTE_SQL = "ALTER TABLE documents ADD COLUMN note TEXT;\n"


def load_module():
    specification = importlib.util.spec_from_file_location(
        "apply_migration_script",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_module()


def write_migrations(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    for name, sql in files.items():
        (directory / name).write_text(sql, encoding="utf-8")

    return directory


def create_database(tmp_path: Path) -> Path:
    """Banco existente (linha de base), com um ativo, sem migrations."""

    empty = write_migrations(tmp_path / "empty_migrations", {})
    path = tmp_path / "cri_cra.db"
    connection = connect(path)
    initialize_database(connection, migrations_dir=empty)
    connection.execute(
        """INSERT INTO assets (
            codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('APL0001', 'CRA', 'S', '1', '1', '1', 'now', 'now')"""
    )
    connection.commit()
    connection.close()
    return path


def query(path: Path, sql: str):
    connection = sqlite3.connect(path)

    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def document_columns(path: Path) -> set[str]:
    return {row[1] for row in query(path, "PRAGMA table_info(documents)")}


def versions(path: Path) -> list[int]:
    return [row[0] for row in query(path, "SELECT version FROM schema_migrations")]


def backups_in(folder: Path) -> list[Path]:
    return sorted(Path(folder).glob("*.sqlite3"))


def arguments(path: Path, migrations: Path, mode: str, *extra: str) -> list[str]:
    return [
        "--database",
        str(path),
        mode,
        "--migrations-dir",
        str(migrations),
        *extra,
    ]


def test_dry_run_leaves_the_database_untouched(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    before = file_sha256(path)

    code = script.main(arguments(path, migrations, "--dry-run"))
    output = capsys.readouterr().out

    assert code == 0
    assert file_sha256(path) == before
    assert "note" not in document_columns(path)
    assert "001_add_note" in output
    assert "Dry-run concluido" in output
    assert "colunas novas: documents.note" in output
    assert not (tmp_path / "backups").exists()


def test_commit_creates_the_backup_before_applying(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    saved = tmp_path / "saved"

    code = script.main(arguments(path, migrations, "--commit", "--backup-dir", str(saved)))
    output = capsys.readouterr().out
    backups = backups_in(saved)

    assert code == 0
    assert len(backups) == 1
    assert "note" in document_columns(path)
    assert versions(path) == [1]
    # O backup e o banco como estava antes da migration.
    assert "note" not in document_columns(backups[0])
    assert query(
        backups[0],
        "SELECT name FROM sqlite_master WHERE name = 'schema_migrations'",
    ) == []
    assert backups[0].name in output
    assert file_sha256(backups[0]) in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output
    assert query(path, "SELECT codigo_cetip FROM assets") == [("APL0001",)]


def test_second_commit_has_nothing_to_apply(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    saved = tmp_path / "saved"
    call = arguments(path, migrations, "--commit", "--backup-dir", str(saved))

    first = script.main(call)
    capsys.readouterr()
    second = script.main(call)
    output = capsys.readouterr().out

    assert (first, second) == (0, 0)
    assert "Nada a aplicar" in output
    assert len(backups_in(saved)) == 1


def test_missing_database_is_refused_without_creating_it(script, tmp_path, capsys):
    path = tmp_path / "missing.db"
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})

    for mode in ("--dry-run", "--commit"):
        code = script.main(arguments(path, migrations, mode))
        error = capsys.readouterr().err

        assert code == 1
        assert "Banco nao encontrado" in error
        assert not path.exists()


def test_file_that_is_not_a_database_is_refused(script, tmp_path, capsys):
    path = tmp_path / "garbage.db"
    path.write_bytes(b"isto nao e um banco sqlite" * 10)
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    before = file_sha256(path)

    code = script.main(arguments(path, migrations, "--commit"))
    capsys.readouterr()

    assert code == 1
    assert file_sha256(path) == before
    assert not (tmp_path / "backups").exists()


def test_failing_migration_rolls_back_and_keeps_the_backup(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = write_migrations(
        tmp_path / "m",
        {"001_broken.sql": NOTE_SQL + "INSERT INTO missing_table VALUES (1);\n"},
    )
    saved = tmp_path / "saved"

    code = script.main(arguments(path, migrations, "--commit", "--backup-dir", str(saved)))
    error = capsys.readouterr().err

    assert code == 1
    assert "missing_table" in error
    assert "Backup:" in error
    assert "note" not in document_columns(path)
    assert len(backups_in(saved)) == 1
    assert sqlite3.connect(path).execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_verification_failure_rolls_back_before_the_commit(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = write_migrations(tmp_path / "m", {"001_wipe.sql": "DELETE FROM assets;\n"})

    code = script.main(arguments(path, migrations, "--commit"))
    error = capsys.readouterr().err

    assert code == 1
    assert "Contagem alterada em assets" in error
    assert query(path, "SELECT COUNT(*) FROM assets") == [(1,)]


def test_backup_failure_stops_before_any_change(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("arquivo", encoding="utf-8")
    before = file_sha256(path)

    code = script.main(arguments(path, migrations, "--commit", "--backup-dir", str(blocker)))
    error = capsys.readouterr().err

    assert code == 1
    assert "Nao foi possivel criar o backup" in error
    assert file_sha256(path) == before


def test_warns_about_a_legacy_cetip_constraint(script, tmp_path, capsys):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        (PROJECT_DIR / "src" / "credit_assets" / "database" / "schema.sql")
        .read_text(encoding="utf-8")
        .replace("codigo_cetip TEXT,", "codigo_cetip TEXT NOT NULL UNIQUE,")
    )
    connection.close()
    migrations = write_migrations(tmp_path / "m", {"001_add_note.sql": NOTE_SQL})

    code = script.main(arguments(path, migrations, "--dry-run"))
    output = capsys.readouterr().out

    assert code == 0
    assert "Aviso: assets.codigo_cetip e NOT NULL" in output


def test_mode_and_database_are_required(script, tmp_path):
    with pytest.raises(SystemExit) as no_mode:
        script.main(["--database", str(tmp_path / "x.db")])

    with pytest.raises(SystemExit) as no_database:
        script.main(["--dry-run"])

    with pytest.raises(SystemExit) as both_modes:
        script.main(["--database", str(tmp_path / "x.db"), "--dry-run", "--commit"])

    assert no_mode.value.code == 2
    assert no_database.value.code == 2
    assert both_modes.value.code == 2
