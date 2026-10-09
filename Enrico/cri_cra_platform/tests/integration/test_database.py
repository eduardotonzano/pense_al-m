from pathlib import Path

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.models.document import Document
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_repository import DocumentRepository

def test_schema_initialization(tmp_path):
    conn = connect(tmp_path / "test.db")
    initialize_database(conn)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "executions", "assets", "documents", "document_versions",
        "collection_attempts", "alerts",
    }.issubset(names)
    run_id_column = next(
        row for row in conn.execute("PRAGMA table_info(documents)")
        if row["name"] == "run_id"
    )
    assert run_id_column["notnull"] == 1


def test_legacy_nullable_run_id_database_remains_usable_and_repository_validates_it(
    tmp_path,
):
    schema_path = Path(__file__).parents[2] / "src" / "credit_assets" / "database" / "schema.sql"
    legacy_schema = schema_path.read_text(encoding="utf-8").replace(
        "run_id TEXT NOT NULL,\n    UNIQUE(source_document_id, source)",
        "run_id TEXT,\n    UNIQUE(source_document_id, source)",
    )
    database_path = tmp_path / "legacy.db"
    conn = connect(database_path)
    conn.executescript(legacy_schema)
    conn.commit()
    initialize_database(conn)

    run_id_column = next(
        row for row in conn.execute("PRAGMA table_info(documents)")
        if row["name"] == "run_id"
    )
    assert run_id_column["notnull"] == 0
    asset_id = AssetRepository(conn).upsert(
        Asset("LEGACY-CETIP", "CRA", "Securitizadora", "123", "1", "1")
    )
    conn.execute(
        "INSERT INTO executions (run_id, started_at, status) VALUES ('legacy-run', 'now', 'running')"
    )
    document = Document(
        asset_id=asset_id,
        source_document_id="legacy-doc",
        category="Outro",
        document_name="Legacy",
        source="Fundos.NET",
        source_url="https://example.test/legacy",
        run_id="",
    )
    with pytest.raises(ValueError, match="run_id é obrigatório"):
        DocumentRepository(conn).upsert(document)
    conn.close()
