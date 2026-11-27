import shutil
import sqlite3
import subprocess
import sys

import pytest

from apoio import MIGRATION_001
from apoio import MODULE_DIR
from titulos_bancarios import migrate
from titulos_bancarios.backup import BackupError
from titulos_bancarios.backup import check_local_paths
from titulos_bancarios.backup import create_backup
from titulos_bancarios.backup import file_sha256
from titulos_bancarios.migrate import MigrationError
from titulos_bancarios.migrate import discover_migrations
from titulos_bancarios.migrate import find_cpf_columns
from titulos_bancarios.migrate import main
from titulos_bancarios.migrate import split_statements


ADD_TABLE_002 = (
    "CREATE TABLE IF NOT EXISTS extra (id INTEGER PRIMARY KEY, note TEXT);\n"
    "INSERT OR IGNORE INTO schema_migrations(version,name) "
    "VALUES(2,'extra_table');\n"
)

CPF_COLUMN_002 = (
    "CREATE TABLE IF NOT EXISTS pessoa (id INTEGER PRIMARY KEY, cpf TEXT);\n"
    "INSERT OR IGNORE INTO schema_migrations(version,name) "
    "VALUES(2,'pessoa');\n"
)

CHANGE_SEEDS_002 = (
    "UPDATE sources SET active = 0 WHERE code = 'CVM_CDA';\n"
    "INSERT OR IGNORE INTO schema_migrations(version,name) "
    "VALUES(2,'change_seeds');\n"
)

BAD_ORDER_002 = (
    "CREATE TABLE IF NOT EXISTS extra (id INTEGER PRIMARY KEY);\n"
    "INSERT INTO schema_migrations(version,name) VALUES(2,'outro_nome');\n"
)


@pytest.fixture
def migrations_dir(tmp_path):
    folder = tmp_path / "migrations"
    folder.mkdir()
    shutil.copy(MIGRATION_001, folder / "001_initial_schema.sql")
    return folder


def run_cli(*arguments):
    return main([str(a) for a in arguments])


def tables(database):
    connection = sqlite3.connect(database)

    try:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        connection.close()


def versions(database):
    connection = sqlite3.connect(database)

    try:
        return [
            tuple(row)
            for row in connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            )
        ]
    finally:
        connection.close()


@pytest.fixture
def committed(tmp_path, migrations_dir):
    """Banco novo com a migration 001 aplicada pelo proprio script."""

    database = tmp_path / "dados" / "tb.db"
    code = run_cli(
        "--database", database, "--create", "--commit",
        "--migrations-dir", migrations_dir,
    )
    assert code == 0
    return database


# --- descoberta e separacao ------------------------------------------------


def test_discover_finds_the_real_migration():
    found = discover_migrations(MODULE_DIR / "migrations")

    assert [(v, n) for v, n, _ in found] == [(1, "initial_schema")]


def test_discover_ignores_files_that_are_not_numbered_migrations(
    migrations_dir,
):
    (migrations_dir / "notas.sql").write_text("-- nada", encoding="utf-8")
    (migrations_dir / "01_curta.sql").write_text("-- nada", encoding="utf-8")
    (migrations_dir / "002_Maiuscula.sql").write_text("--", encoding="utf-8")

    assert [v for v, _, _ in discover_migrations(migrations_dir)] == [1]


def test_discover_refuses_duplicate_numbers(migrations_dir):
    (migrations_dir / "001_outra.sql").write_text("--", encoding="utf-8")

    with pytest.raises(MigrationError, match="mesmo numero"):
        discover_migrations(migrations_dir)


def test_discover_refuses_a_missing_folder(tmp_path):
    with pytest.raises(MigrationError):
        discover_migrations(tmp_path / "nao_existe")


def test_split_statements_keeps_triggers_whole():
    statements = split_statements(MIGRATION_001.read_text(encoding="utf-8"))
    triggers = [s for s in statements if "CREATE TRIGGER" in s]

    assert len(triggers) == 3
    assert all(t.rstrip().endswith("END;") for t in triggers)

    connection = sqlite3.connect(":memory:")
    for statement in statements:
        connection.execute(statement)

    assert connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger'"
    ).fetchone()[0] == 3


def test_split_statements_refuses_an_incomplete_statement():
    with pytest.raises(MigrationError, match="incompleta"):
        split_statements("CREATE TABLE a (id INTEGER")


# --- argumentos ------------------------------------------------------------


def test_database_is_required(migrations_dir):
    with pytest.raises(SystemExit) as error:
        run_cli("--dry-run", "--migrations-dir", migrations_dir)

    assert error.value.code == 2


def test_one_of_dry_run_or_commit_is_required(tmp_path, migrations_dir):
    with pytest.raises(SystemExit) as error:
        run_cli("--database", tmp_path / "x.db", "--migrations-dir", migrations_dir)

    assert error.value.code == 2


def test_dry_run_and_commit_are_mutually_exclusive(tmp_path, migrations_dir):
    with pytest.raises(SystemExit) as error:
        run_cli(
            "--database", tmp_path / "x.db", "--dry-run", "--commit",
            "--migrations-dir", migrations_dir,
        )

    assert error.value.code == 2


def test_script_runs_as_a_program_and_requires_the_flags(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-I",
            str(MODULE_DIR / "scripts" / "apply_migration.py"),
            "--database", str(tmp_path / "x.db"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert not (tmp_path / "x.db").exists()


# --- banco novo ------------------------------------------------------------


def test_missing_database_without_create_is_an_error(
    tmp_path, migrations_dir, capsys
):
    database = tmp_path / "tb.db"

    code = run_cli(
        "--database", database, "--dry-run", "--migrations-dir", migrations_dir
    )

    assert code == 1
    assert "--create" in capsys.readouterr().err
    assert not database.exists()


def test_dry_run_create_does_not_create_the_database(
    tmp_path, migrations_dir, capsys
):
    database = tmp_path / "tb.db"

    code = run_cli(
        "--database", database, "--create", "--dry-run",
        "--migrations-dir", migrations_dir,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert not database.exists()
    assert "nenhum banco foi criado" in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output


def test_commit_create_builds_the_database(committed):
    assert tables(committed) >= {"subjects", "observations", "sources"}
    assert versions(committed) == [(1, "initial_schema")]

    connection = sqlite3.connect(committed)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 4
    finally:
        connection.close()


def test_new_database_needs_no_backup(committed):
    assert not (committed.parent / "backups").exists()


def test_failure_on_a_new_database_removes_the_file(
    tmp_path, migrations_dir, capsys
):
    (migrations_dir / "001_initial_schema.sql").write_text(
        "CREATE TABLE a (id INTEGER);\nSELECT * FROM tabela_que_nao_existe;\n",
        encoding="utf-8",
    )
    database = tmp_path / "dados" / "tb.db"

    code = run_cli(
        "--database", database, "--create", "--commit",
        "--migrations-dir", migrations_dir,
    )

    assert code == 1
    assert not database.exists()
    assert "Erro ao aplicar migration" in capsys.readouterr().err


# --- segunda execucao ------------------------------------------------------


def test_second_commit_has_nothing_to_apply_and_makes_no_backup(
    committed, migrations_dir, capsys
):
    before = file_sha256(committed)
    capsys.readouterr()

    code = run_cli(
        "--database", committed, "--commit", "--migrations-dir", migrations_dir
    )

    assert code == 0
    assert "Nada a aplicar" in capsys.readouterr().out
    assert file_sha256(committed) == before
    assert not (committed.parent / "backups").exists()


def test_reapplying_the_001_script_does_not_duplicate_anything(committed):
    connection = sqlite3.connect(committed)

    try:
        before = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
        after = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        versions_count = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0]
    finally:
        connection.close()

    assert (before, after, versions_count) == (4, 4, 1)


# --- banco existente: dry-run ---------------------------------------------


def test_dry_run_on_an_existing_database_leaves_it_untouched(
    committed, migrations_dir
):
    (migrations_dir / "002_extra_table.sql").write_text(
        ADD_TABLE_002, encoding="utf-8"
    )
    before = file_sha256(committed)

    code = run_cli(
        "--database", committed, "--dry-run", "--migrations-dir", migrations_dir
    )

    assert code == 0
    assert file_sha256(committed) == before
    assert "extra" not in tables(committed)
    assert not (committed.parent / "backups").exists()


def test_dry_run_reports_a_failing_migration_and_changes_nothing(
    committed, migrations_dir, capsys
):
    (migrations_dir / "002_pessoa.sql").write_text(
        CPF_COLUMN_002, encoding="utf-8"
    )
    before = file_sha256(committed)
    capsys.readouterr()

    code = run_cli(
        "--database", committed, "--dry-run", "--migrations-dir", migrations_dir
    )

    assert code == 1
    assert "cpf" in capsys.readouterr().err
    assert file_sha256(committed) == before


# --- banco existente: commit -----------------------------------------------


def test_commit_makes_a_backup_with_the_previous_state(
    committed, migrations_dir
):
    (migrations_dir / "002_extra_table.sql").write_text(
        ADD_TABLE_002, encoding="utf-8"
    )
    before = tables(committed)

    code = run_cli(
        "--database", committed, "--commit", "--migrations-dir", migrations_dir
    )

    assert code == 0
    assert "extra" in tables(committed)
    assert versions(committed) == [(1, "initial_schema"), (2, "extra_table")]

    backups = list((committed.parent / "backups").glob("titulos_bancarios_*.sqlite3"))
    assert len(backups) == 1
    assert tables(backups[0]) == before
    assert versions(backups[0]) == [(1, "initial_schema")]


def test_commit_uses_the_backup_dir_when_given(
    tmp_path, committed, migrations_dir
):
    (migrations_dir / "002_extra_table.sql").write_text(
        ADD_TABLE_002, encoding="utf-8"
    )
    backup_dir = tmp_path / "bk"

    code = run_cli(
        "--database", committed, "--commit", "--backup-dir", backup_dir,
        "--migrations-dir", migrations_dir,
    )

    assert code == 0
    assert len(list(backup_dir.glob("*.sqlite3"))) == 1
    assert not (committed.parent / "backups").exists()


def test_failed_verification_rolls_back_and_keeps_the_backup(
    committed, migrations_dir, capsys
):
    (migrations_dir / "002_pessoa.sql").write_text(
        CPF_COLUMN_002, encoding="utf-8"
    )
    before = file_sha256(committed)
    capsys.readouterr()

    code = run_cli(
        "--database", committed, "--commit", "--migrations-dir", migrations_dir
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "cpf" in error
    assert "Backup:" in error
    assert "pessoa" not in tables(committed)
    assert versions(committed) == [(1, "initial_schema")]
    assert file_sha256(committed) == before
    assert len(list((committed.parent / "backups").glob("*.sqlite3"))) == 1


def test_a_migration_that_changes_existing_rows_is_refused_by_default(
    committed, migrations_dir, capsys
):
    (migrations_dir / "002_change_seeds.sql").write_text(
        CHANGE_SEEDS_002, encoding="utf-8"
    )
    capsys.readouterr()

    code = run_cli(
        "--database", committed, "--commit", "--migrations-dir", migrations_dir
    )

    assert code == 1
    connection = sqlite3.connect(committed)
    try:
        active = connection.execute(
            "SELECT active FROM sources WHERE code = 'CVM_CDA'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert active == 1
    assert versions(committed) == [(1, "initial_schema")]


def test_allow_existing_changes_lets_the_migration_change_rows(
    committed, migrations_dir
):
    (migrations_dir / "002_change_seeds.sql").write_text(
        CHANGE_SEEDS_002, encoding="utf-8"
    )

    code = run_cli(
        "--database", committed, "--commit", "--allow-existing-changes",
        "--migrations-dir", migrations_dir,
    )

    assert code == 0
    assert versions(committed)[-1] == (2, "change_seeds")


def test_a_migration_that_registers_another_name_is_refused(
    committed, migrations_dir
):
    (migrations_dir / "002_extra_table.sql").write_text(
        BAD_ORDER_002, encoding="utf-8"
    )

    code = run_cli(
        "--database", committed, "--commit", "--migrations-dir", migrations_dir
    )

    assert code == 1
    assert versions(committed) == [(1, "initial_schema")]
    assert "extra" not in tables(committed)


# --- caminhos --------------------------------------------------------------


@pytest.mark.parametrize(
    "database",
    ["\\\\servidor\\pasta\\tb.db", "//servidor/pasta/tb.db"],
)
def test_network_database_is_refused_before_touching_it(
    database, migrations_dir, capsys
):
    code = run_cli(
        "--database", database, "--create", "--dry-run",
        "--migrations-dir", migrations_dir,
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "caminho de rede" in error
    assert "servidor" not in error


def test_network_backup_dir_is_refused(tmp_path, migrations_dir, capsys):
    code = run_cli(
        "--database", tmp_path / "tb.db", "--create", "--dry-run",
        "--backup-dir", "\\\\servidor\\bk",
        "--migrations-dir", migrations_dir,
    )

    assert code == 1
    assert "--backup-dir" in capsys.readouterr().err
    assert not (tmp_path / "tb.db").exists()


def test_long_database_path_is_refused(tmp_path, migrations_dir, capsys):
    database = tmp_path / ("a" * 120) / ("b" * 120) / "tb.db"

    code = run_cli(
        "--database", database, "--create", "--dry-run",
        "--migrations-dir", migrations_dir,
    )

    assert code == 1
    assert "caminho longo" in capsys.readouterr().err


def test_check_local_paths_returns_the_resolved_database(tmp_path):
    result = check_local_paths(tmp_path / "tb.db")

    assert result == (tmp_path / "tb.db").resolve()


# --- backup ----------------------------------------------------------------


def test_backup_is_a_valid_copy(committed, tmp_path):
    result = create_backup(committed, tmp_path / "bk")

    assert result.path.name.startswith("titulos_bancarios_")
    assert result.path.suffix == ".sqlite3"
    assert result.sha256 == file_sha256(result.path)
    assert tables(result.path) == tables(committed)


def test_backup_refuses_a_missing_database(tmp_path):
    with pytest.raises(BackupError, match="nao encontrado"):
        create_backup(tmp_path / "nao_existe.db", tmp_path / "bk")


def test_backup_refuses_a_corrupt_database(tmp_path):
    corrupt = tmp_path / "corrompido.db"
    corrupt.write_bytes(b"isto nao e um banco sqlite" * 50)

    with pytest.raises(BackupError):
        create_backup(corrupt, tmp_path / "bk")

    assert not (tmp_path / "bk").exists() or not list((tmp_path / "bk").iterdir())


def test_backup_refuses_a_database_with_a_foreign_key_error(tmp_path):
    database = tmp_path / "fk.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        "CREATE TABLE pai (id INTEGER PRIMARY KEY);"
        "CREATE TABLE filho (id INTEGER PRIMARY KEY, pai_id INTEGER "
        "REFERENCES pai(id));"
        "INSERT INTO filho(id, pai_id) VALUES(1, 99);"
    )
    connection.close()

    with pytest.raises(BackupError, match="chave estrangeira"):
        create_backup(database, tmp_path / "bk")


# --- cpf -------------------------------------------------------------------


def test_the_real_schema_has_no_cpf(committed):
    connection = sqlite3.connect(committed)

    try:
        assert find_cpf_columns(connection) == []
    finally:
        connection.close()


def test_find_cpf_columns_sees_columns_and_objects():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE pessoa (id INTEGER, nr_CPF TEXT);"
        "CREATE TABLE cpf_lista (id INTEGER);"
    )

    found = find_cpf_columns(connection)

    assert "pessoa.nr_CPF" in found
    assert "table cpf_lista" in found


def test_migrate_module_has_the_documented_entry_points():
    assert callable(migrate.main)
    assert callable(migrate.run)
    assert migrate.MIGRATIONS_DIR == MODULE_DIR / "migrations"
