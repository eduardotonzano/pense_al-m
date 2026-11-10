import hashlib
import importlib.util
import pathlib
import shutil
import sqlite3

import pytest

from debenture_search.database import Database


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
MIGRATIONS_DIR = PROJECT_DIR / "migrations"


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


def create_database(directory, name="debenture.db"):
    """Cria um banco na versao 1, com uma debenture."""

    path = directory / name
    db = Database(path)

    with db.connection() as connection:
        connection.executescript(
            (MIGRATIONS_DIR / "001_initial_schema.sql").read_text(
                encoding="utf-8"
            )
        )
        connection.execute(
            "INSERT INTO debentures (asset_code) VALUES ('APLY12')"
        )
        connection.commit()

    return path


def copy_migrations(directory, name, sql):
    """Copia a 001 e acrescenta uma 002 com o conteudo informado."""

    target = directory / "migrations"
    target.mkdir()
    shutil.copy(MIGRATIONS_DIR / "001_initial_schema.sql", target)
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
        for row in query(
            path,
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        )
    }


def versions(path):
    return [
        row[0]
        for row in query(
            path,
            "SELECT version FROM schema_migrations ORDER BY version",
        )
    ]


def backups_in(directory):
    return sorted(pathlib.Path(directory).glob("debenture_*.sqlite3"))


def test_dry_run_leaves_database_untouched(script, tmp_path, capsys):
    path = create_database(tmp_path)
    before = file_hash(path)

    code = script.main(["--database", str(path), "--dry-run"])
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(path) == before
    assert "debenture_events" not in table_names(path)
    assert "002_debenture_events" in output
    assert "Dry-run concluido" in output
    assert "objetos novos: index idx_debenture_events_lookup" in output
    assert not (tmp_path / "backups").exists()


def test_commit_creates_backup_before_applying(script, tmp_path, capsys):
    path = create_database(tmp_path)
    backup_dir = tmp_path / "saved"

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--backup-dir",
            str(backup_dir),
        ]
    )
    output = capsys.readouterr().out
    backups = backups_in(backup_dir)

    assert code == 0
    assert len(backups) == 1
    assert versions(path) == [1, 2, 3]
    assert "debenture_events" in table_names(path)
    # O backup e o banco como estava antes da migration.
    assert versions(backups[0]) == [1]
    assert "debenture_events" not in table_names(backups[0])
    assert backups[0].name in output
    assert "Migrations aplicadas com sucesso." in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output

    db = Database(path)
    assert db.integrity_check() == "ok"
    assert db.foreign_key_check() == []


def test_commit_keeps_existing_rows(script, tmp_path):
    path = create_database(tmp_path)

    script.main(["--database", str(path), "--commit"])

    assert query(path, "SELECT asset_code FROM debentures") == [
        ("APLY12",)
    ]
    assert query(path, "SELECT COUNT(*) FROM debenture_events") == [(0,)]


def test_backup_failure_stops_before_any_change(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("arquivo", encoding="utf-8")
    before = file_hash(path)

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--backup-dir",
            str(blocker),
        ]
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "Nao foi possivel criar o backup" in error
    assert "o banco nao foi alterado" in error
    assert file_hash(path) == before
    assert versions(path) == [1]


def test_second_commit_has_nothing_to_apply(script, tmp_path, capsys):
    path = create_database(tmp_path)
    backup_dir = tmp_path / "saved"
    arguments = [
        "--database",
        str(path),
        "--commit",
        "--backup-dir",
        str(backup_dir),
    ]

    first = script.main(arguments)
    capsys.readouterr()
    second = script.main(arguments)
    output = capsys.readouterr().out

    assert first == 0
    assert second == 0
    assert "Nada a aplicar" in output
    assert len(backups_in(backup_dir)) == 1
    assert versions(path) == [1, 2, 3]


def test_missing_database_is_refused(script, tmp_path, capsys):
    path = tmp_path / "missing.db"

    for mode in ("--dry-run", "--commit"):
        code = script.main(["--database", str(path), mode])
        error = capsys.readouterr().err

        assert code == 1
        assert "Banco nao encontrado" in error
        assert not path.exists()


def test_create_builds_a_new_database(script, tmp_path, capsys):
    path = tmp_path / "new" / "debenture.db"

    code = script.main(["--database", str(path), "--create", "--commit"])
    output = capsys.readouterr().out

    assert code == 0
    assert versions(path) == [1, 2, 3]
    assert "Banco novo" in output
    assert not (path.parent / "backups").exists()
    assert Database(path).integrity_check() == "ok"


def test_failed_create_leaves_no_file(script, tmp_path, capsys):
    path = tmp_path / "new" / "debenture.db"
    migrations = copy_migrations(
        tmp_path,
        "broken",
        "INSERT INTO missing_table VALUES (1);\n",
    )

    code = script.main(
        [
            "--database",
            str(path),
            "--create",
            "--commit",
            "--migrations-dir",
            str(migrations),
        ]
    )
    capsys.readouterr()

    assert code == 1
    assert not path.exists()


def test_create_requires_commit(script, tmp_path):
    with pytest.raises(SystemExit) as error:
        script.main(
            [
                "--database",
                str(tmp_path / "x.db"),
                "--create",
                "--dry-run",
            ]
        )

    assert error.value.code == 2


def test_mode_and_database_are_required(script, tmp_path):
    with pytest.raises(SystemExit) as no_mode:
        script.main(["--database", str(tmp_path / "x.db")])

    with pytest.raises(SystemExit) as no_database:
        script.main(["--dry-run"])

    with pytest.raises(SystemExit) as both_modes:
        script.main(
            [
                "--database",
                str(tmp_path / "x.db"),
                "--dry-run",
                "--commit",
            ]
        )

    assert no_mode.value.code == 2
    assert no_database.value.code == 2
    assert both_modes.value.code == 2


def test_failing_migration_rolls_back_and_keeps_backup(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    migrations = copy_migrations(
        tmp_path,
        "broken",
        "CREATE TABLE half_done (id INTEGER);\n"
        "INSERT INTO schema_migrations(version,name) "
        "VALUES(2,'broken');\n"
        "INSERT INTO missing_table VALUES (1);\n",
    )
    backup_dir = tmp_path / "saved"

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
            "--backup-dir",
            str(backup_dir),
        ]
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "missing_table" in error
    assert "Backup:" in error
    assert "half_done" not in table_names(path)
    assert versions(path) == [1]
    assert len(backups_in(backup_dir)) == 1
    assert Database(path).integrity_check() == "ok"


def test_migration_that_does_not_register_its_version_is_rolled_back(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    migrations = copy_migrations(
        tmp_path,
        "no_version",
        "CREATE TABLE no_version (id INTEGER);\n",
    )

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
        ]
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "nao registrou a versao" in error
    assert "no_version" not in table_names(path)
    assert versions(path) == [1]


def test_migration_registering_another_name_is_rolled_back(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    migrations = copy_migrations(
        tmp_path,
        "right_name",
        "CREATE TABLE named (id INTEGER);\n"
        "INSERT INTO schema_migrations(version,name) "
        "VALUES(2,'other_name');\n",
    )

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
        ]
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "registrou outro nome" in error
    assert "named" not in table_names(path)


ALTER_SQL = (
    "ALTER TABLE issuers ADD COLUMN note TEXT;\n"
    "INSERT INTO schema_migrations(version,name) "
    "VALUES(2,'add_note');\n"
)


def test_changes_to_existing_objects_are_refused_by_default(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "add_note", ALTER_SQL)

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
        ]
    )
    error = capsys.readouterr().err
    columns = [row[1] for row in query(path, "PRAGMA table_info(issuers)")]

    assert code == 1
    assert "DDL alterado: table issuers" in error
    assert "note" not in columns
    assert versions(path) == [1]


def test_changes_to_existing_objects_can_be_allowed(script, tmp_path):
    path = create_database(tmp_path)
    migrations = copy_migrations(tmp_path, "add_note", ALTER_SQL)

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
            "--allow-existing-changes",
        ]
    )
    columns = [row[1] for row in query(path, "PRAGMA table_info(issuers)")]

    assert code == 0
    assert "note" in columns
    assert versions(path) == [1, 2]


def test_deleting_existing_rows_is_refused_by_default(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    migrations = copy_migrations(
        tmp_path,
        "wipe",
        "DELETE FROM debentures;\n"
        "INSERT INTO schema_migrations(version,name) VALUES(2,'wipe');\n",
    )

    code = script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
        ]
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "Contagem alterada em debentures" in error
    assert query(path, "SELECT COUNT(*) FROM debentures") == [(1,)]


def test_file_that_is_not_a_database_is_refused(script, tmp_path, capsys):
    path = tmp_path / "garbage.db"
    path.write_bytes(b"isto nao e um banco sqlite" * 10)
    before = file_hash(path)

    code = script.main(["--database", str(path), "--commit"])
    capsys.readouterr()

    assert code == 1
    assert file_hash(path) == before
    assert not (tmp_path / "backups").exists()


def test_reports_package_from_this_checkout(script, tmp_path, capsys):
    path = create_database(tmp_path)

    script.main(["--database", str(path), "--dry-run"])
    output = capsys.readouterr().out
    expected = (PROJECT_DIR / "src" / "debenture_search").resolve()

    assert "Pacote debenture_search: " + str(expected) in output


def test_discover_migrations_orders_and_ignores_other_files(
    script,
    tmp_path,
):
    for name in (
        "010_ten.sql",
        "002_two.sql",
        "readme.sql",
        "003_Bad.sql",
        "004-bad.sql",
    ):
        (tmp_path / name).write_text("", encoding="utf-8")

    found = script.discover_migrations(tmp_path)

    assert [(version, name) for version, name, _ in found] == [
        (2, "two"),
        (10, "ten"),
    ]


def test_discover_migrations_rejects_duplicate_numbers(script, tmp_path):
    (tmp_path / "002_a.sql").write_text("", encoding="utf-8")
    (tmp_path / "002_b.sql").write_text("", encoding="utf-8")

    with pytest.raises(script.MigrationError, match="mesmo numero"):
        script.discover_migrations(tmp_path)


def test_discover_migrations_rejects_missing_folder(script, tmp_path):
    with pytest.raises(script.MigrationError, match="nao encontrada"):
        script.discover_migrations(tmp_path / "nope")


def test_real_migrations_are_numbered_and_named_like_the_registry(script):
    found = script.discover_migrations(MIGRATIONS_DIR)

    assert [(version, name) for version, name, _ in found][:2] == [
        (1, "initial_schema"),
        (2, "debenture_events"),
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
    assert statements[0] == "PRAGMA foreign_keys = ON;"
    assert statements[2].endswith("VALUES (1, 'a;b');")


def test_split_statements_rejects_incomplete_script(script):
    with pytest.raises(script.MigrationError, match="incompleta"):
        script.split_statements("CREATE TABLE t (a INTEGER")


def test_check_state_accepts_untouched_database(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        problems = script.check_state(connection, before, {}, False)
    finally:
        connection.close()

    assert problems == []


def test_check_state_detects_changed_counts(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        connection.execute("DELETE FROM debentures")
        connection.commit()
        problems = script.check_state(connection, before, {}, False)
        allowed = script.check_state(connection, before, {}, True)
    finally:
        connection.close()

    assert any("Contagem alterada em debentures" in p for p in problems)
    assert allowed == []


def test_check_state_detects_changed_ddl(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        connection.execute("ALTER TABLE issuers ADD COLUMN note TEXT")
        connection.commit()
        problems = script.check_state(connection, before, {}, False)
    finally:
        connection.close()

    assert "DDL alterado: table issuers." in problems


def test_check_state_detects_removed_objects(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        connection.execute("DROP VIEW current_observations")
        connection.commit()
        problems = script.check_state(connection, before, {}, False)
    finally:
        connection.close()

    assert "Objeto removido: view current_observations." in problems


def test_check_state_detects_foreign_key_errors(script, tmp_path):
    path = create_database(tmp_path)
    connection = sqlite3.connect(path)

    try:
        before = script.snapshot(connection)
        connection.execute(
            """
            INSERT INTO observations (
                debenture_id, source_id, field_name, value_type,
                value_text, observed_at, checksum
            ) VALUES (999, 1, 'rating', 'text', 'AA', '2026-09-10', ?)
            """,
            ("a" * 64,),
        )
        connection.commit()
        problems = script.check_state(connection, before, {}, True)
    finally:
        connection.close()

    assert any("foreign_key_check encontrou" in p for p in problems)


# Marcas para recriar tabela (o SQLite nao altera CHECK).

FOREIGN_KEYS_OFF = "-- apply_migration: foreign_keys=off\n"
RECRIA_ISSUERS = "-- apply_migration: recria=issuers\n"


def rebuild_issuers(copy_filter="", index=True):
    """Recria issuers como no roteiro do SQLite (cria, copia, apaga, renomeia)."""

    return (
        "CREATE TABLE issuers_new (\n"
        " id INTEGER PRIMARY KEY AUTOINCREMENT, cnpj TEXT UNIQUE,\n"
        " legal_name TEXT NOT NULL, trade_name TEXT,\n"
        " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
        " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP\n"
        ");\n"
        "INSERT INTO issuers_new SELECT * FROM issuers" + copy_filter + ";\n"
        "DROP TABLE issuers;\n"
        "ALTER TABLE issuers_new RENAME TO issuers;\n"
        + (
            "CREATE INDEX idx_issuers_legal_name ON issuers(legal_name);\n"
            if index
            else ""
        )
    )


def register(name):
    return (
        "INSERT INTO schema_migrations(version,name) "
        "VALUES(2,'" + name + "');\n"
    )


def create_database_with_issuers(directory):
    """Banco na versao 1 com duas emissoras ficticias; so a 1 tem filha."""

    path = create_database(directory)

    with Database(path).connection() as connection:
        connection.execute(
            "INSERT INTO issuers (cnpj, legal_name) "
            "VALUES ('99999991999904', 'Emissora Ficticia Um')"
        )
        connection.execute(
            "INSERT INTO issuers (cnpj, legal_name) "
            "VALUES ('99999992999940', 'Emissora Ficticia Dois')"
        )
        connection.execute(
            "INSERT INTO debentures (issuer_id, asset_code) "
            "VALUES (1, 'FILHA12')"
        )
        connection.commit()

    return path


def issuers_ddl(path):
    return query(
        path,
        "SELECT sql FROM sqlite_master WHERE name = 'issuers'",
    )


def commit_with(script, path, migrations, *extra):
    return script.main(
        [
            "--database",
            str(path),
            "--commit",
            "--migrations-dir",
            str(migrations),
            *extra,
        ]
    )


def test_read_marks(script):
    sql = (
        FOREIGN_KEYS_OFF
        + RECRIA_ISSUERS
        + "  -- apply_migration: recria=debentures  \n"
        + "-- comentario comum\n"
        + "SELECT 1;\n"
    )

    assert script.read_marks("SELECT 1;\n") == (False, frozenset())
    assert script.read_marks(sql) == (
        True,
        frozenset({"issuers", "debentures"}),
    )


@pytest.mark.parametrize(
    "value",
    [
        "foreign_keys=on",
        "foreign_keys = off",
        "foreign_key=off",
        "recria=",
        "recria=Issuers",
        "recria=issuers; DROP TABLE debentures",
        "",
    ],
)
def test_read_marks_rejects_unknown_mark(script, value):
    with pytest.raises(script.MigrationError, match="Marca desconhecida"):
        script.read_marks("-- apply_migration: " + value + "\nSELECT 1;\n")


def test_unknown_mark_stops_before_any_change(script, tmp_path, capsys):
    path = create_database(tmp_path)
    before = file_hash(path)
    migrations = copy_migrations(
        tmp_path,
        "typo",
        "-- apply_migration: foreign_key=off\n" + register("typo"),
    )
    backup_dir = tmp_path / "saved"

    for mode in ("--dry-run", "--commit"):
        code = script.main(
            [
                "--database",
                str(path),
                mode,
                "--migrations-dir",
                str(migrations),
                "--backup-dir",
                str(backup_dir),
            ]
        )
        error = capsys.readouterr().err

        assert code == 1
        assert "002_typo: Marca desconhecida: foreign_key=off" in error

    assert file_hash(path) == before
    assert not backup_dir.exists()
    assert versions(path) == [1]


def test_marked_rebuild_keeps_rows_and_children(script, tmp_path, capsys):
    path = create_database_with_issuers(tmp_path)
    issuers_before = query(path, "SELECT * FROM issuers ORDER BY id")
    debentures_before = query(path, "SELECT * FROM debentures ORDER BY id")
    migrations = copy_migrations(
        tmp_path,
        "rebuild",
        FOREIGN_KEYS_OFF + RECRIA_ISSUERS + rebuild_issuers()
        + register("rebuild"),
    )

    code = commit_with(script, path, migrations)
    output = capsys.readouterr().out

    assert code == 0
    assert "Chaves estrangeiras desligadas durante a transacao" in output
    assert "Tabelas recriadas: issuers" in output
    assert versions(path) == [1, 2]
    assert query(path, "SELECT * FROM issuers ORDER BY id") == (
        issuers_before
    )
    assert query(path, "SELECT * FROM debentures ORDER BY id") == (
        debentures_before
    )

    db = Database(path)
    assert db.integrity_check() == "ok"
    assert db.foreign_key_check() == []


def test_rebuild_without_foreign_keys_mark_is_rolled_back(
    script,
    tmp_path,
    capsys,
):
    # Sem a marca nada muda: as chaves ficam ligadas, como na 001 e na 002.
    path = create_database_with_issuers(tmp_path)
    ddl_before = issuers_ddl(path)
    migrations = copy_migrations(
        tmp_path,
        "rebuild",
        RECRIA_ISSUERS + rebuild_issuers() + register("rebuild"),
    )

    code = commit_with(script, path, migrations)
    error = capsys.readouterr().err

    assert code == 1
    assert "FOREIGN KEY constraint failed" in error
    assert issuers_ddl(path) == ddl_before
    assert "issuers_new" not in table_names(path)
    assert versions(path) == [1]


@pytest.mark.parametrize("allow", [False, True])
def test_orphan_left_by_marked_migration_is_rolled_back(
    script,
    tmp_path,
    capsys,
    allow,
):
    path = create_database_with_issuers(tmp_path)
    migrations = copy_migrations(
        tmp_path,
        "orphan",
        FOREIGN_KEYS_OFF
        + "DELETE FROM issuers WHERE id = 1;\n"
        + register("orphan"),
    )
    extra = ["--allow-existing-changes"] if allow else []

    code = commit_with(script, path, migrations, *extra)
    error = capsys.readouterr().err

    assert code == 1
    assert "foreign_key_check encontrou 1 problema(s)" in error
    assert query(path, "SELECT id FROM issuers ORDER BY id") == [(1,), (2,)]
    assert versions(path) == [1]


@pytest.mark.parametrize("broken", [False, True])
def test_foreign_keys_are_back_on_after_marked_migration(
    script,
    tmp_path,
    broken,
):
    path = create_database(tmp_path)
    body = (
        "CREATE TABLE half_done (id INTEGER);\n"
        "INSERT INTO missing_table VALUES (1);\n"
        if broken
        else "CREATE TABLE done (id INTEGER);\n" + register("marked")
    )
    migrations = copy_migrations(tmp_path, "marked", FOREIGN_KEYS_OFF + body)
    pending = script.discover_migrations(migrations)[1:]
    connection = script.open_connection(path)

    try:
        before = script.snapshot(connection)

        if broken:
            with pytest.raises(sqlite3.OperationalError, match="missing"):
                script.apply_in_transaction(
                    connection, before, pending, False
                )
        else:
            script.apply_in_transaction(connection, before, pending, False)

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        in_transaction = connection.in_transaction
    finally:
        connection.close()

    assert foreign_keys == 1
    assert not in_transaction
    assert "half_done" not in table_names(path)
    assert versions(path) == ([1] if broken else [1, 2])


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        (
            rebuild_issuers()
            + "ALTER TABLE debentures ADD COLUMN note TEXT;\n",
            "DDL alterado: table debentures.",
        ),
        (
            rebuild_issuers(index=False),
            "Objeto removido: index idx_issuers_legal_name.",
        ),
        (
            rebuild_issuers(copy_filter=" WHERE id <> 2"),
            "Contagem alterada em issuers: 2 para 1.",
        ),
    ],
    ids=["outra-tabela", "indice-esquecido", "linha-perdida"],
)
def test_recria_mark_only_frees_the_ddl_of_that_table(
    script,
    tmp_path,
    capsys,
    body,
    problem,
):
    path = create_database_with_issuers(tmp_path)
    ddl_before = issuers_ddl(path)
    migrations = copy_migrations(
        tmp_path,
        "rebuild",
        FOREIGN_KEYS_OFF + RECRIA_ISSUERS + body + register("rebuild"),
    )

    code = commit_with(script, path, migrations)
    error = capsys.readouterr().err

    assert code == 1
    assert problem in error
    assert "DDL alterado: table issuers" not in error
    assert issuers_ddl(path) == ddl_before
    assert query(path, "SELECT COUNT(*) FROM issuers") == [(2,)]
    assert versions(path) == [1]


def test_foreign_keys_mark_without_recria_needs_the_allow_flag(
    script,
    tmp_path,
    capsys,
):
    refused_path = create_database_with_issuers(tmp_path / "refused")
    allowed_path = create_database_with_issuers(tmp_path / "allowed")
    migrations = copy_migrations(
        tmp_path,
        "rebuild",
        FOREIGN_KEYS_OFF + rebuild_issuers() + register("rebuild"),
    )

    refused = commit_with(script, refused_path, migrations)
    error = capsys.readouterr().err
    allowed = commit_with(
        script,
        allowed_path,
        migrations,
        "--allow-existing-changes",
    )

    assert refused == 1
    assert "DDL alterado: table issuers." in error
    assert versions(refused_path) == [1]
    assert allowed == 0
    assert versions(allowed_path) == [1, 2]
