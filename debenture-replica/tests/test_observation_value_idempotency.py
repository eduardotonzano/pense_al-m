from pathlib import Path
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import DebentureRepository
from debenture_search.repositories.observation_repository import ObservationRepository


def create_context(tmp_path):
    db = Database(tmp_path / "idempotency.db")
    migration = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "001_initial_schema.sql"
    ).read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(migration)
        connection.commit()

    debenture = DebentureRepository(db).create(asset_code="IDEM12")
    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("SND",),
    )

    return db, ObservationRepository(db), debenture.id, int(source["id"])


def test_same_value_with_different_observed_at_is_reused(tmp_path):
    _, repository, debenture_id, source_id = create_context(tmp_path)
    first_time = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
    second_time = first_time + timedelta(hours=2)

    first, first_created = repository.create(
        debenture_id=debenture_id,
        source_id=source_id,
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at=first_time,
    )
    second, second_created = repository.create(
        debenture_id=debenture_id,
        source_id=source_id,
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at=second_time,
    )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert repository.count(debenture_id, "rating") == 1


def test_changed_value_creates_history(tmp_path):
    _, repository, debenture_id, source_id = create_context(tmp_path)

    first, first_created = repository.create(
        debenture_id=debenture_id,
        source_id=source_id,
        field_name="rating",
        value_type="text",
        value="A+",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    second, second_created = repository.create(
        debenture_id=debenture_id,
        source_id=source_id,
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at="2026-09-11T14:00:00+00:00",
    )

    assert first_created is True
    assert second_created is True
    assert second.id != first.id
    assert repository.count(debenture_id, "rating") == 2


def test_same_value_from_different_source_is_not_reused(tmp_path):
    db, repository, debenture_id, snd_id = create_context(tmp_path)
    manual = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("MANUAL",),
    )

    snd, snd_created = repository.create(
        debenture_id=debenture_id,
        source_id=snd_id,
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    manual_record, manual_created = repository.create(
        debenture_id=debenture_id,
        source_id=int(manual["id"]),
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at="2026-09-11T14:00:00+00:00",
    )

    assert snd_created is True
    assert manual_created is True
    assert manual_record.id != snd.id

