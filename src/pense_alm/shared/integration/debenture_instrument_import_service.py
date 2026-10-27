"""Servico conservador de importacao de debentures (instrumento)."""

from pense_alm.shared.entities import (
    Entity,
    EntityMatcher,
    EntityMatchResult,
    EntityRepository,
    EntityType,
    IdentifierType,
    RelationshipRepository,
    RelationshipType,
)

from .debenture_instrument_adapter import (
    DebentureInstrumentAdapter,
)
from .import_result import (
    EntityImportAction,
    InstrumentImportReason,
    InstrumentImportResult,
)
from .records import DebentureInstrumentRecord


class DebentureInstrumentImportService:
    """Importa debentures sem criar emissores nem unir por nome.

    O instrumento so e ligado a uma entidade existente por
    identificador inequivoco (ISIN, codigo do ativo ou CNPJ do
    emissor ja registrado). Sem isso o registro fica pendente ou
    bloqueado e nada e gravado.
    """

    def __init__(
        self,
        entity_repository: EntityRepository,
        relationship_repository: RelationshipRepository,
        adapter: DebentureInstrumentAdapter | None = None,
        matcher: EntityMatcher | None = None,
    ) -> None:
        if any(
            not callable(
                getattr(entity_repository, method, None)
            )
            for method in (
                "save",
                "get_by_id",
                "get_by_identifier",
            )
        ):
            raise TypeError(
                "entity_repository nao implementa "
                "EntityRepository."
            )

        if any(
            not callable(
                getattr(relationship_repository, method, None)
            )
            for method in (
                "save",
                "list_by_target",
            )
        ):
            raise TypeError(
                "relationship_repository nao implementa "
                "RelationshipRepository."
            )

        self._entities = entity_repository
        self._relationships = relationship_repository
        self._adapter = adapter or DebentureInstrumentAdapter()
        self._matcher = matcher or EntityMatcher()

    def import_record(
        self,
        record: DebentureInstrumentRecord,
    ) -> InstrumentImportResult:
        """Converte, compara e importa uma debenture legada."""

        incoming = self._adapter.convert(record)

        issuer, reason = self._find_issuer(record)

        if issuer is None:
            return self._pending(
                EntityImportAction.REVIEW,
                record,
                incoming,
                reason,
            )

        candidates = self._find_candidates(incoming)

        if len(candidates) > 1:
            return self._pending(
                EntityImportAction.BLOCKED,
                record,
                incoming,
                InstrumentImportReason.CONFLICTING_CANDIDATES,
                issuer=issuer,
            )

        if not candidates:
            return self._create(record, incoming, issuer)

        return self._match(
            record,
            incoming,
            issuer,
            candidates[0],
        )

    def _find_issuer(
        self,
        record: DebentureInstrumentRecord,
    ) -> tuple[Entity | None, InstrumentImportReason | None]:
        if record.issuer_legacy_id is None:
            return None, InstrumentImportReason.ISSUER_MISSING

        if record.issuer_cnpj is None:
            return (
                None,
                InstrumentImportReason.ISSUER_WITHOUT_CNPJ,
            )

        issuer = self._entities.get_by_identifier(
            IdentifierType.CNPJ,
            record.issuer_cnpj,
        )

        if (
            issuer is None
            or issuer.entity_type is EntityType.DEBENTURE
        ):
            return (
                None,
                InstrumentImportReason.ISSUER_NOT_REGISTERED,
            )

        return issuer, None

    def _find_candidates(
        self,
        incoming: Entity,
    ) -> tuple[Entity, ...]:
        found: dict = {}

        for identifier in incoming.identifiers:
            entity = self._entities.get_by_identifier(
                identifier.identifier_type,
                identifier.value,
            )

            if entity is not None:
                found[entity.entity_id] = entity

        return tuple(found.values())

    def _create(
        self,
        record: DebentureInstrumentRecord,
        incoming: Entity,
        issuer: Entity,
    ) -> InstrumentImportResult:
        previous = self._entities.get_by_id(
            incoming.entity_id
        )

        if previous is not None:
            # O mesmo legacy_id ja foi importado com outros
            # identificadores. Gravar sobrescreveria a entidade.
            return self._pending(
                EntityImportAction.BLOCKED,
                record,
                incoming,
                InstrumentImportReason.IDENTIFIER_CONFLICT,
                issuer=issuer,
                existing=previous,
            )

        # Entidade e relacionamento usam repositorios distintos.
        # Se a segunda gravacao falhar, a proxima execucao acha o
        # instrumento pelos identificadores e completa a relacao.
        saved = self._entities.save(incoming)
        relationship = self._relationships.save(
            self._adapter.build_issuance_relationship(
                issuer,
                saved,
            )
        )

        return InstrumentImportResult(
            action=EntityImportAction.CREATED,
            legacy_id=record.legacy_id,
            incoming_entity=incoming,
            resolved_entity=saved,
            issuer_entity=issuer,
            relationship=relationship,
            relationship_created=True,
        )

    def _match(
        self,
        record: DebentureInstrumentRecord,
        incoming: Entity,
        issuer: Entity,
        existing: Entity,
    ) -> InstrumentImportResult:
        if existing.entity_type is not EntityType.DEBENTURE:
            return self._pending(
                EntityImportAction.BLOCKED,
                record,
                incoming,
                InstrumentImportReason.NOT_AN_INSTRUMENT,
                issuer=issuer,
                existing=existing,
            )

        match_result = self._matcher.compare(incoming, existing)

        if not match_result.can_auto_match:
            return self._pending(
                EntityImportAction.BLOCKED,
                record,
                incoming,
                InstrumentImportReason.IDENTIFIER_CONFLICT,
                issuer=issuer,
                existing=existing,
                match_result=match_result,
            )

        issuances = tuple(
            relationship
            for relationship in self._relationships.list_by_target(
                existing.entity_id
            )
            if relationship.relationship_type
            is RelationshipType.ISSUES
        )

        if any(
            relationship.source_entity_id != issuer.entity_id
            for relationship in issuances
        ):
            return self._pending(
                EntityImportAction.BLOCKED,
                record,
                incoming,
                InstrumentImportReason.ISSUER_MISMATCH,
                issuer=issuer,
                existing=existing,
                match_result=match_result,
            )

        if issuances:
            relationship = issuances[0]
            relationship_created = False
        else:
            relationship = self._relationships.save(
                self._adapter.build_issuance_relationship(
                    issuer,
                    existing,
                )
            )
            relationship_created = True

        # Identificador novo nao e incorporado: a camada nao
        # atualiza entidade existente sem regra de precedencia.
        unmerged = tuple(
            identifier.canonical_key
            for identifier in incoming.identifiers
            if existing.get_identifier(identifier.identifier_type)
            is None
        )

        return InstrumentImportResult(
            action=EntityImportAction.MATCHED,
            legacy_id=record.legacy_id,
            incoming_entity=incoming,
            resolved_entity=existing,
            issuer_entity=issuer,
            relationship=relationship,
            relationship_created=relationship_created,
            match_result=match_result,
            unmerged_identifiers=unmerged,
        )

    @staticmethod
    def _pending(
        action: EntityImportAction,
        record: DebentureInstrumentRecord,
        incoming: Entity,
        reason: InstrumentImportReason,
        issuer: Entity | None = None,
        existing: Entity | None = None,
        match_result: EntityMatchResult | None = None,
    ) -> InstrumentImportResult:
        return InstrumentImportResult(
            action=action,
            legacy_id=record.legacy_id,
            incoming_entity=incoming,
            resolved_entity=existing,
            issuer_entity=issuer,
            match_result=match_result,
            reason=reason,
        )
