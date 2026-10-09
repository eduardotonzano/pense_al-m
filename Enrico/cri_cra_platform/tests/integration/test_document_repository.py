import csv

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.models.document import DOCUMENT_CATEGORIES, Document
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_repository import DocumentRepository


RUN_ID = "document-repository-test-run"


def make_asset(connection, codigo="CRA-001"):
    connection.execute(
        """INSERT OR IGNORE INTO executions (run_id, started_at, status)
           VALUES (?, '2026-01-01T00:00:00Z', 'running')""",
        (RUN_ID,),
    )
    connection.commit()
    return AssetRepository(connection).upsert(
        Asset(codigo, "CRA", "Securitizadora", "123", "1", "1")
    )


def make_document(asset_id, **changes):
    values = dict(
        asset_id=asset_id,
        source_document_id="doc-1",
        category="Informe Mensal",
        document_name="Informe",
        source="origem",
        source_url="https://example.test/doc",
        run_id=RUN_ID,
        reference_date="2026-01-01",
        publication_date="2026-01-02",
        file_hash="hash-1",
    )
    values.update(changes)
    return Document(**values)


def test_schema_has_categories_and_allows_shared_physical_hashes(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(documents)"
        )
    }
    assert {"category", "file_hash", "asset_id"} <= columns
    assert len(DOCUMENT_CATEGORIES) == 9
    indexes = {
        row["name"]: row["sql"]
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index'"
        )
    }
    assert "uq_documents_file_hash_nonempty" not in indexes
    assert indexes["ix_documents_file_hash"] is not None
    asset_id = make_asset(connection)
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name, source,
            source_url, file_hash, run_id
        ) VALUES ('first', ?, 'Outro', 'A', 'Fundos.NET', 'https://example/1', ?, ?)""",
        (asset_id, "a" * 64, RUN_ID),
    )
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name, source,
            source_url, file_hash, run_id
        ) VALUES ('second', ?, 'Outro', 'B', 'Fundos.NET', 'https://example/2', ?, ?)""",
        (asset_id, "a" * 64, RUN_ID),
    )
    connection.commit()
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE file_hash = ?", ("a" * 64,)
    ).fetchone()[0] == 2


def test_upsert_by_hash_and_does_not_replace_values_with_empty(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    asset_id = make_asset(connection)
    repository = DocumentRepository(connection)

    first_id = repository.upsert(make_document(asset_id))
    second_id = repository.upsert(
        make_document(
            asset_id,
            source_document_id="different-id",
            document_name="",
            reference_date="",
            publication_date="",
            file_hash="hash-1",
        )
    )

    assert first_id == second_id
    row = repository.find_by_hash("hash-1")
    assert row["document_name"] == "Informe"
    assert row["reference_date"] == "2026-01-01"
    assert row["source_document_id"] == "different-id"


def test_upsert_without_hash_uses_source_document_id_and_source(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    asset_id = make_asset(connection)
    repository = DocumentRepository(connection)

    first_id = repository.upsert(make_document(asset_id, file_hash=None))
    second_id = repository.upsert(
        make_document(
            asset_id,
            file_hash="",
            document_name="Atualizado",
        )
    )
    third_id = repository.upsert(
        make_document(
            asset_id,
            source="outra-origem",
            file_hash=None,
        )
    )

    assert first_id == second_id
    assert third_id != first_id
    assert len(repository.list_by_asset_id(asset_id)) == 2


def test_list_by_asset_and_cetip_and_export_csv(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    asset_id = make_asset(connection, "CRA-EXPORT")
    repository = DocumentRepository(connection)
    repository.upsert(make_document(asset_id))

    assert len(repository.list_by_asset_id(asset_id)) == 1
    assert repository.list_by_cetip("CRA-EXPORT")[0]["codigo_cetip"] == "CRA-EXPORT"

    output = repository.export_csv(tmp_path / "catalogo_documentos.csv")
    with output.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == [
        "documento_id",
        "codigo_cetip",
        "categoria",
        "nome_documento",
        "data_referencia",
        "data_publicacao",
        "url",
        "fonte",
        "status_download",
        "hash_arquivo",
    ]
    assert rows[1][1:] == [
        "CRA-EXPORT",
        "Informe Mensal",
        "Informe",
        "2026-01-01",
        "2026-01-02",
        "https://example.test/doc",
        "origem",
        "pending",
        "hash-1",
    ]


def test_upsert_status_distinguishes_unchanged_and_updated(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    asset_id = make_asset(connection)
    repository = DocumentRepository(connection)
    document = make_document(asset_id)

    _, first = repository.upsert_with_status(document)
    _, unchanged = repository.upsert_with_status(document)
    _, updated = repository.upsert_with_status(
        make_document(asset_id, document_name="Informe corrigido")
    )

    assert first == "inserted"
    assert unchanged == "unchanged"
    assert updated == "updated"


def test_document_without_run_id_is_rejected_before_sqlite_write(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    asset_id = make_asset(connection)
    repository = DocumentRepository(connection)
    before = repository.count()

    with pytest.raises(ValueError, match="run_id é obrigatório"):
        repository.upsert_with_status(make_document(asset_id, run_id=""))

    assert repository.count() == before


def test_document_run_id_must_reference_registered_execution(tmp_path):
    connection = connect(tmp_path / "documents.db")
    initialize_database(connection)
    asset_id = make_asset(connection)
    repository = DocumentRepository(connection)

    with pytest.raises(ValueError, match="execução registrada"):
        repository.upsert_with_status(
            make_document(asset_id, run_id="unregistered-run")
        )

    assert repository.count() == 0
