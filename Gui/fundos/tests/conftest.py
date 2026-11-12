"""Fixtures dos testes do modulo de Fundos.

Todo banco e sintetico, criado em tmp_path. db e connection aplicam so a
migration 001 (os testes da 001 isolada dependem disso); full_db e
full_connection aplicam todas as migrations, em ordem. Nenhum teste abre
banco real nem acessa a rede.
"""

from pathlib import Path

import pytest

from fundos.database import Database


MODULE_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = MODULE_DIR / "migrations"
MIGRATION_001 = MIGRATIONS_DIR / "001_initial_schema.sql"


def create_schema(path, migrations=(MIGRATION_001,)):
    """Cria um banco novo com as migrations informadas e devolve o Database."""

    db = Database(path)
    connection = db.connect(create=True)

    try:
        for migration in migrations:
            connection.executescript(migration.read_text(encoding="utf-8"))
    finally:
        connection.close()

    return db


def all_migrations():
    """As migrations NNN_nome.sql do modulo, em ordem."""

    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def create_full_schema(path):
    """Cria um banco novo com todas as migrations."""

    return create_schema(path, all_migrations())


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


@pytest.fixture
def full_db(tmp_path):
    return create_full_schema(tmp_path / "fundos.db")


@pytest.fixture
def full_connection(full_db):
    connection = full_db.connect()

    try:
        yield connection
    finally:
        connection.close()
