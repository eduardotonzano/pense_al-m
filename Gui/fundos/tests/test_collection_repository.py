import pytest

from apoio import T0
from apoio import T1
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.source_repository import SourceRepository


@pytest.fixture
def runs(connection):
    return CollectionRunRepository(connection)


@pytest.fixture
def cvm(connection):
    return SourceRepository(connection).get_by_code("CVM_DADOS_ABERTOS").id


def test_start_and_finish(runs, cvm):
    run = runs.start(cvm, started_at=T0, requested_items=3)

    assert (run.status, run.finished_at, run.requested_items) == ("running", None, 3)

    finished = runs.finish(
        run.id,
        "partial",
        successful_items=2,
        failed_items=1,
        error_summary={"arquivo": "falha ficticia"},
        finished_at=T1,
    )

    assert finished.status == "partial"
    assert finished.finished_at == T1
    assert (finished.successful_items, finished.failed_items) == (2, 1)
    assert finished.errors == {"arquivo": "falha ficticia"}


def test_start_needs_existing_source_and_timezone(runs, cvm):
    with pytest.raises(ValueError, match="fonte"):
        runs.start(999)

    with pytest.raises(ValueError, match="fuso"):
        runs.start(cvm, started_at="2026-10-27T13:00:00")


def test_invalid_status_is_refused(runs, cvm):
    run = runs.start(cvm, started_at=T0)

    for status in ("running", "ok"):
        with pytest.raises(ValueError, match="Status"):
            runs.finish(run.id, status, successful_items=0, failed_items=0)


def test_negative_counters_and_end_before_start_are_refused(runs, cvm):
    run = runs.start(cvm, started_at=T1)

    with pytest.raises(ValueError, match="negativo"):
        runs.start(cvm, requested_items=-1)

    with pytest.raises(ValueError, match="negativo"):
        runs.finish(run.id, "success", successful_items=-1, failed_items=0)

    with pytest.raises(ValueError, match="anterior"):
        runs.finish(run.id, "success", successful_items=0, failed_items=0, finished_at=T0)


def test_finished_run_cannot_be_finished_again(runs, cvm):
    run = runs.start(cvm, started_at=T0)
    runs.finish(run.id, "success", successful_items=1, failed_items=0, finished_at=T1)

    with pytest.raises(ValueError, match="encerrada"):
        runs.finish(run.id, "failed", successful_items=0, failed_items=1)

    assert runs.get_by_id(run.id).status == "success"
