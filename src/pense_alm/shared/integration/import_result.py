"""Resultados auditaveis da integracao de entidades."""

from dataclasses import dataclass
from enum import StrEnum

from pense_alm.shared.entities import (
    Entity,
    EntityMatchResult,
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
