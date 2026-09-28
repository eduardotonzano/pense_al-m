"""Servico conservador de importacao de emissores."""

from pense_alm.shared.entities import (
    EntityMatcher,
    EntityRepository,
    EntityType,
    IdentifierType,
    MatchDecision,
    normalize_matching_name,
)

from .debenture_issuer_adapter import (
    DebentureIssuerAdapter,
)
from .import_result import (
    EntityImportAction,
    EntityImportResult,
)
from .records import DebentureIssuerRecord


class DebentureIssuerImportService:
    """Importa emissores sem realizar fusoes inseguras."""

    def __init__(
        self,
        repository: EntityRepository,
        adapter: DebentureIssuerAdapter | None = None,
        matcher: EntityMatcher | None = None,
    ) -> None:
        required_methods = (
            "save",
            "get_by_identifier",
            "list_all",
        )

        if any(
            not callable(getattr(repository, method, None))
            for method in required_methods
        ):
            raise TypeError(
                "repository nao implementa EntityRepository."
            )

        self._repository = repository
        self._adapter = adapter or DebentureIssuerAdapter()
        self._matcher = matcher or EntityMatcher()

    def import_record(
        self,
        record: DebentureIssuerRecord,
    ) -> EntityImportResult:
        """Converte, compara e importa um emissor legado."""

        incoming = self._adapter.convert(record)

        if record.cnpj is not None:
            existing = self._repository.get_by_identifier(
                IdentifierType.CNPJ,
                record.cnpj,
            )

            if existing is not None:
                match_result = self._matcher.compare(
                    incoming,
                    existing,
                )

                return EntityImportResult(
                    action=EntityImportAction.MATCHED,
                    incoming_entity=incoming,
                    resolved_entity=existing,
                    match_result=match_result,
                )

        incoming_names = {
            normalize_matching_name(incoming.legal_name),
            normalize_matching_name(incoming.display_name),
        }

        for existing in self._repository.list_all(
            EntityType.COMPANY
        ):
            existing_names = {
                normalize_matching_name(
                    existing.legal_name
                ),
                normalize_matching_name(
                    existing.display_name
                ),
            }

            if incoming_names.isdisjoint(existing_names):
                continue

            match_result = self._matcher.compare(
                incoming,
                existing,
            )

            if match_result.decision is MatchDecision.BLOCKED:
                return EntityImportResult(
                    action=EntityImportAction.BLOCKED,
                    incoming_entity=incoming,
                    resolved_entity=existing,
                    match_result=match_result,
                )

            if match_result.requires_review:
                return EntityImportResult(
                    action=EntityImportAction.REVIEW,
                    incoming_entity=incoming,
                    resolved_entity=existing,
                    match_result=match_result,
                )

            if match_result.can_auto_match:
                return EntityImportResult(
                    action=EntityImportAction.MATCHED,
                    incoming_entity=incoming,
                    resolved_entity=existing,
                    match_result=match_result,
                )

        saved = self._repository.save(incoming)

        return EntityImportResult(
            action=EntityImportAction.CREATED,
            incoming_entity=incoming,
            resolved_entity=saved,
        )
