"""Testes da fundacao de persistencia SQLite."""

import sqlite3

import pytest

from pense_alm.shared.persistence import (
    MigrationRunner,
    SQLiteConnectionManager,
)


EXPECTED_TABLES = {
    "data_provenance",
    "entities",
    "entity_identifiers",
    "entity_relationships",
    "schema_migrations",
    "sqlite_sequence",
}

EXPECTED_INDEXES = {
    "idx_entities_legal_name",
    "idx_entities_type",
    "idx_identifiers_entity",
    "idx_relationships_source",
    "idx_relationships_target",
    "idx_relationships_type",
}


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "shared_entity_test.sqlite3"


@pytest.fixture
def connection_manager(database_path):
    return SQLiteConnectionManager(database_path)


@pytest.fixture
def migrated_database(connection_manager):
    runner = MigrationRunner(connection_manager)
    runner.apply_all()

    return connection_manager


def test_connection_manager_creates_parent_directory(
    tmp_path,
):
    database_path = (
        tmp_path
        / "nested"
        / "database"
        / "shared.sqlite3"
    )

    manager = SQLiteConnectionManager(database_path)

    with manager.read_connection() as connection:
        connection.execute("SELECT 1").fetchone()

    assert database_path.exists()
    assert database_path.parent.exists()


def test_connection_uses_row_factory(
    connection_manager,
):
    with connection_manager.read_connection() as connection:
        row = connection.execute(
            "SELECT 10 AS value"
        ).fetchone()

    assert row["value"] == 10


def test_foreign_keys_are_enabled(
    connection_manager,
):
    with connection_manager.read_connection() as connection:
        result = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

    assert result == 1


def test_transaction_commits_successful_changes(
    connection_manager,
):
    with connection_manager.transaction() as connection:
        connection.execute(
            """
            CREATE TABLE transaction_test (
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO transaction_test (value)
            VALUES (?)
            """,
            ("committed",),
        )

    with connection_manager.read_connection() as connection:
        value = connection.execute(
            """
            SELECT value
            FROM transaction_test
            """
        ).fetchone()["value"]

    assert value == "committed"


def test_transaction_rolls_back_failed_changes(
    connection_manager,
):
    with connection_manager.transaction() as connection:
        connection.execute(
            """
            CREATE TABLE rollback_test (
                value TEXT NOT NULL
            )
            """
        )

    with pytest.raises(RuntimeError):
        with connection_manager.transaction() as connection:
            connection.execute(
                """
                INSERT INTO rollback_test (value)
                VALUES (?)
                """,
                ("must_rollback",),
            )

            raise RuntimeError("failure for rollback test")

    with connection_manager.read_connection() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM rollback_test
            """
        ).fetchone()["total"]

    assert count == 0


def test_first_migration_application_returns_version(
    connection_manager,
):
    runner = MigrationRunner(connection_manager)

    applied = runner.apply_all()

    assert applied == (1,)
    assert runner.current_version() == 1


def test_migrations_are_idempotent(
    connection_manager,
):
    runner = MigrationRunner(connection_manager)

    first = runner.apply_all()
    second = runner.apply_all()

    assert first == (1,)
    assert second == ()
    assert runner.current_version() == 1


def test_initial_schema_contains_expected_tables(
    migrated_database,
):
    with migrated_database.read_connection() as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = ?
            ORDER BY name
            """,
            ("table",),
        ).fetchall()

    tables = {row["name"] for row in rows}

    assert EXPECTED_TABLES.issubset(tables)


def test_initial_schema_contains_expected_indexes(
    migrated_database,
):
    with migrated_database.read_connection() as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = ?
              AND name NOT LIKE ?
            ORDER BY name
            """,
            (
                "index",
                "sqlite_autoindex%",
            ),
        ).fetchall()

    indexes = {row["name"] for row in rows}

    assert EXPECTED_INDEXES == indexes


def test_database_integrity_is_valid(
    migrated_database,
):
    with migrated_database.read_connection() as connection:
        result = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

    assert result == "ok"


def test_database_has_no_foreign_key_errors(
    migrated_database,
):
    with migrated_database.read_connection() as connection:
        errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    assert errors == []


def test_duplicate_migration_version_is_recorded_once(
    connection_manager,
):
    runner = MigrationRunner(connection_manager)

    runner.apply_all()
    runner.apply_all()

    with connection_manager.read_connection() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM schema_migrations
            WHERE version = ?
            """,
            (1,),
        ).fetchone()["total"]

    assert count == 1


def test_sqlite_schema_rejects_self_relationship(
    migrated_database,
):
    entity_id = "entity-1"
    provenance_id = "provenance-1"

    with migrated_database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO data_provenance (
                provenance_id,
                source_type,
                source_name,
                collected_at,
                validation_status,
                confidence_score
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                provenance_id,
                "manual",
                "Teste",
                "2026-09-21T12:00:00+00:00",
                "valid",
                100,
            ),
        )

        connection.execute(
            """
            INSERT INTO entities (
                entity_id,
                legal_name,
                entity_type,
                status,
                country_code,
                provenance_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                "Empresa Exemplo",
                "company",
                "active",
                "BR",
                provenance_id,
                "2026-09-21T12:00:00+00:00",
                "2026-09-21T12:00:00+00:00",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with migrated_database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO entity_relationships (
                    relationship_id,
                    source_entity_id,
                    target_entity_id,
                    relationship_type,
                    canonical_key,
                    provenance_id,
                    status,
                    confidence_score,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "relationship-1",
                    entity_id,
                    entity_id,
                    "controls",
                    "entity-1:controls:entity-1",
                    provenance_id,
                    "active",
                    100,
                    "2026-09-21T12:00:00+00:00",
                ),
            )
