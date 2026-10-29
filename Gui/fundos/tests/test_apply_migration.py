import hashlib
import importlib.util
import pathlib
import shutil
import sqlite3

import pytest

from apoio import make_test_cnpj
from fundos.database import Database


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
MIGRATIONS_DIR = PROJECT_DIR / "migrations"
MIGRATION_001 = MIGRATIONS_DIR / "001_initial_schema.sql"

EXTRA_SQL = (
    "CREATE TABLE extra_ficticia (id INTEGER PRIMARY KEY);\n"
    "CREATE INDEX idx_extra_ficticia ON extra_ficticia(id);\n"
    "INSERT INTO schema_migrations(version,name) VALUES(2,'extra');\n"
)

ALTER_SQL = (
    "ALTER TABLE funds ADD COLUMN note TEXT;\n"
    "INSERT INTO schema_migrations(version,name) VALUES(2,'add_note');\n"
)


def load_module():
    specification = importlib.util.spec_from_file_location(
        "apply_migration",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_module()


def create_database(directory, name="fundos.db"):
    """Cria um banco na versao 1, com um fundo ficticio."""

    path = directory / name
    connection = Database(path).connect(create=True)

    try:
        connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO funds (cnpj) VALUES (?)",
            (make_test_cnpj(1),),
        )
    finally:
        connection.close()

    return path


def copy_migrations(directory, name, sql):
    """Copia a 001 e acrescenta uma 002 com o conteudo informado."""

    target = directory / "migrations"
    target.mkdir()
    shutil.copy(MIGRATION_001, target)
    (target / ("002_" + name + ".sql")).write_text(sql, encoding="utf-8")
    return target


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def query(path, sql):
    connection = sqlite3.connect(path)

    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def table_names(path):
    return {
        row[0]
        for row in query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def versions(path):
    return [
        row[0]
        for row in query(path, "SELECT version FROM schema_migrations ORDER BY version")
    ]


def backups_in(directory):
    return sorted(pathlib.Path(directory).glob("fundos_*.sqlite3"))


def run_with(script, path, *extra):
    return script.main(["--database", str(path), *extra])


def test_create_dry_run_creates_nothing(script, tmp_path, capsys):
    path = tmp_path / "novo" / "fundos.db"

    code = run_with(script, path, "--create", "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert not path.exists()
    assert not path.parent.exists()
    assert "001_initial_schema" in output
    assert "colunas com cpf: 0" in output
    assert "Dry-run concluido: nenhum banco foi criado." in output


def test_create_commit_builds_a_new_database(script, tmp_path, capsys):
    path = tmp_path / "novo" / "fundos.db"

    code = run_with(script, path, "--create", "--commit")
    output = capsys.readouterr().out

    assert code == 0
    assert versions(path) == [1, 2]
    assert "Banco novo" in output
    assert "Migrations aplicadas com sucesso." in output
    assert not (path.parent / "backups").exists()
    assert Database(path).integrity_check() == "ok"


def test_dry_run_on_existing_database_leaves_it_untouched(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "extra", EXTRA_SQL)
    before = file_hash(path)

    code = run_with(script, path, "--dry-run", "--migrations-dir", str(migrations))
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(path) == before
    assert "extra_ficticia" not in table_names(path)
    assert "002_extra" in output
    assert "objetos novos: index idx_extra_ficticia, table extra_ficticia" in output
    assert "Dry-run concluido: o banco informado nao foi alterado." in output
    assert not (tmp_path / "backups").exists()


def test_commit_creates_the_backup_before_applying(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "extra", EXTRA_SQL)
    backup_dir = tmp_path / "bk"

    code = run_with(
        script,
        path,
        "--commit",
        "--migrations-dir",
        str(migrations),
        "--backup-dir",
        str(backup_dir),
    )
    output = capsys.readouterr().out
    backups = backups_in(backup_dir)

    assert code == 0
    assert len(backups) == 1
    assert versions(path) == [1, 2]
    # O backup e o banco como estava antes da migration.
    assert versions(backups[0]) == [1]
    assert "extra_ficticia" not in table_names(backups[0])
    assert backups[0].name in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output
    assert query(path, "SELECT COUNT(*) FROM funds") == [(1,)]


def test_second_commit_has_nothing_to_apply(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "extra", EXTRA_SQL)
    backup_dir = tmp_path / "bk"
    arguments = ["--commit", "--migrations-dir", str(migrations), "--backup-dir", str(backup_dir)]

    first = run_with(script, path, *arguments)
    capsys.readouterr()
    second = run_with(script, path, *arguments)
    output = capsys.readouterr().out

    assert (first, second) == (0, 0)
    assert "Nada a aplicar" in output
    assert len(backups_in(backup_dir)) == 1
    assert versions(path) == [1, 2]


def test_backup_failure_stops_before_any_change(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "extra", EXTRA_SQL)
    blocker = tmp_path / "nao_e_pasta"
    blocker.write_text("arquivo", encoding="utf-8")
    before = file_hash(path)

    code = run_with(
        script,
        path,
        "--commit",
        "--migrations-dir",
        str(migrations),
        "--backup-dir",
        str(blocker),
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "Nao foi possivel criar o backup" in error
    assert "o banco nao foi alterado" in error
    assert file_hash(path) == before
    assert versions(path) == [1]


def test_long_backup_path_is_refused_before_touching_the_database(script, tmp_path, capsys):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "extra", EXTRA_SQL)
    long_dir = tmp_path / ("b" * 255)
    before = file_hash(path)

    code = run_with(
        script,
        path,
        "--commit",
        "--migrations-dir",
        str(migrations),
        "--backup-dir",
        str(long_dir),
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "caminho longo" in error
    assert "--backup-dir com uma pasta curta" in error
    assert file_hash(path) == before
    assert versions(path) == [1]
    assert not long_dir.exists()


def test_long_database_path_is_refused(script, tmp_path, capsys):
    path = tmp_path / ("d" * 255 + ".db")

    code = run_with(script, path, "--create", "--dry-run")
    error = capsys.readouterr().err

    assert code == 1
    assert "Banco com caminho longo" in error


def test_missing_database_is_refused_without_create(script, tmp_path, capsys):
    path = tmp_path / "inexistente.db"

    for mode in ("--dry-run", "--commit"):
        code = run_with(script, path, mode)
        error = capsys.readouterr().err

        assert code == 1
        assert "Banco nao encontrado" in error
        assert not path.exists()


def test_failed_create_leaves_no_file(script, tmp_path, capsys):
    path = tmp_path / "novo" / "fundos.db"
    migrations = copy_migrations(tmp_path, "broken", "INSERT INTO missing_table VALUES (1);\n")

    code = run_with(script, path, "--create", "--commit", "--migrations-dir", str(migrations))
    capsys.readouterr()

    assert code == 1
    assert not path.exists()


def test_mode_and_database_are_required(script, tmp_path):
    for arguments in (
        ["--database", str(tmp_path / "x.db")],
        ["--dry-run"],
        ["--database", str(tmp_path / "x.db"), "--dry-run", "--commit"],
    ):
        with pytest.raises(SystemExit) as error:
            script.main(arguments)

        assert error.value.code == 2


def run_broken(script, tmp_path, name, sql, *extra):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, name, sql)
    code = run_with(script, path, "--commit", "--migrations-dir", str(migrations), *extra)
    return path, code


def test_failing_migration_rolls_back_and_keeps_the_backup(script, tmp_path, capsys):
    backup_dir = tmp_path / "bk"
    path, code = run_broken(
        script,
        tmp_path,
        "broken",
        "CREATE TABLE half_done (id INTEGER);\n"
        "INSERT INTO schema_migrations(version,name) VALUES(2,'broken');\n"
        "INSERT INTO missing_table VALUES (1);\n",
        "--backup-dir",
        str(backup_dir),
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "missing_table" in error
    assert "Backup:" in error
    assert "half_done" not in table_names(path)
    assert versions(path) == [1]
    assert len(backups_in(backup_dir)) == 1
    assert Database(path).integrity_check() == "ok"


def test_migration_that_does_not_register_its_version_is_rolled_back(script, tmp_path, capsys):
    path, code = run_broken(script, tmp_path, "no_version", "CREATE TABLE no_version (id INTEGER);\n")
    error = capsys.readouterr().err

    assert code == 1
    assert "nao registrou a versao" in error
    assert "no_version" not in table_names(path)


def test_migration_registering_another_name_is_rolled_back(script, tmp_path, capsys):
    path, code = run_broken(
        script,
        tmp_path,
        "right_name",
        "CREATE TABLE named (id INTEGER);\n"
        "INSERT INTO schema_migrations(version,name) VALUES(2,'other_name');\n",
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "registrou outro nome" in error
    assert "named" not in table_names(path)


def test_changes_to_existing_objects_are_refused_by_default(script, tmp_path, capsys):
    path, code = run_broken(script, tmp_path, "add_note", ALTER_SQL)
    error = capsys.readouterr().err
    columns = [row[1] for row in query(path, "PRAGMA table_info(funds)")]

    assert code == 1
    assert "DDL alterado: table funds" in error
    assert "note" not in columns
    assert versions(path) == [1]


def test_changes_to_existing_objects_can_be_allowed(script, tmp_path, capsys):
    path, code = run_broken(script, tmp_path, "add_note", ALTER_SQL, "--allow-existing-changes")
    capsys.readouterr()
    columns = [row[1] for row in query(path, "PRAGMA table_info(funds)")]

    assert code == 0
    assert "note" in columns
    assert versions(path) == [1, 2]


def test_deleting_existing_rows_is_refused_by_default(script, tmp_path, capsys):
    path, code = run_broken(
        script,
        tmp_path,
        "wipe",
        "DELETE FROM funds;\nINSERT INTO schema_migrations(version,name) VALUES(2,'wipe');\n",
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "Contagem alterada em funds" in error
    assert query(path, "SELECT COUNT(*) FROM funds") == [(1,)]


@pytest.mark.parametrize("allow", [False, True], ids=["padrao", "com-allow-existing-changes"])
def test_migration_creating_a_cpf_column_is_refused_before_commit(script, tmp_path, capsys, allow):
    extra = ["--allow-existing-changes"] if allow else []
    path, code = run_broken(
        script,
        tmp_path,
        "cpf_column",
        "CREATE TABLE gestores_pf (id INTEGER, cpf_gestor TEXT);\n"
        "INSERT INTO schema_migrations(version,name) VALUES(2,'cpf_column');\n",
        *extra,
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "gestores_pf.cpf_gestor" in error
    assert "nao guarda CPF" in error
    assert "gestores_pf" not in table_names(path)
    assert versions(path) == [1]


def test_file_that_is_not_a_database_is_refused(script, tmp_path, capsys):
    path = tmp_path / "lixo.db"
    path.write_bytes(b"isto nao e um banco sqlite" * 10)
    before = file_hash(path)

    code = run_with(script, path, "--commit")
    capsys.readouterr()

    assert code == 1
    assert file_hash(path) == before
    assert not (tmp_path / "backups").exists()


def test_reports_the_package_from_this_checkout(script, tmp_path, capsys):
    path = create_database(tmp_path)

    run_with(script, path, "--dry-run")
    output = capsys.readouterr().out
    expected = (PROJECT_DIR / "src" / "fundos").resolve()

    assert "Pacote fundos: " + str(expected) in output
    assert "Migrations pendentes: 002_party_observations" in output


def test_discover_migrations_orders_and_ignores_other_files(script, tmp_path):
    for name in ("010_ten.sql", "002_two.sql", "readme.sql", "003_Bad.sql", "004-bad.sql"):
        (tmp_path / name).write_text("", encoding="utf-8")

    found = script.discover_migrations(tmp_path)

    assert [(version, name) for version, name, _ in found] == [(2, "two"), (10, "ten")]


def test_discover_migrations_rejects_duplicates_and_missing_folder(script, tmp_path):
    (tmp_path / "002_a.sql").write_text("", encoding="utf-8")
    (tmp_path / "002_b.sql").write_text("", encoding="utf-8")

    with pytest.raises(script.MigrationError, match="mesmo numero"):
        script.discover_migrations(tmp_path)

    with pytest.raises(script.MigrationError, match="nao encontrada"):
        script.discover_migrations(tmp_path / "nope")


def test_real_migrations_are_numbered_and_named_like_the_registry(script):
    found = script.discover_migrations(MIGRATIONS_DIR)

    assert [(version, name) for version, name, _ in found] == [
        (1, "initial_schema"),
        (2, "party_observations"),
    ]


def test_split_statements(script):
    sql = (
        "PRAGMA foreign_keys = ON;\n"
        "CREATE TABLE t (\n"
        " a INTEGER,\n"
        " b TEXT\n"
        ");\n"
        "-- comentario\n"
        "INSERT INTO t VALUES (1, 'a;b');\n"
    )

    statements = script.split_statements(sql)

    assert len(statements) == 3
    assert statements[2].endswith("VALUES (1, 'a;b');")

    with pytest.raises(script.MigrationError, match="incompleta"):
        script.split_statements("CREATE TABLE t (a INTEGER")


def test_split_statements_keeps_the_triggers_of_migration_001(script):
    statements = script.split_statements(MIGRATION_001.read_text(encoding="utf-8"))
    triggers = [s for s in statements if "CREATE TRIGGER" in s]

    assert len(triggers) == 3
    assert all(s.rstrip().endswith("END;") for s in triggers)


def test_check_state_accepts_untouched_database(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        problems = script.check_state(connection, before, {}, False)
    finally:
        connection.close()

    assert problems == []


def test_check_state_detects_changed_counts_ddl_and_removed_objects(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        connection.execute("DELETE FROM funds")
        connection.execute("ALTER TABLE sources ADD COLUMN note TEXT")
        connection.execute("DROP VIEW current_observations")
        connection.commit()
        problems = script.check_state(connection, before, {}, False)
        allowed = script.check_state(connection, before, {}, True)
    finally:
        connection.close()

    assert "Contagem alterada em funds: 1 para 0." in problems
    assert "DDL alterado: table sources." in problems
    assert "Objeto removido: view current_observations." in problems
    assert allowed == []


def test_check_state_detects_foreign_key_errors(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        connection.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (999, ?)",
            (make_test_cnpj(2),),
        )
        connection.commit()
        problems = script.check_state(connection, before, {}, True)
    finally:
        connection.close()

    assert any("foreign_key_check encontrou" in p for p in problems)
