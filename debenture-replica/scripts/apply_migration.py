import pathlib
import sqlite3
import sys


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_DIR / "data" / "debenture.db"
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


def configure_database(
    connection: sqlite3.Connection,
) -> None:
    """Configura segurança e integridade da conexão SQLite."""

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA busy_timeout = 5000")


def apply_migration() -> None:
    """Aplica a migration inicial e valida o banco."""

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not MIGRATION_PATH.exists():
        raise FileNotFoundError(
            f"Migration não encontrada: {MIGRATION_PATH}"
        )

    migration_sql = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        configure_database(connection)

        journal_mode = connection.execute(
            "PRAGMA journal_mode = WAL"
        ).fetchone()[0]

        connection.executescript(migration_sql)
        connection.commit()

        integrity_result = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        views = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'view'
            ORDER BY name
            """
        ).fetchall()

        sources = connection.execute(
            """
            SELECT
                code,
                priority,
                active
            FROM sources
            ORDER BY priority
            """
        ).fetchall()

        migrations = connection.execute(
            """
            SELECT
                version,
                name,
                applied_at
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

        print("Migration aplicada com sucesso.")
        print(f"Banco: {DATABASE_PATH}")
        print(f"Journal mode: {journal_mode}")
        print(f"Integrity check: {integrity_result}")
        print(
            "Foreign key errors:",
            foreign_key_errors,
        )
        print(
            "Tabelas:",
            [row[0] for row in tables],
        )
        print(
            "Views:",
            [row[0] for row in views],
        )
        print("Fontes:", sources)
        print("Migrations:", migrations)

        if integrity_result != "ok":
            raise RuntimeError(
                "Falha na integridade do banco: "
                f"{integrity_result}"
            )

        if foreign_key_errors:
            raise RuntimeError(
                "Foram encontradas falhas nas "
                "chaves estrangeiras: "
                f"{foreign_key_errors}"
            )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    try:
        apply_migration()

    except Exception as error:
        print(
            f"Erro ao aplicar migration: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1)