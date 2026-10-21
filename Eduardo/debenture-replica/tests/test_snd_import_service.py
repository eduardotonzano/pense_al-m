from pathlib import Path

import pytest

from debenture_search.database import Database
from debenture_search.services.debenture_query_service import (
    DebentureQueryService,
)
from debenture_search.services.snd_import_service import SndImportService


PROJECT_DIR = Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"
FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_exemplo.html"
)
TABULAR_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_tabular_exemplo.txt"
)
IDENTITY_FIELDS = ("codigo_ativo", "isin", "emissor", "cnpj_emissor")


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "snd_import.db")
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(migration_sql)
        connection.commit()

    return {
        "db": db,
        "service": SndImportService(db),
        "html": FIXTURE_PATH.read_text(encoding="utf-8"),
    }


def identity_rows(context, debenture_id):
    rows = context["db"].fetch_all(
        """
        SELECT o.field_name, o.value_text, o.observed_at, s.code AS source_code
        FROM observations o
        JOIN sources s ON s.id = o.source_id
        WHERE o.debenture_id = ? AND o.field_name IN (?, ?, ?, ?)
        """,
        (debenture_id, *IDENTITY_FIELDS),
    )
    return {row["field_name"]: row for row in rows}


def table_identity(context, result):
    """Identificacao como esta em debentures/issuers, para comparar."""

    debenture = context["db"].fetch_one(
        "SELECT asset_code, isin FROM debentures WHERE id = ?",
        (result.debenture_id,),
    )
    issuer = context["db"].fetch_one(
        "SELECT cnpj, legal_name FROM issuers WHERE id = ?",
        (result.issuer_id,),
    )
    return {
        "codigo_ativo": debenture["asset_code"],
        "isin": debenture["isin"],
        "emissor": issuer["legal_name"],
        "cnpj_emissor": issuer["cnpj"],
    }


def test_imports_fixture(context):
    result = context["service"].import_html(
        context["html"],
        request_url="https://example.test/snd/EXMP12",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    assert result.status == "success"
    assert result.issuer_id is not None
    assert result.debenture_id > 0
    assert result.raw_record_id > 0
    assert result.observations_created > 0


def test_imports_identity_fields(context):
    result = context["service"].import_html(context["html"])

    debenture = context["db"].fetch_one(
        """
        SELECT asset_code, isin, issue_number, series, status
        FROM debentures
        WHERE id = ?
        """,
        (result.debenture_id,),
    )

    assert debenture["asset_code"] == "EXMP12"
    assert debenture["isin"] == "BREXMPDBS001"
    assert debenture["issue_number"] == "1"
    assert debenture["series"] == "2"
    assert debenture["status"] == "active"


def test_imports_issuer(context):
    result = context["service"].import_html(context["html"])

    issuer = context["db"].fetch_one(
        """
        SELECT cnpj, legal_name
        FROM issuers
        WHERE id = ?
        """,
        (result.issuer_id,),
    )

    assert issuer["cnpj"] == "12345678000199"
    assert issuer["legal_name"] == (
        "Companhia Exemplo de Energia S.A."
    )


def test_imports_observations(context):
    result = context["service"].import_html(context["html"])

    rows = context["db"].fetch_all(
        """
        SELECT field_name
        FROM observations
        WHERE debenture_id = ?
        """,
        (result.debenture_id,),
    )

    fields = {row["field_name"] for row in rows}

    assert "rating" in fields
    assert "spread" in fields
    assert "valor_nominal" in fields
    assert "data_vencimento" in fields


def test_preserves_original_html(context):
    result = context["service"].import_html(context["html"])

    raw = context["db"].fetch_one(
        """
        SELECT payload, content_type, processing_status
        FROM raw_records
        WHERE id = ?
        """,
        (result.raw_record_id,),
    )

    assert bytes(raw["payload"]).decode("utf-8") == context["html"]
    assert raw["content_type"] == "text/html"
    assert raw["processing_status"] == "processed"


def test_repeated_import_is_idempotent(context):
    first = context["service"].import_html(
        context["html"],
        observed_at="2026-09-10T12:00:00+00:00",
    )
    second = context["service"].import_html(
        context["html"],
        observed_at="2026-09-10T12:00:00+00:00",
    )

    assert first.debenture_id == second.debenture_id
    assert first.raw_record_id == second.raw_record_id
    assert second.observations_created == 0
    assert second.observations_reused == first.observations_created


def test_rejects_empty_html(context):
    with pytest.raises(ValueError, match="nao pode ficar vazio"):
        context["service"].import_html("   ")


def test_rejects_non_text_html(context):
    with pytest.raises(ValueError, match="fornecido como texto"):
        context["service"].import_html(b"html")


def test_parser_failure_does_not_create_financial_records(context):
    with pytest.raises(ValueError, match="codigo do ativo nem ISIN"):
        context["service"].import_html(
            "<html><body>sem identificadores</body></html>"
        )

    assert context["db"].fetch_one(
        "SELECT COUNT(*) AS total FROM debentures"
    )["total"] == 0
    assert context["db"].fetch_one(
        "SELECT COUNT(*) AS total FROM observations"
    )["total"] == 0


def test_creates_collection_and_audit(context):
    result = context["service"].import_html(context["html"])

    collection = context["db"].fetch_one(
        "SELECT status FROM collection_runs WHERE id = ?",
        (result.collection_run_id,),
    )
    audit = context["db"].fetch_one(
        """
        SELECT action, entity_type
        FROM audit_log
        WHERE entity_id = ?
        """,
        (result.debenture_id,),
    )

    assert collection["status"] == "success"
    assert audit["action"] == "ingest"
    assert audit["entity_type"] == "debenture"


def test_database_integrity(context):
    context["service"].import_html(context["html"])

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []


def test_records_identity_fields_as_observations(context):
    result = context["service"].import_html(
        context["html"],
        observed_at="2026-09-10T12:00:00+00:00",
    )

    rows = identity_rows(context, result.debenture_id)
    assert set(rows) == set(IDENTITY_FIELDS)
    assert rows["codigo_ativo"]["value_text"] == "EXMP12"
    assert rows["isin"]["value_text"] == "BREXMPDBS001"
    assert rows["cnpj_emissor"]["value_text"] == "12345678000199"
    # emissor e a razao social (issuers.legal_name), nao o nome fantasia.
    assert rows["emissor"]["value_text"] == "Companhia Exemplo de Energia S.A."
    for row in rows.values():
        assert row["source_code"] == "SND"
        assert row["observed_at"].startswith("2026-09-10T12:00:00")


def test_identity_observations_match_entity_tables(context):
    result = context["service"].import_html(context["html"])

    rows = identity_rows(context, result.debenture_id)

    assert {
        name: row["value_text"] for name, row in rows.items()
    } == table_identity(context, result)


def test_identity_observations_are_idempotent(context):
    kwargs = {"observed_at": "2026-09-10T12:00:00+00:00"}
    context["service"].import_html(context["html"], **kwargs)
    second = context["service"].import_html(context["html"], **kwargs)

    assert second.observations_created == 0
    total = context["db"].fetch_one(
        "SELECT COUNT(*) AS n FROM observations WHERE field_name IN (?, ?, ?, ?)",
        IDENTITY_FIELDS,
    )
    assert total["n"] == 4


def test_records_identity_fields_from_tabular_document(context):
    result = context["service"].import_document(
        TABULAR_PATH.read_text(encoding="utf-8"),
        asset_code="PETR27",
        content_type="text/plain",
        observed_at="2026-09-11T12:00:00+00:00",
    )

    rows = identity_rows(context, result.debenture_id)
    assert rows["codigo_ativo"]["value_text"] == "PETR27"
    assert rows["isin"]["value_text"] == "BRPETRDBS0C2"
    assert rows["cnpj_emissor"]["value_text"] == "33000167000101"
    assert rows["emissor"]["value_text"] == "PETROLEO BRASILEIRO S/A - PETROBRAS"
    assert {
        name: row["value_text"] for name, row in rows.items()
    } == table_identity(context, result)


def test_observations_share_one_timestamp_when_not_informed(context):
    result = context["service"].import_html(context["html"])

    stamps = context["db"].fetch_all(
        "SELECT DISTINCT observed_at FROM observations WHERE debenture_id = ?",
        (result.debenture_id,),
    )

    assert len(stamps) == 1


def test_current_values_expose_identity_with_source_and_date(context):
    result = context["service"].import_html(
        context["html"],
        observed_at="2026-09-10T12:00:00+00:00",
    )

    current = DebentureQueryService(context["db"]).current_values(
        result.debenture_id
    )

    assert current["isin"].value == "BREXMPDBS001"
    assert current["isin"].source_code == "SND"
    assert current["isin"].observed_at.startswith("2026-09-10T12:00:00")
    assert current["emissor"].value == "Companhia Exemplo de Energia S.A."
