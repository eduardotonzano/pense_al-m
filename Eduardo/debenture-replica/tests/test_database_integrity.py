import pathlib
import sqlite3

import pytest


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")

    connection.execute("PRAGMA foreign_keys = ON")

    migration_sql = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    connection.executescript(migration_sql)

    yield connection

    connection.close()


def test_migration_was_registered(database):
    migration = database.execute(
        """
        SELECT version, name
        FROM schema_migrations
        WHERE version = 1
        """
    ).fetchone()

    assert migration == (1, "initial_schema")


def test_initial_sources_were_created(database):
    sources = database.execute(
        """
        SELECT code
        FROM sources
        ORDER BY priority
        """
    ).fetchall()

    assert sources == [
        ("SND",),
        ("CVM",),
        ("ANBIMA_API",),
        ("MANUAL",),
    ]


def test_rejects_invalid_cnpj(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO issuers (
                cnpj,
                legal_name
            )
            VALUES (?, ?)
            """,
            (
                "123",
                "Empresa com CNPJ invalido",
            ),
        )


def test_rejects_duplicate_cnpj(database):
    database.execute(
        """
        INSERT INTO issuers (
            cnpj,
            legal_name
        )
        VALUES (?, ?)
        """,
        (
            "12345678000199",
            "Empresa A",
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO issuers (
                cnpj,
                legal_name
            )
            VALUES (?, ?)
            """,
            (
                "12345678000199",
                "Empresa B",
            ),
        )


def test_rejects_lowercase_asset_code(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO debentures (
                asset_code,
                status
            )
            VALUES (?, ?)
            """,
            (
                "body12",
                "active",
            ),
        )


def test_rejects_duplicate_asset_code(database):
    database.execute(
        """
        INSERT INTO debentures (
            asset_code,
            status
        )
        VALUES (?, ?)
        """,
        (
            "BODY12",
            "active",
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO debentures (
                asset_code,
                status
            )
            VALUES (?, ?)
            """,
            (
                "BODY12",
                "active",
            ),
        )


def test_rejects_invalid_isin(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO debentures (
                isin,
                status
            )
            VALUES (?, ?)
            """,
            (
                "INVALIDO",
                "active",
            ),
        )


def test_rejects_debenture_without_identifier(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO debentures (
                status
            )
            VALUES (?)
            """,
            ("active",),
        )


def test_rejects_invalid_foreign_key(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
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
                "TEST12",
                "active",
            ),
        )


def test_rejects_invalid_status(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO debentures (
                asset_code,
                status
            )
            VALUES (?, ?)
            """,
            (
                "TEST13",
                "qualquer_status",
            ),
        )


def test_rejects_invalid_observation_value(database):
    database.execute(
        """
        INSERT INTO debentures (
            asset_code,
            status
        )
        VALUES (?, ?)
        """,
        (
            "TEST14",
            "active",
        ),
    )

    debenture_id = database.execute(
        """
        SELECT id
        FROM debentures
        WHERE asset_code = ?
        """,
        ("TEST14",),
    ).fetchone()[0]

    source_id = database.execute(
        """
        SELECT id
        FROM sources
        WHERE code = ?
        """,
        ("SND",),
    ).fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO observations (
                debenture_id,
                source_id,
                field_name,
                value_type,
                value_text,
                value_numeric,
                observed_at,
                checksum
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debenture_id,
                source_id,
                "rating",
                "text",
                "AA",
                100,
                "2026-09-10T12:00:00Z",
                "a" * 64,
            ),
        )
