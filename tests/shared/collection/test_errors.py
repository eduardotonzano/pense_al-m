"""Testes dos erros compartilhados de coleta."""

from uuid import uuid4

import pytest

from pense_alm.shared.collection.errors import (
    CollectionError,
)


def create_error(**overrides):
    values = {
     "error_type": "TimeoutError",
        "message": "Tempo limite excedido.",
        "retryable": True,
        "category": "timeout",
    }

    values.update(overrides)

    return CollectionError(**values)


def test_error_normalizes_text_fields():
    error = create_error(
        error_type="  TimeoutError  ",
        message="  Tempo   limite excedido.  ",
        category="  TIMEOUT  ",
    )

    assert error.error_type == "TimeoutError"
    assert error.message == "Tempo limite excedido."
    assert error.category == "timeout"


def test_error_accepts_optional_references():
    run_id = uuid4()
    request_id = uuid4()

    error = create_error(
        run_id=run_id,
        request_id=request_id,
        item_reference="  ABC123  ",
        http_status=503,
        attempt=2,
    )

    assert error.run_id == run_id
    assert error.request_id == request_id
    assert error.item_reference == "ABC123"
    assert error.http_status == 503
    assert error.attempt == 2


def test_error_accepts_missing_optional_fields():
    error = create_error()

    assert error.run_id is None
    assert error.request_id is None
    assert error.item_reference is None
    assert error.http_status is None
    assert error.attempt == 1


def test_error_rejects_empty_error_type():
    with pytest.raises(
        ValueError,
        match="error_type nao pode ser vazio",
    ):
        create_error(error_type="   ")


def test_error_rejects_empty_message():
    with pytest.raises(
        ValueError,
        match="message nao pode ser vazio",
    ):
        create_error(message="   ")


def test_error_rejects_empty_category():
    with pytest.raises(
        ValueError,
        match="category nao pode ser vazio",
    ):
        create_error(category="   ")


def test_error_rejects_invalid_run_id():
    with pytest.raises(
        TypeError,
        match="run_id deve ser UUID ou None",
    ):
        create_error(run_id="invalid")


def test_error_rejects_invalid_request_id():
    with pytest.raises(
        TypeError,
        match="request_id deve ser UUID ou None",
    ):
        create_error(request_id="invalid")


def test_error_rejects_invalid_retryable():
    with pytest.raises(
        TypeError,
        match="retryable deve ser booleano",
    ):
        create_error(retryable="sim")


def test_error_rejects_boolean_http_status():
    with pytest.raises(
        TypeError,
        match="http_status deve ser inteiro",
    ):
        create_error(http_status=True)


def test_error_rejects_invalid_http_status():
    with pytest.raises(
        ValueError,
        match="entre 100 e 599",
    ):
        create_error(http_status=600)


def test_error_rejects_boolean_attempt():
    with pytest.raises(
        TypeError,
        match="attempt deve ser inteiro",
    ):
        create_error(attempt=True)


def test_error_rejects_non_positive_attempt():
    with pytest.raises(
        ValueError,
        match="attempt deve ser maior que zero",
    ):
        create_error(attempt=0)
