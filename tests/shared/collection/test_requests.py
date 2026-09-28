"""Testes das requisicoes compartilhadas de coleta."""

from types import MappingProxyType
from uuid import uuid4

import pytest

from pense_alm.shared.collection.requests import (
    CollectionRequest,
)


def test_request_normalizes_operation_and_target():
    request = CollectionRequest(
        source_id=uuid4(),
        operation="  get  ",
        target="  https://example.com/data  ",
    )

    assert request.operation == "GET"
    assert request.target == "https://example.com/data"


def test_request_preserves_parameters_and_headers():
    request = CollectionRequest(
        source_id=uuid4(),
        operation="post",
        target="https://example.com/search",
        parameters={
            "asset_code": "ABC123",
            "page": 1,
        },
        headers={
            "Accept": "application/json",
        },
    )

    assert request.parameters["asset_code"] == "ABC123"
    assert request.parameters["page"] == 1
    assert request.headers["Accept"] == "application/json"


def test_request_protects_mappings():
    request = CollectionRequest(
        source_id=uuid4(),
        operation="GET",
        target="https://example.com/data",
        parameters={
            "page": 1,
        },
    )

    assert isinstance(
        request.parameters,
        MappingProxyType,
    )

    with pytest.raises(TypeError):
        request.parameters["page"] = 2


def test_request_copies_input_mapping():
    parameters = {
        "page": 1,
    }

    request = CollectionRequest(
        source_id=uuid4(),
        operation="GET",
        target="https://example.com/data",
        parameters=parameters,
    )

    parameters["page"] = 2

    assert request.parameters["page"] == 1


def test_request_generates_request_id():
    request = CollectionRequest(
        source_id=uuid4(),
        operation="GET",
        target="https://example.com/data",
    )

    assert request.request_id is not None


def test_request_rejects_invalid_source_id():
    with pytest.raises(
        TypeError,
        match="source_id deve ser UUID",
    ):
        CollectionRequest(
            source_id="invalid",
            operation="GET",
            target="https://example.com/data",
        )


def test_request_rejects_empty_operation():
    with pytest.raises(
        ValueError,
        match="operation nao pode ser vazio",
    ):
        CollectionRequest(
            source_id=uuid4(),
            operation="   ",
            target="https://example.com/data",
        )


def test_request_rejects_empty_target():
    with pytest.raises(
        ValueError,
        match="target nao pode ser vazio",
    ):
        CollectionRequest(
            source_id=uuid4(),
            operation="GET",
            target="   ",
        )


def test_request_rejects_invalid_parameters():
    with pytest.raises(
        TypeError,
        match="parameters deve ser um mapeamento",
    ):
        CollectionRequest(
            source_id=uuid4(),
            operation="GET",
            target="https://example.com/data",
            parameters=[
                ("page", 1),
            ],
        )


def test_request_rejects_empty_mapping_key():
    with pytest.raises(
        ValueError,
        match="parameters.key nao pode ser vazio",
    ):
        CollectionRequest(
            source_id=uuid4(),
            operation="GET",
            target="https://example.com/data",
            parameters={
                "   ": 1,
            },
        )
