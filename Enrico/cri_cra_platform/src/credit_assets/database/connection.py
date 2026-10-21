from __future__ import annotations

import sqlite3
from pathlib import Path

from credit_assets.database.migrations import (
    apply_pending,
    pending_migrations,
)


def connect(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(
    connection: sqlite3.Connection,
    migrations_dir: str | Path | None = None,
) -> None:
    # Banco novo (sem tabelas) nao tem dados a proteger: recebe tambem as
    # migrations numeradas. Banco existente so as recebe por
    # scripts/apply_migration.py, que faz backup e verifica antes de confirmar.
    is_new = connection.execute(
        """SELECT COUNT(*) FROM sqlite_master
           WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"""
    ).fetchone()[0] == 0
    schema_path = Path(__file__).with_name("schema.sql")
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    # Older catalogs enforced a global unique hash on documents. Physical hashes
    # belong to document_versions and may legitimately be shared by documents.
    connection.execute("DROP INDEX IF EXISTS uq_documents_file_hash_nonempty")
    connection.execute(
        """CREATE INDEX IF NOT EXISTS ix_documents_file_hash
           ON documents(file_hash)
           WHERE file_hash IS NOT NULL AND file_hash <> ''"""
    )
    version_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(document_versions)")
    }
    if "error_message" not in version_columns:
        connection.execute(
            "ALTER TABLE document_versions ADD COLUMN error_message TEXT"
        )
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(assets)")
    }
    if "isin" not in columns:
        connection.execute("ALTER TABLE assets ADD COLUMN isin TEXT")
    attempt_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(collection_attempts)")
    }
    additive_attempt_columns = {
        "document_id": "INTEGER REFERENCES documents(document_pk)",
        "attempt_number": "INTEGER",
        "response_content_type": "TEXT",
        "final_url": "TEXT",
    }
    for column_name, column_type in additive_attempt_columns.items():
        if column_name not in attempt_columns:
            connection.execute(
                f"ALTER TABLE collection_attempts ADD COLUMN {column_name} {column_type}"
            )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS ix_collection_attempts_document_id
           ON collection_attempts(document_id)"""
    )
    connection.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_isin_normalized_nonempty
           ON assets(UPPER(REPLACE(TRIM(isin), ' ', '')))
           WHERE isin IS NOT NULL AND TRIM(isin) <> ''"""
    )
    connection.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_codigo_cetip_normalized_nonempty
           ON assets(UPPER(REPLACE(TRIM(codigo_cetip), ' ', '')))
           WHERE codigo_cetip IS NOT NULL AND TRIM(codigo_cetip) <> ''"""
    )
    connection.commit()
    if is_new:
        apply_pending(
            connection,
            pending_migrations(connection, migrations_dir),
        )
