"""Ativos, documentos e versoes de arquivo inventados para os testes das tabelas que
apontam para o documento de origem (informe_indicators e ratings). Nenhum dado real."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_version_repository import DocumentVersionRepository

RUNS = ("run-1", "run-2", "run-3")


def insert_document(connection: sqlite3.Connection, asset_id: int, source_id: str, category: str) -> int:
    cursor = connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name, source, source_url, run_id
        ) VALUES (?, ?, ?, ?, 'Fundos.NET', ?, 'run-1')""",
        (source_id, asset_id, category, f"documento {source_id}", f"https://example.test/{source_id}"),
    )
    return int(cursor.lastrowid)


def insert_version(
    connection: sqlite3.Connection,
    document_id: int,
    file_hash: str,
    *,
    file_format: str = "xml",
    current: bool = True,
) -> int:
    version_id, _ = DocumentVersionRepository(connection).create_version(
        document_id=document_id,
        file_name=f"{document_id}.{file_format}",
        local_file_path=f"data/documents/{document_id}.{file_format}",
        file_format=file_format,
        file_size_bytes=20,
        file_hash=file_hash,
        source_url=f"https://example.test/download?id={document_id}",
        is_current=current,
        validation_status="valid",
    )
    return version_id


def make_origin(connection: sqlite3.Connection) -> SimpleNamespace:
    """Dois ativos, um documento e uma versao de arquivo para cada, e tres execucoes."""

    for run_id in RUNS:
        connection.execute(
            "INSERT INTO executions (run_id, started_at, status) "
            "VALUES (?, '2026-10-23T00:00:00+00:00', 'success')",
            (run_id,),
        )

    assets = AssetRepository(connection)
    asset1 = assets.upsert(Asset("CRA-TESTE-1", "CRA", "Securitizadora", "1", "1", "1", isin="BR0000000019"))
    asset2 = assets.upsert(Asset("CRA-TESTE-2", "CRA", "Securitizadora", "1", "2", "1", isin="BR0000000027"))
    doc1 = insert_document(connection, asset1, "doc-1", "Informe Mensal")
    doc2 = insert_document(connection, asset2, "doc-2", "Informe Mensal")
    ver1 = insert_version(connection, doc1, "a" * 64)
    ver2 = insert_version(connection, doc2, "b" * 64)
    connection.commit()
    return SimpleNamespace(
        asset1=asset1, asset2=asset2, doc1=doc1, doc2=doc2, ver1=ver1, ver2=ver2
    )
