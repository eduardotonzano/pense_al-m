from __future__ import annotations

import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest

from credit_assets.database.backup import file_sha256
from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    apply_pending,
    discover_migrations,
    pending_migrations,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
MIGRATIONS_DIR = PROJECT_DIR / "migrations"
CNPJ_MIGRATION = "004_asset_cnpj_observations"


def label(migration) -> str:
    return format(migration.version, "03d") + "_" + migration.name


def all_versions() -> list[tuple[int]]:
    """Versoes da pasta, calculadas: a lista nao depende de quantas existem."""

    return [(item.version,) for item in discover_migrations(MIGRATIONS_DIR)]


def load_module():
    specification = importlib.util.spec_from_file_location(
        "apply_migration_script_004",
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


def test_dry_run_applies_every_migration_on_a_copy_and_leaves_the_database_alone(
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
    assert CNPJ_MIGRATION in output
    assert all(label(item) in output for item in discover_migrations(MIGRATIONS_DIR))
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
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == all_versions()
    assert query(path, "SELECT version, name FROM schema_migrations WHERE version = 4") == [
        (4, "asset_cnpj_observations")
    ]
    assert query(path, "SELECT codigo_cetip, cnpj_securitizadora FROM assets") == [
        ("24G2100031", "")
    ]
    assert query(path, "SELECT COUNT(*) FROM asset_cnpj_observations") == [(0,)]
    assert query(path, "SELECT COUNT(*) FROM asset_cnpj_provenance") == [(0,)]
    assert file_sha256(backups[0]) in output


def test_database_already_at_001_receives_only_the_pending_ones_including_004(
    tmp_path, capsys
):
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

    pending_line = output.split("Migrations pendentes: ")[1].splitlines()[0]
    expected = [label(item) for item in discover_migrations(MIGRATIONS_DIR) if item.version > 1]

    assert code == 0
    assert pending_line.split(", ") == expected
    assert CNPJ_MIGRATION in expected
    assert "001_document_catalog" not in pending_line
    assert query(path, "SELECT version FROM schema_migrations ORDER BY version") == all_versions()
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


def insert_observation_with_cnpj(tmp_path: Path, cnpj: str) -> None:
    """Grava uma observacao valida em tudo, menos talvez no CNPJ (CHECK da 004)."""

    connection = connect(tmp_path / "check.db")
    initialize_database(connection)
    asset_id = connection.execute(
        """INSERT INTO assets (
            codigo_cetip, isin, tipo_ativo, securitizadora, cnpj_securitizadora,
            emissao, serie, created_at, updated_at
        ) VALUES ('24G2100031', 'BRRBRACRIP13', 'CRI', 'Opea', '', '301', '1',
                  'now', 'now')"""
    ).lastrowid
    connection.execute(
        "INSERT INTO executions (run_id, started_at, status) "
        "VALUES ('run-1', '2026-10-23T00:00:00+00:00', 'success')"
    )

    try:
        connection.execute(
            """INSERT INTO asset_cnpj_observations (
                asset_id, field, cnpj, decision, source_id, matched_by,
                reference_first, reference_last, filings, evidence_json,
                observed_at, run_id, checksum
            ) VALUES (?, 'cnpj_securitizadora', ?, 'applied', 'cvm_inf_mensal_cri',
                      'isin', '2025-01-01', '2026-08-01', 20, '{}',
                      '2026-10-23T12:00:00+00:00', 'run-1', ?)""",
            (asset_id, cnpj, "0" * 64),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize(
    "cnpj",
    [
        "02773542000122",  # numerico (Opea)
        "12ABC34501DE35",  # alfanumerico, exemplo da Receita
        "ZZZZZZZ1ZZZZ04",  # alfanumerico ficticio
    ],
)
def test_cnpj_check_accepts_numeric_and_alphanumeric_canonical_cnpj(tmp_path, cnpj):
    insert_observation_with_cnpj(tmp_path, cnpj)

    assert query(tmp_path / "check.db", "SELECT cnpj FROM asset_cnpj_observations") == [
        (cnpj,)
    ]


@pytest.mark.parametrize(
    "cnpj",
    [
        "12abc34501de35",  # tudo minusculo: GLOB diferencia maiusculas
        "12ABC34501De35",  # uma minuscula
        "12ABC34501DE3",  # 13 caracteres
        "12ABC34501DE355",  # 15 caracteres
        "12ABC34501DE3A",  # letra no ultimo caractere (DV)
        "12ABC34501DEA5",  # letra no penultimo caractere (DV)
        "12ABC3450.DE35",  # mascara: ponto no lugar de um caractere
        "12ABC 34501D35",  # espaco
        "\uff112ABC34501DE35",  # digito de largura total
        "12\u0131BC34501DE35",  # i sem ponto
        "12\u00c1BC34501DE35",  # letra acentuada
        "",
    ],
)
def test_cnpj_check_refuses_lowercase_wrong_length_letter_in_check_digit_and_other_characters(
    tmp_path, cnpj
):
    with pytest.raises(sqlite3.IntegrityError):
        insert_observation_with_cnpj(tmp_path, cnpj)
