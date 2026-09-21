"""Testes de identificadores de entidade."""

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    EntityIdentifier,
    IdentifierType,
    IdentifierValidationError,
    SourceType,
    normalize_cnpj,
)


@pytest.fixture
def bacen_provenance():
    return DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )


def test_cnpj_is_normalized(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value="12.345.678/0001-90",
        provenance=bacen_provenance,
        is_primary=True,
    )

    assert identifier.value == "12345678000190"
    assert identifier.canonical_key == "cnpj:12345678000190"


def test_non_cnpj_identifier_is_uppercase(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.BACEN_CODE,
        value="  abc123  ",
        provenance=bacen_provenance,
    )

    assert identifier.value == "ABC123"


def test_empty_identifier_is_rejected(bacen_provenance):
    with pytest.raises(IdentifierValidationError):
        EntityIdentifier(
            identifier_type=IdentifierType.CVM_CODE,
            value=" ",
            provenance=bacen_provenance,
        )


@pytest.mark.parametrize(
    "value",
    [
        "123",
        "11.111.111/1111-11",
    ],
)
def test_invalid_cnpj_is_rejected(value):
    with pytest.raises(IdentifierValidationError):
        normalize_cnpj(value)


def test_identifier_is_immutable(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.BACEN_CODE,
        value="123",
        provenance=bacen_provenance,
    )

    with pytest.raises(AttributeError):
        identifier.value = "456"
