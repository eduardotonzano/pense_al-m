from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    MIGRATIONS_DIR,
    apply_pending,
    pending_migrations,
    read_applied_versions,
)


def _existing_database_with_001(tmp_path: Path):
    """Banco existente na situação atual: só a 001 aplicada."""

    only_001 = tmp_path / "m"
    only_001.mkdir()
    (only_001 / "001_document_catalog.sql").write_text(
        (MIGRATIONS_DIR / "001_document_catalog.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    connection = connect(tmp_path / "cri_cra.db")
    initialize_database(connection, migrations_dir=only_001)
    connection.execute(
        """INSERT INTO assets (codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
               emissao, serie, created_at, updated_at)
           VALUES ('CRA02500C1D', 'CRA', 'Eco', '1', '426', '1', 'now', 'now')"""
    )
    connection.commit()
    return connection


def test_002_creates_asset_series_and_is_idempotent(tmp_path):
    connection = _existing_database_with_001(tmp_path)
    assert [m.version for m in pending_migrations(connection, MIGRATIONS_DIR)] == [2]

    apply_pending(connection, pending_migrations(connection, MIGRATIONS_DIR))
    assert read_applied_versions(connection)[2] == "asset_series"
    assert apply_pending(connection, pending_migrations(connection, MIGRATIONS_DIR)) == []
    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    insert = """INSERT INTO asset_series (asset_id, numero_serie, isin, evidence_json)
                VALUES (1, ?, 'BRECOACRALJ8', '{}')"""
    connection.execute(insert, (1,))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, (1,))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO asset_series (asset_id, numero_serie, evidence_json, review_status)
               VALUES (1, 2, '{}', 'approved')"""
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO asset_series (asset_id, numero_serie, evidence_json) VALUES (99, 3, '{}')"
        )


def test_new_database_receives_002(tmp_path):
    connection = connect(tmp_path / "new.db")
    initialize_database(connection)
    assert 2 in read_applied_versions(connection)
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'asset_series'"
    ).fetchone()
