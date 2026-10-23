from __future__ import annotations

import importlib.util
import shutil
import sqlite3
from pathlib import Path

from credit_assets.database.backup import file_sha256
from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import apply_pending, pending_migrations


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
MIGRATIONS_DIR = PROJECT_DIR / "migrations"


def load_module():
    specification = importlib.util.spec_from_file_location(
        "apply_migration_script_002",
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
        ) VALUES ('24G2100031', 'BRRBRACRIP13', 'CRI', 'Opea', '', '301', '1',
                  'now', 'now')"""
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


def tables(path: Path) -> set[str]:
    return {
        row[0]
        for row in query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def test_dry_run_applies_001_and_002_on_a_copy_and_leaves_the_database_alone(
    tmp_path, capsys
):
    path = create_baseline_database(tmp_path)
    before = file_sha256(path)

    code = load_module().main(["--database", str(path), "--dry-run"])
    output = capsys.readouterr().out

    assert code == 0
    assert file_sha256(path) == before
    assert "asset_cnpj_observations" not in tables(path)
    assert "001_document_catalog" in output
    assert "002_asset_cnpj_observations" in output
    assert "asset_cnpj_observations" in output.split("tabelas novas:")[1].splitlines()[0]
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output


def test_commit_creates_the_observation_table_and_keeps_every_existing_row(
    tmp_path, capsys
):
    path = create_baseline_database(tmp_path)
    saved = tmp_path / "saved"

    code = load_module().main(
        ["--database", str(path), "--commit", "--backup-dir", str(saved)]
    )
    output = capsys.readouterr().out
    backups = sorted(saved.glob("*.sqlite3"))

    assert code == 0
    assert len(backups) == 1
    assert "asset_cnpj_observations" in tables(path)
    assert "asset_cnpj_observations" not in tables(backups[0])
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == [(1,), (2,)]
    assert query(path, "SELECT codigo_cetip, cnpj_securitizadora FROM assets") == [
        ("24G2100031", "")
    ]
    assert query(path, "SELECT COUNT(*) FROM asset_cnpj_observations") == [(0,)]
    assert query(path, "SELECT COUNT(*) FROM asset_cnpj_provenance") == [(0,)]
    assert file_sha256(backups[0]) in output


def test_database_already_at_001_receives_only_002(tmp_path, capsys):
    path = create_baseline_database(tmp_path)
    only_001 = tmp_path / "only_001"
    only_001.mkdir()
    shutil.copy(MIGRATIONS_DIR / "001_document_catalog.sql", only_001)
    connection = connect(path)
    apply_pending(connection, pending_migrations(connection, only_001))
    connection.close()
    assert query(path, "SELECT version FROM schema_migrations") == [(1,)]

    code = load_module().main(
        ["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "saved")]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Migrations pendentes: 002_asset_cnpj_observations" in output
    assert "001_document_catalog" not in output.split("Migrations pendentes:")[1].splitlines()[0]
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == [(1,), (2,)]
    assert "asset_cnpj_observations" in tables(path)


def test_second_commit_has_nothing_to_apply(tmp_path, capsys):
    path = create_baseline_database(tmp_path)
    module = load_module()
    arguments = ["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "saved")]
    module.main(arguments)
    capsys.readouterr()

    code = module.main(arguments)

    assert code == 0
    assert "Nada a aplicar" in capsys.readouterr().out
