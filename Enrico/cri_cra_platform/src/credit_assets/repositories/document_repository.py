from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from credit_assets.models.document import DOCUMENT_CATEGORIES, Document

# Colunas da migration 001 (campos oficiais da grade). Bancos sem ela
# seguem no caminho antigo de gravacao.
CATALOG_COLUMNS = (
    "source_category",
    "source_type",
    "source_species",
    "grid_version",
    "source_description",
    "source_row_json",
)


class DocumentRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self._catalog_columns: Optional[bool] = None

    def _has_catalog_columns(self) -> bool:
        if self._catalog_columns is None:
            columns = {
                row[1]
                for row in self.connection.execute("PRAGMA table_info(documents)")
            }
            self._catalog_columns = {*CATALOG_COLUMNS, "first_seen_at"} <= columns
        return self._catalog_columns

    @staticmethod
    def _catalog_download_status(existing, document: Document) -> str:
        """Mantem o estado do download; so reabre se a versao na grade mudou."""
        status = existing["download_status"] or document.download_status or "pending"
        incoming_version = (document.grid_version or "").strip()
        stored_version = (existing["grid_version"] or "").strip()
        if incoming_version and stored_version and incoming_version != stored_version:
            return "pending"
        return status

    def upsert(self, document: Document) -> int:
        document_pk, _ = self.upsert_with_status(document)
        return document_pk

    def upsert_with_status(self, document: Document) -> tuple[int, str]:
        if document.category not in DOCUMENT_CATEGORIES:
            raise ValueError(f"Categoria de documento inválida: {document.category}")
        if not document.source or not document.source_url:
            raise ValueError("source e source_url são obrigatórios")
        run_id = self._value(document.run_id)
        if not run_id:
            raise ValueError("run_id é obrigatório para persistir um documento")
        execution = self.connection.execute(
            "SELECT 1 FROM executions WHERE run_id = ?", (run_id,)
        ).fetchone()
        if execution is None:
            raise ValueError(f"run_id não corresponde a uma execução registrada: {run_id}")

        file_hash = self._value(document.file_hash)
        source_document_id = self._value(document.source_document_id) or ""
        existing = None
        if file_hash:
            existing = self.connection.execute(
                "SELECT * FROM documents WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()
        if existing is None:
            existing = self.connection.execute(
                """SELECT * FROM documents
                   WHERE source_document_id = ? AND source = ?""",
                (source_document_id, document.source),
            ).fetchone()

        now = document.collected_at or datetime.now(timezone.utc).isoformat()
        has_catalog = self._has_catalog_columns()
        catalog = (
            {column: self._value(getattr(document, column)) for column in CATALOG_COLUMNS}
            if has_catalog
            else {}
        )
        values = (
            source_document_id,
            document.asset_id,
            document.category,
            document.document_name,
            document.reference_date,
            document.publication_date,
            document.source,
            document.source_url,
            document.download_status,
            file_hash,
            now,
            run_id,
        )
        if existing is None:
            columns = [
                "source_document_id", "asset_id", "category", "document_name",
                "reference_date", "publication_date", "source", "source_url",
                "download_status", "file_hash", "collected_at", "run_id",
            ]
            parameters = list(values)
            if has_catalog:
                columns += [*CATALOG_COLUMNS, "first_seen_at"]
                parameters += [*(catalog[column] for column in CATALOG_COLUMNS), now]
            cursor = self.connection.execute(
                f"INSERT INTO documents ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' for _ in columns)})",
                parameters,
            )
            document_pk = int(cursor.lastrowid)
            status = "inserted"
        elif document.financial_statements_evidence and document.category == "Outro":
            status = (
                "updated"
                if existing["category"] != document.category
                else "unchanged"
            )
            if status == "updated":
                self.connection.execute(
                    "UPDATE documents SET category = ? WHERE document_pk = ?",
                    (document.category, existing["document_pk"]),
                )
            document_pk = int(existing["document_pk"])
        else:
            document_pk = int(existing["document_pk"])
            category = (
                existing["category"]
                if document.category == "Outro"
                and existing["category"] != "Outro"
                else document.category
            )
            download_status = (
                self._catalog_download_status(existing, document)
                if has_catalog
                else document.download_status or existing["download_status"]
            )
            incoming = {
                "asset_id": document.asset_id,
                "category": category,
                "document_name": document.document_name or existing["document_name"],
                "reference_date": document.reference_date or existing["reference_date"],
                "publication_date": document.publication_date or existing["publication_date"],
                "source": document.source,
                "source_url": document.source_url or existing["source_url"],
                "download_status": download_status,
                "file_hash": file_hash or existing["file_hash"],
            }
            for column in catalog:
                incoming[column] = catalog[column] or existing[column]
            current = {key: existing[key] for key in incoming}
            status = "updated" if incoming != current else "unchanged"
            assignments = [
                "source_document_id = COALESCE(NULLIF(?, ''), source_document_id)",
                "asset_id = ?",
                "category = ?",
                "document_name = COALESCE(NULLIF(?, ''), document_name)",
                "reference_date = COALESCE(NULLIF(?, ''), reference_date)",
                "publication_date = COALESCE(NULLIF(?, ''), publication_date)",
                "source = ?",
                "source_url = COALESCE(NULLIF(?, ''), source_url)",
                (
                    "download_status = ?"
                    if has_catalog
                    else "download_status = COALESCE(NULLIF(?, ''), download_status)"
                ),
                "file_hash = COALESCE(NULLIF(?, ''), file_hash)",
                "collected_at = ?",
                "run_id = COALESCE(NULLIF(?, ''), run_id)",
            ]
            parameters = [
                values[0], values[1], category, *values[3:8],
                download_status if has_catalog else values[8],
                *values[9:],
            ]
            for column in catalog:
                assignments.append(f"{column} = COALESCE(NULLIF(?, ''), {column})")
                parameters.append(catalog[column])
            self.connection.execute(
                f"UPDATE documents SET {', '.join(assignments)} WHERE document_pk = ?",
                [*parameters, document_pk],
            )
        self.connection.commit()
        return document_pk, status

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def count_by_asset_id(self, asset_id: int) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM documents WHERE asset_id = ?", (asset_id,)
            ).fetchone()[0]
        )

    def find_by_source_document(self, source_document_id: str, source: str):
        return self.connection.execute(
            "SELECT * FROM documents WHERE source_document_id = ? AND source = ?",
            (source_document_id, source),
        ).fetchone()

    def find_by_hash(self, file_hash: str) -> Optional[sqlite3.Row]:
        normalized_hash = self._value(file_hash)
        if not normalized_hash:
            return None
        return self.connection.execute(
            """SELECT d.*, a.codigo_cetip
               FROM documents d JOIN assets a ON a.asset_id = d.asset_id
               WHERE d.file_hash = ?""",
            (normalized_hash,),
        ).fetchone()

    def list_by_asset_id(self, asset_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """SELECT d.*, a.codigo_cetip
                   FROM documents d JOIN assets a ON a.asset_id = d.asset_id
                   WHERE d.asset_id = ? ORDER BY d.document_pk""",
                (asset_id,),
            )
        )

    def list_by_cetip(self, codigo_cetip: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """SELECT d.*, a.codigo_cetip
                   FROM documents d JOIN assets a ON a.asset_id = d.asset_id
                   WHERE a.codigo_cetip = ? ORDER BY d.document_pk""",
                (codigo_cetip,),
            )
        )

    def export_csv(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.connection.execute(
            """SELECT d.document_pk, a.codigo_cetip, d.category,
                      d.document_name, d.reference_date, d.publication_date,
                      d.source_url, d.source, d.download_status, d.file_hash
               FROM documents d JOIN assets a ON a.asset_id = d.asset_id
               ORDER BY d.document_pk"""
        )
        headers = (
            "documento_id", "codigo_cetip", "categoria", "nome_documento",
            "data_referencia", "data_publicacao", "url", "fonte",
            "status_download", "hash_arquivo",
        )
        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(
                    (
                        row["document_pk"], row["codigo_cetip"], row["category"],
                        row["document_name"], row["reference_date"] or "",
                        row["publication_date"] or "", row["source_url"],
                        row["source"], row["download_status"], row["file_hash"] or "",
                    )
                )
        return output_path

    @staticmethod
    def _value(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
