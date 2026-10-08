from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional


VALIDATION_STATUSES = (
    "valid",
)


class DocumentVersionRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_version(
        self,
        document_id: int,
        file_name: str | None,
        local_file_path: str | None,
        file_format: str | None,
        file_size_bytes: int | None,
        file_hash: str | None,
        source_url: str | None,
        source_version: str | None = None,
        is_current: bool = False,
        validation_status: str = "pending_review",
        downloaded_at: str | None = None,
        error_message: str | None = None,
    ) -> tuple[int, str]:
        if validation_status not in VALIDATION_STATUSES:
            raise ValueError(
                "document_versions aceita somente versões físicas válidas; "
                "registre falhas em collection_attempts"
            )
        normalized_hash = (file_hash or "").strip().lower() or None
        if normalized_hash and not re.fullmatch(r"[0-9a-f]{64}", normalized_hash):
            raise ValueError("file_hash deve ser SHA-256 hexadecimal de 64 caracteres")
        if validation_status == "valid" and not normalized_hash:
            raise ValueError("uma versão válida deve possuir file_hash SHA-256")
        if validation_status == "valid" and (
            not file_name or not local_file_path or not file_format
            or file_size_bytes is None or file_size_bytes == 0
            or not source_url
        ):
            raise ValueError(
                "versão física válida exige nome, caminho, formato, tamanho positivo, "
                "hash e URL de origem"
            )
        if is_current and validation_status != "valid":
            raise ValueError("somente uma versão válida pode ser atual")
        if file_size_bytes is not None and file_size_bytes < 0:
            raise ValueError("file_size_bytes não pode ser negativo")
        if is_current and not normalized_hash:
            raise ValueError("uma versão atual válida deve possuir file_hash")

        if normalized_hash:
            existing = self.connection.execute(
                """SELECT version_id FROM document_versions
                   WHERE document_id = ? AND file_hash = ?""",
                (document_id, normalized_hash),
            ).fetchone()
            if existing:
                return int(existing["version_id"]), "unchanged"

        savepoint = "document_version_create"
        self.connection.execute(f"SAVEPOINT {savepoint}")
        try:
            if is_current:
                self.connection.execute(
                    "UPDATE document_versions SET is_current = 0 WHERE document_id = ?",
                    (document_id,),
                )
            cursor = self.connection.execute(
                """INSERT INTO document_versions (
                    document_id, file_name, local_file_path, file_format,
                    file_size_bytes, file_hash, downloaded_at, source_url,
                    source_version, is_current, validation_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    document_id,
                    file_name,
                    local_file_path,
                    file_format,
                    file_size_bytes,
                    normalized_hash,
                    downloaded_at or (
                        datetime.now(timezone.utc).isoformat()
                        if validation_status == "valid"
                        else None
                    ),
                    source_url,
                    source_version,
                    int(is_current),
                    validation_status,
                    error_message,
                ),
            )
            version_id = int(cursor.lastrowid)
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            return version_id, "inserted"
        except Exception:
            self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise

    def get_current_version(self, document_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            """SELECT * FROM document_versions
               WHERE document_id = ? AND is_current = 1""",
            (document_id,),
        ).fetchone()

    def list_versions(self, document_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """SELECT * FROM document_versions
                   WHERE document_id = ? ORDER BY version_id""",
                (document_id,),
            )
        )

    def find_by_hash(self, file_hash: str) -> list[sqlite3.Row]:
        normalized_hash = (file_hash or "").strip().lower()
        if not normalized_hash:
            return []
        return list(
            self.connection.execute(
                """SELECT * FROM document_versions
                   WHERE file_hash = ? ORDER BY version_id""",
                (normalized_hash,),
            )
        )

    def mark_current(self, version_id: int) -> None:
        row = self.connection.execute(
            """SELECT document_id, validation_status, file_hash
               FROM document_versions WHERE version_id = ?""",
            (version_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Versão documental inexistente: {version_id}")
        if row["validation_status"] != "valid" or not row["file_hash"]:
            raise ValueError("somente versão válida com hash pode ser marcada como atual")
        savepoint = "document_version_mark_current"
        self.connection.execute(f"SAVEPOINT {savepoint}")
        try:
            self.connection.execute(
                "UPDATE document_versions SET is_current = 0 WHERE document_id = ?",
                (row["document_id"],),
            )
            self.connection.execute(
                "UPDATE document_versions SET is_current = 1 WHERE version_id = ?",
                (version_id,),
            )
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise

    def count_versions(self, document_id: int) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM document_versions WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
        )

    def count(self) -> int:
        return int(
            self.connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0]
        )
