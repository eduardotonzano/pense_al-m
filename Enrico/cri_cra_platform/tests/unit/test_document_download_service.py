from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from contextlib import AbstractContextManager

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.download_diagnostics import (
    detect_content,
    safe_document_filename,
    validate_download,
)
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.document_version_repository import (
    DocumentVersionRepository,
)
from credit_assets.services.document_download_service import (
    DocumentDownloadService,
    FundosNetBrowserDownloader,
    SAMPLE_CATEGORIES,
    planned_document_path,
    select_sample_documents,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def create_catalog(tmp_path: Path, names: tuple[str, ...] = (
    "Informe Mensal de CRA",
    "AGO/E",
)) -> tuple[sqlite3.Connection, list[int]]:
    connection = connect(tmp_path / "catalog.db")
    initialize_database(connection)
    connection.execute(
        """INSERT INTO executions (run_id, started_at, status)
           VALUES ('download-service-catalog-run', '2026-01-01T00:00:00Z', 'running')"""
    )
    asset_id = AssetRepository(connection).upsert(
        Asset(
            "CRA022009VM", "CRA", "Eco Securitizadora",
            "12345678000199", "190", "1",
            devedor="Café Brasil", isin="BRECOACRABX0",
        )
    )
    documents = []
    for index, name in enumerate(names, start=1):
        publication_date = "2026-09-01" if index == 1 else "2026-08-01"
        cursor = connection.execute(
            """INSERT INTO documents (
                source_document_id, asset_id, category, document_name,
                reference_date, publication_date, source, source_url, run_id
            ) VALUES (?, ?, 'Outro', ?, ?, ?, 'Fundos.NET', ?, 'download-service-catalog-run')""",
            (
                str(981500 + index), asset_id, name, "07/2026",
                publication_date,
                f"https://fnet.bmfbovespa.com.br/fnet/publico/visualizarDocumento?id={981500 + index}",
            ),
        )
        documents.append(int(cursor.lastrowid))
    connection.commit()
    return connection, documents


class FakeDownloader:
    def __init__(self, payloads: dict[str, bytes]):
        self.payloads = payloads
        self.called = False

    def download_selected(self, asset, documents, temporary_directory):
        self.called = True
        result = {}
        for document in documents:
            source_id = document["source_document_id"]
            payload = self.payloads[source_id]
            path = temporary_directory / f"{source_id}.download"
            path.write_bytes(payload)
            result[document["document_id"]] = {
                "temporary_path": str(path),
                "official_url": (
                    "https://fnet.bmfbovespa.com.br/fnet/publico/"
                    f"downloadDocumento?id={source_id}"
                ),
                "source_version": "1",
                "mechanism": "event_download",
                "isin_description_validated": True,
                "live_type": document["category"],
                "live_species": "",
                "response": {
                    "status": 200,
                    "content_type": "application/octet-stream",
                    "content_disposition": "attachment",
                    "redirect_count": 0,
                },
            }
        return result


def make_service(connection, root, downloader, max_bytes=25_000_000):
    return DocumentDownloadService(
        connection,
        DocumentVersionRepository(connection),
        root,
        downloader=downloader,
        max_bytes=max_bytes,
    )


def test_sample_selects_existing_categories_and_reports_absent_ones(tmp_path):
    connection, document_ids = create_catalog(tmp_path)
    selection = select_sample_documents(
        connection, "CRA022009VM", "BRECOACRABX0"
    )

    assert [item["document_id"] for item in selection["selected"]] == document_ids
    assert selection["found_categories"] == ["Informe Mensal", "Ata/Edital"]
    assert selection["missing_categories"] == [
        "Termo de Securitização", "Aditamento"
    ]
    assert all(item["asset_isin"] == "BRECOACRABX0" for item in selection["selected"])


def test_sample_prefers_most_recent_and_never_invents_missing_category(tmp_path):
    connection, _ = create_catalog(tmp_path, ("Informe Mensal anterior",))
    asset_id = connection.execute(
        "SELECT asset_id FROM assets WHERE codigo_cetip = 'CRA022009VM'"
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name,
            publication_date, source, source_url, run_id
        ) VALUES ('novo', ?, 'Outro', 'Informe Mensal novo', '2026-09-20',
                  'Fundos.NET', 'https://fnet.test/visualizar?id=novo',
                  'download-service-catalog-run')""",
        (asset_id,),
    )
    connection.commit()
    selection = select_sample_documents(
        connection, "CRA022009VM", "BRECOACRABX0",
        categories=["Informe Mensal"],
    )
    assert selection["selected"][0]["source_document_id"] == "novo"
    assert selection["missing_categories"] == []


def test_explicit_ids_select_multiple_documents_of_same_category(tmp_path):
    connection, document_ids = create_catalog(
        tmp_path, ("Informe Mensal de CRA", "Informe Mensal de CRA", "AGO/E")
    )
    selection = select_sample_documents(
        connection, "CRA022009VM", "BRECOACRABX0",
        source_document_ids=["981502", "981501", "981501"],
    )
    assert [item["document_id"] for item in selection["selected"]] == [
        document_ids[1], document_ids[0]
    ]
    assert {item["category"] for item in selection["selected"]} == {"Informe Mensal"}
    assert selection["requested_source_document_ids"] == ["981502", "981501"]


@pytest.mark.parametrize("source_id, message", [
    ("999999", "não catalogado"),
    ("981502", "fora da amostra"),
])
def test_explicit_ids_reject_unknown_or_unapproved_documents(tmp_path, source_id, message):
    connection, _ = create_catalog(tmp_path, ("Informe Mensal de CRA", "Demonstrações Financeiras"))
    with pytest.raises(ValueError, match=message):
        select_sample_documents(
            connection, "CRA022009VM", "BRECOACRABX0",
            source_document_ids=[source_id],
        )


def test_explicit_ids_accept_trustee_report_and_material_fact_but_default_sample_does_not(tmp_path):
    connection, _ = create_catalog(
        tmp_path, ("Relatório de Agente Fiduciário", "Fato Relevante", "Informe Mensal de CRA")
    )
    explicit = select_sample_documents(
        connection, "CRA022009VM", "BRECOACRABX0", source_document_ids=["981501", "981502"],
    )
    assert [item["category"] for item in explicit["selected"]] == [
        "Relatório Agente Fiduciário", "Fato Relevante"
    ]
    default = select_sample_documents(connection, "CRA022009VM", "BRECOACRABX0")
    assert {item["category"] for item in default["selected"]} == {"Informe Mensal"}


def test_other_category_requires_explicit_opt_in(tmp_path):
    connection, _ = create_catalog(tmp_path, ("Outros Comunicados Não Considerados Fatos Relevantes",))
    with pytest.raises(ValueError, match="fora da amostra"):
        select_sample_documents(connection, "CRA022009VM", "BRECOACRABX0", source_document_ids=["981501"])
    selected = select_sample_documents(
        connection, "CRA022009VM", "BRECOACRABX0", source_document_ids=["981501"], allow_other=True,
    )
    assert selected["selected"][0]["category"] == "Outro"


def test_explicit_ids_reject_document_of_another_asset(tmp_path):
    connection, _ = create_catalog(tmp_path)
    other_asset_id = AssetRepository(connection).upsert(
        Asset(
            "24G2100031", "CRI", "Opea Securitizadora",
            "02773542000122", "301", "1", isin="BRRBRACRIP13",
        )
    )
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name,
            source, source_url, run_id
        ) VALUES ('outro-ativo', ?, 'Informe Mensal', 'Informe Mensal de CRI',
                  'Fundos.NET', 'https://fnet.test/visualizar?id=outro-ativo',
                  'download-service-catalog-run')""",
        (other_asset_id,),
    )
    connection.commit()
    with pytest.raises(ValueError, match="outro ativo"):
        select_sample_documents(
            connection, "CRA022009VM", "BRECOACRABX0",
            source_document_ids=["outro-ativo"],
        )


def test_sample_prefers_previously_verified_version_over_newer_unverified_document(
    tmp_path,
):
    connection, document_ids = create_catalog(tmp_path, ("Informe Mensal antigo",))
    asset_id = connection.execute(
        "SELECT asset_id FROM assets WHERE codigo_cetip = 'CRA022009VM'"
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO documents (
            source_document_id, asset_id, category, document_name,
            publication_date, source, source_url, run_id
        ) VALUES ('novo', ?, 'Outro', 'Informe Mensal novo', '2026-09-20',
                  'Fundos.NET', 'https://fnet.test/visualizar?id=novo',
                  'download-service-catalog-run')""",
        (asset_id,),
    )
    content = b"%PDF-verified-sample"
    file_path = tmp_path / "verified.pdf"
    file_path.write_bytes(content)
    connection.execute(
        """INSERT INTO document_versions (
            document_id, file_name, local_file_path, file_format,
            file_size_bytes, file_hash, is_current, validation_status
        ) VALUES (?, 'verified.pdf', ?, 'pdf', ?, ?, 1, 'valid')""",
        (
            document_ids[0],
            str(file_path),
            len(content),
            hashlib.sha256(content).hexdigest(),
        ),
    )
    connection.commit()

    selection = select_sample_documents(
        connection,
        "CRA022009VM",
        "BRECOACRABX0",
        categories=["Informe Mensal"],
    )

    assert selection["selected"][0]["document_id"] == document_ids[0]
    assert selection["selected"][0]["current_file_hash"] == hashlib.sha256(
        content
    ).hexdigest()


def test_dry_run_does_not_call_downloader_or_mutate_files_or_database(tmp_path):
    connection, _ = create_catalog(tmp_path)
    downloader = FakeDownloader({})
    before_documents = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    before_versions = connection.execute(
        "SELECT COUNT(*) FROM document_versions"
    ).fetchone()[0]
    before_attempts = connection.execute(
        "SELECT COUNT(*) FROM collection_attempts"
    ).fetchone()[0]
    before_runs = connection.execute("SELECT COUNT(*) FROM executions").fetchone()[0]

    result = make_service(connection, tmp_path, downloader).run(
        "CRA022009VM", "BRECOACRABX0", dry_run=True
    )

    assert not downloader.called
    assert result["dry_run"]
    assert result["inserted"] == result["failed"] == 0
    assert result["missing_categories"] == ["Termo de Securitização", "Aditamento"]
    assert all(
        Path(tmp_path / item["planned_directory"]).is_relative_to(tmp_path)
        for item in result["selected_documents"]
    )
    assert not (tmp_path / "data" / "documents").exists()
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == before_documents
    assert connection.execute(
        "SELECT COUNT(*) FROM document_versions"
    ).fetchone()[0] == before_versions
    assert connection.execute(
        "SELECT COUNT(*) FROM collection_attempts"
    ).fetchone()[0] == before_attempts
    assert connection.execute("SELECT COUNT(*) FROM executions").fetchone()[0] == before_runs


def test_first_download_then_same_hash_is_unchanged(tmp_path):
    connection, document_ids = create_catalog(tmp_path)
    content = b"<?xml version='1.0'?><report><row>real bytes</row></report>"
    downloader = FakeDownloader({
        "981501": content,
        "981502": b"%PDF-1.7\nvalid sample",
    })
    service = make_service(connection, tmp_path, downloader)

    first = service.run("CRA022009VM", "BRECOACRABX0")
    assert first["inserted"] == 2
    assert first["failed"] == 0
    assert first["files_removed"] == 2
    assert first["attempts_recorded"] == 2
    assert first["temporary_directory_removed"]
    assert first["description_validation"]["all_selected_rows_verified"]
    assert all(item["result"] == "inserted" for item in first["files_downloaded"])
    assert all(Path(tmp_path / item["local_file_path"]).is_file() for item in first["files_downloaded"])
    assert connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM collection_attempts WHERE document_id IN (?, ?)",
        tuple(document_ids),
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE download_status = 'downloaded' "
        "AND file_hash IS NOT NULL"
    ).fetchone()[0] == 2

    second = service.run("CRA022009VM", "BRECOACRABX0")
    assert second["inserted"] == 0
    assert second["unchanged"] == 2
    assert second["new_version"] == 0
    categories = connection.execute(
        "SELECT category FROM documents ORDER BY document_pk"
    ).fetchall()
    assert [row["category"] for row in categories] == [
        "Informe Mensal", "Ata/Edital"
    ]
    assert connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == len(document_ids)
    assert second["files_removed"] == 2
    assert second["temporary_directory_removed"]
    assert second["attempts_recorded"] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM document_versions"
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM collection_attempts WHERE document_id IN (?, ?)",
        tuple(document_ids),
    ).fetchone()[0] == 4


def test_live_official_category_corrects_other_without_changing_document_or_versions(
    tmp_path,
):
    connection, document_ids = create_catalog(tmp_path)
    version_repository = DocumentVersionRepository(connection)
    file_records = []
    for index, document_id in enumerate(document_ids):
        content = f"%PDF-1.7\nverified-{index}".encode()
        path = tmp_path / "data" / "documents" / f"verified-{index}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        file_hash = hashlib.sha256(content).hexdigest()
        version_repository.create_version(
            document_id=document_id,
            file_name=path.name,
            local_file_path=str(path.relative_to(tmp_path)),
            file_format="pdf",
            file_size_bytes=len(content),
            file_hash=file_hash,
            source_url=f"https://fnet.test/download?id={document_id}",
            is_current=True,
            validation_status="valid",
        )
        connection.execute(
            """UPDATE documents SET file_hash = ?, download_status = 'downloaded'
               WHERE document_pk = ?""",
            (file_hash, document_id),
        )
        file_records.append((path, content, file_hash))
    connection.commit()

    protected_columns = (
        "source_document_id", "asset_id", "document_name", "reference_date",
        "publication_date", "source", "source_url", "download_status",
        "file_hash", "run_id", "collected_at",
    )
    before_documents = {
        document_id: tuple(
            connection.execute(
                f"SELECT {', '.join(protected_columns)} FROM documents "
                "WHERE document_pk = ?",
                (document_id,),
            ).fetchone()
        )
        for document_id in document_ids
    }
    before_versions = {
        document_id: tuple(
            connection.execute(
                "SELECT * FROM document_versions WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        )
        for document_id in document_ids
    }
    service = make_service(connection, tmp_path, FakeDownloader({}))
    report = {"asset": {"codigo_cetip": "CRA022009VM"}, "failed": 0, "errors": []}
    live_rows = (
        {"live_type": "Informe Mensal de CRA", "live_species": ""},
        {"live_type": "AGO/E", "live_species": "Ata da Assembleia"},
    )
    for document_id, live_row in zip(document_ids, live_rows):
        service._process_document(
            {
                "document_id": document_id,
                "source_document_id": str(
                    connection.execute(
                        "SELECT source_document_id FROM documents WHERE document_pk = ?",
                        (document_id,),
                    ).fetchone()[0]
                ),
                "category": "Outro",
                "document_name": "",
                "source_url": f"https://fnet.test/visualizar?id={document_id}",
            },
            {
                "error": "test metadata-only reclassification",
                "isin_description_validated": True,
                **live_row,
            },
            report,
            tmp_path,
        )

    categories = {
        document_id: connection.execute(
            "SELECT category FROM documents WHERE document_pk = ?",
            (document_id,),
        ).fetchone()["category"]
        for document_id in document_ids
    }
    assert categories == {
        document_ids[0]: "Informe Mensal",
        document_ids[1]: "Ata/Edital",
    }
    for document_id in document_ids:
        after_document = tuple(
            connection.execute(
                f"SELECT {', '.join(protected_columns)} FROM documents "
                "WHERE document_pk = ?",
                (document_id,),
            ).fetchone()
        )
        after_version = tuple(
            connection.execute(
                "SELECT * FROM document_versions WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        )
        assert after_document == before_documents[document_id]
        assert after_version == before_versions[document_id]
    assert report["failed"] == 2
    assert all(path.read_bytes() == content for path, content, _ in file_records)
    assert [
        connection.execute(
            "SELECT file_hash FROM documents WHERE document_pk = ?",
            (document_id,),
        ).fetchone()["file_hash"]
        for document_id in document_ids
    ] == [record[2] for record in file_records]


def test_live_category_requires_asset_description_validation(tmp_path):
    connection, document_ids = create_catalog(tmp_path, ("Informe Mensal de CRA",))
    service = make_service(connection, tmp_path, FakeDownloader({}))

    category = service.persist_live_category(
        document_ids[0],
        {"live_type": "Informe Mensal de CRA"},
    )

    assert category is None
    assert connection.execute(
        "SELECT category FROM documents WHERE document_pk = ?",
        (document_ids[0],),
    ).fetchone()["category"] == "Outro"


def test_new_hash_creates_version_and_preserves_history(tmp_path):
    connection, document_ids = create_catalog(tmp_path, ("Informe Mensal de CRA",))
    service = make_service(
        connection, tmp_path,
        FakeDownloader({"981501": b"<?xml version='1.0'?><version>1</version>"}),
    )
    first = service.run("CRA022009VM", "BRECOACRABX0", categories=["Informe Mensal"])
    old_hash = first["files_downloaded"][0]["file_hash"]

    service.downloader = FakeDownloader({
        "981501": b"<?xml version='1.0'?><version>2</version>"
    })
    second = service.run("CRA022009VM", "BRECOACRABX0", categories=["Informe Mensal"])

    rows = connection.execute(
        "SELECT * FROM document_versions WHERE document_id = ? ORDER BY version_id",
        (document_ids[0],),
    ).fetchall()
    assert second["new_version"] == 1
    assert len(rows) == 2
    assert rows[0]["file_hash"] == old_hash
    assert [row["is_current"] for row in rows] == [0, 1]
    old_path = tmp_path / rows[0]["local_file_path"]
    new_path = tmp_path / rows[1]["local_file_path"]
    assert old_path != new_path
    assert hashlib.sha256(old_path.read_bytes()).hexdigest() == old_hash
    assert hashlib.sha256(new_path.read_bytes()).hexdigest() == rows[1]["file_hash"]


def test_shared_content_is_linked_across_documents_without_duplicate_file(tmp_path):
    connection, _ = create_catalog(tmp_path)
    shared = b"<?xml version='1.0'?><same-content/>"
    result = make_service(
        connection, tmp_path,
        FakeDownloader({"981501": shared, "981502": shared}),
    ).run("CRA022009VM", "BRECOACRABX0")

    rows = connection.execute(
        "SELECT document_id, local_file_path, file_hash FROM document_versions "
        "ORDER BY document_id"
    ).fetchall()
    assert result["inserted"] == 2
    assert result["duplicate_content"] == 1
    assert rows[0]["file_hash"] == rows[1]["file_hash"]
    assert rows[0]["local_file_path"] == rows[1]["local_file_path"]
    physical = list((tmp_path / "data" / "documents").rglob("*"))
    assert len([path for path in physical if path.is_file()]) == 1


def test_one_download_error_does_not_stop_other_sample_documents(tmp_path):
    connection, document_ids = create_catalog(tmp_path)

    class OneFailureDownloader:
        def download_selected(self, asset, documents, temporary_directory):
            result = {
                documents[0]["document_id"]: {
                    "error": "TimeoutError: official download timed out",
                    "validation_status": "download_failed",
                }
            }
            path = temporary_directory / "second.xml"
            path.write_bytes(b"<?xml version='1.0'?><ok/>")
            result[documents[1]["document_id"]] = {
                "temporary_path": str(path),
                "official_url": "https://fnet.test/downloadDocumento?id=981502",
                "response": {"status": 200, "content_type": "application/xml"},
                "mechanism": "event_download",
            }
            return result

    report = make_service(
        connection, tmp_path, OneFailureDownloader()
    ).run("CRA022009VM", "BRECOACRABX0")

    assert report["failed"] == 1
    assert report["inserted"] == 1
    assert connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM collection_attempts"
    ).fetchone()[0] == 2
    statuses = {
        row["document_pk"]: row["download_status"]
        for row in connection.execute("SELECT document_pk, download_status FROM documents")
    }
    assert statuses[document_ids[0]] == "failed"
    assert statuses[document_ids[1]] == "downloaded"


@pytest.mark.parametrize(
    ("content", "expected_status"),
    [
        (b"<!DOCTYPE html><html><body>login</body></html>", "html_instead_of_file"),
        (b"", "empty_file"),
        (b"unrecognized payload", "invalid_format"),
    ],
)
def test_invalid_files_are_recorded_without_becoming_current(
    tmp_path, content, expected_status
):
    connection, document_ids = create_catalog(tmp_path, ("Informe Mensal de CRA",))
    result = make_service(
        connection, tmp_path, FakeDownloader({"981501": content})
    ).run("CRA022009VM", "BRECOACRABX0", categories=["Informe Mensal"])

    version = connection.execute(
        "SELECT * FROM document_versions WHERE document_id = ?",
        (document_ids[0],),
    ).fetchone()
    document = connection.execute(
        "SELECT download_status, file_hash FROM documents WHERE document_pk = ?",
        (document_ids[0],),
    ).fetchone()
    assert result["failed"] == 1
    assert version is None
    attempt = connection.execute(
        """SELECT status, error_message FROM collection_attempts
           WHERE document_id = ? ORDER BY attempt_id DESC LIMIT 1""",
        (document_ids[0],),
    ).fetchone()
    assert attempt["status"] == "failed"
    assert attempt["error_message"]
    assert document["download_status"] == "failed"
    assert document["file_hash"] is None
    assert not list((tmp_path / "data" / "documents").rglob("*")) if (tmp_path / "data" / "documents").exists() else True


def test_size_limit_failure_does_not_replace_document_hash(tmp_path):
    connection, document_ids = create_catalog(tmp_path, ("Informe Mensal de CRA",))
    repository = DocumentVersionRepository(connection)
    repository.create_version(
        document_ids[0], "old.xml", "data/documents/old.xml", "xml", 10,
        "a" * 64, "https://fnet.test/download?id=981501",
        is_current=True, validation_status="valid",
    )
    connection.execute(
        "UPDATE documents SET file_hash = ?, download_status = 'downloaded' WHERE document_pk = ?",
        ("a" * 64, document_ids[0]),
    )
    connection.commit()
    result = make_service(
        connection, tmp_path,
        FakeDownloader({"981501": b"<?xml version='1.0'?><long>123456</long>"}),
        max_bytes=10,
    ).run("CRA022009VM", "BRECOACRABX0", categories=["Informe Mensal"])

    current = connection.execute(
        "SELECT download_status, file_hash FROM documents WHERE document_pk = ?",
        (document_ids[0],),
    ).fetchone()
    assert result["failed"] == 1
    assert current["download_status"] == "downloaded"
    assert current["file_hash"] == "a" * 64
    assert connection.execute(
        "SELECT COUNT(*) FROM document_versions WHERE document_id = ?",
        (document_ids[0],),
    ).fetchone()[0] == 1
    assert connection.execute(
        """SELECT status, error_message FROM collection_attempts
           WHERE document_id = ? ORDER BY attempt_id DESC LIMIT 1""",
        (document_ids[0],),
    ).fetchone()["status"] == "failed"


def test_atomic_write_and_temporary_cleanup_after_atomic_failure(tmp_path, monkeypatch):
    connection, _ = create_catalog(tmp_path, ("Informe Mensal de CRA",))
    service = make_service(connection, tmp_path, FakeDownloader({}))
    destination = planned_document_path(
        tmp_path, "CRA022009VM", "Informe Mensal", "07/2026",
        "981501", "Informe Mensal", "XML",
    )
    service._atomic_write(destination, b"<?xml version='1.0'?><ok/>")
    assert destination.read_bytes().startswith(b"<?xml")
    assert not list(destination.parent.glob("*.tmp"))

    def fail_replace(*args):
        raise OSError("replace failed")

    monkeypatch.setattr("credit_assets.services.document_download_service.os.replace", fail_replace)
    failed_path = destination.with_name("failed.xml")
    with pytest.raises(OSError, match="replace failed"):
        service._atomic_write(failed_path, b"contents")
    assert not failed_path.exists()
    assert not list(destination.parent.glob("*.tmp"))


def test_safe_filename_and_path_traversal_guard(tmp_path):
    filename = safe_document_filename(
        "07/2026", "../../981509", r"..\Informe: mensal", "xml"
    )
    assert filename.startswith("2026-07_")
    assert "/" not in filename and "\\" not in filename
    target = planned_document_path(
        tmp_path, r"..\..\escape", "Informe Mensal", "07/2026",
        "../../981509", "../Informe: mensal", "XML",
    )
    assert target.is_relative_to(tmp_path / "data" / "documents")


class FakeRequest:
    method = "GET"
    redirected_from = None


class FakeResponse:
    def __init__(self, url, body):
        self.url = url
        self.request = FakeRequest()
        self.status = 200
        self.headers = {
            "content-type": "application/octet-stream",
            "content-disposition": "attachment",
        }
        self._body = body

    def body(self):
        return self._body


class FakeDownload:
    suggested_filename = "official.xml"
    url = "https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=981502"

    def __init__(self, content):
        self.content = content

    def save_as(self, path):
        Path(path).write_bytes(self.content)


class FakeLocator:
    def __init__(self, response_events, download_events, response=None, download=None):
        self.response_events = response_events
        self.download_events = download_events
        self.response = response
        self.download = download

    def click(self, **kwargs):
        if self.response:
            self.response_events.append(self.response)
        if self.download:
            self.download_events.append(self.download)


class FakePage:
    def __init__(self, download_events):
        self.download_events = download_events

    def expect_download(self, timeout):
        return FakeDownloadExpectation(self.download_events)

    def wait_for_timeout(self, _):
        pass


class FakeDownloadExpectation(AbstractContextManager):
    def __init__(self, download_events):
        self.download_events = download_events
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return False
        if not self.download_events:
            raise PlaywrightTimeoutError("no download event")
        self.value = self.download_events[-1]
        return False


@pytest.mark.parametrize("mechanism", ["event_download", "binary_response"])
def test_official_download_capture_supports_event_and_binary_response(
    tmp_path, mechanism
):
    data = b"<?xml version='1.0'?><document/>"
    response_events, download_events = [], []
    response = FakeResponse(
        "https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id=981502",
        data,
    )
    download = FakeDownload(data) if mechanism == "event_download" else None
    locator = FakeLocator(response_events, download_events, response, download)
    response_bodies = {id(response): data} if mechanism == "binary_response" else {}
    result = FundosNetBrowserDownloader(timeout_ms=100)._click_download(
        FakePage(download_events), locator, "981502", tmp_path,
        response_events, download_events, [], [], response_bodies,
    )

    assert result["mechanism"] == mechanism
    assert Path(result["temporary_path"]).read_bytes() == data
    assert result["response"]["status"] == 200
    assert detect_content(data)["format"] == "XML"


def test_content_detection_sha_and_size_limit():
    assert detect_content(b"%PDF-1.7", "application/octet-stream")["format"] == "PDF"
    assert detect_content(b"<?xml version='1.0'?><a/>")["format"] == "XML"
    assert detect_content(b"PK\x03\x04payload")["format"] == "ZIP"
    assert validate_download(b"<html>login</html>", "", 100)["is_html"]
    assert validate_download(b"", "", 100)["sha256"] is None
    too_large = validate_download(b"%PDF-" + b"x" * 20, "application/pdf", 5)
    assert not too_large["within_limit"]
    assert too_large["sha256"] is None
    valid = validate_download(b"%PDF-1.7", "", 100)
    assert valid["sha256"] == hashlib.sha256(b"%PDF-1.7").hexdigest()
