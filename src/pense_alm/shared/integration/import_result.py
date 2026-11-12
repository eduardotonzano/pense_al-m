"""Resultados auditaveis da integracao de entidades."""

from dataclasses import dataclass
from enum import StrEnum

from pense_alm.shared.entities import (
    Entity,
    EntityMatchResult,
    EntityRelationship,
)


class EntityImportAction(StrEnum):
    """Acao tomada durante uma importacao."""

    CREATED = "created"
    MATCHED = "matched"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EntityImportResult:
    """Resultado da importacao de uma entidade legada."""

    action: EntityImportAction
    incoming_entity: Entity
    resolved_entity: Entity | None = None
    match_result: EntityMatchResult | None = None

    @property
    def was_created(self) -> bool:
        """Indica se uma nova entidade foi persistida."""

        return self.action is EntityImportAction.CREATED

    @property
    def was_matched(self) -> bool:
        """Indica correspondencia com entidade existente."""

        return self.action is EntityImportAction.MATCHED

    @property
    def requires_review(self) -> bool:
        """Indica necessidade de revisao humana."""

        return self.action is EntityImportAction.REVIEW

    @property
    def was_blocked(self) -> bool:
        """Indica bloqueio por conflito."""

        return self.action is EntityImportAction.BLOCKED


class InstrumentImportReason(StrEnum):
    """Motivo pelo qual uma debenture nao foi gravada."""

    ISSUER_MISSING = "issuer_missing"
    ISSUER_WITHOUT_CNPJ = "issuer_without_cnpj"
    ISSUER_NOT_REGISTERED = "issuer_not_registered"
    CONFLICTING_CANDIDATES = "conflicting_candidates"
    IDENTIFIER_CONFLICT = "identifier_conflict"
    ISSUER_MISMATCH = "issuer_mismatch"
    NOT_AN_INSTRUMENT = "not_an_instrument"


@dataclass(frozen=True, slots=True)
class InstrumentImportResult:
    """Resultado auditavel da importacao de uma debenture."""

    action: EntityImportAction
    legacy_id: int
    incoming_entity: Entity
    resolved_entity: Entity | None = None
    issuer_entity: Entity | None = None
    relationship: EntityRelationship | None = None
    relationship_created: bool = False
    match_result: EntityMatchResult | None = None
    reason: InstrumentImportReason | None = None
    unmerged_identifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        pending = self.action in (
            EntityImportAction.REVIEW,
            EntityImportAction.BLOCKED,
        )

        if pending and self.reason is None:
            raise ValueError(
                "REVIEW e BLOCKED exigem um motivo."
            )

        if not pending and self.reason is not None:
            raise ValueError(
                "CREATED e MATCHED nao possuem motivo."
            )

        if pending and (
            self.relationship_created
            or self.relationship is not None
        ):
            raise ValueError(
                "REVIEW e BLOCKED nao gravam relacionamento."
            )

        object.__setattr__(
            self,
            "unmerged_identifiers",
            tuple(self.unmerged_identifiers),
        )

    @property
    def was_created(self) -> bool:
        """Indica se uma nova entidade foi persistida."""

        return self.action is EntityImportAction.CREATED

    @property
    def was_matched(self) -> bool:
        """Indica correspondencia com entidade existente."""

        return self.action is EntityImportAction.MATCHED

    @property
    def requires_review(self) -> bool:
        """Indica pendencia de revisao humana."""

        return self.action is EntityImportAction.REVIEW

    @property
    def was_blocked(self) -> bool:
        """Indica bloqueio por conflito."""

        return self.action is EntityImportAction.BLOCKED
