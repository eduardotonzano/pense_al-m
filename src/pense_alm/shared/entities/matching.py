"""Matching conservador de entidades."""

from dataclasses import dataclass
from re import sub
from unicodedata import normalize

from .enums import (
    IdentifierType,
    MatchDecision,
    MatchStrength,
)
from .models import Entity


_STRONG_IDENTIFIER_TYPES = frozenset(
    {
        IdentifierType.CNPJ,
        IdentifierType.BACEN_CODE,
        IdentifierType.CVM_CODE,
        IdentifierType.ANBIMA_CODE,
        IdentifierType.LEI,
    }
)


def normalize_matching_name(value: str) -> str:
    """Normaliza um nome exclusivamente para comparacao."""

    ascii_value = normalize("NFKD", value).encode(
        "ascii",
        "ignore",
    ).decode("ascii")

    alphanumeric = sub(
        r"[^A-Z0-9]+",
        " ",
        ascii_value.upper(),
    )

    return " ".join(alphanumeric.split())


@dataclass(frozen=True, slots=True)
class EntityMatchResult:
    """Resultado auditavel da comparacao entre duas entidades."""

    decision: MatchDecision
    strength: MatchStrength
    score: int
    reasons: tuple[str, ...]
    matched_identifier_type: IdentifierType | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError(
                "O score de matching deve estar entre 0 e 100."
            )

        object.__setattr__(
            self,
            "reasons",
            tuple(self.reasons),
        )

    @property
    def can_auto_match(self) -> bool:
        """Indica se o resultado permite vinculo automatico."""

        return self.decision is MatchDecision.AUTO_MATCH

    @property
    def requires_review(self) -> bool:
        """Indica se o resultado exige revisao humana."""

        return self.decision is MatchDecision.REVIEW


class EntityMatcher:
    """Compara entidades sem realizar fusao automaticamente."""

    def compare(
        self,
        left: Entity,
        right: Entity,
    ) -> EntityMatchResult:
        """Compara duas entidades e retorna evidencias."""

        strong_result = self._compare_strong_identifiers(
            left,
            right,
        )

        if strong_result is not None:
            return strong_result

        return self._compare_names(left, right)

    def _compare_strong_identifiers(
        self,
        left: Entity,
        right: Entity,
    ) -> EntityMatchResult | None:
        left_identifiers = {
            identifier.identifier_type: identifier.value
            for identifier in left.identifiers
            if identifier.identifier_type
            in _STRONG_IDENTIFIER_TYPES
        }

        right_identifiers = {
            identifier.identifier_type: identifier.value
            for identifier in right.identifiers
            if identifier.identifier_type
            in _STRONG_IDENTIFIER_TYPES
        }

        shared_types = (
            set(left_identifiers)
            & set(right_identifiers)
        )

        for identifier_type in sorted(
            shared_types,
            key=lambda item: item.value,
        ):
            left_value = left_identifiers[identifier_type]
            right_value = right_identifiers[identifier_type]

            if left_value != right_value:
                return EntityMatchResult(
                    decision=MatchDecision.BLOCKED,
                    strength=MatchStrength.CONFLICT,
                    score=0,
                    reasons=(
                        "Identificador oficial conflitante: "
                        f"{identifier_type.value}.",
                    ),
                    matched_identifier_type=identifier_type,
                )

        for identifier_type in sorted(
            shared_types,
            key=lambda item: item.value,
        ):
            if (
                left_identifiers[identifier_type]
                == right_identifiers[identifier_type]
            ):
                return EntityMatchResult(
                    decision=MatchDecision.AUTO_MATCH,
                    strength=MatchStrength.STRONG,
                    score=100,
                    reasons=(
                        "Identificador oficial coincidente: "
                        f"{identifier_type.value}.",
                    ),
                    matched_identifier_type=identifier_type,
                )

        return None

    def _compare_names(
        self,
        left: Entity,
        right: Entity,
    ) -> EntityMatchResult:
        left_legal_name = normalize_matching_name(
            left.legal_name
        )
        right_legal_name = normalize_matching_name(
            right.legal_name
        )

        if left_legal_name == right_legal_name:
            if left.entity_type is right.entity_type:
                return EntityMatchResult(
                    decision=MatchDecision.REVIEW,
                    strength=MatchStrength.MODERATE,
                    score=70,
                    reasons=(
                        "Razao social normalizada coincidente.",
                        "Tipo de entidade coincidente.",
                        "Identificador oficial compartilhado ausente.",
                    ),
                )

            return EntityMatchResult(
                decision=MatchDecision.REVIEW,
                strength=MatchStrength.WEAK,
                score=45,
                reasons=(
                    "Razao social normalizada coincidente.",
                    "Tipos de entidade diferentes.",
                    "Identificador oficial compartilhado ausente.",
                ),
            )

        left_display_name = normalize_matching_name(
            left.display_name
        )
        right_display_name = normalize_matching_name(
            right.display_name
        )

        if left_display_name == right_display_name:
            return EntityMatchResult(
                decision=MatchDecision.REVIEW,
                strength=MatchStrength.WEAK,
                score=40,
                reasons=(
                    "Nome de exibicao normalizado coincidente.",
                    "Identificador oficial compartilhado ausente.",
                ),
            )

        return EntityMatchResult(
            decision=MatchDecision.NO_MATCH,
            strength=MatchStrength.NONE,
            score=0,
            reasons=(
                "Nenhuma evidencia suficiente de correspondencia.",
            ),
        )
