"""Testes do adaptador de emissores de Debentures."""

from datetime import UTC, datetime

import pytest

from pense_alm.shared.entities import (
    EntityStatus,
    EntityType,
    IdentifierType,
    SourceType,
)
from pense_alm.shared.integration import (
    DebentureIssuerAdapter,
    DebentureIssuerRecord,
)


def create_record(**overrides):
    values = {
        "legacy_id": 42,
        "legal_name": "Empresa Brasileira S.A.",
        "trade_name": "Empresa Brasileira",
        "cnpj": "12.345.678/0001-99",
        "created_at": "2026-09-20 10:00:00",
        "updated_at": "2026-09-21 12:30:00",
    }
    values.update(overrides)
    return DebentureIssuerRecord(**values)


def test_record_normalizes_fields():
    record = create_record(
        legal_name="  Empresa   Brasileira S.A. ",
        trade_name="  Empresa   Brasileira ",
    )

    assert record.legal_name == "Empresa Brasileira S.A."
    assert record.trade_name == "Empresa Brasileira"
    assert record.cnpj == "12345678000199"


def test_record_accepts_missing_cnpj():
    assert create_record(cnpj=None).cnpj is None


def test_record_rejects_invalid_cnpj():
    with pytest.raises(ValueError, match="14 digitos"):
        create_record(cnpj="123")


def test_record_rejects_invalid_legacy_id():
    with pytest.raises(ValueError, match="maior que zero"):
        create_record(legacy_id=0)


def test_adapter_converts_complete_issuer():
    entity = DebentureIssuerAdapter().convert(
        create_record()
    )

    assert entity.legal_name == "Empresa Brasileira S.A."
    assert entity.trade_name == "Empresa Brasileira"
    assert entity.entity_type is EntityType.COMPANY
    assert entity.status is EntityStatus.ACTIVE
    assert entity.country_code == "BR"
    assert len(entity.identifiers) == 1

    identifier = entity.identifiers[0]

    assert identifier.identifier_type is IdentifierType.CNPJ
    assert identifier.value == "12345678000199"
    assert identifier.is_primary is True


def test_adapter_preserves_legacy_reference():
    entity = DebentureIssuerAdapter().convert(
        create_record(legacy_id=123)
    )

    assert entity.provenance.source_type is SourceType.SPECIALIZED
    assert entity.provenance.source_reference == "issuer:123"


def test_adapter_converts_sqlite_dates_to_utc():
    entity = DebentureIssuerAdapter().convert(
        create_record()
    )

    assert entity.created_at == datetime(
        2026,
        9,
        20,
        10,
        0,
        tzinfo=UTC,
    )
    assert entity.updated_at == datetime(
        2026,
        9,
        21,
        12,
        30,
        tzinfo=UTC,
    )


def test_adapter_accepts_timestamp_with_timezone():
    entity = DebentureIssuerAdapter().convert(
        create_record(
            created_at="2026-09-20T10:00:00-03:00",
            updated_at="2026-09-21T12:30:00-03:00",
        )
    )

    assert entity.created_at == datetime(
        2026,
        9,
        20,
        13,
        0,
        tzinfo=UTC,
    )


def test_adapter_allows_issuer_without_cnpj():
    entity = DebentureIssuerAdapter().convert(
        create_record(cnpj=None)
    )

    assert entity.identifiers == ()


def test_same_legacy_id_produces_same_entity_id():
    adapter = DebentureIssuerAdapter()

    first = adapter.convert(
        create_record(legacy_id=77)
    )
    second = adapter.convert(
        create_record(
            legacy_id=77,
            legal_name="Nome Atualizado S.A.",
        )
    )

    assert first.entity_id == second.entity_id


def test_different_legacy_ids_produce_different_ids():
    adapter = DebentureIssuerAdapter()

    first = adapter.convert(
        create_record(legacy_id=77)
    )
    second = adapter.convert(
        create_record(legacy_id=78)
    )

    assert first.entity_id != second.entity_id


def test_adapter_rejects_invalid_record_type():
    with pytest.raises(
        TypeError,
        match="DebentureIssuerRecord",
    ):
        DebentureIssuerAdapter().convert("invalid")


def test_adapter_rejects_invalid_timestamp():
    with pytest.raises(
        ValueError,
        match="Timestamp legado invalido",
    ):
        DebentureIssuerAdapter().convert(
            create_record(created_at="data-invalida")
        )


def test_adapter_rejects_inverted_dates():
    with pytest.raises(ValueError, match="updated_at"):
        DebentureIssuerAdapter().convert(
            create_record(
                created_at="2026-09-22 10:00:00",
                updated_at="2026-09-21 10:00:00",
            )
        )
