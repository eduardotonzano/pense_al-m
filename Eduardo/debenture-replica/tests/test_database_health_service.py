import pathlib

from debenture_search.database import Database
from debenture_search.services.database_health_service import (
    DatabaseHealthReport,
    DatabaseHealthService,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"


def create_context(tmp_path):
    db = Database(tmp_path / "data" / "health.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    service = DatabaseHealthService(
        db,
        backup_dir=tmp_path / "backups",
    )

    return db, service


def test_healthy_database(tmp_path):
    _, service = create_context(tmp_path)
    report = service.check()

    assert isinstance(report, DatabaseHealthReport)
    assert report.healthy is True
    assert report.status == "healthy"
    assert report.integrity == "ok"
    assert report.foreign_key_errors == ()
    assert report.migration_version == 1
    assert report.missing_tables == ()
    assert report.missing_views == ()
    assert report.missing_sources == ()


def test_reports_database_size(tmp_path):
    _, service = create_context(tmp_path)
    report = service.check()

    assert report.database_size_bytes > 0


def test_detects_stuck_collection(tmp_path):
    db, service = create_context(tmp_path)
    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = 'SND'"
    )

    with db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO collection_runs (source_id, status)
            VALUES (?, 'running')
            """,
            (source["id"],),
        )

    report = service.check()

    assert report.healthy is False
    assert report.stuck_collection_runs == 1
    assert "Existem coletas presas em running." in report.issues


def test_counts_pending_raw_records_without_failing_health(tmp_path):
    db, service = create_context(tmp_path)
    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = 'SND'"
    )

    with db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO raw_records (
                source_id, payload, payload_sha256,
                processing_status
            )
            VALUES (?, ?, ?, 'pending')
            """,
            (source["id"], b"payload", "a" * 64),
        )

    report = service.check()

    assert report.pending_raw_records == 1
    assert report.healthy is True


def test_detects_failed_raw_record(tmp_path):
    db, service = create_context(tmp_path)
    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = 'SND'"
    )

    with db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO raw_records (
                source_id, payload, payload_sha256,
                processing_status, processing_error
            )
            VALUES (?, ?, ?, 'failed', ?)
            """,
            (
                source["id"],
                b"payload",
                "b" * 64,
                "Parser falhou",
            ),
        )

    report = service.check()

    assert report.failed_raw_records == 1
    assert report.healthy is False


def test_detects_open_conflict(tmp_path):
    db, service = create_context(tmp_path)
    snd = db.fetch_one(
        "SELECT id FROM sources WHERE code = 'SND'"
    )
    manual = db.fetch_one(
        "SELECT id FROM sources WHERE code = 'MANUAL'"
    )

    with db.transaction() as connection:
        debenture_id = connection.execute(
            "INSERT INTO debentures (asset_code) VALUES ('HLTH12')"
        ).lastrowid
        first = connection.execute(
            """
            INSERT INTO observations (
                debenture_id, source_id, field_name,
                value_type, value_text, observed_at, checksum
            )
            VALUES (?, ?, 'rating', 'text', 'AAA', ?, ?)
            """,
            (
                debenture_id,
                snd["id"],
                "2026-09-10T12:00:00+00:00",
                "c" * 64,
            ),
        ).lastrowid
        second = connection.execute(
            """
            INSERT INTO observations (
                debenture_id, source_id, field_name,
                value_type, value_text, observed_at, checksum
            )
            VALUES (?, ?, 'rating', 'text', 'AA-', ?, ?)
            """,
            (
                debenture_id,
                manual["id"],
                "2026-09-10T12:00:00+00:00",
                "d" * 64,
            ),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO data_conflicts (
                debenture_id, field_name,
                observation_a_id, observation_b_id
            )
            VALUES (?, 'rating', ?, ?)
            """,
            (debenture_id, first, second),
        )

    report = service.check()

    assert report.open_conflicts == 1
    assert report.healthy is False


def test_detects_missing_required_source(tmp_path):
    db, service = create_context(tmp_path)

    with db.transaction() as connection:
        connection.execute(
            "DELETE FROM sources WHERE code = 'CVM'"
        )

    report = service.check()

    assert report.missing_sources == ("CVM",)
    assert report.healthy is False


def test_reports_backup_information(tmp_path):
    _, service = create_context(tmp_path)
    service.backup_dir.mkdir(parents=True, exist_ok=True)
    backup = service.backup_dir / "debenture_20260910T120000Z.sqlite3"
    backup.write_bytes(b"backup")

    report = service.check()

    assert report.backup_count == 1
    assert report.latest_backup is not None


def test_lists_required_objects(tmp_path):
    _, service = create_context(tmp_path)

    tables = service.list_objects("table")
    views = service.list_objects("view")

    assert "debentures" in tables
    assert "observations" in tables
    assert "current_observations" in views


def test_database_remains_integral_after_check(tmp_path):
    db, service = create_context(tmp_path)
    service.check()

    assert db.integrity_check() == "ok"
    assert db.foreign_key_check() == []
