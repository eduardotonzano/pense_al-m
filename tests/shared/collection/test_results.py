"""Testes dos resultados compartilhados de coleta."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pense_alm.shared.collection.enums import (
    CollectionRunStatus,
)
from pense_alm.shared.collection.errors import (
    CollectionError,
)
from pense_alm.shared.collection.raw_records import (
    RawCollectionRecord,
)
from pense_alm.shared.collection.responses import (
    CollectedResponse,
)
from pense_alm.shared.collection.results import (
    CollectionResult,
)
from pense_alm.shared.collection.runs import (
    CollectionRun,
)


def collection_time():
    return datetime(
        2026,
        9,
        20,
        10,
        0,
        tzinfo=UTC,
    )


def finished_time():
    return datetime(
        2026,
        9,
        20,
        11,
        0,
        tzinfo=UTC,
    )


def create_run(
    source_id,
    *,
    status=CollectionRunStatus.SUCCESS,
    requested_items=1,
    successful_items=1,
    failed_items=0,
):
    return CollectionRun(
        source_id=source_id,
        requested_items=requested_items,
        status=status,
        successful_items=successful_items,
        failed_items=failed_items,
        started_at=collection_time(),
        finished_at=finished_time(),
    )


def create_response(source_id):
    return CollectedResponse(
        request_id=uuid4(),
        source_id=source_id,
        payload=b"conteudo coletado",
        status_code=200,
        content_type="text/plain",
        response_url="https://example.com/data",
        collected_at=collection_time(),
    )


def create_raw_record(
    source_id,
    run_id,
):
    payload = b"conteudo coletado"

    return RawCollectionRecord(
        source_id=source_id,
        collection_run_id=run_id,
        payload=payload,
        payload_sha256=hashlib.sha256(
            payload
        ).hexdigest(),
        collected_at=collection_time(),
    )


def create_error(run_id):
    return CollectionError(
        error_type="TimeoutError",
        message="Tempo limite excedido.",
        retryable=True,
        category="timeout",
        run_id=run_id,
        item_reference="ABC123",
        attempt=1,
    )


def test_successful_collection_result():
    source_id = uuid4()

    run = create_run(source_id)
    response = create_response(source_id)
    raw_record = create_raw_record(
        source_id,
        run.run_id,
    )

    result = CollectionResult(
        run=run,
        responses=(response,),
        raw_records=(raw_record,),
    )

    assert result.run == run
    assert result.responses == (response,)
    assert result.raw_records == (raw_record,)
    assert result.errors == ()


def test_failed_collection_result():
    source_id = uuid4()

    run = create_run(
        source_id,
        status=CollectionRunStatus.FAILED,
        requested_items=1,
        successful_items=0,
        failed_items=1,
    )

    error = create_error(run.run_id)

    result = CollectionResult(
        run=run,
        errors=(error,),
    )

    assert result.run == run
    assert result.responses == ()
    assert result.raw_records == ()
    assert result.errors == (error,)


def test_result_rejects_response_from_other_source():
    run = create_run(uuid4())
    response = create_response(uuid4())

    with pytest.raises(
        ValueError,
        match="responses devem pertencer",
    ):
        CollectionResult(
            run=run,
            responses=(response,),
        )


def test_result_rejects_raw_record_from_other_source():
    source_id = uuid4()
    run = create_run(source_id)

    raw_record = create_raw_record(
        uuid4(),
        run.run_id,
    )

    with pytest.raises(
        ValueError,
        match="raw_records devem pertencer",
    ):
        CollectionResult(
            run=run,
            raw_records=(raw_record,),
        )
