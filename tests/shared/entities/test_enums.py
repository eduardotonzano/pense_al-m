"""Testes das enumeracoes da Shared Entity Layer."""

import pytest

from pense_alm.shared.entities import (
    EntityStatus,
    EntityType,
    IdentifierType,
    SourceType,
    ValidationStatus,
)


def test_entity_type_uses_stable_string_values():
    assert EntityType.BANK == "bank"
    assert EntityType.FIDC == "fidc"
    assert EntityType.SECURITIZER == "securitizer"


def test_entity_status_contains_operational_states():
    assert EntityStatus.ACTIVE == "active"
    assert EntityStatus.UNDER_INTERVENTION == "under_intervention"
    assert EntityStatus.UNKNOWN == "unknown"


def test_identifier_type_contains_official_identifiers():
    assert IdentifierType.CNPJ == "cnpj"
    assert IdentifierType.BACEN_CODE == "bacen_code"
    assert IdentifierType.CVM_CODE == "cvm_code"


def test_source_type_respects_source_categories():
    assert SourceType.BACEN == "bacen"
    assert SourceType.SPECIALIZED == "specialized"
    assert SourceType.INSTITUTIONAL == "institutional"


def test_validation_status_is_controlled():
    assert ValidationStatus.VALID == "valid"
    assert ValidationStatus.INVALID == "invalid"
    assert ValidationStatus.CONFLICT == "conflict"


def test_invalid_entity_type_is_rejected():
    with pytest.raises(ValueError):
        EntityType("invalid_type")
