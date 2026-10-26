import hashlib

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.services.raw_xml_extraction_service import (
    RawXmlExtractionService,
    walk_values,
)

XML = """<?xml version="1.0" encoding="UTF-8"?>
<InformeMensalCRA xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <DadosGerais><Competencia>2026-08-31</Competencia><Vazio/></DadosGerais>
  <Ativo total="10.5"><Nil xsi:nil="true"/><Zero>0</Zero></Ativo>
  <Series><Serie><N>1</N></Serie><Serie><N>2</N></Serie></Series>
  <Devedor><CPF>123.456.789-09</CPF></Devedor>
</InformeMensalCRA>""".encode("utf-8")
MAPPING = {"mapping_version": "0.0.0-test", "paths": {}}


def _setup(tmp_path, data=XML, stored_hash=None):
    connection = connect(tmp_path / "t.db")
    initialize_database(connection)
    connection.execute(
        "INSERT INTO executions (run_id, started_at, status) VALUES ('r', '2026-01-01', 'success')"
    )
    AssetRepository(connection).upsert(
        Asset("CRA022009VM", "CRA", "Eco", "1", "190", "1", isin="BRECOACRABX0")
    )
    connection.execute(
        """INSERT INTO documents (source_document_id, asset_id, category, document_name,
               publication_date, source, source_url, run_id)
           VALUES ('1', 1, 'Informe Mensal', 'Informe Mensal de CRA', '25/09/2026',
                   'Fundos.NET', 'https://fnet.test/1', 'r')"""
    )
    (tmp_path / "f.xml").write_bytes(data)
    connection.execute(
        """INSERT INTO document_versions (document_id, local_file_path, file_format,
               file_size_bytes, file_hash, source_version, is_current, validation_status)
           VALUES (1, 'f.xml', 'xml', ?, ?, '2', 1, 'valid')""",
        (len(data), stored_hash or hashlib.sha256(data).hexdigest()),
    )
    connection.commit()
    return connection


def test_walk_values_keeps_literal_text_and_instances():
    values = {(v["xml_path"], v["instance_index"]): v for v in walk_values(XML)}
    assert values[("/InformeMensalCRA/Ativo/@total", 0)]["raw_text"] == "10.5"
    assert values[("/InformeMensalCRA/Ativo/Nil", 0)]["xsi_nil"] is True
    assert values[("/InformeMensalCRA/Series/Serie/N", 1)]["raw_text"] == "2"
    assert not any(path.endswith("@nil") for path, _ in values)


def test_extraction_persists_states_evidence_and_masking(tmp_path):
    connection = _setup(tmp_path)
    result = RawXmlExtractionService(connection, tmp_path).extract_version(1, MAPPING)
    assert result["status"] == "success" and result["unmapped_fields_count"] == result["values"]
    report = connection.execute("SELECT * FROM extracted_reports").fetchone()
    assert report["reference_date"] == "2026-08-31" and report["source_version"] == "2"
    assert report["is_current"] == 0 and report["human_review_status"] == "pending"
    rows = {
        (r["xml_path"].rsplit("/", 1)[-1], r["instance_index"]): r
        for r in connection.execute(
            """SELECT v.*, e.evidence_excerpt, e.line_number, e.masking_applied
               FROM extracted_values v JOIN evidences e USING (extracted_value_id)"""
        )
    }
    assert rows[("Vazio", 0)]["field_state"] == "present_empty"
    assert rows[("Nil", 0)]["field_state"] == "present_empty" and rows[("Nil", 0)]["xsi_nil"] == 1
    assert rows[("Zero", 0)]["field_state"] == "present_value"
    assert rows[("Zero", 0)]["normalized_value"] is None
    assert rows[("N", 1)]["original_value"] == "2" and rows[("N", 1)]["line_number"] == 5
    assert rows[("CPF", 0)]["masking_applied"] == 1
    assert "123" not in rows[("CPF", 0)]["evidence_excerpt"]


def test_reprocessing_creates_new_run_and_keeps_previous(tmp_path):
    connection = _setup(tmp_path)
    service = RawXmlExtractionService(connection, tmp_path)
    first = service.extract_version(1, MAPPING)
    second = service.extract_version(1, MAPPING)
    assert first["extraction_run_id"] != second["extraction_run_id"]
    assert connection.execute("SELECT COUNT(*) FROM extracted_reports").fetchone()[0] == 2


def test_hash_mismatch_fails_run_without_values(tmp_path):
    connection = _setup(tmp_path, stored_hash="0" * 64)
    result = RawXmlExtractionService(connection, tmp_path).extract_version(1, MAPPING)
    assert result["status"] == "failed"
    run = connection.execute("SELECT status, error_message FROM extraction_runs").fetchone()
    assert run["status"] == "failed" and "hash" in run["error_message"]
    assert connection.execute("SELECT COUNT(*) FROM extracted_values").fetchone()[0] == 0
