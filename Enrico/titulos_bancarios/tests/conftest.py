"""Fixtures dos testes do modulo de Titulos bancarios.

Todo banco e sintetico, criado em tmp_path, com so a migration 001 aplicada.
"""

import pytest

from apoio import apply_migration
from apoio import open_connection


@pytest.fixture
def connection(tmp_path):
    connection = open_connection(tmp_path / "titulos_bancarios.db")
    apply_migration(connection)

    try:
        yield connection
    finally:
        connection.close()
