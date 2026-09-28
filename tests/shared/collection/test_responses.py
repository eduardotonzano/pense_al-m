"""Testes das respostas compartilhadas de coleta."""

from datetime import UTC, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from pense_alm.shared.collection.responses import (
    CollectedResponse,
)


def create_response(**overrides):
    values = {
        "request_id": uuid4(),
        "source_id": uuid4(),
        "payload": "conteudo coletado",
        "status_code": 200,
        "content_type": "text/plain",
        "response_url": "https://example.com/data",
        "headers": {
            "Content-Type": "text/plain",
        },
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

    return CollectedResponse(**values)


def test_response_converts_text_payload_to_bytes():
    response = create_response(
        payload="conteudo coletado"
    )

    assert response.payload == b"conteudo coletado"
    assert response.text == "conteudo coletado"


def test_response_accepts_bytearray_payload():
    response = create_response(
        payload=bytearray(b"conteudo")
    )

    assert response.payload == b"conteudo"


def test_response_calculates_size():
    response = create_response(
        payload=b"12345"
    )

    assert response.size_bytes == 5


def test_response_calculates_sha256():
    response = create_response(
        payload=b"abc"
    )

    assert response.payload_sha256 == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )


def test_response_protects_headers():
    response = create_response()

    assert isinstance(
        response.headers,
        MappingProxyType,
    )

    with pytest.raises(TypeError):
        response.headers["Content-Type"] = (
            "application/json"
        )


def test_response_copies_headers():
    headers = {
        "Content-Type": "text/plain",
    }

    response = create_response(
        headers=headers
    )

    headers["Content-Type"] = "application/json"

    assert response.headers["Content-Type"] == (
        "text/plain"
    )


def test_response_converts_collected_at_to_utc():
    response = create_response(
        collected_at=datetime.fromisoformat(
            "2026-09-20T10:00:00-03:00"
        )
    )

    assert response.collected_at == datetime(
        2026,
        9,
        20,
        13,
        0,
        tzinfo=UTC,
    )


def test_response_rejects_empty_payload():
    with pytest.raises(
        ValueError,
        match="payload nao pode ser vazio",
    ):
        create_response(payload=b"")


def test_response_rejects_invalid_payload_type():
    with pytest.raises(
        TypeError,
        match="payload deve ser texto ou bytes",
    ):
        create_response(payload=123)


def test_response_rejects_boolean_status():
    with pytest.raises(
        TypeError,
        match="status_code deve ser inteiro",
    ):
        create_response(status_code=True)


def test_response_rejects_invalid_status_range():
    with pytest.raises(
        ValueError,
        match="entre 100 e 599",
    ):
        create_response(status_code=99)


def test_response_accepts_missing_http_metadata():
    response = create_response(
        status_code=None,
        content_type=None,
        response_url=None,
    )

    assert response.status_code is None
    assert response.content_type is None
    assert response.response_url is None


def test_response_rejects_naive_collected_at():
    with pytest.raises(
        ValueError,
        match="deve possuir timezone",
    ):
        create_response(
            collected_at=datetime(
                2026,
                9,
                20,
                10,
                0,
            )
        )
