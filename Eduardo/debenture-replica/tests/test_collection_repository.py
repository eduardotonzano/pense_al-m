import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.collection_repository import (
    CollectionRepository,
    CollectionRunRecord,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "collections.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("SND",),
    )

    return {
        "db": db,
        "source_id": int(source["id"]),
        "repository": CollectionRepository(db),
    }


def test_start_collection(context):
    record = context["repository"].start(
        context["source_id"],
        requested_items=10,
    )

    assert isinstance(record, CollectionRunRecord)
    assert record.status == "running"
    assert record.requested_items == 10
    assert record.successful_items == 0
    assert record.failed_items == 0
    assert record.finished_at is None


def test_rejects_unknown_source(context):
    with pytest.raises(ValueError, match="fonte informada nao existe"):
        context["repository"].start(999999)


def test_rejects_negative_requested_count(context):
    with pytest.raises(ValueError, match="nao pode ser negativo"):
        context["repository"].start(
            context["source_id"],
            requested_items=-1,
        )


def test_finish_success(context):
    repository = context["repository"]
    started = repository.start(
        context["source_id"],
        requested_items=3,
    )

    finished = repository.finish(
        started.id,
        status="success",
        successful_items=3,
        failed_items=0,
    )

    assert finished.status == "success"
    assert finished.successful_items == 3
    assert finished.failed_items == 0
    assert finished.finished_at is not None


def test_finish_partial_with_errors(context):
    repository = context["repository"]
    started = repository.start(
        context["source_id"],
        requested_items=5,
    )

    finished = repository.finish(
        started.id,
        status="partial",
        successful_items=4,
        failed_items=1,
        errors={"TEST12": "timeout"},
    )

    assert finished.status == "partial"
    assert finished.errors == {"TEST12": "timeout"}


def test_finish_failed_requires_failure(context):
    repository = context["repository"]
    started = repository.start(context["source_id"])

    with pytest.raises(ValueError, match="ao menos uma falha"):
        repository.finish(started.id, status="failed")


def test_success_rejects_failures(context):
    repository = context["repository"]
    started = repository.start(context["source_id"])

    with pytest.raises(ValueError, match="success nao pode ter falhas"):
        repository.finish(
            started.id,
            status="success",
            failed_items=1,
        )


def test_rejects_processed_above_requested(context):
    repository = context["repository"]
    started = repository.start(
        context["source_id"],
        requested_items=2,
    )

    with pytest.raises(ValueError, match="excede"):
        repository.finish(
            started.id,
            status="partial",
            successful_items=2,
            failed_items=1,
        )


def test_cannot_finish_twice(context):
    repository = context["repository"]
    started = repository.start(context["source_id"])
    repository.finish(started.id, status="success")

    with pytest.raises(ValueError, match="ja foi finalizada"):
        repository.finish(started.id, status="success")


def test_cancel_collection(context):
    repository = context["repository"]
    started = repository.start(context["source_id"])

    cancelled = repository.cancel(
        started.id,
        reason="interrompida pelo usuario",
    )

    assert cancelled.status == "cancelled"
    assert cancelled.errors == {
        "reason": "interrompida pelo usuario"
    }


def test_get_by_id(context):
    created = context["repository"].start(
        context["source_id"]
    )

    found = context["repository"].get_by_id(created.id)

    assert found is not None
    assert found.id == created.id


def test_list_by_source_and_status(context):
    repository = context["repository"]
    first = repository.start(context["source_id"])
    second = repository.start(context["source_id"])
    repository.finish(first.id, status="success")

    all_runs = repository.list_by_source(context["source_id"])
    running = repository.list_by_source(
        context["source_id"],
        status="running",
    )

    assert len(all_runs) == 2
    assert len(running) == 1
    assert running[0].id == second.id


def test_count_with_filters(context):
    repository = context["repository"]
    first = repository.start(context["source_id"])
    repository.start(context["source_id"])
    repository.finish(first.id, status="success")

    assert repository.count() == 2
    assert repository.count(context["source_id"]) == 2
    assert repository.count(status="success") == 1
    assert repository.count(status="running") == 1


def test_database_integrity(context):
    repository = context["repository"]
    started = repository.start(context["source_id"])
    repository.finish(started.id, status="success")

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
