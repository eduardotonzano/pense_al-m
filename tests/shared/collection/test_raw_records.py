"""Testes dos registros brutos compartilhados."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pense_alm.shared.collection.enums import (
    RawRecordStatus,
)
from pense_alm.shared.collection.raw_records import (
    RawCollectionRecord,
)


def create_raw_record(**overrides):
    payload = overrides.pop(
        "payload",
        b"conteudo bruto",
    )

    values = {
        "source_id": uuid4(),
        "payload": payload,
        "payload_sha256": hashlib.sha256(
            payload
        ).hexdigest(),
        "collected_at": datetime(
            2026,
            9,
            20,
            10,
            0,
            tzinfo=UTC,
        ),
    }

    values.update(overrides)

    return RawCollectionRecord(**values)


def test_raw_record_accepts_pending_payload():
    record = create_raw_record()

    assert record.status is RawRecordStatus.PENDING
    assert record.payload == b"conteudo bruto"
    assert record.processing_error is None


def test_raw_record_accepts_collection_links():
    collection_run_id = uuid4()
    request_id = uuid4()
    response_id = uuid4()

    record = create_raw_record(
        collection_run_id=collection_run_id,
        request_id=request_id,
        response_id=response_id,
    )

    assert record.collection_run_id == collection_run_id
    assert record.request_id == request_id
    assert record.response_id == response_id


def test_raw_record_normalizes_hash_to_lowercase():
    payload = b"conteudo"
    payload_hash = hashlib.sha256(
        payload
    ).hexdigest().upper()

    record = create_raw_record(
        payload=payload,
        payload_sha256=payload_hash,
    )

    assert record.payload_sha256 == (
        payload_hash.lower()
    )


def test_raw_record_converts_collected_at_to_utc():
    record = create_raw_record(
        collected_at=datetime.fromisoformat(
            "2026-09-20T10:00:00-03:00"
        )
    )

    assert record.collected_at == datetime(
        2026,
        9,
        20,
        13,
        0,
        tzinfo=UTC,
    )


def test_raw_record_normalizes_optional_text():
    record = create_raw_record(
        content_type="  application/json  ",
        parser_version="  2.0.0  ",
    )

    assert record.content_type == "application/json"
    assert record.parser_version == "2.0.0"


def test_failed_record_requires_error():
    with pytest.raises(
        ValueError,
        match="failed deve possuir",
    ):
        create_raw_record(
            status=RawRecordStatus.FAILED,
        )


def test_failed_record_accepts_error():
    record = create_raw_record(
        status=RawRecordStatus.FAILED,
        processing_error="  Falha   de parsing.  ",
    )

    assert record.processing_error == (
        "Falha de parsing."
    )


def test_non_failed_record_rejects_error():
    with pytest.raises(
        ValueError,
        match="somente pode ser informado",
    ):
        create_raw_record(
            status=RawRecordStatus.PROCESSED,
            processing_error="Erro indevido.",
        )


def test_raw_record_rejects_empty_payload():
    with pytest.raises(
        ValueError,
        match="payload nao pode ser vazio",
    ):
        create_raw_record(
            payload=b"",
            payload_sha256="0" * 64,
        )


def test_raw_record_rejects_invalid_hash():
    with pytest.raises(
        ValueError,
        match="SHA-256 valido",
    ):
        create_raw_record(
            payload_sha256="invalid",
        )


def test_raw_record_rejects_invalid_status():
    with pytest.raises(
        TypeError,
        match="RawRecordStatus",
    ):
        create_raw_record(
            status="pending",
        )


def test_raw_record_rejects_boolean_http_status():
    with pytest.raises(
        TypeError,
        match="http_status deve ser inteiro",
    ):
        create_raw_record(
            http_status=True,
        )


def test_raw_record_rejects_invalid_http_status():
    with pytest.raises(
        ValueError,
        match="entre 100 e 599",
    ):
        create_raw_record(
            http_status=600,
        )


def test_raw_record_rejects_naive_collected_at():
    with pytest.raises(
        ValueError,
        match="deve possuir timezone",
    ):
        create_raw_record(
            collected_at=datetime(
                2026,
                9,
                20,
                10,
                0,
            ),
        )
