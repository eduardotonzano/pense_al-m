"""Testes da serializacao da persistencia SQLite."""

from datetime import UTC, datetime
from sqlite3 import Row, connect
from uuid import uuid4

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityRelationship,
    EntityStatus,
    EntityType,
    IdentifierType,
    RelationshipStatus,
    RelationshipType,
    SourceType,
    ValidationStatus,
)
from pense_alm.shared.persistence.serialization import (
    datetime_from_text,
    datetime_to_text,
    entity_from_rows,
    entity_to_record,
    identifier_from_row,
    identifier_to_record,
    provenance_from_row,
    provenance_id,
    provenance_to_record,
    relationship_from_row,
    relationship_to_record,
)


def create_row(values):
    connection = connect(":memory:")
    connection.row_factory = Row

    columns = ", ".join(
        f"? AS {column}"
        for column in values
    )

    row = connection.execute(
        f"SELECT {columns}",
        tuple(values.values()),
    ).fetchone()

    connection.close()

    return row


def create_provenance():
    return DataProvenance(
        source_type=SourceType.CVM,
        source_name="CVM",
        source_reference="documento-123",
        collected_at=datetime(
            2026,
            9,
            21,
            12,
            0,
            tzinfo=UTC,
        ),
        reference_date=datetime(
            2026,
            6,
            30,
            tzinfo=UTC,
        ),
        validation_status=ValidationStatus.VALID,
        confidence_score=95,
    )


def test_datetime_round_trip():
    original = datetime(
        2026,
        9,
        21,
        12,
        30,
        tzinfo=UTC,
    )

    serialized = datetime_to_text(original)
    restored = datetime_from_text(serialized)

    assert restored == original


def test_none_datetime_round_trip():
    assert datetime_to_text(None) is None
    assert datetime_from_text(None) is None


def test_equal_provenance_has_stable_identifier():
    first = create_provenance()
    second = create_provenance()

    assert provenance_id(first) == provenance_id(second)
    assert len(provenance_id(first)) == 64


def test_provenance_round_trip():
    original = create_provenance()
    record = provenance_to_record(original)
    row = create_row(record)

    restored = provenance_from_row(row)

    assert restored == original


def test_identifier_round_trip():
    provenance = create_provenance()

    original = EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value="12.345.678/0001-90",
        provenance=provenance,
        is_primary=True,
    )

    record = identifier_to_record(
        uuid4(),
        original,
    )
    row = create_row(record)

    restored = identifier_from_row(
        row,
        provenance,
    )

    assert restored == original


def test_entity_round_trip():
    provenance = create_provenance()

    identifier = EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value="12.345.678/0001-90",
        provenance=provenance,
        is_primary=True,
    )

    original = Entity(
        entity_id=uuid4(),
        legal_name="Empresa Exemplo S.A.",
        trade_name="Empresa Exemplo",
        entity_type=EntityType.COMPANY,
        status=EntityStatus.ACTIVE,
        identifiers=(identifier,),
        country_code="BR",
        sector="Financeiro",
        subsector="Credito",
        website="https://example.test",
        provenance=provenance,
        created_at=datetime(
            2026,
            9,
            21,
            12,
            0,
            tzinfo=UTC,
        ),
        updated_at=datetime(
            2026,
            9,
            21,
            13,
            0,
            tzinfo=UTC,
        ),
    )

    entity_row = create_row(
        entity_to_record(original)
    )

    restored = entity_from_rows(
        entity_row,
        provenance,
        (identifier,),
    )

    assert restored == original


def test_relationship_round_trip():
    provenance = create_provenance()

    original = EntityRelationship(
        relationship_id=uuid4(),
        source_entity_id=uuid4(),
        target_entity_id=uuid4(),
        relationship_type=RelationshipType.CONTROLS,
        provenance=provenance,
        status=RelationshipStatus.ACTIVE,
        valid_from=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
        valid_to=None,
        confidence_score=90,
        notes="Controle societario",
        created_at=datetime(
            2026,
            9,
            21,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    relationship_row = create_row(
        relationship_to_record(original)
    )

    restored = relationship_from_row(
        relationship_row,
        provenance,
    )

    assert restored == original
