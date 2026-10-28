"""Fixtures dos testes do modulo de Fundos.

Todo banco e sintetico, criado em tmp_path a partir da migration 001. Nenhum
teste abre banco real nem acessa a rede.
"""

from pathlib import Path

import pytest

from fundos.database import Database


MODULE_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = MODULE_DIR / "migrations"
MIGRATION_001 = MIGRATIONS_DIR / "001_initial_schema.sql"


def create_schema(path):
    """Cria um banco novo com a migration 001 e devolve o Database."""

    db = Database(path)
    connection = db.connect(create=True)

    try:
        connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
    finally:
        connection.close()

    return db


@pytest.fixture
def db(tmp_path):
    return create_schema(tmp_path / "fundos.db")


@pytest.fixture
def connection(db):
    connection = db.connect()

    try:
        yield connection
    finally:
        connection.close()
