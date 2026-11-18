"""Regras das relacoes de prestadora de Fundos (FU7.2, fase 3), sem banco.

Funcoes puras: o servico le as relacoes gravadas e grava o que estas funcoes
decidirem. Regras do ADR-012 (D3, D4), do ADR-013 (D5, D7) e das decisoes
B1, B3, B4 e de 17/11/2026:

- so o grupo em funcionamento normal resolvido na fase 1 tem pares (quem
  chama garante); o par e (tipo, origem, destino) pela direcao do papel, e
  varias linhas do mesmo par viram um par so, com a menor linha;
- gestora pessoa fisica nao tem linha de papel (o banco de Fundos so guarda
  CNPJ), entao nao gera par (D5);
- prestadora sem entidade e autorrelacao nao viram par: sao contadas, uma
  vez por tipo e prestadora;
- a relacao gravada e achada pela chave canonica entre as do proprio fundo,
  qualquer que seja o relationship_id (C6). So a de proveniencia deste
  adaptador (CVM, "Fundos - CVM Cadastro") e reaberta ou fechada (B4); a
  nossa com status fora de ativo e inativo fica intacta (status_inesperado);
- reabrir: ativa, valid_to vazio, valid_from = R as 00:00 UTC, proveniencia
  da linha. Fechar: inativa, valid_to = R, proveniencia da coleta (B3). As
  duas por dataclasses.replace, preservando relationship_id, created_at,
  confidence_score e notes. A relacao nao tem updated_at: a marca da
  mudanca e a proveniencia nova;
- fechar so com leitura completa (snapshot.complete); sem ela, a relacao
  ausente fica como esta e conta como fechamento suspenso.

Os reprs dos resultados nao mostram CNPJ, nome nem id de entidade.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from uuid import UUID

from pense_alm.shared.entities import (
    Entity,
    EntityRelationship,
    IdentifierValidationError,
    RelationshipStatus,
    RelationshipType,
)

from .fundos_adapter import (
    FUND_SOURCE_TYPES,
    FUND_TARGET_TYPES,
    RELATION_TYPES,
    ROLE_RELATIONS,
    FundosAdapter,
)
from .fundos_records import CadastroSnapshot, FundosSubjectRecord


class RelationOutcome(StrEnum):
    """Resultado de um par lido ou de uma relacao gravada de um fundo."""

    CRIADA = "criada"
    MANTIDA = "mantida"
    REABERTA = "reaberta"
    OUTRA_FONTE_PRESENTE = "outra_fonte_presente"
    FECHADA = "fechada"
    FECHAMENTO_SUSPENSO = "fechamento_suspenso"
    INATIVA_AUSENTE = "inativa_ausente"
    OUTRA_FONTE_AUSENTE = "outra_fonte_ausente"
    STATUS_INESPERADO = "status_inesperado"


class PairSkip(StrEnum):
    """Motivo para uma linha de papel nao virar par."""

    PRESTADORA_SEM_ENTIDADE = "prestadora_sem_entidade"
    AUTORRELACAO = "autorrelacao"


class RelationOperation(StrEnum):
    """Gravacao que um resultado pede (para contar erros por operacao)."""

    CRIAR = "criar"
    REABRIR = "reabrir"
    FECHAR = "fechar"


_WITH_PAIR_AND_STORED = frozenset(
    {
        RelationOutcome.MANTIDA,
        RelationOutcome.REABERTA,
        RelationOutcome.OUTRA_FONTE_PRESENTE,
    }
)
_ABSENT = frozenset(
    {
        RelationOutcome.FECHADA,
        RelationOutcome.FECHAMENTO_SUSPENSO,
        RelationOutcome.INATIVA_AUSENTE,
        RelationOutcome.OUTRA_FONTE_AUSENTE,
    }
)
_OPERATIONS = {
    RelationOutcome.CRIADA: RelationOperation.CRIAR,
    RelationOutcome.REABERTA: RelationOperation.REABRIR,
    RelationOutcome.FECHADA: RelationOperation.FECHAR,
}


def _require_relation_type(kind) -> None:
    if not isinstance(kind, RelationshipType) or kind not in RELATION_TYPES:
        raise ValueError("Tipo de relacao fora do adaptador de Fundos.")


def _fund_side(kind: RelationshipType, source_id: UUID, target_id: UUID):
    """O id do lado do fundo, pela direcao do tipo; None fora dos tres."""

    if kind in FUND_SOURCE_TYPES:
        return source_id

    if kind in FUND_TARGET_TYPES:
        return target_id

    return None


@dataclass(frozen=True, slots=True)
class RelationPair:
    """Par lido: (tipo, origem, destino) e a menor linha de papel em R."""

    relationship_type: RelationshipType
    source_entity_id: UUID = field(repr=False)
    target_entity_id: UUID = field(repr=False)
    party_observation_id: int

    def __post_init__(self) -> None:
        _require_relation_type(self.relationship_type)

        if not isinstance(self.source_entity_id, UUID) or not isinstance(
            self.target_entity_id, UUID
        ):
            raise TypeError("Origem e destino devem ser UUID.")

        if self.source_entity_id == self.target_entity_id:
            raise ValueError("Origem e destino nao podem ser a mesma entidade.")

        if isinstance(self.party_observation_id, bool) or not isinstance(
            self.party_observation_id, int
        ):
            raise TypeError("party_observation_id deve ser inteiro.")

        if self.party_observation_id < 1:
            raise ValueError("party_observation_id deve ser positivo.")

    @property
    def canonical_key(self) -> str:
        return (
            f"{self.source_entity_id}:"
            f"{self.relationship_type.value}:"
            f"{self.target_entity_id}"
        )


@dataclass(frozen=True, slots=True)
class SkippedPair:
    """Linha de papel que nao virou par, contada uma vez por prestadora."""

    relationship_type: RelationshipType
    reason: PairSkip

    def __post_init__(self) -> None:
        _require_relation_type(self.relationship_type)

        if not isinstance(self.reason, PairSkip):
            raise TypeError("reason deve ser PairSkip.")


@dataclass(frozen=True, slots=True)
class FundPairs:
    """Pares lidos de um fundo e as linhas que nao viraram par."""

    pairs: tuple[RelationPair, ...] = ()
    skipped: tuple[SkippedPair, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (("pairs", RelationPair), ("skipped", SkippedPair)):
            items = getattr(self, name)

            if isinstance(items, str) or not isinstance(items, (tuple, list)):
                raise TypeError(f"{name} deve ser uma tupla.")

            if any(not isinstance(item, kind) for item in items):
                raise TypeError(f"{name} deve conter {kind.__name__}.")

            object.__setattr__(self, name, tuple(items))


@dataclass(frozen=True, slots=True)
class RelationDecision:
    """O que fazer com um par lido ou com uma relacao gravada do fundo.

    criada: so o par. Ausentes (fechada, fechamento_suspenso,
    inativa_ausente, outra_fonte_ausente): so a gravada. mantida, reaberta e
    outra_fonte_presente: os dois. status_inesperado: a gravada, com o par
    quando ele foi lido.
    """

    outcome: RelationOutcome
    relationship_type: RelationshipType
    pair: RelationPair | None = field(default=None, repr=False)
    stored: EntityRelationship | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, RelationOutcome):
            raise TypeError("outcome deve ser RelationOutcome.")

        _require_relation_type(self.relationship_type)

        if self.pair is not None and not isinstance(self.pair, RelationPair):
            raise TypeError("pair deve ser RelationPair.")

        if self.stored is not None and not isinstance(
            self.stored, EntityRelationship
        ):
            raise TypeError("stored deve ser EntityRelationship.")

        has_pair = self.pair is not None
        has_stored = self.stored is not None

        if self.outcome is RelationOutcome.CRIADA:
            coherent = has_pair and not has_stored
        elif self.outcome in _ABSENT:
            coherent = has_stored and not has_pair
        elif self.outcome in _WITH_PAIR_AND_STORED:
            coherent = has_pair and has_stored
        else:
            coherent = has_stored

        if not coherent:
            raise ValueError("Resultado incoerente com o par e a relacao gravada.")

        for item in (self.pair, self.stored):
            if item is not None and item.relationship_type is not self.relationship_type:
                raise ValueError("O tipo do resultado difere do par ou da gravada.")

    @property
    def operation(self) -> RelationOperation | None:
        """criar, reabrir ou fechar; None quando nada e gravado."""

        return _OPERATIONS.get(self.outcome)


def collect_pairs(
    subject: FundosSubjectRecord,
    fund: Entity,
    providers: Mapping[str, Entity],
    adapter: FundosAdapter,
) -> FundPairs:
    """Pares lidos de um grupo resolvido: um por (tipo, origem, destino).

    providers vai do CNPJ canonico para a entidade (FundosEntityPhase).
    """

    best = {}
    skipped = {}

    for link in subject.parties:
        kind = ROLE_RELATIONS[link.role]

        try:
            key = adapter.canonical_cnpj(link.cnpj)
        except IdentifierValidationError:
            key = None

        marker = (kind.value, "cnpj", key) if key is not None else (
            kind.value,
            "texto",
            link.cnpj,
        )
        provider = None if key is None else providers.get(key)

        if provider is None:
            skipped[marker] = SkippedPair(kind, PairSkip.PRESTADORA_SEM_ENTIDADE)
            continue

        if provider.entity_id == fund.entity_id:
            skipped[marker] = SkippedPair(kind, PairSkip.AUTORRELACAO)
            continue

        kind, source_id, target_id = adapter.relation_ends(
            link.role,
            fund.entity_id,
            provider.entity_id,
        )
        pair_key = (kind, source_id, target_id)
        current = best.get(pair_key)

        if current is None or link.party_observation_id < current.party_observation_id:
            best[pair_key] = RelationPair(
                kind,
                source_id,
                target_id,
                link.party_observation_id,
            )

    return FundPairs(
        pairs=tuple(sorted(best.values(), key=lambda pair: pair.canonical_key)),
        skipped=tuple(
            sorted(
                skipped.values(),
                key=lambda item: (item.relationship_type.value, item.reason.value),
            )
        ),
    )


def _present(pair, stored, adapter) -> RelationDecision:
    kind = pair.relationship_type

    if stored is None:
        return RelationDecision(RelationOutcome.CRIADA, kind, pair=pair)

    if not adapter.is_cadastro_provenance(stored.provenance):
        outcome = RelationOutcome.OUTRA_FONTE_PRESENTE
    elif stored.status is RelationshipStatus.ACTIVE:
        outcome = RelationOutcome.MANTIDA
    elif stored.status is RelationshipStatus.INACTIVE:
        outcome = RelationOutcome.REABERTA
    else:
        outcome = RelationOutcome.STATUS_INESPERADO

    return RelationDecision(outcome, kind, pair=pair, stored=stored)


def _absent(stored, snapshot, adapter) -> RelationDecision:
    if not adapter.is_cadastro_provenance(stored.provenance):
        outcome = RelationOutcome.OUTRA_FONTE_AUSENTE
    elif stored.status is RelationshipStatus.INACTIVE:
        outcome = RelationOutcome.INATIVA_AUSENTE
    elif stored.status is RelationshipStatus.ACTIVE:
        outcome = (
            RelationOutcome.FECHADA
            if snapshot.complete
            else RelationOutcome.FECHAMENTO_SUSPENSO
        )
    else:
        outcome = RelationOutcome.STATUS_INESPERADO

    return RelationDecision(outcome, stored.relationship_type, stored=stored)


def classify(
    fund_id: UUID,
    pairs: FundPairs,
    stored: Iterable[EntityRelationship],
    snapshot: CadastroSnapshot,
    adapter: FundosAdapter,
) -> tuple[RelationDecision, ...]:
    """Compara os pares lidos de um fundo com as relacoes gravadas dele.

    stored pode trazer qualquer relacao da origem ou do destino do fundo:
    so entram os tres tipos, na direcao em que o fundo e o lado do fundo.
    Saida estavel: os pares lidos e depois as ausentes, pela chave.
    """

    if not isinstance(fund_id, UUID):
        raise TypeError("fund_id deve ser UUID.")

    if not isinstance(pairs, FundPairs):
        raise TypeError("pairs deve ser FundPairs.")

    own = {}

    for relationship in stored:
        if not isinstance(relationship, EntityRelationship):
            raise TypeError("stored deve conter EntityRelationship.")

        side = _fund_side(
            relationship.relationship_type,
            relationship.source_entity_id,
            relationship.target_entity_id,
        )

        if side != fund_id:
            continue

        key = relationship.canonical_key

        if key in own:
            raise ValueError("Chave canonica repetida nas relacoes gravadas.")

        own[key] = relationship

    decisions = []
    read = set()

    for pair in sorted(pairs.pairs, key=lambda item: item.canonical_key):
        side = _fund_side(
            pair.relationship_type,
            pair.source_entity_id,
            pair.target_entity_id,
        )

        if side != fund_id:
            raise ValueError("Par de outro fundo.")

        if pair.canonical_key in read:
            raise ValueError("Par repetido.")

        read.add(pair.canonical_key)
        decisions.append(_present(pair, own.get(pair.canonical_key), adapter))

    for key in sorted(own):
        if key not in read:
            decisions.append(_absent(own[key], snapshot, adapter))

    return tuple(decisions)


def relationship_to_save(
    decision: RelationDecision,
    snapshot: CadastroSnapshot,
    adapter: FundosAdapter,
) -> EntityRelationship | None:
    """A relacao a gravar (criar, reabrir ou fechar); None nos demais.

    Pode levantar EntityValidationError (por exemplo, fechar com R anterior
    ao valid_from); o servico conta como erro da operacao.
    """

    if not isinstance(decision, RelationDecision):
        raise TypeError("decision deve ser RelationDecision.")

    reference = adapter.reference_datetime(snapshot)

    if decision.outcome is RelationOutcome.CRIADA:
        pair = decision.pair

        return adapter.build_relationship(
            pair.relationship_type,
            pair.source_entity_id,
            pair.target_entity_id,
            adapter.relationship_provenance(snapshot, pair.party_observation_id),
            snapshot,
        )

    if decision.outcome is RelationOutcome.REABERTA:
        return replace(
            decision.stored,
            status=RelationshipStatus.ACTIVE,
            valid_from=reference,
            valid_to=None,
            provenance=adapter.relationship_provenance(
                snapshot,
                decision.pair.party_observation_id,
            ),
        )

    if decision.outcome is RelationOutcome.FECHADA:
        return replace(
            decision.stored,
            status=RelationshipStatus.INACTIVE,
            valid_to=reference,
            provenance=adapter.closing_provenance(snapshot),
        )

    return None
