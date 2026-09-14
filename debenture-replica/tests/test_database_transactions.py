import pathlib
import sqlite3

import pytest

from debenture_search.database import Database


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def database(tmp_path):
    database_path = tmp_path / "test_debenture.db"
    test_database = Database(database_path)

    migration_sql = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    with test_database.connection() as connection:
        connection.executescript(migration_sql)
        connection.commit()

    return test_database


def test_transaction_commits_valid_data(database):
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO issuers (
                cnpj,
                legal_name
            )
            VALUES (?, ?)
            """,
            (
                "12345678000199",
                "Empresa Teste",
            ),
        )

    issuer = database.fetch_one(
        """
        SELECT cnpj, legal_name
        FROM issuers
        WHERE cnpj = ?
        """,
        ("12345678000199",),
    )

    assert issuer is not None
    assert issuer["cnpj"] == "12345678000199"
    assert issuer["legal_name"] == "Empresa Teste"


def test_transaction_rolls_back_after_error(database):
    with pytest.raises(RuntimeError):
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO issuers (
                    cnpj,
                    legal_name
                )
                VALUES (?, ?)
                """,
                (
                    "98765432000188",
                    "Empresa que deve desaparecer",
                ),
            )

            raise RuntimeError(
                "Falha simulada durante a transacao"
            )

    issuer = database.fetch_one(
        """
        SELECT id
        FROM issuers
        WHERE cnpj = ?
        """,
        ("98765432000188",),
    )

    assert issuer is None


def test_transaction_rolls_back_integrity_error(database):
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO issuers (
                    cnpj,
                    legal_name
                )
                VALUES (?, ?)
                """,
                (
                    "11111111000111",
                    "Empresa Valida",
                ),
            )

            connection.execute(
                """
                INSERT INTO issuers (
                    cnpj,
                    legal_name
                )
                VALUES (?, ?)
                """,
                (
                    "123",
                    "Empresa Invalida",
                ),
            )

    issuer = database.fetch_one(
        """
        SELECT id
        FROM issuers
        WHERE cnpj = ?
        """,
        ("11111111000111",),
    )

    assert issuer is None


def test_data_persists_after_reopening_database(database):
    issuer_id = database.execute(
        """
        INSERT INTO issuers (
            cnpj,
            legal_name
        )
        VALUES (?, ?)
        """,
        (
            "22222222000122",
            "Empresa Persistente",
        ),
    )

    reopened_database = Database(
        database.database_path
    )

    issuer = reopened_database.fetch_one(
        """
        SELECT id, legal_name
        FROM issuers
        WHERE cnpj = ?
        """,
        ("22222222000122",),
    )

    assert issuer is not None
    assert issuer["id"] == issuer_id
    assert issuer["legal_name"] == "Empresa Persistente"


def test_foreign_keys_are_enabled_on_every_connection(
    database,
):
    with database.connection() as connection:
        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

    assert foreign_keys == 1


def test_invalid_foreign_key_is_rejected(database):
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO debentures (
                    issuer_id,
                    asset_code,
                    status
                )
                VALUES (?, ?, ?)
                """,
                (
                    999999,
                    "TEST99",
                    "active",
                ),
            )


def test_duplicate_asset_code_is_rejected(database):
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO debentures (
                asset_code,
                status
            )
            VALUES (?, ?)
            """,
            (
                "DUPL12",
                "active",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO debentures (
                    asset_code,
                    status
                )
                VALUES (?, ?)
                """,
                (
                    "DUPL12",
                    "active",
                ),
            )

    records = database.fetch_all(
        """
        SELECT id
        FROM debentures
        WHERE asset_code = ?
        """,
        ("DUPL12",),
    )

    assert len(records) == 1


def test_database_integrity_remains_valid(database):
    assert database.integrity_check() == "ok"
    assert database.foreign_key_check() == []