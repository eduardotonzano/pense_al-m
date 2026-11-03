"""Testes do adaptador de debentures (instrumento)."""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

import pytest

from pense_alm.shared.entities import (
    EntityStatus,
    EntityType,
    IdentifierType,
    RelationshipStatus,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration import (
    DebentureInstrumentAdapter,
    DebentureInstrumentRecord,
    DebentureIssuerAdapter,
    DebentureIssuerRecord,
)


def create_record(**overrides):
    values = {
        "legacy_id": 7,
        "asset_code": "ALFA11",
        "isin": "BRALFADBS001",
        "status": "active",
        "issuer_legacy_id": 1,
        "issuer_cnpj": "12345678000199",
        "created_at": "2026-09-20 10:00:00",
        "updated_at": "2026-09-21 12:00:00",
    }
    values.update(overrides)
    return DebentureInstrumentRecord(**values)


def create_issuer():
    return DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=1,
            legal_name="Empresa Alfa S.A.",
            cnpj="12345678000199",
            created_at="2026-09-20 10:00:00",
            updated_at="2026-09-21 12:00:00",
        )
    )


def test_convert_creates_debenture_entity():
    entity = DebentureInstrumentAdapter().convert(
        create_record()
    )

    assert entity.entity_type is EntityType.DEBENTURE
    assert entity.legal_name == "ALFA11"
    assert entity.country_code == "BR"
    assert entity.status is EntityStatus.ACTIVE
    assert entity.provenance.source_type is SourceType.SPECIALIZED
    assert entity.provenance.source_reference == "debenture:7"

    identifiers = {
        identifier.identifier_type: identifier
        for identifier in entity.identifiers
    }

    assert set(identifiers) == {
        IdentifierType.ASSET_CODE,
        IdentifierType.ISIN,
    }
    assert identifiers[IdentifierType.ASSET_CODE].value == "ALFA11"
    assert identifiers[IdentifierType.ISIN].value == "BRALFADBS001"
    assert all(
        identifier.is_primary
        for identifier in entity.identifiers
    )


def test_convert_uses_isin_as_name_without_asset_code():
    entity = DebentureInstrumentAdapter().convert(
        create_record(asset_code=None)
    )

    assert entity.legal_name == "BRALFADBS001"
    assert [
        identifier.identifier_type
        for identifier in entity.identifiers
    ] == [IdentifierType.ISIN]


def test_convert_has_no_cnpj_identifier():
    entity = DebentureInstrumentAdapter().convert(
        create_record()
    )

    assert entity.cnpj is None


@pytest.mark.parametrize(
    ("legacy_status", "expected"),
    [
        ("active", EntityStatus.ACTIVE),
        ("inactive", EntityStatus.INACTIVE),
        ("matured", EntityStatus.INACTIVE),
        ("cancelled", EntityStatus.INACTIVE),
        ("unknown", EntityStatus.UNKNOWN),
    ],
)
def test_convert_maps_legacy_status(legacy_status, expected):
    entity = DebentureInstrumentAdapter().convert(
        create_record(status=legacy_status)
    )

    assert entity.status is expected


def test_convert_reads_naive_timestamps_as_utc():
    entity = DebentureInstrumentAdapter().convert(
        create_record()
    )

    assert entity.created_at == datetime(
        2026, 9, 20, 10, 0, 0, tzinfo=UTC
    )
    assert entity.updated_at == datetime(
        2026, 9, 21, 12, 0, 0, tzinfo=UTC
    )
    assert entity.provenance.collected_at == entity.updated_at
    assert entity.provenance.reference_date == entity.updated_at


def test_convert_converts_timestamps_with_timezone_to_utc():
    entity = DebentureInstrumentAdapter().convert(
        create_record(
            created_at="2026-09-20T10:00:00-03:00",
            updated_at="2026-09-21T12:00:00-03:00",
        )
    )

    assert entity.created_at == datetime(
        2026, 9, 20, 13, 0, 0, tzinfo=UTC
    )


def test_entity_id_is_deterministic():
    adapter = DebentureInstrumentAdapter()

    first = adapter.convert(create_record())
    second = adapter.convert(
        create_record(asset_code="OUTRO1", isin=None)
    )
    other = adapter.convert(create_record(legacy_id=8))

    assert first.entity_id == second.entity_id
    assert first.entity_id != other.entity_id
    assert first.entity_id == uuid5(
        NAMESPACE_URL,
        "pense-alm:debenture-instrument:7",
    )


def test_entity_id_differs_from_issuer_entity_id():
    issuer = DebentureIssuerAdapter().convert(
        DebentureIssuerRecord(
            legacy_id=7,
            legal_name="Empresa Alfa S.A.",
            created_at="2026-09-20 10:00:00",
            updated_at="2026-09-21 12:00:00",
        )
    )
    instrument = DebentureInstrumentAdapter().convert(
        create_record(legacy_id=7)
    )

    assert issuer.entity_id != instrument.entity_id


def test_convert_rejects_update_before_creation():
    with pytest.raises(ValueError):
        DebentureInstrumentAdapter().convert(
            create_record(
                created_at="2026-09-22 10:00:00",
                updated_at="2026-09-21 10:00:00",
            )
        )


def test_convert_rejects_invalid_timestamp():
    with pytest.raises(
        ValueError,
        match="Timestamp legado invalido.",
    ):
        DebentureInstrumentAdapter().convert(
            create_record(created_at="data-invalida")
        )


def test_convert_rejects_unexpected_type():
    with pytest.raises(TypeError):
        DebentureInstrumentAdapter().convert(object())


def test_relationship_links_issuer_to_instrument():
    adapter = DebentureInstrumentAdapter()
    issuer = create_issuer()
    instrument = adapter.convert(create_record())

    relationship = adapter.build_issuance_relationship(
        issuer,
        instrument,
    )

    assert relationship.source_entity_id == issuer.entity_id
    assert relationship.target_entity_id == instrument.entity_id
    assert relationship.relationship_type is RelationshipType.ISSUES
    assert relationship.status is RelationshipStatus.ACTIVE
    assert relationship.provenance == instrument.provenance
    assert relationship.valid_from is None
    assert relationship.valid_to is None


def test_relationship_is_deterministic():
    adapter = DebentureInstrumentAdapter()
    issuer = create_issuer()
    instrument = adapter.convert(create_record())

    first = adapter.build_issuance_relationship(
        issuer,
        instrument,
    )
    second = adapter.build_issuance_relationship(
        issuer,
        instrument,
    )

    assert first == second
    assert first.relationship_id == uuid5(
        NAMESPACE_URL,
        first.canonical_key,
    )


def test_relationship_rejects_non_debenture_target():
    adapter = DebentureInstrumentAdapter()
    issuer = create_issuer()

    with pytest.raises(ValueError):
        adapter.build_issuance_relationship(issuer, issuer)
