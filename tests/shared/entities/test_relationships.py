"""Testes de relacionamentos entre entidades."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    EntityRelationship,
    EntityValidationError,
    RelationshipStatus,
    RelationshipType,
    SourceType,
)


@pytest.fixture
def cvm_provenance():
    return DataProvenance(
        source_type=SourceType.CVM,
        source_name="Comissao de Valores Mobiliarios",
    )


def create_relationship(
    provenance,
    **overrides,
):
    values = {
        "source_entity_id": uuid4(),
        "target_entity_id": uuid4(),
        "relationship_type": RelationshipType.MANAGES,
        "provenance": provenance,
        "status": RelationshipStatus.ACTIVE,
    }

    values.update(overrides)

    return EntityRelationship(**values)


def test_relationship_is_created_with_uuid(
    cvm_provenance,
):
    relationship = create_relationship(cvm_provenance)

    assert relationship.relationship_id is not None


def test_self_relationship_is_rejected(
    cvm_provenance,
):
    entity_id = uuid4()

    with pytest.raises(EntityValidationError):
        create_relationship(
            cvm_provenance,
            source_entity_id=entity_id,
            target_entity_id=entity_id,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "source_entity_id",
        "target_entity_id",
    ],
)
def test_entity_ids_must_be_uuid(
    cvm_provenance,
    field_name,
):
    with pytest.raises(EntityValidationError):
        create_relationship(
            cvm_provenance,
            **{field_name: "invalid"},
        )


def test_invalid_validity_period_is_rejected(
    cvm_provenance,
):
    valid_from = datetime.now(UTC)

    with pytest.raises(EntityValidationError):
        create_relationship(
            cvm_provenance,
            valid_from=valid_from,
            valid_to=valid_from - timedelta(days=1),
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "valid_from",
        "valid_to",
    ],
)
def test_validity_dates_require_timezone(
    cvm_provenance,
    field_name,
):
    with pytest.raises(EntityValidationError):
        create_relationship(
            cvm_provenance,
            **{
                field_name: datetime(2026, 9, 21),
            },
        )


@pytest.mark.parametrize(
    "score",
    [-1, 101],
)
def test_invalid_confidence_is_rejected(
    cvm_provenance,
    score,
):
    with pytest.raises(EntityValidationError):
        create_relationship(
            cvm_provenance,
            confidence_score=score,
        )


def test_notes_are_normalized(cvm_provenance):
    relationship = create_relationship(
        cvm_provenance,
        notes="  Gestao   iniciada em 2026  ",
    )

    assert relationship.notes == "Gestao iniciada em 2026"


def test_empty_notes_become_none(cvm_provenance):
    relationship = create_relationship(
        cvm_provenance,
        notes="   ",
    )

    assert relationship.notes is None


def test_canonical_key_is_stable(cvm_provenance):
    source_id = uuid4()
    target_id = uuid4()

    first = create_relationship(
        cvm_provenance,
        source_entity_id=source_id,
        target_entity_id=target_id,
    )
    second = create_relationship(
        cvm_provenance,
        source_entity_id=source_id,
        target_entity_id=target_id,
    )

    assert first.canonical_key == second.canonical_key


def test_relationship_direction_changes_key(
    cvm_provenance,
):
    source_id = uuid4()
    target_id = uuid4()

    direct = create_relationship(
        cvm_provenance,
        source_entity_id=source_id,
        target_entity_id=target_id,
    )
    inverse = create_relationship(
        cvm_provenance,
        source_entity_id=target_id,
        target_entity_id=source_id,
    )

    assert direct.canonical_key != inverse.canonical_key


def test_open_ended_active_relationship(
    cvm_provenance,
):
    relationship = create_relationship(
        cvm_provenance,
        valid_from=datetime.now(UTC) - timedelta(days=1),
    )

    assert relationship.is_open_ended is True
    assert relationship.is_active is True


def test_future_relationship_is_not_active(
    cvm_provenance,
):
    relationship = create_relationship(
        cvm_provenance,
        valid_from=datetime.now(UTC) + timedelta(days=1),
    )

    assert relationship.is_active is False


def test_expired_relationship_is_not_active(
    cvm_provenance,
):
    now = datetime.now(UTC)

    relationship = create_relationship(
        cvm_provenance,
        valid_from=now - timedelta(days=10),
        valid_to=now - timedelta(days=1),
    )

    assert relationship.is_active is False


@pytest.mark.parametrize(
    "status",
    [
        RelationshipStatus.PENDING_REVIEW,
        RelationshipStatus.DISPUTED,
        RelationshipStatus.INACTIVE,
        RelationshipStatus.UNKNOWN,
    ],
)
def test_non_active_status_is_not_canonical(
    cvm_provenance,
    status,
):
    relationship = create_relationship(
        cvm_provenance,
        status=status,
    )

    assert relationship.is_active is False


def test_active_at_historical_date(
    cvm_provenance,
):
    valid_from = datetime(2025, 1, 1, tzinfo=UTC)
    valid_to = datetime(2025, 12, 31, tzinfo=UTC)

    relationship = create_relationship(
        cvm_provenance,
        valid_from=valid_from,
        valid_to=valid_to,
    )

    reference = datetime(2025, 6, 30, tzinfo=UTC)

    assert relationship.is_active_at(reference) is True


def test_reference_datetime_requires_timezone(
    cvm_provenance,
):
    relationship = create_relationship(cvm_provenance)

    with pytest.raises(EntityValidationError):
        relationship.is_active_at(
            datetime(2026, 9, 21)
        )


def test_relationship_is_immutable(
    cvm_provenance,
):
    relationship = create_relationship(cvm_provenance)

    with pytest.raises(FrozenInstanceError):
        relationship.status = RelationshipStatus.INACTIVE
