"""Testes das execucoes compartilhadas de coleta."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pense_alm.shared.collection.enums import (
    CollectionRunStatus,
)
from pense_alm.shared.collection.runs import (
    CollectionRun,
)


def started_at():
    return datetime(
        2026,
        9,
        20,
        10,
        0,
        tzinfo=UTC,
    )


def finished_at():
    return datetime(
        2026,
        9,
        20,
        11,
        0,
        tzinfo=UTC,
    )


def test_running_collection_is_valid():
    run = CollectionRun(
        source_id=uuid4(),
        requested_items=3,
        started_at=started_at(),
    )

    assert run.status is CollectionRunStatus.RUNNING
    assert run.successful_items == 0
    assert run.failed_items == 0
    assert run.finished_at is None


def test_successful_collection_is_valid():
    run = CollectionRun(
        source_id=uuid4(),
        requested_items=3,
        status=CollectionRunStatus.SUCCESS,
        successful_items=3,
        failed_items=0,
        started_at=started_at(),
        finished_at=finished_at(),
    )

    assert run.status is CollectionRunStatus.SUCCESS
    assert run.successful_items == 3


def test_partial_collection_is_valid():
    run = CollectionRun(
        source_id=uuid4(),
        requested_items=3,
        status=CollectionRunStatus.PARTIAL,
        successful_items=2,
        failed_items=1,
        started_at=started_at(),
        finished_at=finished_at(),
    )

    assert run.successful_items == 2
    assert run.failed_items == 1


def test_failed_collection_is_valid():
    run = CollectionRun(
        source_id=uuid4(),
        requested_items=3,
        status=CollectionRunStatus.FAILED,
        successful_items=0,
        failed_items=3,
        started_at=started_at(),
        finished_at=finished_at(),
    )

    assert run.failed_items == 3


def test_cancelled_collection_is_valid():
    run = CollectionRun(
        source_id=uuid4(),
        requested_items=3,
        status=CollectionRunStatus.CANCELLED,
        started_at=started_at(),
        finished_at=finished_at(),
    )

    assert run.status is CollectionRunStatus.CANCELLED


def test_run_converts_dates_to_utc():
    run = CollectionRun(
        source_id=uuid4(),
        requested_items=1,
        status=CollectionRunStatus.SUCCESS,
        successful_items=1,
        started_at=datetime.fromisoformat(
            "2026-09-20T10:00:00-03:00"
        ),
        finished_at=datetime.fromisoformat(
            "2026-09-20T11:00:00-03:00"
        ),
    )

    assert run.started_at == datetime(
        2026,
        9,
        20,
        13,
        0,
        tzinfo=UTC,
    )
    assert run.finished_at == datetime(
        2026,
        9,
        20,
        14,
        0,
        tzinfo=UTC,
    )


def test_run_rejects_invalid_status():
    with pytest.raises(
        TypeError,
        match="CollectionRunStatus",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            status="running",
        )


def test_run_rejects_negative_counter():
    with pytest.raises(
        ValueError,
        match="nao pode ser negativo",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=-1,
        )


def test_run_rejects_boolean_counter():
    with pytest.raises(
        TypeError,
        match="deve ser inteiro",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=True,
        )


def test_run_rejects_processed_above_requested():
    with pytest.raises(
        ValueError,
        match="nao pode exceder",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            successful_items=2,
        )


def test_running_run_rejects_finished_at():
    with pytest.raises(
        ValueError,
        match="running nao pode possuir",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            started_at=started_at(),
            finished_at=finished_at(),
        )


def test_finalized_run_requires_finished_at():
    with pytest.raises(
        ValueError,
        match="finalizada deve possuir",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            status=CollectionRunStatus.SUCCESS,
            successful_items=1,
            started_at=started_at(),
        )


def test_success_rejects_failed_items():
    with pytest.raises(
        ValueError,
        match="success nao pode possuir",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=2,
            status=CollectionRunStatus.SUCCESS,
            successful_items=1,
            failed_items=1,
            started_at=started_at(),
            finished_at=finished_at(),
        )


def test_failed_requires_failed_items():
    with pytest.raises(
        ValueError,
        match="ao menos uma falha",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            status=CollectionRunStatus.FAILED,
            failed_items=0,
            started_at=started_at(),
            finished_at=finished_at(),
        )


def test_run_rejects_inverted_dates():
    with pytest.raises(
        ValueError,
        match="nao pode ser anterior",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            status=CollectionRunStatus.CANCELLED,
            started_at=finished_at(),
            finished_at=started_at(),
        )


def test_run_rejects_naive_started_at():
    with pytest.raises(
        ValueError,
        match="started_at deve possuir timezone",
    ):
        CollectionRun(
            source_id=uuid4(),
            requested_items=1,
            started_at=datetime(
                2026,
                9,
                20,
                10,
                0,
            ),
        )
