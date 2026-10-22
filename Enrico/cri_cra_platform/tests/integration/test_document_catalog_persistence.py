from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from credit_assets.collectors.fundosnet_collector import FundosNetCollector
from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    apply_pending,
    pending_migrations,
    read_applied_versions,
)
from credit_assets.models.asset import Asset
from credit_assets.models.document import Document
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_repository import DocumentRepository


RUN_ID = "catalog-persistence-run"
GRID_FIELDS = (
    "source_category",
    "source_type",
    "source_species",
    "grid_version",
    "source_description",
    "source_row_json",
)


def columns(connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def make_asset(connection) -> int:
    connection.execute(
        """INSERT OR IGNORE INTO executions (run_id, started_at, status)
           VALUES (?, '2026-01-01T00:00:00Z', 'running')""",
        (RUN_ID,),
    )
    connection.commit()
    return AssetRepository(connection).upsert(
        Asset("CRA-CAT-1", "CRA", "Securitizadora", "123", "1", "1")
    )


def make_document(asset_id: int, **changes) -> Document:
    values = dict(
        asset_id=asset_id,
        source_document_id="doc-1",
        category="Outro",
        document_name="Informe Mensal de CRA",
        source="Fundos.NET",
        source_url="https://example.test/doc",
        run_id=RUN_ID,
        publication_date="25/09/2026 10:00",
        collected_at="2026-10-01T10:00:00Z",
    )
    values.update(changes)
    return Document(**values)


def new_database(tmp_path: Path):
    connection = connect(tmp_path / "catalog.db")
    initialize_database(connection)
    return connection, make_asset(connection)


def stored(connection, column: str):
    return connection.execute(f"SELECT {column} FROM documents").fetchone()[0]


def collector_asset() -> Asset:
    return Asset(
        codigo_cetip="CRA022009VM",
        isin="BRECOACRABX0",
        tipo_ativo="CRA",
        securitizadora="Eco Securitizadora",
        cnpj_securitizadora="10.753.164/0001-43",
        emissao="190",
        serie="1",
        devedor="Café Brasil",
        cnpj_devedor="",
        asset_id=1,
    )


def test_migration_001_adds_the_catalog_columns_to_an_existing_database(tmp_path):
    empty = tmp_path / "empty_migrations"
    empty.mkdir()
    connection = connect(tmp_path / "old.db")
    initialize_database(connection, migrations_dir=empty)
    asset_id = make_asset(connection)
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name, source,
            source_url, collected_at, run_id
        ) VALUES ('old-1', ?, 'Outro', 'Informe', 'Fundos.NET', 'https://x',
                  '2026-09-01T10:00:00Z', ?)""",
        (asset_id, RUN_ID),
    )
    connection.commit()
    assert "source_row_json" not in columns(connection, "documents")

    apply_pending(connection, pending_migrations(connection))

    assert read_applied_versions(connection)[1] == "document_catalog"
    assert {*GRID_FIELDS, "first_seen_at"} <= columns(connection, "documents")
    row = connection.execute(
        "SELECT first_seen_at, collected_at, source_row_json FROM documents"
    ).fetchone()
    assert row["first_seen_at"] == row["collected_at"] == "2026-09-01T10:00:00Z"
    assert row["source_row_json"] is None
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_new_database_already_has_the_catalog_columns(tmp_path):
    connection = connect(tmp_path / "new.db")

    initialize_database(connection)

    assert {*GRID_FIELDS, "first_seen_at"} <= columns(connection, "documents")
    assert "document_category_changes" in {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_category_audit_table_enforces_its_checks(tmp_path):
    connection, asset_id = new_database(tmp_path)
    document_pk, _ = DocumentRepository(connection).upsert_with_status(
        make_document(asset_id)
    )

    def insert(old: str, new: str, group: str):
        connection.execute(
            """INSERT INTO document_category_changes (
                document_id, old_category, new_category, rule_id, rule_group,
                classifier_version
            ) VALUES (?, ?, ?, 'R-TESTE', ?, 'teste')""",
            (document_pk, old, new, group),
        )

    insert("Outro", "Informe Mensal", "verified")
    with pytest.raises(sqlite3.IntegrityError):
        insert("Outro", "Outro", "verified")
    with pytest.raises(sqlite3.IntegrityError):
        insert("Outro", "Informe Mensal", "guess")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO document_category_changes (
                document_id, old_category, new_category, rule_id, rule_group,
                classifier_version
            ) VALUES (9999, 'Outro', 'Aditamento', 'R', 'verified', 'v')"""
        )


def test_collector_keeps_the_official_grid_fields_and_the_raw_row():
    row = {
        "id": 1328844,
        "descricaoFundo": "ECO CRA Emissão:190 Série:1 CAFÉ BRASIL BRECOACRABX0",
        "categoriaDocumento": "Informes Periódicos",
        "tipoDocumento": "Informe Mensal de CRA",
        "especieDocumento": "",
        "versao": 1,
        "dataEntrega": "25/09/2026 10:00",
        "dataReferencia": "08/2026",
        "status": "AC",
    }

    document = FundosNetCollector._to_document(collector_asset(), row, "run-1")

    assert document.source_category == "Informes Periódicos"
    assert document.source_type == "Informe Mensal de CRA"
    assert document.source_species is None
    assert document.grid_version == "1"
    assert document.source_description.startswith("ECO CRA")
    assert document.reference_date == "08/2026"
    assert document.publication_date == "25/09/2026 10:00"
    assert json.loads(document.source_row_json) == row


def test_collector_row_without_official_fields_keeps_only_the_raw_row():
    row = {"id": "fx-1", "tipo": "Informe Mensal de CRI", "url": "https://x"}

    document = FundosNetCollector._to_document(collector_asset(), row, "run-1")

    assert (
        document.source_category,
        document.source_type,
        document.source_species,
        document.grid_version,
        document.source_description,
    ) == (None, None, None, None, None)
    assert json.loads(document.source_row_json) == row


def test_grid_fields_are_persisted_with_the_document(tmp_path):
    connection, asset_id = new_database(tmp_path)

    DocumentRepository(connection).upsert_with_status(
        make_document(
            asset_id,
            source_category="Informes Periódicos",
            source_type="Informe Mensal de CRA",
            source_species="  ",
            grid_version="1",
            source_description="ECO CRA BRECOACRABX0",
            source_row_json='{"id": 1}',
        )
    )

    row = connection.execute("SELECT * FROM documents").fetchone()
    assert row["source_category"] == "Informes Periódicos"
    assert row["source_type"] == "Informe Mensal de CRA"
    assert row["source_species"] is None
    assert row["grid_version"] == "1"
    assert row["source_row_json"] == '{"id": 1}'
    assert row["first_seen_at"] == "2026-10-01T10:00:00Z"


def test_catalog_refresh_keeps_the_download_state(tmp_path):
    connection, asset_id = new_database(tmp_path)
    repository = DocumentRepository(connection)
    document = make_document(asset_id, grid_version="1")
    document_pk, _ = repository.upsert_with_status(document)
    connection.execute(
        "UPDATE documents SET download_status = 'downloaded', file_hash = ? "
        "WHERE document_pk = ?",
        ("a" * 64, document_pk),
    )
    connection.commit()

    _, status = repository.upsert_with_status(document)

    assert stored(connection, "download_status") == "downloaded"
    assert stored(connection, "file_hash") == "a" * 64
    assert status == "unchanged"


def test_new_grid_version_reopens_the_download(tmp_path):
    connection, asset_id = new_database(tmp_path)
    repository = DocumentRepository(connection)
    document_pk, _ = repository.upsert_with_status(
        make_document(asset_id, grid_version="1")
    )
    connection.execute(
        "UPDATE documents SET download_status = 'downloaded' WHERE document_pk = ?",
        (document_pk,),
    )
    connection.commit()

    _, status = repository.upsert_with_status(
        make_document(asset_id, grid_version="2")
    )

    assert stored(connection, "download_status") == "pending"
    assert stored(connection, "grid_version") == "2"
    assert status == "updated"


def test_unknown_previous_version_does_not_reopen_the_download(tmp_path):
    connection, asset_id = new_database(tmp_path)
    repository = DocumentRepository(connection)
    document_pk, _ = repository.upsert_with_status(make_document(asset_id))
    connection.execute(
        "UPDATE documents SET download_status = 'downloaded' WHERE document_pk = ?",
        (document_pk,),
    )
    connection.commit()

    repository.upsert_with_status(make_document(asset_id, grid_version="1"))

    assert stored(connection, "download_status") == "downloaded"
    assert stored(connection, "grid_version") == "1"


def test_refresh_does_not_wipe_grid_fields_with_empty_values(tmp_path):
    connection, asset_id = new_database(tmp_path)
    repository = DocumentRepository(connection)
    repository.upsert_with_status(
        make_document(
            asset_id,
            source_type="Informe Mensal de CRA",
            source_row_json='{"id": 1}',
        )
    )

    _, status = repository.upsert_with_status(make_document(asset_id))

    assert stored(connection, "source_type") == "Informe Mensal de CRA"
    assert stored(connection, "source_row_json") == '{"id": 1}'
    assert status == "unchanged"


def test_first_seen_is_kept_and_last_seen_moves(tmp_path):
    connection, asset_id = new_database(tmp_path)
    repository = DocumentRepository(connection)
    repository.upsert_with_status(
        make_document(asset_id, collected_at="2026-10-01T10:00:00Z")
    )

    repository.upsert_with_status(
        make_document(asset_id, collected_at="2026-10-05T10:00:00Z")
    )

    row = connection.execute("SELECT first_seen_at, collected_at FROM documents").fetchone()
    assert row["first_seen_at"] == "2026-10-01T10:00:00Z"
    assert row["collected_at"] == "2026-10-05T10:00:00Z"


def test_new_grid_fields_make_an_existing_document_updated_once(tmp_path):
    connection, asset_id = new_database(tmp_path)
    repository = DocumentRepository(connection)

    _, first = repository.upsert_with_status(make_document(asset_id))
    _, second = repository.upsert_with_status(
        make_document(asset_id, source_category="Informes Periódicos")
    )
    _, third = repository.upsert_with_status(
        make_document(asset_id, source_category="Informes Periódicos")
    )

    assert (first, second, third) == ("inserted", "updated", "unchanged")


def test_database_without_the_catalog_columns_still_upserts(tmp_path):
    empty = tmp_path / "empty_migrations"
    empty.mkdir()
    connection = connect(tmp_path / "legacy.db")
    initialize_database(connection, migrations_dir=empty)
    asset_id = make_asset(connection)
    repository = DocumentRepository(connection)
    assert "grid_version" not in columns(connection, "documents")

    _, first = repository.upsert_with_status(
        make_document(asset_id, grid_version="1")
    )
    _, second = repository.upsert_with_status(
        make_document(asset_id, grid_version="1")
    )

    assert (first, second) == ("inserted", "unchanged")
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
