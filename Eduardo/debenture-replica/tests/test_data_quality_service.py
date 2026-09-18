import pathlib
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import DebentureRepository
from debenture_search.repositories.issuer_repository import IssuerRepository
from debenture_search.repositories.observation_repository import ObservationRepository
from debenture_search.services.data_quality_service import DataQualityReport
from debenture_search.services.data_quality_service import DataQualityService


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"


def create_context(tmp_path):
    db = Database(tmp_path / "quality.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    issuers = IssuerRepository(db)
    debentures = DebentureRepository(db)
    observations = ObservationRepository(db)
    service = DataQualityService(db, stale_days=30)
    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = 'SND'"
    )

    return db, issuers, debentures, observations, service, int(source["id"])


def test_empty_database_is_healthy(tmp_path):
    _, _, _, _, service, _ = create_context(tmp_path)
    report = service.check()

    assert isinstance(report, DataQualityReport)
    assert report.status == "healthy"
    assert report.valid is True
    assert report.issue_count == 0


def test_detects_debenture_without_issuer(tmp_path):
    _, _, debentures, _, service, _ = create_context(tmp_path)
    debentures.create(asset_code="QUAL12")

    report = service.check()
    codes = {item.code for item in report.issues}

    assert "DEBENTURE_WITHOUT_ISSUER" in codes
    assert report.status == "attention"


def test_detects_debenture_without_observations(tmp_path):
    _, issuers, debentures, _, service, _ = create_context(tmp_path)
    issuer = issuers.create(
        legal_name="Empresa",
        cnpj="12345678000199",
    )
    debentures.create(asset_code="QUAL13", issuer_id=issuer.id)

    report = service.check()
    codes = {item.code for item in report.issues}

    assert "DEBENTURE_WITHOUT_OBSERVATIONS" in codes


def test_detects_non_positive_value(tmp_path):
    _, issuers, debentures, observations, service, source_id = create_context(tmp_path)
    issuer = issuers.create("Empresa", "12345678000199")
    debenture = debentures.create("QUAL14", issuer_id=issuer.id)
    observations.create(
        debenture.id,
        source_id,
        "valor nominal",
        "numeric",
        0,
        observed_at=datetime.now(timezone.utc),
    )

    report = service.check()

    assert report.status == "critical"
    assert "NON_POSITIVE_FINANCIAL_VALUE" in {
        item.code for item in report.issues
    }


def test_detects_suspect_observation(tmp_path):
    _, issuers, debentures, observations, service, source_id = create_context(tmp_path)
    issuer = issuers.create("Empresa", "12345678000199")
    debenture = debentures.create("QUAL15", issuer_id=issuer.id)
    observations.create(
        debenture.id,
        source_id,
        "rating",
        "text",
        "AA-",
        observed_at=datetime.now(timezone.utc),
        confidence="suspect",
    )

    report = service.check()

    assert "SUSPECT_OBSERVATION" in {
        item.code for item in report.issues
    }


def test_detects_stale_current_observation(tmp_path):
    _, issuers, debentures, observations, service, source_id = create_context(tmp_path)
    issuer = issuers.create("Empresa", "12345678000199")
    debenture = debentures.create("QUAL16", issuer_id=issuer.id)
    old_date = datetime.now(timezone.utc) - timedelta(days=60)
    observations.create(
        debenture.id,
        source_id,
        "rating",
        "text",
        "AA-",
        observed_at=old_date,
    )

    report = service.check()

    assert "STALE_CURRENT_OBSERVATION" in {
        item.code for item in report.issues
    }


def test_detects_failed_collection(tmp_path):
    db, _, _, _, service, source_id = create_context(tmp_path)

    with db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO collection_runs (
                source_id, status, failed_items, finished_at
            )
            VALUES (?, 'failed', 1, ?)
            """,
            (source_id, datetime.now(timezone.utc).isoformat()),
        )

    report = service.check()

    assert "FAILED_COLLECTION" in {
        item.code for item in report.issues
    }


def test_valid_data_has_no_issues(tmp_path):
    _, issuers, debentures, observations, service, source_id = create_context(tmp_path)
    issuer = issuers.create("Empresa", "12345678000199")
    debenture = debentures.create("QUAL17", issuer_id=issuer.id)
    observations.create(
        debenture.id,
        source_id,
        "valor nominal",
        "numeric",
        1000,
        observed_at=datetime.now(timezone.utc),
    )

    report = service.check()

    assert report.status == "healthy"
    assert report.issue_count == 0
    assert report.total_debentures == 1
    assert report.total_observations == 1


def test_report_counts_severities(tmp_path):
    _, _, debentures, _, service, _ = create_context(tmp_path)
    debentures.create("QUAL18")

    report = service.check()

    assert report.warning_count == 2
    assert report.critical_count == 0
    assert report.issue_count == 2


def test_database_integrity_after_check(tmp_path):
    db, _, _, _, service, _ = create_context(tmp_path)
    service.check()

    assert db.integrity_check() == "ok"
    assert db.foreign_key_check() == []
