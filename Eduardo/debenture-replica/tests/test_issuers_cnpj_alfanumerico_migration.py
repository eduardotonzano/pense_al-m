"""Migration 003: o CHECK de issuers.cnpj aceita o CNPJ alfanumerico.

So dados ficticios: CNPJs numericos de raiz 9999999n9999 e o alfanumerico
ZZZZZZZ1ZZZZ04, com DV valido (mesma convencao do ADR-011). Nenhum CNPJ
real. Todos os bancos ficam em tmp_path.
"""

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
MIGRATION_PATHS = (
    MIGRATIONS_DIR / "001_initial_schema.sql",
    MIGRATIONS_DIR / "002_debenture_events.sql",
)
MIGRATION_003 = MIGRATIONS_DIR / "003_issuers_cnpj_alfanumerico.sql"

CNPJ_1 = "99999991999904"
CNPJ_2 = "99999992999940"
CNPJ_3 = "99999993999995"
CNPJ_4 = "99999994999930"
CNPJ_ALFA = "ZZZZZZZ1ZZZZ04"

OLD_CHECK = (
    "CHECK(cnpj IS NULL OR (length(cnpj)=14"
    " AND cnpj NOT GLOB '*[^0-9]*'))"
)
NEW_CHECK = (
    "CHECK(cnpj IS NULL OR (length(cnpj)=14"
    " AND substr(cnpj,1,12) NOT GLOB '*[^0-9A-Z]*'"
    " AND substr(cnpj,13,2) NOT GLOB '*[^0-9]*'))"
)

RENAME = "ALTER TABLE issuers_new RENAME TO issuers;\n"


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


def create_database(directory, migration_paths=MIGRATION_PATHS):
    """Banco com emissoras e debentures ficticias (versao 2 por padrao).

    A emissora 4 e apagada para o seq (4) ficar maior que o maior id (3).
    """

    path = directory / "debenture.db"

    with Database(path).connection() as connection:
        for migration in migration_paths:
            connection.executescript(migration.read_text(encoding="utf-8"))

        connection.executemany(
            """
            INSERT INTO issuers (
                cnpj, legal_name, trade_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    CNPJ_1,
                    "Emissora Ficticia Um",
                    None,
                    "2026-01-02 10:00:00",
                    "2026-03-04 11:00:00",
                ),
                (
                    None,
                    "Emissora Ficticia Sem CNPJ",
                    "Ficticia",
                    "2026-01-03 10:00:00",
                    "2026-01-03 10:00:00",
                ),
                (
                    CNPJ_2,
                    "Emissora Ficticia Dois",
                    "Dois",
                    "2026-01-04 10:00:00",
                    "2026-02-05 09:30:00",
                ),
                (
                    CNPJ_3,
                    "Emissora Ficticia Apagada",
                    None,
                    "2026-01-05 10:00:00",
                    "2026-01-05 10:00:00",
                ),
            ],
        )
        connection.execute("DELETE FROM issuers WHERE id = 4")
        connection.executemany(
            "INSERT INTO debentures (issuer_id, asset_code) VALUES (?, ?)",
            [(1, "FICT11"), (3, "FICT12"), (None, "FICT13")],
        )
        connection.commit()

    return path


def query(path, sql, parameters=()):
    connection = sqlite3.connect(path)

    try:
        return connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()


def versions(path):
    return [
        row[0]
        for row in query(
            path,
            "SELECT version FROM schema_migrations ORDER BY version",
        )
    ]


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def issuers_ddl(path):
    return query(
        path,
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'issuers'",
    )[0][0]


def other_objects(path):
    """DDL de todos os objetos, menos a tabela issuers."""

    return {
        (kind, name): sql
        for kind, name, sql in query(
            path,
            "SELECT type, name, sql FROM sqlite_master",
        )
        if (kind, name) != ("table", "issuers")
    }


def sequence(path):
    return query(
        path,
        "SELECT seq FROM sqlite_sequence WHERE name = 'issuers'",
    )


def issuer_rows(path):
    return query(path, "SELECT * FROM issuers ORDER BY id")


def debenture_rows(path):
    return query(path, "SELECT * FROM debentures ORDER BY id")


def insert_issuer(path, cnpj, legal_name="Emissora Ficticia Nova"):
    """Insere pela conexao do projeto (chaves estrangeiras ligadas)."""

    with Database(path).connection() as connection:
        cursor = connection.execute(
            "INSERT INTO issuers (cnpj, legal_name) VALUES (?, ?)",
            (cnpj, legal_name),
        )
        connection.commit()

    return cursor.lastrowid


def run_script(script, path, mode="--commit", *extra):
    return script.main(
        [
            "--database",
            str(path),
            mode,
            "--backup-dir",
            str(path.parent / "saved"),
            *extra,
        ]
    )


def copy_with_failure_after_rename(directory):
    """Copia as migrations reais; a 003 falha logo depois do RENAME."""

    target = directory / "migrations"
    target.mkdir()

    for migration in MIGRATION_PATHS:
        shutil.copy(migration, target)

    sql = MIGRATION_003.read_text(encoding="utf-8")
    assert sql.count(RENAME) == 1
    (target / MIGRATION_003.name).write_text(
        sql.replace(RENAME, RENAME + "INSERT INTO missing_table VALUES (1);\n"),
        encoding="utf-8",
    )

    return target


@pytest.fixture
def migrated(script, tmp_path, capsys):
    """Banco na versao 2 com linhas e filhas, ja migrado para a 3."""

    path = create_database(tmp_path)
    before = {
        "ddl": issuers_ddl(path),
        "others": other_objects(path),
        "issuers": issuer_rows(path),
        "debentures": debenture_rows(path),
        "sequence": sequence(path),
        "table_info": query(path, "PRAGMA table_info(issuers)"),
        "foreign_keys": query(path, "PRAGMA foreign_key_list(debentures)"),
    }

    code = run_script(script, path)
    output = capsys.readouterr().out

    assert code == 0

    return path, before, output


def test_version_2_database_refuses_alphanumeric(tmp_path):
    path = create_database(tmp_path)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_issuer(path, CNPJ_ALFA)


def test_commit_applies_003_and_registers_version_3(migrated):
    path, _, output = migrated

    assert versions(path) == [1, 2, 3]
    assert query(
        path,
        "SELECT name FROM schema_migrations WHERE version = 3",
    ) == [("issuers_cnpj_alfanumerico",)]
    assert "003_issuers_cnpj_alfanumerico" in output
    assert "Chaves estrangeiras desligadas durante a transacao" in output
    assert "Tabelas recriadas: issuers" in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output
    assert "Migrations aplicadas com sucesso." in output


def test_issuer_rows_and_ids_are_preserved(migrated):
    path, before, _ = migrated

    assert issuer_rows(path) == before["issuers"]
    assert [row[0] for row in issuer_rows(path)] == [1, 2, 3]


def test_children_and_foreign_key_are_preserved(migrated):
    path, before, _ = migrated
    db = Database(path)

    assert debenture_rows(path) == before["debentures"]
    assert query(path, "PRAGMA foreign_key_list(debentures)") == (
        before["foreign_keys"]
    )
    assert db.foreign_key_check() == []
    assert db.integrity_check() == "ok"


def test_foreign_key_actions_still_work(migrated):
    path, _, _ = migrated

    with Database(path).connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute("DELETE FROM issuers WHERE id = 1")

        connection.rollback()
        connection.execute("UPDATE issuers SET id = 30 WHERE id = 3")
        connection.commit()

    assert query(
        path,
        "SELECT issuer_id FROM debentures WHERE asset_code = 'FICT12'",
    ) == [(30,)]


def test_autoincrement_sequence_is_preserved(migrated):
    path, before, _ = migrated

    assert before["sequence"] == [(4,)]
    assert sequence(path) == [(4,)]
    # O id 4 era da emissora apagada e nao volta a ser usado.
    assert insert_issuer(path, CNPJ_4) == 5


def test_schema_is_the_same_except_the_cnpj_check(migrated):
    path, before, _ = migrated

    def flat(sql):
        return " ".join(sql.split())

    expected = (
        flat(before["ddl"])
        .replace("CREATE TABLE issuers (", 'CREATE TABLE "issuers" (')
        .replace(OLD_CHECK, NEW_CHECK)
    )

    assert OLD_CHECK in flat(before["ddl"])
    assert flat(issuers_ddl(path)) == expected
    assert query(path, "PRAGMA table_info(issuers)") == before["table_info"]
    assert other_objects(path) == before["others"]

    indexes = sorted(
        row[1:] for row in query(path, "PRAGMA index_list(issuers)")
    )

    assert indexes == [
        ("idx_issuers_legal_name", 0, "c", 0),
        ("sqlite_autoindex_issuers_1", 1, "u", 0),
    ]
    assert [
        row[2]
        for row in query(path, "PRAGMA index_info(sqlite_autoindex_issuers_1)")
    ] == ["cnpj"]
    assert [
        row[2] for row in query(path, "PRAGMA index_info(idx_issuers_legal_name)")
    ] == ["legal_name"]


def test_accepts_numeric_alphanumeric_and_null(migrated):
    path, _, _ = migrated

    for cnpj in (CNPJ_4, CNPJ_ALFA, None):
        insert_issuer(path, cnpj)

    assert query(
        path,
        "SELECT cnpj FROM issuers WHERE id > 3 ORDER BY id",
    ) == [(CNPJ_4,), (CNPJ_ALFA,), (None,)]


@pytest.mark.parametrize(
    "cnpj",
    [
        "zzzzzzz1zzzz04",
        "ZZZZZZZ1ZZZZ0",
        "ZZZZZZZ1ZZZZ045",
        "ZZZZZZZ1ZZZZ0A",
        "ZZZZZZZ1ZZZZA4",
        "ZZZZZZZ1ZZZ*04",
        "ZZZZZZZ1ZZZ-04",
        "ZZZZZZZ1ZZZ 04",
        "ZZZZZZZ1ZZZ" + chr(0xC9) + "04",
        "99.999.991/9999-04",
        "",
    ],
    ids=[
        "minuscula",
        "tamanho-13",
        "tamanho-15",
        "letra-no-ultimo",
        "letra-no-penultimo",
        "asterisco",
        "hifen",
        "espaco",
        "nao-ascii",
        "mascara",
        "vazio",
    ],
)
def test_rejects_invalid_cnpj(migrated, cnpj):
    path, before, _ = migrated

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_issuer(path, cnpj)

    assert issuer_rows(path) == before["issuers"]


def test_unique_and_legal_name_checks_still_apply(migrated):
    path, _, _ = migrated

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_issuer(path, CNPJ_1)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_issuer(path, CNPJ_ALFA, legal_name="   ")


def test_second_run_has_nothing_to_apply(script, migrated, capsys):
    path, _, _ = migrated
    before = file_hash(path)

    code = run_script(script, path)
    output = capsys.readouterr().out

    assert code == 0
    assert "Nada a aplicar" in output
    assert file_hash(path) == before
    assert len(list((path.parent / "saved").glob("*.sqlite3"))) == 1
    assert versions(path) == [1, 2, 3]


def test_failure_in_the_middle_rolls_back_everything(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    ddl_before = issuers_ddl(path)
    issuers_before = issuer_rows(path)
    debentures_before = debenture_rows(path)
    migrations = copy_with_failure_after_rename(tmp_path)

    code = run_script(
        script,
        path,
        "--commit",
        "--migrations-dir",
        str(migrations),
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "missing_table" in error
    assert "Backup:" in error
    assert issuers_ddl(path) == ddl_before
    assert issuer_rows(path) == issuers_before
    assert debenture_rows(path) == debentures_before
    assert sequence(path) == [(4,)]
    assert "issuers_new" not in {
        row[0] for row in query(path, "SELECT name FROM sqlite_master")
    }
    assert versions(path) == [1, 2]
    assert Database(path).foreign_key_check() == []


def test_failure_in_the_middle_leaves_foreign_keys_on(script, tmp_path):
    path = create_database(tmp_path)
    ddl_before = issuers_ddl(path)
    migrations = copy_with_failure_after_rename(tmp_path)
    pending = [
        migration
        for migration in script.discover_migrations(migrations)
        if migration[0] == 3
    ]
    connection = script.open_connection(path)

    try:
        before = script.snapshot(connection)

        with pytest.raises(sqlite3.OperationalError, match="missing_table"):
            script.apply_in_transaction(connection, before, pending, False)

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        in_transaction = connection.in_transaction
    finally:
        connection.close()

    assert foreign_keys == 1
    assert not in_transaction
    assert issuers_ddl(path) == ddl_before
    assert versions(path) == [1, 2]


def create_database_with_orphan(directory):
    path = create_database(directory)
    # Orfao gravado com as chaves desligadas (padrao do sqlite3.connect).
    connection = sqlite3.connect(path)

    try:
        connection.execute(
            "INSERT INTO debentures (issuer_id, asset_code) "
            "VALUES (99, 'ORFA11')"
        )
        connection.commit()
    finally:
        connection.close()

    return path


def test_existing_orphan_is_refused_before_the_backup(
    script,
    tmp_path,
    capsys,
):
    path = create_database_with_orphan(tmp_path)
    before = file_hash(path)

    code = run_script(script, path)
    error = capsys.readouterr().err

    assert code == 1
    assert "erros de chave estrangeira" in error
    assert file_hash(path) == before
    assert not (tmp_path / "saved").exists()


def test_foreign_key_check_before_commit_rolls_003_back(script, tmp_path):
    # Sem passar pelo backup: o foreign_key_check da transacao desfaz tudo.
    path = create_database_with_orphan(tmp_path)
    ddl_before = issuers_ddl(path)
    issuers_before = issuer_rows(path)
    pending = [
        migration
        for migration in script.discover_migrations(MIGRATIONS_DIR)
        if migration[0] == 3
    ]
    connection = script.open_connection(path)

    try:
        before = script.snapshot(connection)

        with pytest.raises(
            script.MigrationError,
            match="foreign_key_check encontrou 1 problema",
        ):
            script.apply_in_transaction(connection, before, pending, False)

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
    finally:
        connection.close()

    assert foreign_keys == 1
    assert issuers_ddl(path) == ddl_before
    assert issuer_rows(path) == issuers_before
    assert versions(path) == [1, 2]


def test_dry_run_does_not_write_to_the_given_database(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path)
    before = file_hash(path)

    code = run_script(script, path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert "Dry-run concluido" in output
    assert "Tabelas recriadas: issuers" in output
    assert "foreign_key_check: 0 problema(s)" in output
    assert file_hash(path) == before
    assert versions(path) == [1, 2]
    assert not (tmp_path / "saved").exists()
    assert not (tmp_path / "backups").exists()

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_issuer(path, CNPJ_ALFA)


def test_version_1_database_applies_002_and_003_together(
    script,
    tmp_path,
    capsys,
):
    path = create_database(tmp_path, MIGRATION_PATHS[:1])
    issuers_before = issuer_rows(path)
    debentures_before = debenture_rows(path)

    code = run_script(script, path)
    output = capsys.readouterr().out

    assert code == 0
    assert "002_debenture_events, 003_issuers_cnpj_alfanumerico" in output
    assert versions(path) == [1, 2, 3]
    assert issuer_rows(path) == issuers_before
    assert debenture_rows(path) == debentures_before
    assert query(path, "SELECT COUNT(*) FROM debenture_events") == [(0,)]
    assert Database(path).foreign_key_check() == []
    assert insert_issuer(path, CNPJ_ALFA) == 5


def test_new_database_accepts_alphanumeric(script, tmp_path, capsys):
    path = tmp_path / "new" / "debenture.db"

    code = script.main(["--database", str(path), "--create", "--commit"])
    capsys.readouterr()

    assert code == 0
    assert versions(path) == [1, 2, 3]
    assert insert_issuer(path, CNPJ_ALFA) == 1


def test_003_is_discovered_with_its_marks(script):
    found = script.discover_migrations(MIGRATIONS_DIR)
    sql = MIGRATION_003.read_text(encoding="utf-8")

    assert (3, "issuers_cnpj_alfanumerico", MIGRATION_003) in found
    assert script.read_marks(sql) == (True, frozenset({"issuers"}))
    # ASCII e sem BOM, como a 001 e a 002.
    MIGRATION_003.read_bytes().decode("ascii")
