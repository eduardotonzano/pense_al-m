"""Testes de proveniencia."""

from datetime import UTC, datetime

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    ProvenanceValidationError,
    SourceType,
    ValidationStatus,
)


def test_bacen_has_highest_priority():
    provenance = DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )

    assert provenance.source_priority == 1


def test_source_name_is_trimmed():
    provenance = DataProvenance(
        source_type=SourceType.CVM,
        source_name="  CVM  ",
    )

    assert provenance.source_name == "CVM"


def test_empty_source_name_is_rejected():
    with pytest.raises(ProvenanceValidationError):
        DataProvenance(
            source_type=SourceType.BACEN,
            source_name="   ",
        )


@pytest.mark.parametrize("score", [-1, 101])
def test_invalid_confidence_is_rejected(score):
    with pytest.raises(ProvenanceValidationError):
        DataProvenance(
            source_type=SourceType.ANBIMA,
            source_name="ANBIMA",
            confidence_score=score,
        )


def test_naive_collection_datetime_is_rejected():
    with pytest.raises(ProvenanceValidationError):
        DataProvenance(
            source_type=SourceType.CVM,
            source_name="CVM",
            collected_at=datetime(2026, 9, 21),
        )


def test_validation_status_can_be_defined():
    provenance = DataProvenance(
        source_type=SourceType.INSTITUTIONAL,
        source_name="Site do emissor",
        collected_at=datetime.now(UTC),
        validation_status=ValidationStatus.VALID,
    )

    assert provenance.validation_status is ValidationStatus.VALID
