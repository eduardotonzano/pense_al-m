"""Fase 4 da importacao de Fundos: INVESTS_IN a partir do CDA (FU7.2, PR C2).

Sobre o CdaSnapshot do leitor e o FundosEntityPhase das fases 1 e 2 (mapas
funds e backlog_funds pelo CNPJ canonico), cria, reabre ou fecha INVESTS_IN
pelas regras de fundos_investment_rules (ADR-013, D9; decisoes C1 a C7 de
19/11/2026 e D1 a D6 de 23/11/2026):

- sem dados de CDA (sem a migration 004 ou sem coleta): so o motivo; o
  destino nao e lido;
- cada detentor do CDA cai numa categoria so, pelo CNPJ canonico. Em
  funcionamento normal e resolvido nas fases 1 e 2 (phase.funds): os pares
  lidos no L_H dele sao comparados com as INVESTS_IN que saem dele, e cada
  criacao, reabertura ou fechamento e um save, numa transacao propria. O
  fechamento e por detentor: o L_H incompleto suspende o dele, e os outros
  detentores seguem (D6). Do backlog ja na camada (S8): as INVESTS_IN deste
  adaptador que saem dele sao lidas e contadas, nunca escritas. Fundo da
  camada fora do retrato, fora da camada ou com CNPJ recusado: so conta;
- o investido e achado pelo CNPJ nas fases 1 e 2 ou no destino, uma vez por
  execucao; so vira par se ja esta na camada como FIDC ou FIAGRO (C2). O
  par cujo investido nao esta em funcionamento normal no retrato e criado e
  contado a parte (informativo);
- atraso (C4, informativo): o detentor processado com L_H em mes anterior
  ao da maior competencia completa (C_max) e contado pelos meses de atraso,
  com as INVESTS_IN deste adaptador que ficam ativas nele;
- detentor ausente do CDA (D5, informativo): as INVESTS_IN deste adaptador
  ativas na competencia mais nova do CDA cujo detentor nao esta entre os
  detentores do CDA sao contadas, numa leitura so por tipo, e nunca escritas.

A leitura do destino nao e protegida: falha de leitura e sistemica e
interrompe a execucao. Uma excecao na montagem ou no save de uma relacao
vira erro contado por operacao e tipo da excecao, sem a mensagem, e a
execucao segue. A trava do CDA e a orquestracao das quatro fases ficam em
fundos_cadastro_import.
"""

from collections import Counter

from pense_alm.shared.entities import (
    IdentifierType,
    IdentifierValidationError,
    RelationshipStatus,
)

from .fundos_adapter import FUND_ENTITY_TYPES, FundosAdapter
from .fundos_import_service import FundosEntityPhase
from .fundos_investment_report import (
    COUNTERS,
    AtrasoEmMeses,
    FundosInvestmentError,
    FundosInvestmentReport,
    InvestimentosNaoCriados,
)
from .fundos_investment_rules import (
    INVESTS_IN,
    HolderReading,
    InvestmentSkip,
    classify_investments,
    collect_investment_pairs,
    investment_to_save,
)
from .fundos_records import CadastroSnapshot, CdaSnapshot, months_between
from .fundos_relation_rules import RelationOutcome


# Categorias do detentor (contadores do relatorio).
IN_LAYER = "detentores_na_camada"
OUT_OF_NORMAL = "detentores_fora_do_normal_na_camada"
OUT_OF_LAYER = "detentores_fora_da_camada"
OUT_OF_SNAPSHOT = "detentores_fora_do_retrato"
CNPJ_REFUSED = "detentores_cnpj_recusado"

_OUTCOME_FIELDS = {
    RelationOutcome.CRIADA: "criadas",
    RelationOutcome.MANTIDA: "mantidas",
    RelationOutcome.REABERTA: "reabertas",
    RelationOutcome.OUTRA_FONTE_PRESENTE: "outra_fonte_presente",
    RelationOutcome.FECHADA: "fechadas",
    RelationOutcome.FECHAMENTO_SUSPENSO: "fechamento_suspenso",
    RelationOutcome.SUSPENSA_POR_CONFIDENCIAL: "suspensa_por_confidencial",
    RelationOutcome.INATIVA_AUSENTE: "inativa_ausente",
    RelationOutcome.OUTRA_FONTE_AUSENTE: "outra_fonte_ausente",
}
# Resultados que valem com e sem o par lido: o campo leva o lado.
_SPLIT_FIELDS = {
    RelationOutcome.STATUS_INESPERADO: "status_inesperado",
    RelationOutcome.VIGENCIA_POSTERIOR: "vigencia_posterior",
}
# Resultados em que a INVESTS_IN deste adaptador fica ativa (atraso, C4); a
# vigencia posterior so quando a gravada esta ativa.
_ACTIVE_AFTER = (
    RelationOutcome.CRIADA,
    RelationOutcome.MANTIDA,
    RelationOutcome.REABERTA,
    RelationOutcome.FECHAMENTO_SUSPENSO,
    RelationOutcome.SUSPENSA_POR_CONFIDENCIAL,
)


def _stays_active(decision) -> bool:
    if decision.outcome is RelationOutcome.VIGENCIA_POSTERIOR:
        return decision.stored.status is RelationshipStatus.ACTIVE

    return decision.outcome in _ACTIVE_AFTER


def _outcome_field(decision) -> str:
    prefix = _SPLIT_FIELDS.get(decision.outcome)

    if prefix is not None:
        return prefix + ("_presente" if decision.pair is not None else "_ausente")

    return _OUTCOME_FIELDS[decision.outcome]


def _reading(cda: CdaSnapshot, holder) -> HolderReading:
    """O L_H do detentor e a coleta usada no fechamento."""

    competence = cda.competence(holder.competence)

    return HolderReading(
        competence=holder.competence,
        complete=competence.complete,
        has_confidential=holder.has_confidential,
        closing_run_id=competence.closing_run_id,
        closing_collected_at=competence.closing_started_at,
    )


class FundosInvestmentService:
    """Cria, reabre ou fecha INVESTS_IN a partir do CDA (fase 4)."""

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

    def _holder(self, cnpj, phase, snapshot_cnpjs):
        """(categoria, CNPJ canonico, entidade); a entidade, se ja esta na camada."""

        canonical = self._canonical(cnpj)

        if canonical is None:
            return CNPJ_REFUSED, None, None

        if canonical in phase.funds:
            return IN_LAYER, canonical, phase.funds[canonical]

        if canonical in phase.backlog_funds:
            return OUT_OF_NORMAL, canonical, phase.backlog_funds[canonical]

        # Sem try de proposito: leitura do destino.
        existing = self._entities.get_by_identifier(IdentifierType.CNPJ, canonical)

        if existing is None or existing.entity_type not in FUND_ENTITY_TYPES:
            return OUT_OF_LAYER, canonical, None

        if canonical not in snapshot_cnpjs:
            return OUT_OF_SNAPSHOT, canonical, existing

        # No retrato, sem ser resolvido nas fases 1 e 2: so conta.
        return OUT_OF_LAYER, canonical, existing

    def _investees(self, links, phase, cache):
        """Do CNPJ canonico a entidade ja na camada, para os investidos das linhas."""

        found = {}

        for link in links:
            key = self._canonical(link.investee_cnpj)

            if key is None:
                continue

            if key not in cache:
                entity = phase.funds.get(key)

                if entity is None:
                    entity = phase.backlog_funds.get(key)

                if entity is None:
                    # Sem try de proposito: leitura do destino.
                    entity = self._entities.get_by_identifier(IdentifierType.CNPJ, key)

                cache[key] = entity

            if cache[key] is not None:
                found[key] = cache[key]

        return found

    def _own(self, entity_id):
        """As INVESTS_IN deste adaptador que saem do detentor (S8)."""

        # Sem try de proposito: leitura do destino.
        return [
            relationship
            for relationship in self._relationships.list_by_source(entity_id)
            if relationship.relationship_type is INVESTS_IN
            and self._adapter.is_cda_provenance(relationship.provenance)
        ]

    def _import_holder(self, holder, entity, cda, phase, state):
        """Pares, decisoes e saves de um detentor; devolve as nossas que ficam ativas."""

        cache, normal, counts, skipped, errors = state
        reading = _reading(cda, holder)
        pairs = collect_investment_pairs(
            entity,
            holder.links,
            self._investees(holder.links, phase, cache),
            holder.competence,
        )
        counts["pares_lidos"] += len(pairs.pairs) + len(pairs.skipped)
        skipped.update(item.reason.value for item in pairs.skipped)
        counts["pares_com_investido_fora_do_normal"] += sum(
            1 for pair in pairs.pairs if pair.investee_entity_id not in normal
        )

        if not reading.complete:
            counts["detentores_em_cda_incompleto"] += 1

        decisions = classify_investments(
            entity.entity_id,
            pairs,
            # Sem try de proposito: leitura do destino.
            self._relationships.list_by_source(entity.entity_id),
            reading,
            self._adapter,
        )

        active = 0

        for decision in decisions:
            if decision.stored is not None:
                counts["gravadas"] += 1

            operation = decision.operation

            if operation is not None:
                try:
                    self._relationships.save(
                        investment_to_save(decision, reading, self._adapter)
                    )
                except Exception as error:
                    errors[(operation, type(error).__name__)] += 1
                    continue

            counts[_outcome_field(decision)] += 1
            active += _stays_active(decision)

        return active

    def _absent_from_cda(self, cda, holder_ids) -> int:
        """D5: INVESTS_IN nossas ativas cujo detentor nao esta entre os do CDA."""

        latest = cda.latest_competence

        if latest is None:
            return 0

        # Sem try de proposito: leitura do destino, uma so pelo tipo.
        return sum(
            1
            for relationship in self._relationships.list_active_at(
                self._adapter.competence_datetime(latest), INVESTS_IN
            )
            if self._adapter.is_cda_provenance(relationship.provenance)
            and relationship.source_entity_id not in holder_ids
        )

    def import_investments(
        self,
        cda: CdaSnapshot,
        snapshot: CadastroSnapshot,
        phase: FundosEntityPhase,
    ) -> FundosInvestmentReport:
        """Fase 4: INVESTS_IN dos detentores do CDA, cada um no seu L_H."""

        if not isinstance(cda, CdaSnapshot):
            raise TypeError("cda deve ser CdaSnapshot.")

        if not isinstance(snapshot, CadastroSnapshot):
            raise TypeError("snapshot deve ser CadastroSnapshot.")

        if not isinstance(phase, FundosEntityPhase):
            raise TypeError("phase deve ser FundosEntityPhase.")

        if not cda.available:
            return FundosInvestmentReport.sem_cda(cda.unavailable_reason)

        snapshot_cnpjs = {
            canonical
            for canonical in (self._canonical(subject.cnpj) for subject in snapshot.subjects)
            if canonical is not None
        }
        counts = Counter()
        skipped = Counter()
        errors = Counter()
        delay = {}
        seen = set()
        holder_ids = set()
        latest = cda.latest_complete
        normal = {fund.entity_id for fund in phase.funds.values()}
        state = ({}, normal, counts, skipped, errors)

        for holder in cda.holders:
            category, canonical, entity = self._holder(holder.cnpj, phase, snapshot_cnpjs)

            if canonical is not None:
                if canonical in seen:
                    raise ValueError("Dois detentores do CDA com o mesmo CNPJ canonico.")

                seen.add(canonical)

            if entity is not None:
                holder_ids.add(entity.entity_id)

            counts["detentores_lidos"] += 1
            counts[category] += 1

            if category == IN_LAYER:
                active = self._import_holder(holder, entity, cda, phase, state)
                months = 0 if latest is None else months_between(holder.competence, latest)

                if months >= 1:
                    holders, relations = delay.get(months, (0, 0))
                    delay[months] = (holders + 1, relations + active)
            elif category == OUT_OF_NORMAL:
                # S8: so le e conta.
                own = self._own(entity.entity_id)

                if own:
                    counts["detentores_fora_do_normal_com_relacao"] += 1
                    counts["relacoes_de_detentor_fora_do_normal_intactas"] += len(own)

        counts["relacoes_de_detentor_ausente_do_cda"] = self._absent_from_cda(cda, holder_ids)
        atraso = tuple(
            AtrasoEmMeses(meses=months, detentores=holders, relacoes=relations)
            for months, (holders, relations) in sorted(delay.items())
        )
        counts["detentores_atrasados"] = sum(item.detentores for item in atraso)
        counts["relacoes_de_detentor_atrasado"] = sum(item.relacoes for item in atraso)

        return FundosInvestmentReport(
            cda_disponivel=True,
            leitura_completa=cda.complete,
            motivo_incompleto=cda.incomplete_reason,
            competencia_mais_nova_completa=cda.latest_complete,
            nao_criadas=InvestimentosNaoCriados(
                **{reason.value: skipped[reason.value] for reason in InvestmentSkip}
            ),
            erros=tuple(
                FundosInvestmentError(operacao=operation, tipo=tipo, quantidade=quantidade)
                for (operation, tipo), quantidade in errors.items()
            ),
            atraso=atraso,
            **{name: counts[name] for name in COUNTERS},
        )
