"""Execucao de migracoes da camada compartilhada."""

from datetime import UTC, datetime
from sqlite3 import Connection

from .connection import SQLiteConnectionManager
from .migrations import v001_initial_schema


MIGRATIONS = (
    v001_initial_schema,
)


class MigrationRunner:
    """Aplica migracoes SQLite ainda nao executadas."""

    def __init__(
        self,
        connection_manager: SQLiteConnectionManager,
    ) -> None:
        if not isinstance(
            connection_manager,
            SQLiteConnectionManager,
        ):
            raise TypeError(
                "connection_manager deve ser SQLiteConnectionManager."
            )

        self._connection_manager = connection_manager

    def apply_all(self) -> tuple[int, ...]:
        """Aplica todas as migracoes pendentes."""

        applied_versions: list[int] = []

        with self._connection_manager.transaction() as connection:
            self._create_migration_table(connection)

            registered_versions = self._registered_versions(
                connection
            )

            for migration in MIGRATIONS:
                if migration.VERSION in registered_versions:
                    continue

                for statement in migration.STATEMENTS:
                    connection.execute(statement)

                connection.execute(
                    """
                    INSERT INTO schema_migrations (
                        version,
                        name,
                        applied_at
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        migration.VERSION,
                        migration.NAME,
                        datetime.now(UTC).isoformat(),
                    ),
                )

                applied_versions.append(migration.VERSION)

        return tuple(applied_versions)

    def current_version(self) -> int:
        """Retorna a maior versao aplicada."""

        with self._connection_manager.read_connection() as connection:
            self._create_migration_table(connection)

            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS version
                FROM schema_migrations
                """
            ).fetchone()

        return int(row["version"])

    @staticmethod
    def _create_migration_table(
        connection: Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _registered_versions(
        connection: Connection,
    ) -> set[int]:
        rows = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            """
        ).fetchall()

        return {
            int(row["version"])
            for row in rows
        }
