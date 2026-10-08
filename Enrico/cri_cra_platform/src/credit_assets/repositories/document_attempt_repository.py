from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class DocumentAttemptRepository:
    """Stores operational document downloads in the existing collection_attempts table."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_attempt(
        self,
        *,
        run_id: str,
        asset_id: int,
        document_id: int,
        source: str,
        started_at: str,
        finished_at: str,
        status: str,
        http_status: int | None,
        error_message: str | None,
        response_content_type: str | None,
        final_url: str | None,
    ) -> tuple[int, int]:
        attempt_number = int(
            self.connection.execute(
                """SELECT COALESCE(MAX(attempt_number), 0) + 1
                   FROM collection_attempts WHERE document_id = ?""",
                (document_id,),
            ).fetchone()[0]
        )
        cursor = self.connection.execute(
            """INSERT INTO collection_attempts (
                run_id, asset_id, document_id, source, started_at,
                finished_at, status, http_status, error_message,
                attempt_number, response_content_type, final_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                asset_id,
                document_id,
                source,
                started_at,
                finished_at,
                status,
                http_status,
                error_message,
                attempt_number,
                response_content_type,
                final_url,
            ),
        )
        return int(cursor.lastrowid), attempt_number

    def list_by_document_id(self, document_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """SELECT * FROM collection_attempts
                   WHERE document_id = ?
                   ORDER BY attempt_number, attempt_id""",
                (document_id,),
            )
        )

    def count_by_document_id(self, document_id: int) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM collection_attempts WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
        )
