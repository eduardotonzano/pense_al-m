"""Regras da relacao INVESTS_IN a partir do CDA (FU7.2, PR C), sem banco.

Funcoes puras: o servico da fase 4 le as relacoes gravadas e grava o que
estas funcoes decidirem. Regras do ADR-013 (D6, D7, D9) e das decisoes de
19/11/2026 (C2, C3, C4):

- o par vai do fundo detentor para o fundo investido; varias linhas de
  holdings do mesmo investido na competencia viram um par so, com a menor
  linha;
- so ha par se o investido ja esta na camada como FIDC ou FIAGRO (C2); o
  resto e contado por motivo, uma vez por investido: CNPJ recusado, fora da
  camada, de outro tipo ou autorrelacao;
- a gravada e achada pela chave canonica entre as INVESTS_IN que saem do
  detentor, qualquer que seja o relationship_id. So a de proveniencia do CDA
  (CVM, "Fundos - CVM CDA") e reaberta ou fechada;
- ordem, como no B2: outra fonte, status fora de ativo e inativo, e so
  depois a vigencia posterior: a nossa cuja maior data (reference_date da
  proveniencia ou valid_from) passa da competencia do detentor fica intacta;
- so a nossa ativa ausente fecha. Leitura incompleta suspende o fechamento;
  com leitura completa e posicao confidencial na competencia, tambem nao
  fecha (C3, suspensa_por_confidencial). As demais ausentes seguem as regras
  do B2;
- reabrir: ativa, valid_to vazio, valid_from = competencia as 00:00 UTC e a
  proveniencia da linha de holdings. Fechar: inativa, valid_to = competencia
  e a proveniencia da coleta. As duas por dataclasses.replace, preservando
  relationship_id, created_at, confidence_score e notes.

Os reprs nao mostram CNPJ, nome nem id de entidade.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pense_alm.shared.entities import (
    Entity,
    EntityRelationship,
    IdentifierValidationError,
    RelationshipType,
    normalize_cnpj,
)

from .fundos_adapter import FUND_ENTITY_TYPES
from .fundos_records import CdaHoldingLink
from .fundos_relation_rules import (
    RelationOperation,
    RelationOutcome,
    decision_is_coherent,
    operation_for,
)


INVESTS_IN = RelationshipType.INVESTS_IN


class InvestmentSkip(StrEnum):
    """Motivo para um investido do CDA nao virar par."""

    CNPJ_RECUSADO = "cnpj_recusado"
    INVESTIDO_FORA_DA_CAMADA = "investido_fora_da_camada"
    INVESTIDO_DE_OUTRO_TIPO = "investido_de_outro_tipo"
    AUTORRELACAO = "autorrelacao"


def _require_row_id(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} deve ser inteiro.")

    if value < 1:
        raise ValueError(f"{name} deve ser positivo.")


def _require_date(value, name: str) -> None:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError(f"{name} deve ser date.")


def _require_aware(value, name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} deve ser datetime.")

    if value.utcoffset() is None:
        raise ValueError(f"{name} deve possuir timezone.")


@dataclass(frozen=True, slots=True)
class InvestmentPair:
    """Par lido: detentor, investido, a menor linha de holdings e a competencia."""

    holder_entity_id: UUID = field(repr=False)
    investee_entity_id: UUID = field(repr=False)
    holding_id: int
    competence: date
    collected_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.holder_entity_id, UUID) or not isinstance(
            self.investee_entity_id, UUID
        ):
            raise TypeError("Detentor e investido devem ser UUID.")

        if self.holder_entity_id == self.investee_entity_id:
            raise ValueError("Detentor e investido nao podem ser a mesma entidade.")

        _require_row_id(self.holding_id, "holding_id")
        _require_date(self.competence, "competence")
        _require_aware(self.collected_at, "collected_at")

    @property
    def relationship_type(self) -> RelationshipType:
        return INVESTS_IN

    @property
    def canonical_key(self) -> str:
        return f"{self.holder_entity_id}:{INVESTS_IN.value}:{self.investee_entity_id}"


@dataclass(frozen=True, slots=True)
class SkippedInvestment:
    """Investido que nao virou par, contado uma vez por investido."""

    reason: InvestmentSkip

    def __post_init__(self) -> None:
        if not isinstance(self.reason, InvestmentSkip):
            raise TypeError("reason deve ser InvestmentSkip.")


@dataclass(frozen=True, slots=True)
class HolderPairs:
    """Pares lidos de um detentor e os investidos que nao viraram par."""

    pairs: tuple[InvestmentPair, ...] = ()
    skipped: tuple[SkippedInvestment, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (("pairs", InvestmentPair), ("skipped", SkippedInvestment)):
            items = getattr(self, name)

            if isinstance(items, str) or not isinstance(items, (tuple, list)):
                raise TypeError(f"{name} deve ser uma tupla.")

            if any(not isinstance(item, kind) for item in items):
                raise TypeError(f"{name} deve conter {kind.__name__}.")

            object.__setattr__(self, name, tuple(items))


@dataclass(frozen=True, slots=True)
class HolderReading:
    """A competencia do detentor (L_H) e a coleta usada para fechar."""

    competence: date
    complete: bool
    has_confidential: bool
    closing_run_id: int
    closing_collected_at: datetime

    def __post_init__(self) -> None:
        _require_date(self.competence, "competence")

        for name in ("complete", "has_confidential"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} deve ser booleano.")

        _require_row_id(self.closing_run_id, "closing_run_id")
        _require_aware(self.closing_collected_at, "closing_collected_at")


@dataclass(frozen=True, slots=True)
class InvestmentDecision:
    """O que fazer com um par lido ou com uma INVESTS_IN gravada do detentor.

    As formas sao as do B2 (decision_is_coherent): criada, so o par; as
    ausentes (inclusive suspensa_por_confidencial), so a gravada; mantida,
    reaberta e outra_fonte_presente, os dois; status_inesperado e
    vigencia_posterior, a gravada, com o par quando ele foi lido.
    """

    outcome: RelationOutcome
    pair: InvestmentPair | None = field(default=None, repr=False)
    stored: EntityRelationship | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, RelationOutcome):
            raise TypeError("outcome deve ser RelationOutcome.")

        if self.pair is not None and not isinstance(self.pair, InvestmentPair):
            raise TypeError("pair deve ser InvestmentPair.")

        if self.stored is not None:
            if not isinstance(self.stored, EntityRelationship):
                raise TypeError("stored deve ser EntityRelationship.")

            if self.stored.relationship_type is not INVESTS_IN:
                raise ValueError("A gravada deve ser INVESTS_IN.")

        if not decision_is_coherent(
            self.outcome,
            self.pair is not None,
            self.stored is not None,
        ):
            raise ValueError("Resultado incoerente com o par e a relacao gravada.")

        if (
            self.pair is not None
            and self.stored is not None
            and self.pair.canonical_key != self.stored.canonical_key
        ):
            raise ValueError("O par e a gravada tem chaves diferentes.")

    @property
    def relationship_type(self) -> RelationshipType:
        return INVESTS_IN

    @property
    def operation(self) -> RelationOperation | None:
        """criar, reabrir ou fechar; None quando nada e gravado."""

        return operation_for(self.outcome)


def collect_investment_pairs(
    holder: Entity,
    links: Iterable[CdaHoldingLink],
    investees: Mapping[str, Entity],
    competence: date,
) -> HolderPairs:
    """Pares lidos de um detentor na competencia: um por investido.

    links sao as linhas de holdings do detentor na competencia; investees vai
    do CNPJ canonico para a entidade ja na camada (o servico busca).
    """

    if not isinstance(holder, Entity):
        raise TypeError("holder deve ser Entity.")

    _require_date(competence, "competence")

    best = {}
    skipped = {}

    for link in links:
        if not isinstance(link, CdaHoldingLink):
            raise TypeError("links deve conter CdaHoldingLink.")

        try:
            key = normalize_cnpj(link.investee_cnpj)
        except IdentifierValidationError:
            skipped[("texto", link.investee_cnpj)] = InvestmentSkip.CNPJ_RECUSADO
            continue

        investee = investees.get(key)

        if investee is None:
            reason = InvestmentSkip.INVESTIDO_FORA_DA_CAMADA
        elif investee.entity_type not in FUND_ENTITY_TYPES:
            reason = InvestmentSkip.INVESTIDO_DE_OUTRO_TIPO
        elif investee.entity_id == holder.entity_id:
            reason = InvestmentSkip.AUTORRELACAO
        else:
            reason = None

        if reason is not None:
            skipped[("cnpj", key)] = reason
            continue

        current = best.get(investee.entity_id)

        if current is None or link.holding_id < current.holding_id:
            best[investee.entity_id] = InvestmentPair(
                holder.entity_id,
                investee.entity_id,
                link.holding_id,
                competence,
                link.collected_at,
            )

    return HolderPairs(
        pairs=tuple(sorted(best.values(), key=lambda pair: pair.canonical_key)),
        skipped=tuple(
            SkippedInvestment(reason)
            for reason in sorted(skipped.values(), key=lambda item: item.value)
        ),
    )
