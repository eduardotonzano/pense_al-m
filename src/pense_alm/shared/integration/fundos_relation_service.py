"""Fase 3 da importacao de Fundos: relacoes de prestadora (FU7.2).

Sobre o FundosEntityPhase das fases 1 e 2 (mapas funds, providers e
backlog_funds pelo CNPJ canonico), cria, reabre ou fecha ADMINISTERED_BY,
CUSTODIED_BY e MANAGES pelas regras de fundos_relation_rules:

- fundo em funcionamento normal resolvido: os pares lidos sao comparados com
  as relacoes gravadas dele, lidas pelos dois lados (como origem e como
  destino; sem o destino, as MANAGES gravadas nunca seriam achadas). Cada
  criacao, reabertura ou fechamento e um save, numa transacao propria;
- fundo em funcionamento normal nao resolvido: so conta os pares;
- fundo do backlog ja na camada (S8, decisao B2): as relacoes deste
  adaptador (B4) sao lidas e contadas, nunca escritas;
- fundo ausente do retrato: as relacoes ativas deste adaptador cujo fundo
  nao tem CNPJ entre os assuntos do retrato sao contadas (informativo) e
  nunca escritas.

A leitura do destino nao e protegida: falha de leitura e sistemica e
interrompe a execucao. Uma excecao na montagem ou no save de uma relacao
vira erro contado por tipo de relacao, operacao e tipo da excecao, sem a
mensagem, e a execucao segue. A trava B6 e a orquestracao das tres fases
ficam em fundos_cadastro_import.
"""

from collections import Counter

from pense_alm.shared.entities import IdentifierType, IdentifierValidationError

from .fundos_adapter import RELATION_TYPES, FundosAdapter, SituationGroup
from .fundos_import_service import FundosEntityPhase
from .fundos_records import CadastroSnapshot
from .fundos_relation_report import (
    TYPE_COUNTERS,
    TYPE_FIELDS,
    FundosRelationError,
    FundosRelationReport,
    RelacoesNaoCriadas,
    RelacoesPorTipo,
)
from .fundos_relation_rules import (
    RelationOutcome,
    classify,
    collect_pairs,
    fund_side,
    relationship_to_save,
    unresolved_pair_types,
)


_OUTCOME_FIELDS = {
    RelationOutcome.CRIADA: "criadas",
    RelationOutcome.MANTIDA: "mantidas",
    RelationOutcome.REABERTA: "reabertas",
    RelationOutcome.OUTRA_FONTE_PRESENTE: "outra_fonte_presente",
    RelationOutcome.FECHADA: "fechadas",
    RelationOutcome.FECHAMENTO_SUSPENSO: "fechamento_suspenso",
    RelationOutcome.INATIVA_AUSENTE: "inativa_ausente",
    RelationOutcome.OUTRA_FONTE_AUSENTE: "outra_fonte_ausente",
}


def _outcome_field(decision) -> str:
    if decision.outcome is RelationOutcome.STATUS_INESPERADO:
        if decision.pair is not None:
            return "status_inesperado_presente"

        return "status_inesperado_ausente"

    return _OUTCOME_FIELDS[decision.outcome]


def _type_counts(counter: Counter) -> RelacoesPorTipo:
    return RelacoesPorTipo(
        nao_criadas=RelacoesNaoCriadas(
            prestadora_sem_entidade=counter["prestadora_sem_entidade"],
            autorrelacao=counter["autorrelacao"],
        ),
        **{name: counter[name] for name in TYPE_COUNTERS},
    )


class FundosRelationService:
    """Cria, reabre ou fecha as relacoes de prestadora (fase 3)."""

    def __init__(
        self,
        entity_repository,
        relationship_repository,
        adapter: FundosAdapter | None = None,
    ):
        self._entities = entity_repository
        self._relationships = relationship_repository
        self._adapter = adapter if adapter is not None else FundosAdapter()

    def _canonical(self, cnpj: str) -> str | None:
        try:
            return self._adapter.canonical_cnpj(cnpj)
        except IdentifierValidationError:
            return None

    def _stored(self, entity_id):
        # Sem try de proposito: leitura do destino. Os dois lados: como
        # origem (ADMINISTERED_BY, CUSTODIED_BY) e como destino (MANAGES).
        return tuple(self._relationships.list_by_source(entity_id)) + tuple(
            self._relationships.list_by_target(entity_id)
        )

    def _own_of_fund(self, entity_id):
        """Relacoes deste adaptador (B4), dos tres tipos, na direcao do fundo."""

        return [
            relationship
            for relationship in self._stored(entity_id)
            if fund_side(
                relationship.relationship_type,
                relationship.source_entity_id,
                relationship.target_entity_id,
            )
            == entity_id
            and self._adapter.is_cadastro_provenance(relationship.provenance)
        ]

    def _import_fund(self, subject, fund, phase, snapshot, counts, errors):
        pairs = collect_pairs(subject, fund, phase.providers, self._adapter)

        for pair in pairs.pairs:
            counts[pair.relationship_type]["pares_lidos"] += 1

        for item in pairs.skipped:
            counts[item.relationship_type]["pares_lidos"] += 1
            counts[item.relationship_type][item.reason.value] += 1

        decisions = classify(
            fund.entity_id,
            pairs,
            self._stored(fund.entity_id),
            snapshot,
            self._adapter,
        )

        for decision in decisions:
            kind = decision.relationship_type

            if decision.stored is not None:
                counts[kind]["gravadas"] += 1

            operation = decision.operation

            if operation is not None:
                try:
                    relationship = relationship_to_save(
                        decision,
                        snapshot,
                        self._adapter,
                    )
                    self._relationships.save(relationship)
                except Exception as error:
                    errors[(kind, operation, type(error).__name__)] += 1
                    continue

            counts[kind][_outcome_field(decision)] += 1

    def _in_snapshot(self, entity_id, snapshot_cnpjs) -> bool:
        """Se a entidade tem algum CNPJ entre os assuntos do retrato."""

        entity = self._entities.get_by_id(entity_id)

        if entity is None:
            return False

        return any(
            identifier.identifier_type is IdentifierType.CNPJ
            and self._canonical(identifier.value) in snapshot_cnpjs
            for identifier in entity.identifiers
        )

    def import_relationships(
        self,
        snapshot: CadastroSnapshot,
        phase: FundosEntityPhase,
    ) -> FundosRelationReport:
        """Fase 3: relacoes de prestadora dos fundos do retrato."""

        if not isinstance(snapshot, CadastroSnapshot):
            raise TypeError("snapshot deve ser CadastroSnapshot.")

        if not isinstance(phase, FundosEntityPhase):
            raise TypeError("phase deve ser FundosEntityPhase.")

        counts = {kind: Counter() for kind in RELATION_TYPES}
        errors = Counter()
        general = Counter()
        known = set()
        snapshot_cnpjs = set()

        for subject in snapshot.subjects:
            canonical = self._canonical(subject.cnpj)

            if canonical is not None:
                snapshot_cnpjs.add(canonical)

            if self._adapter.situation_group(subject) is not SituationGroup.NORMAL:
                continue

            fund = None if canonical is None else phase.funds.get(canonical)

            if fund is None:
                general["pares_de_fundo_nao_resolvido"] += len(
                    unresolved_pair_types(subject, self._adapter)
                )
                continue

            known.add(fund.entity_id)
            self._import_fund(subject, fund, phase, snapshot, counts, errors)

        # S8 (decisao B2): fundo do backlog ja na camada; so le e conta.
        backlog = {fund.entity_id for fund in phase.backlog_funds.values()}

        for entity_id in sorted(backlog, key=str):
            known.add(entity_id)
            own = self._own_of_fund(entity_id)

            if own:
                general["fundos_fora_do_normal_com_relacao"] += 1
                general["relacoes_de_fundo_fora_do_normal_intactas"] += len(own)

        # Fundo ausente do retrato: so conta, nunca escreve.
        reference = self._adapter.reference_datetime(snapshot)
        in_snapshot = {}

        for kind in RELATION_TYPES:
            for relationship in self._relationships.list_active_at(reference, kind):
                if not self._adapter.is_cadastro_provenance(relationship.provenance):
                    continue

                side = fund_side(
                    kind,
                    relationship.source_entity_id,
                    relationship.target_entity_id,
                )

                if side in known:
                    continue

                if side not in in_snapshot:
                    in_snapshot[side] = self._in_snapshot(side, snapshot_cnpjs)

                if not in_snapshot[side]:
                    general["relacoes_de_fundo_ausente_do_retrato"] += 1

        return FundosRelationReport(
            leitura_completa=snapshot.complete,
            motivo_nao_fechar=snapshot.incomplete_reason,
            pares_de_fundo_nao_resolvido=general["pares_de_fundo_nao_resolvido"],
            fundos_fora_do_normal_com_relacao=general[
                "fundos_fora_do_normal_com_relacao"
            ],
            relacoes_de_fundo_fora_do_normal_intactas=general[
                "relacoes_de_fundo_fora_do_normal_intactas"
            ],
            relacoes_de_fundo_ausente_do_retrato=general[
                "relacoes_de_fundo_ausente_do_retrato"
            ],
            erros=tuple(
                FundosRelationError(
                    tipo_relacao=kind,
                    operacao=operation,
                    tipo=tipo,
                    quantidade=quantidade,
                )
                for (kind, operation, tipo), quantidade in errors.items()
            ),
            **{
                TYPE_FIELDS[kind]: _type_counts(counts[kind])
                for kind in RELATION_TYPES
            },
        )
