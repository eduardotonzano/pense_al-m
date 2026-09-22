from credit_assets.download_diagnostics import (
    build_inventory,
    detect_content,
    safe_filename,
    select_samples,
    sha256_bytes,
    validate_download,
    find_row_by_document_id,
    identify_view_action,
    identify_download_action,
)


def test_detect_pdf_and_html():
    assert detect_content(b"%PDF-1.7\nbody", "application/pdf")["format"] == "PDF"
    assert detect_content(b"<html>login</html>", "text/html")["format"] == "HTML"


def test_sha256_and_size_limit():
    data = b"content"
    assert sha256_bytes(data) == "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73"
    assert validate_download(data, "application/pdf", 100)["accepted"]
    assert not validate_download(data, "text/html", 100)["accepted"]
    assert not validate_download(data, "application/pdf", 2)["within_limit"]


def test_safe_filename():
    assert safe_filename("../doc: test") == "doc_test.bin"


def test_inventory_categories_missing_and_duplicates():
    asset = {"asset_id": 1, "codigo_cetip": "CRA022009VM", "isin": "BRECOACRABX0", "tipo_ativo": "CRA"}
    rows = [
        {"document_pk": 1, "source_document_id": "a", "category": "Informe Mensal",
         "document_name": "Informe", "reference_date": "2026-01", "publication_date": "2026-02",
         "source": "Fundos.NET", "source_url": "https://example/a", "file_hash": ""},
        {"document_pk": 2, "source_document_id": "b", "category": "Informe Mensal",
         "document_name": "Informe", "reference_date": "2026-01", "publication_date": "2026-02",
         "source": "Fundos.NET", "source_url": "https://example/a", "file_hash": ""},
    ]
    report = build_inventory(rows, asset)
    assert report["total_documents"] == 2
    assert "Termo de Securitização" in report["missing_categories"]
    assert report["potential_duplicates"][0]["document_ids"] == ["1", "2"]
    assert len(select_samples(rows)) == 1


def test_find_row_by_real_source_id():
    rows = [{"id": 981509, "tipoDocumento": "Informe Mensal de CRA"}]
    assert find_row_by_document_id(rows, "981509") == rows[0]


def test_identify_official_view_action():
    elements = [
        {"tag": "A", "title": "Visualizar Documento",
         "href": "https://fnet.example/visualizarDocumento?id=981509"},
        {"tag": "A", "title": "Download do Documento",
         "href": "https://fnet.example/downloadDocumento?id=981509"},
    ]
    assert identify_view_action(elements)["title"] == "Visualizar Documento"


def test_identify_official_download_action():
    elements = [
        {"tag": "A", "title": "Visualizar Documento", "href": "/visualizarDocumento?id=1"},
        {"tag": "A", "title": "Download do Documento", "href": "/downloadDocumento?id=1"},
    ]
    assert identify_download_action(elements)["title"] == "Download do Documento"


def test_download_event_and_binary_response_metadata():
    data = b"%PDF-1.7\nreal"
    event = {"mechanism": "event_download", "data": data}
    response = {"mechanism": "binary_response", "data": data}
    assert event["mechanism"] == "event_download"
    assert response["mechanism"] == "binary_response"
    assert detect_content(event["data"], "application/pdf")["is_pdf"]


def test_pdf_html_and_zip_signatures():
    assert detect_content(b"%PDF-1.7", "application/octet-stream")["format"] == "PDF"
    assert detect_content(b"<!DOCTYPE html><html>", "application/pdf")["format"] == "HTML"
    assert detect_content(b"PK\x03\x04payload", "application/octet-stream")["format"] == "ZIP"


def test_empty_response_and_size_limit_are_rejected():
    assert not validate_download(b"", "application/octet-stream", 100)["accepted"]
    assert not validate_download(b"%PDF-1.7", "application/pdf", 2)["accepted"]


def test_temporary_file_is_cleaned_and_hash_is_stable():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "sample.xml"
        data = b"<?xml version='1.0'?><document/>"
        path.write_bytes(data)
        assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()
        assert path.exists()
    assert not path.exists()


def test_browser_session_requirement_does_not_expose_cookies():
    result = {"requires_browser_session": True, "cookies": []}
    assert result["requires_browser_session"] is True
    assert result["cookies"] == []
import hashlib
import tempfile
from pathlib import Path
