"""Testes do modelo universal de entidade."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityStatus,
    EntityType,
    EntityValidationError,
    IdentifierType,
    SourceType,
)


@pytest.fixture
def bacen_provenance():
    return DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )


@pytest.fixture
def cnpj_identifier(bacen_provenance):
    return EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value="12.345.678/0001-90",
        provenance=bacen_provenance,
        is_primary=True,
    )


def test_entity_is_created_with_internal_uuid(
    bacen_provenance,
):
    entity = Entity(
        legal_name="Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        provenance=bacen_provenance,
    )

    assert isinstance(entity.entity_id, UUID)


def test_entity_normalizes_names(bacen_provenance):
    entity = Entity(
        legal_name="  Banco   Exemplo   S.A.  ",
        trade_name="  Banco   Exemplo  ",
        entity_type=EntityType.BANK,
        provenance=bacen_provenance,
    )

    assert entity.legal_name == "Banco Exemplo S.A."
    assert entity.trade_name == "Banco Exemplo"


def test_display_name_prefers_trade_name(
    bacen_provenance,
):
    entity = Entity(
        legal_name="Banco Exemplo S.A.",
        trade_name="Banco Exemplo",
        entity_type=EntityType.BANK,
        provenance=bacen_provenance,
    )

    assert entity.display_name == "Banco Exemplo"


def test_display_name_uses_legal_name_as_fallback(
    bacen_provenance,
):
    entity = Entity(
        legal_name="Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        provenance=bacen_provenance,
    )

    assert entity.display_name == "Banco Exemplo S.A."


def test_entity_returns_normalized_cnpj(
    bacen_provenance,
    cnpj_identifier,
):
    entity = Entity(
        legal_name="Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        provenance=bacen_provenance,
        identifiers=(cnpj_identifier,),
    )

    assert entity.cnpj == "12345678000190"


def test_entity_without_cnpj_returns_none(
    bacen_provenance,
):
    entity = Entity(
        legal_name="Tesouro Nacional",
        entity_type=EntityType.GOVERNMENT,
        provenance=bacen_provenance,
    )

    assert entity.cnpj is None


def test_empty_legal_name_is_rejected(
    bacen_provenance,
):
    with pytest.raises(EntityValidationError):
        Entity(
            legal_name=" ",
            entity_type=EntityType.COMPANY,
            provenance=bacen_provenance,
        )


@pytest.mark.parametrize(
    "country_code",
    ["B", "BRA", "12", ""],
)
def test_invalid_country_code_is_rejected(
    bacen_provenance,
    country_code,
):
    with pytest.raises(EntityValidationError):
        Entity(
            legal_name="Entidade Exemplo",
            entity_type=EntityType.COMPANY,
            provenance=bacen_provenance,
            country_code=country_code,
        )


def test_country_code_is_normalized(
    bacen_provenance,
):
    entity = Entity(
        legal_name="Entidade Exemplo",
        entity_type=EntityType.COMPANY,
        provenance=bacen_provenance,
        country_code="br",
    )

    assert entity.country_code == "BR"


def test_duplicate_identifier_is_rejected(
    bacen_provenance,
    cnpj_identifier,
):
    with pytest.raises(EntityValidationError):
        Entity(
            legal_name="Banco Exemplo S.A.",
            entity_type=EntityType.BANK,
            provenance=bacen_provenance,
            identifiers=(
                cnpj_identifier,
                cnpj_identifier,
            ),
        )


def test_updated_at_before_created_at_is_rejected(
    bacen_provenance,
):
    created_at = datetime.now(UTC)

    with pytest.raises(EntityValidationError):
        Entity(
            legal_name="Empresa Exemplo S.A.",
            entity_type=EntityType.COMPANY,
            provenance=bacen_provenance,
            created_at=created_at,
            updated_at=created_at - timedelta(seconds=1),
        )


def test_entity_is_immutable(bacen_provenance):
    entity = Entity(
        legal_name="Banco Exemplo S.A.",
        entity_type=EntityType.BANK,
        provenance=bacen_provenance,
        status=EntityStatus.ACTIVE,
    )

    with pytest.raises(FrozenInstanceError):
        entity.status = EntityStatus.INACTIVE
