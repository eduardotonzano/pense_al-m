import csv

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.models.document import DOCUMENT_CATEGORIES, Document
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_repository import DocumentRepository


def make_asset(connection, codigo="CRA-001"):
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
        reference_date="2026-01-01",
        publication_date="2026-01-02",
        file_hash="hash-1",
    )
    values.update(changes)
    return Document(**values)


def test_schema_has_categories_and_safe_hash_uniqueness(tmp_path):
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
    indexes = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    assert any(row[0] == "uq_documents_file_hash_nonempty" for row in indexes)


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
