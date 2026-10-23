from __future__ import annotations

import importlib.util
import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from credit_assets.database.backup import file_sha256
from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    apply_pending,
    discover_migrations,
    pending_migrations,
    split_statements,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
MIGRATIONS_DIR = PROJECT_DIR / "migrations"
MIGRATION_FILE = MIGRATIONS_DIR / "003_informe_indicators_ratings.sql"
NEW_OBJECTS = {"informe_indicators", "ratings", "ratings_verified"}


def load_module():
    specification = importlib.util.spec_from_file_location(
        "apply_migration_script_003",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def create_baseline_database(tmp_path: Path) -> Path:
    """Banco existente na linha de base (sem nenhuma migration), com um ativo."""

    empty = tmp_path / "empty_migrations"
    empty.mkdir()
    path = tmp_path / "cri_cra.db"
    connection = connect(path)
    initialize_database(connection, migrations_dir=empty)
    connection.execute(
        """INSERT INTO assets (
            codigo_cetip, isin, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('CRA-TESTE-1', 'BR0000000019', 'CRA', 'S', '', '1', '1', 'now', 'now')"""
    )
    connection.commit()
    connection.close()
    return path


def query(path: Path, sql: str):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(sql).fetchall()


def objects(path: Path) -> set[str]:
    return {
        row[0]
        for row in query(path, "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
    }


def test_the_migration_file_splits_into_complete_statements_with_their_triggers():
    statements = split_statements(MIGRATION_FILE.read_text(encoding="utf-8"))

    def starting_with(prefix: str) -> list[str]:
        return [item for item in statements if re.search(rf"^{prefix}", item, re.MULTILINE)]

    assert len(statements) == 11
    assert len(starting_with("CREATE TABLE")) == 2
    assert len(starting_with("CREATE INDEX")) == 4
    assert len(starting_with("CREATE TRIGGER")) == 4
    assert len(starting_with("CREATE VIEW")) == 1
    assert all(item.rstrip().endswith("END;") for item in starting_with("CREATE TRIGGER"))
    assert all("RAISE(ABORT" in item for item in starting_with("CREATE TRIGGER"))


def test_dry_run_applies_001_to_003_on_a_copy_and_leaves_the_database_alone(tmp_path, capsys):
    path = create_baseline_database(tmp_path)
    before = file_sha256(path)

    code = load_module().main(["--database", str(path), "--dry-run"])
    output = capsys.readouterr().out

    assert code == 0
    assert file_sha256(path) == before
    assert not (NEW_OBJECTS & objects(path))
    assert "003_informe_indicators_ratings" in output
    assert "informe_indicators" in output.split("tabelas novas:")[1].splitlines()[0]
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output


def test_commit_creates_the_tables_and_the_view_and_keeps_every_existing_row(tmp_path, capsys):
    path = create_baseline_database(tmp_path)
    saved = tmp_path / "saved"

    code = load_module().main(["--database", str(path), "--commit", "--backup-dir", str(saved)])
    output = capsys.readouterr().out
    backups = sorted(saved.glob("*.sqlite3"))

    assert code == 0
    assert len(backups) == 1
    assert NEW_OBJECTS <= objects(path)
    assert not (NEW_OBJECTS & objects(backups[0]))
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == [
        (item.version,) for item in discover_migrations()
    ]
    assert query(path, "SELECT codigo_cetip FROM assets") == [("CRA-TESTE-1",)]
    assert query(path, "SELECT COUNT(*) FROM informe_indicators") == [(0,)]
    assert query(path, "SELECT COUNT(*) FROM ratings") == [(0,)]
    assert query(path, "SELECT COUNT(*) FROM ratings_verified") == [(0,)]
    assert file_sha256(backups[0]) in output


def test_database_already_at_002_receives_003_and_the_later_ones_but_not_002(tmp_path, capsys):
    path = create_baseline_database(tmp_path)
    up_to_002 = tmp_path / "up_to_002"
    up_to_002.mkdir()

    for name in ("001_document_catalog.sql", "002_asset_cnpj_observations.sql"):
        shutil.copy(MIGRATIONS_DIR / name, up_to_002)

    connection = connect(path)
    apply_pending(connection, pending_migrations(connection, up_to_002))
    connection.close()
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == [(1,), (2,)]

    code = load_module().main(
        ["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "saved")]
    )
    output = capsys.readouterr().out

    pending_line = output.split("Migrations pendentes:")[1].splitlines()[0]
    assert code == 0
    assert pending_line.strip().startswith("003_informe_indicators_ratings")
    assert "002_asset_cnpj_observations" not in pending_line
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == [
        (item.version,) for item in discover_migrations()
    ]
    assert NEW_OBJECTS <= objects(path)


def test_second_commit_has_nothing_to_apply(tmp_path, capsys):
    path = create_baseline_database(tmp_path)
    module = load_module()
    arguments = ["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "saved")]
    module.main(arguments)
    capsys.readouterr()

    code = module.main(arguments)

    assert code == 0
    assert "Nada a aplicar" in capsys.readouterr().out
