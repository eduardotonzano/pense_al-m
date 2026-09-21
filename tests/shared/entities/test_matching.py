"""Testes do matching conservador de entidades."""

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityMatcher,
    EntityType,
    IdentifierType,
    MatchDecision,
    MatchStrength,
    SourceType,
    normalize_matching_name,
)


@pytest.fixture
def bacen_provenance():
    return DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )


def create_identifier(
    provenance,
    identifier_type,
    value,
):
    return EntityIdentifier(
        identifier_type=identifier_type,
        value=value,
        provenance=provenance,
        is_primary=True,
    )


def create_entity(
    provenance,
    legal_name,
    entity_type=EntityType.BANK,
    trade_name=None,
    identifiers=(),
):
    return Entity(
        legal_name=legal_name,
        trade_name=trade_name,
        entity_type=entity_type,
        provenance=provenance,
        identifiers=identifiers,
    )


def test_matching_name_removes_accents_and_punctuation():
    normalized = normalize_matching_name(
        "Instituição Financeira S.A."
    )

    assert normalized == "INSTITUICAO FINANCEIRA S A"


def test_same_cnpj_allows_automatic_match(
    bacen_provenance,
):
    left_identifier = create_identifier(
        bacen_provenance,
        IdentifierType.CNPJ,
        "12.345.678/0001-90",
    )
    right_identifier = create_identifier(
        bacen_provenance,
        IdentifierType.CNPJ,
        "12345678000190",
    )

    left = create_entity(
        bacen_provenance,
        "Banco Exemplo S.A.",
        identifiers=(left_identifier,),
    )
    right = create_entity(
        bacen_provenance,
        "Banco Exemplo",
        identifiers=(right_identifier,),
    )

    result = EntityMatcher().compare(left, right)

    assert result.decision is MatchDecision.AUTO_MATCH
    assert result.strength is MatchStrength.STRONG
    assert result.score == 100
    assert result.can_auto_match is True
    assert (
        result.matched_identifier_type
        is IdentifierType.CNPJ
    )


def test_conflicting_cnpj_blocks_match(
    bacen_provenance,
):
    left = create_entity(
        bacen_provenance,
        "Banco Exemplo S.A.",
        identifiers=(
            create_identifier(
                bacen_provenance,
                IdentifierType.CNPJ,
                "12.345.678/0001-90",
            ),
        ),
    )
    right = create_entity(
        bacen_provenance,
        "Banco Exemplo S.A.",
        identifiers=(
            create_identifier(
                bacen_provenance,
                IdentifierType.CNPJ,
                "98.765.432/0001-10",
            ),
        ),
    )

    result = EntityMatcher().compare(left, right)

    assert result.decision is MatchDecision.BLOCKED
    assert result.strength is MatchStrength.CONFLICT
    assert result.score == 0
    assert result.can_auto_match is False


def test_same_legal_name_requires_human_review(
    bacen_provenance,
):
    left = create_entity(
        bacen_provenance,
        "Banco Exemplo S.A.",
    )
    right = create_entity(
        bacen_provenance,
        "  BANCO   EXEMPLO   S.A.  ",
    )

    result = EntityMatcher().compare(left, right)

    assert result.decision is MatchDecision.REVIEW
    assert result.strength is MatchStrength.MODERATE
    assert result.score == 70
    assert result.requires_review is True


def test_same_name_with_different_types_is_weak(
    bacen_provenance,
):
    left = create_entity(
        bacen_provenance,
        "Grupo Exemplo",
        entity_type=EntityType.HOLDING,
    )
    right = create_entity(
        bacen_provenance,
        "Grupo Exemplo",
        entity_type=EntityType.COMPANY,
    )

    result = EntityMatcher().compare(left, right)

    assert result.decision is MatchDecision.REVIEW
    assert result.strength is MatchStrength.WEAK
    assert result.score == 45


def test_same_trade_name_requires_review(
    bacen_provenance,
):
    left = create_entity(
        bacen_provenance,
        "Banco Exemplo S.A.",
        trade_name="Exemplo",
    )
    right = create_entity(
        bacen_provenance,
        "Exemplo Financeira S.A.",
        trade_name="Exemplo",
    )

    result = EntityMatcher().compare(left, right)

    assert result.decision is MatchDecision.REVIEW
    assert result.strength is MatchStrength.WEAK
    assert result.score == 40


def test_different_entities_do_not_match(
    bacen_provenance,
):
    left = create_entity(
        bacen_provenance,
        "Banco Alfa S.A.",
    )
    right = create_entity(
        bacen_provenance,
        "Banco Beta S.A.",
    )

    result = EntityMatcher().compare(left, right)

    assert result.decision is MatchDecision.NO_MATCH
    assert result.strength is MatchStrength.NONE
    assert result.score == 0


def test_match_result_is_immutable(
    bacen_provenance,
):
    entity = create_entity(
        bacen_provenance,
        "Banco Exemplo S.A.",
    )

    result = EntityMatcher().compare(entity, entity)

    with pytest.raises(AttributeError):
        result.score = 10
