import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.services.ingestion_service import (
    IngestionResult,
    IngestionService,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "ingestion.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    return {
        "db": db,
        "service": IngestionService(db),
    }


def base_ingestion(service, source="SND", rating="AA-"):
    return service.ingest(
        source_code=source,
        payload="<html>TEST12</html>",
        asset_code="TEST12",
        isin="BRTESTDBS001",
        issuer_legal_name="Companhia Teste S.A.",
        issuer_cnpj="12345678000199",
        observations=[
            {
                "field_name": "rating",
                "value_type": "text",
                "value": rating,
                "observed_at": "2026-09-10T12:00:00+00:00",
            },
            {
                "field_name": "spread",
                "value_type": "numeric",
                "value": "2.5",
                "unit": "percentual",
                "observed_at": "2026-09-10T12:00:00+00:00",
            },
        ],
        content_type="text/html",
        http_status=200,
        parser_version="1.0.0",
    )


def test_complete_ingestion(context):
    result = base_ingestion(context["service"])

    assert isinstance(result, IngestionResult)
    assert result.status == "success"
    assert result.issuer_id is not None
    assert result.observations_created == 2
    assert result.observations_reused == 0


def test_ingestion_creates_linked_records(context):
    result = base_ingestion(context["service"])
    db = context["db"]

    assert db.fetch_one(
        "SELECT id FROM issuers WHERE id = ?",
        (result.issuer_id,),
    ) is not None
    assert db.fetch_one(
        "SELECT id FROM debentures WHERE id = ?",
        (result.debenture_id,),
    ) is not None
    assert db.fetch_one(
        "SELECT id FROM raw_records WHERE id = ?",
        (result.raw_record_id,),
    ) is not None


def test_ingestion_finishes_collection(context):
    result = base_ingestion(context["service"])
    run = context["db"].fetch_one(
        "SELECT status FROM collection_runs WHERE id = ?",
        (result.collection_run_id,),
    )

    assert run["status"] == "success"


def test_ingestion_marks_raw_record_processed(context):
    result = base_ingestion(context["service"])
    raw = context["db"].fetch_one(
        "SELECT processing_status FROM raw_records WHERE id = ?",
        (result.raw_record_id,),
    )

    assert raw["processing_status"] == "processed"


def test_ingestion_creates_audit_record(context):
    result = base_ingestion(context["service"])
    audit = context["db"].fetch_one(
        """
        SELECT action, entity_type, entity_id
        FROM audit_log
        WHERE entity_id = ?
        """,
        (result.debenture_id,),
    )

    assert audit["action"] == "ingest"
    assert audit["entity_type"] == "debenture"


def test_rejects_unknown_source(context):
    with pytest.raises(ValueError, match="fonte informada nao existe"):
        context["service"].ingest(
            source_code="INEXISTENTE",
            payload="conteudo",
            asset_code="TEST12",
        )


def test_rejects_disabled_source(context):
    with pytest.raises(ValueError, match="esta desativada"):
        context["service"].ingest(
            source_code="ANBIMA_API",
            payload="conteudo",
            asset_code="TEST12",
        )


def test_failed_ingestion_is_recorded(context):
    with pytest.raises(ValueError, match="codigo do ativo ou o ISIN"):
        context["service"].ingest(
            source_code="SND",
            payload="conteudo",
            observations=[],
        )

    run = context["db"].fetch_one(
        """
        SELECT status, failed_items
        FROM collection_runs
        ORDER BY id DESC
        LIMIT 1
        """
    )

    assert run["status"] == "failed"
    assert run["failed_items"] >= 1


def test_repeated_ingestion_reuses_data(context):
    first = base_ingestion(context["service"])
    second = base_ingestion(context["service"])

    assert first.debenture_id == second.debenture_id
    assert first.raw_record_id == second.raw_record_id
    assert second.observations_created == 0
    assert second.observations_reused == 2


def test_conflict_is_created_for_different_sources(context):
    base_ingestion(context["service"], source="SND", rating="AAA")

    result = context["service"].ingest(
        source_code="MANUAL",
        payload="rating manual AA-",
        asset_code="TEST12",
        observations=[
            {
                "field_name": "rating",
                "value_type": "text",
                "value": "AA-",
                "observed_at": "2026-09-10T12:00:00+00:00",
                "confidence": "manual",
            }
        ],
    )

    assert result.conflicts_created == 1
    assert context["db"].fetch_one(
        "SELECT COUNT(*) AS total FROM data_conflicts"
    )["total"] == 1


def test_database_integrity(context):
    base_ingestion(context["service"])

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
