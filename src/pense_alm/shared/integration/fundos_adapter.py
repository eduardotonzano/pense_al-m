"""Adaptador do cadastro de Fundos para entidades da camada (FU7.2).

Transforma os records do leitor (fundos_reader) em Entity. Nao grava nada e
nao decide o que entra: isso e do servico. Regras do ADR-012, do ADR-013 e
das decisoes de 16 e 17/11/2026:

- entity_id = uuid5(NAMESPACE_URL, "pense-alm:fundos:cnpj:" + CNPJ canonico),
  um namespace so para fundo, classe e prestadora (um CNPJ, uma entidade);
- tipo so pelo par Tipo_Fundo e Tipo_Classe, com o texto exato da CVM, nunca
  pelo nome do fundo: FIDC ou FIAGRO. Valor fora do mapa, tipo ausente do
  lado que decide e par divergente viram motivo;
- situacao com o texto exato da CVM, com acento: so "Em Funcionamento
  Normal" entra (D7); as demais viram grupo de backlog;
- nome normalizado pela mesma funcao do Entity (normalize_name, que junta
  espacos), sem mexer em maiuscula nem acento. Sem nome, ou com mais de um
  nome, vira motivo;
- prestadora criada pelo adaptador: FINANCIAL_INSTITUTION, com status
  UNKNOWN (o cadastro nao informa a situacao dela);
- proveniencia: SourceType.CVM, source_reference so com id de linha do banco
  de Fundos, reference_date = competencia as 00:00 UTC e collected_at = inicio
  da coleta usada no retrato;
- relacoes de prestadora (ADR-012, D3): ADMINISTERED_BY e CUSTODIED_BY vao do
  fundo para a prestadora, MANAGES vai da gestora para o fundo; o
  relationship_id e o uuid5 da chave canonica origem:tipo:destino, como no
  adaptador de debentures; a proveniencia e a linha de party_observations
  (criar e reabrir) ou a coleta (fechar, decisao B3);
- "investe em" (ADR-013, D9; PR C): INVESTS_IN vai do fundo detentor para o
  fundo investido, com o relationship_id pelo mesmo uuid5 da chave; a
  proveniencia e "Fundos - CVM CDA", com a linha de holdings (criar e
  reabrir) ou a coleta do CDA (fechar), e as datas sao a competencia do CDA
  as 00:00 UTC.

created_at e updated_at de toda entidade sao o inicio da coleta usada na
proveniencia (snapshot.started_at), igual para todas: a entidade sai
deterministica, sem depender do relogio. As mensagens de erro nunca trazem
CNPJ nem nome.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityRelationship,
    EntityStatus,
    EntityType,
    IdentifierType,
    RelationshipStatus,
    RelationshipType,
    SourceType,
    normalize_cnpj,
    normalize_name,
)

from .fundos_records import (
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)


ENTITY_NAMESPACE = "pense-alm:fundos:cnpj:"
SOURCE_NAME_CADASTRO = "Fundos - CVM Cadastro"
SOURCE_NAME_CDA = "Fundos - CVM CDA"
NORMAL = "Em Funcionamento Normal"

# Texto exato da CVM (o mesmo SCOPE de cadastro/columns.py do modulo de
# Fundos, copiado aqui, sem importar).
FUND_TYPES = {
    "FIDC": EntityType.FIDC,
    "FIAGRO": EntityType.FIAGRO,
}
CLASS_TYPES = {
    "Classes de Cotas de Fundos FIDC": EntityType.FIDC,
    "Classes de Cotas de Fundos FIAGRO": EntityType.FIAGRO,
}

# Papel do cadastro e tipo da relacao (ADR-012, D1 e D3).
ROLE_RELATIONS = {
    "administrador": RelationshipType.ADMINISTERED_BY,
    "custodiante": RelationshipType.CUSTODIED_BY,
    "gestor": RelationshipType.MANAGES,
}
# Na forma passiva (..._BY) o fundo e a origem; em MANAGES, o destino.
FUND_SOURCE_TYPES = (
    RelationshipType.ADMINISTERED_BY,
    RelationshipType.CUSTODIED_BY,
)
FUND_TARGET_TYPES = (RelationshipType.MANAGES,)
RELATION_TYPES = FUND_SOURCE_TYPES + FUND_TARGET_TYPES
# Tipos de fundo e classe na camada (D6, D7): o detentor e o investido do
# INVESTS_IN; a fase 1 tambem reconhece por eles o fundo ja na camada.
FUND_ENTITY_TYPES = (EntityType.FIDC, EntityType.FIAGRO)


class SituationGroup(StrEnum):
    """Grupo da situacao do fundo (D7): entra, ou o grupo de backlog."""

    NORMAL = "normal"
    FASE_PRE_OPERACIONAL = "fase_pre_operacional"
    EM_LIQUIDACAO = "em_liquidacao"
    CANCELADO = "cancelado"
    INCORPORACAO = "incorporacao"
    EM_SITUACAO_ESPECIAL = "em_situacao_especial"
    SITUACAO_FORA_DA_TABELA = "situacao_fora_da_tabela"
    SEM_SITUACAO = "sem_situacao"
    SITUACAO_CONFLITANTE = "situacao_conflitante"


# Texto exato medido no banco de teste em 17/11/2026, com os acentos em
# escape para nao depender da forma do arquivo: Fase Pre-Operacional, Em
# Liquidacao, Incorporacao e Em Situacao Especial levam acento.
SITUATIONS = {
    NORMAL: SituationGroup.NORMAL,
    "Fase Pr\xe9-Operacional": SituationGroup.FASE_PRE_OPERACIONAL,
    "Em Liquida\xe7\xe3o": SituationGroup.EM_LIQUIDACAO,
    "Cancelado": SituationGroup.CANCELADO,
    "Incorpora\xe7\xe3o": SituationGroup.INCORPORACAO,
    "Em Situa\xe7\xe3o Especial": SituationGroup.EM_SITUACAO_ESPECIAL,
}


class FundosReason(StrEnum):
    """Motivo para um fundo ou uma prestadora nao virar entidade."""

    SEM_NOME = "sem_nome"
    NOME_DIVERGENTE = "nome_divergente"
    TIPO_FORA_DO_MAPA = "tipo_fora_do_mapa"
    TIPO_DIVERGENTE = "tipo_divergente"


class FundosAdapterError(ValueError):
    """O record nao pode virar entidade (a mensagem nunca traz dado)."""


def _require_row_id(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FundosAdapterError(f"{name} deve ser inteiro.")

    if value < 1:
        raise FundosAdapterError(f"{name} deve ser positivo.")


@dataclass(frozen=True, slots=True)
class NameResolution:
    """O nome resolvido (e, na prestadora, a linha que o deu) ou o motivo."""

    name: str | None = field(default=None, repr=False)
    reason: FundosReason | None = None
    party_observation_id: int | None = None

    def __post_init__(self) -> None:
        if (self.name is None) == (self.reason is None):
            raise ValueError("Informe o nome ou o motivo, nunca os dois.")

        if self.reason is not None and self.party_observation_id is not None:
            raise ValueError("Motivo nao tem linha de origem.")


@dataclass(frozen=True, slots=True)
class TypeResolution:
    """O tipo resolvido ou o motivo."""

    entity_type: EntityType | None = None
    reason: FundosReason | None = None

    def __post_init__(self) -> None:
        if (self.entity_type is None) == (self.reason is None):
            raise ValueError("Informe o tipo ou o motivo, nunca os dois.")


class FundosAdapter:
    """Converte records do cadastro de Fundos em Entity, sem gravar."""

    ENTITY_NAMESPACE = ENTITY_NAMESPACE
    SOURCE_NAME_CADASTRO = SOURCE_NAME_CADASTRO
    SOURCE_NAME_CDA = SOURCE_NAME_CDA

    @staticmethod
    def canonical_cnpj(cnpj: str) -> str:
        """CNPJ canonico pela regra da camada (ADR-011)."""

        return normalize_cnpj(cnpj)

    def entity_id(self, cnpj: str) -> UUID:
        """uuid5 do CNPJ canonico, o mesmo para fundo, classe e prestadora."""

        return uuid5(NAMESPACE_URL, ENTITY_NAMESPACE + normalize_cnpj(cnpj))

    def situation_group(self, subject: FundosSubjectRecord) -> SituationGroup:
        """Grupo da situacao do lado que decide, pelo texto exato."""

        if not subject.situacoes:
            return SituationGroup.SEM_SITUACAO

        if len(subject.situacoes) > 1:
            return SituationGroup.SITUACAO_CONFLITANTE

        return SITUATIONS.get(
            subject.situacoes[0],
            SituationGroup.SITUACAO_FORA_DA_TABELA,
        )

    def fund_name(self, subject: FundosSubjectRecord) -> NameResolution:
        """Nome do lado que decide, normalizado como o Entity (normalize_name)."""

        names = {normalize_name(name, "legal_name") for name in subject.names}

        if not names:
            return NameResolution(reason=FundosReason.SEM_NOME)

        if len(names) > 1:
            return NameResolution(reason=FundosReason.NOME_DIVERGENTE)

        return NameResolution(name=names.pop())

    def fund_type(self, subject: FundosSubjectRecord) -> TypeResolution:
        """Tipo pelo par Tipo_Fundo e Tipo_Classe; o nome nunca entra."""

        decisive = (
            subject.tipos_fundo
            if subject.source_table == "funds"
            else subject.tipos_classe
        )

        if not decisive:
            return TypeResolution(reason=FundosReason.TIPO_FORA_DO_MAPA)

        labels = set()

        for values, mapping in (
            (subject.tipos_fundo, FUND_TYPES),
            (subject.tipos_classe, CLASS_TYPES),
        ):
            for value in values:
                if value not in mapping:
                    return TypeResolution(reason=FundosReason.TIPO_FORA_DO_MAPA)

                labels.add(mapping[value])

        if len(labels) > 1:
            return TypeResolution(reason=FundosReason.TIPO_DIVERGENTE)

        return TypeResolution(entity_type=labels.pop())

    def provider_name(self, links) -> NameResolution:
        """Nome da prestadora e a menor linha em R com esse nome (P5).

        Quem chama passa so as linhas de grupos em funcionamento normal
        (P6): linha de fundo do backlog nao bloqueia a prestadora.
        """

        first_line = {}

        for link in links:
            if not isinstance(link, FundosPartyLink):
                raise TypeError("links deve conter FundosPartyLink.")

            if link.name is None:
                continue

            name = normalize_name(link.name, "legal_name")
            current = first_line.get(name)

            if current is None or link.party_observation_id < current:
                first_line[name] = link.party_observation_id

        if not first_line:
            return NameResolution(reason=FundosReason.SEM_NOME)

        if len(first_line) > 1:
            return NameResolution(reason=FundosReason.NOME_DIVERGENTE)

        ((name, party_observation_id),) = first_line.items()

        return NameResolution(
            name=name,
            party_observation_id=party_observation_id,
        )

    def cadastro_provenance(
        self,
        snapshot: CadastroSnapshot,
        source_reference: str,
    ) -> DataProvenance:
        """Proveniencia do cadastro: CVM, id de linha e datas do retrato."""

        return DataProvenance(
            source_type=SourceType.CVM,
            source_name=SOURCE_NAME_CADASTRO,
            source_reference=source_reference,
            collected_at=snapshot.started_at,
            reference_date=self.reference_datetime(snapshot),
        )

    @staticmethod
    def reference_datetime(snapshot: CadastroSnapshot) -> datetime:
        """Competencia do retrato as 00:00 UTC (proveniencia e vigencia)."""

        return datetime.combine(snapshot.reference_date, time(0, 0), tzinfo=UTC)

    def relationship_provenance(
        self,
        snapshot: CadastroSnapshot,
        party_observation_id: int,
    ) -> DataProvenance:
        """Proveniencia de criar ou reabrir: a linha do papel em R."""

        return self.cadastro_provenance(
            snapshot,
            f"fundos:party_observations:{party_observation_id}",
        )

    def closing_provenance(self, snapshot: CadastroSnapshot) -> DataProvenance:
        """Proveniencia do fechamento: a coleta que mostra a ausencia (B3)."""

        return self.cadastro_provenance(
            snapshot,
            f"fundos:collection_runs:{snapshot.collection_run_id}",
        )

    @staticmethod
    def is_cadastro_provenance(provenance: DataProvenance) -> bool:
        """Se a proveniencia e deste adaptador (B4): CVM e o nome do cadastro."""

        return (
            provenance.source_type is SourceType.CVM
            and provenance.source_name == SOURCE_NAME_CADASTRO
        )

    @staticmethod
    def relation_ends(
        role: str,
        fund_id: UUID,
        provider_id: UUID,
    ) -> tuple[RelationshipType, UUID, UUID]:
        """Tipo, origem e destino da relacao de um papel (ADR-012, D3)."""

        kind = ROLE_RELATIONS.get(role)

        if kind is None:
            raise FundosAdapterError("Papel sem relacao na camada.")

        if kind in FUND_SOURCE_TYPES:
            return kind, fund_id, provider_id

        return kind, provider_id, fund_id

    @staticmethod
    def relationship_id(
        source_id: UUID,
        kind: RelationshipType,
        target_id: UUID,
    ) -> UUID:
        """uuid5 da chave canonica origem:tipo:destino (o padrao do #11)."""

        return uuid5(NAMESPACE_URL, f"{source_id}:{kind.value}:{target_id}")

    def build_relationship(
        self,
        kind: RelationshipType,
        source_id: UUID,
        target_id: UUID,
        provenance: DataProvenance,
        snapshot: CadastroSnapshot,
    ) -> EntityRelationship:
        """Relacao nova, ativa desde a competencia; created_at = started_at."""

        if not isinstance(kind, RelationshipType) or kind not in RELATION_TYPES:
            raise FundosAdapterError("Tipo de relacao fora do adaptador de Fundos.")

        return EntityRelationship(
            relationship_id=self.relationship_id(source_id, kind, target_id),
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=kind,
            provenance=provenance,
            status=RelationshipStatus.ACTIVE,
            valid_from=self.reference_datetime(snapshot),
            created_at=snapshot.started_at,
        )

    @staticmethod
    def competence_datetime(competence: date) -> datetime:
        """Competencia do CDA as 00:00 UTC (proveniencia e vigencia)."""

        if isinstance(competence, datetime) or not isinstance(competence, date):
            raise FundosAdapterError("A competencia do CDA deve ser uma data.")

        return datetime.combine(competence, time(0, 0), tzinfo=UTC)

    def cda_provenance(
        self,
        competence: date,
        collected_at: datetime,
        source_reference: str,
    ) -> DataProvenance:
        """Proveniencia do CDA: CVM, referencia de linha e competencia."""

        return DataProvenance(
            source_type=SourceType.CVM,
            source_name=SOURCE_NAME_CDA,
            source_reference=source_reference,
            collected_at=collected_at,
            reference_date=self.competence_datetime(competence),
        )

    def holding_provenance(
        self,
        competence: date,
        collected_at: datetime,
        holding_id: int,
    ) -> DataProvenance:
        """Proveniencia de criar ou reabrir INVESTS_IN: a linha de holdings."""

        _require_row_id(holding_id, "holding_id")

        return self.cda_provenance(
            competence,
            collected_at,
            f"fundos:holdings:{holding_id}",
        )

    def cda_closing_provenance(
        self,
        competence: date,
        collected_at: datetime,
        run_id: int,
    ) -> DataProvenance:
        """Proveniencia do fechamento: a coleta do CDA que mostra a ausencia."""

        _require_row_id(run_id, "run_id")

        return self.cda_provenance(
            competence,
            collected_at,
            f"fundos:collection_runs:{run_id}",
        )

    @staticmethod
    def is_cda_provenance(provenance: DataProvenance) -> bool:
        """Se a proveniencia e do CDA deste adaptador: CVM e o nome do CDA."""

        return (
            provenance.source_type is SourceType.CVM
            and provenance.source_name == SOURCE_NAME_CDA
        )

    def build_investment(
        self,
        holder_id: UUID,
        investee_id: UUID,
        provenance: DataProvenance,
        competence: date,
        created_at: datetime,
    ) -> EntityRelationship:
        """INVESTS_IN nova, ativa desde a competencia do CDA (D9)."""

        if not isinstance(provenance, DataProvenance) or not self.is_cda_provenance(
            provenance
        ):
            raise FundosAdapterError("A proveniencia do INVESTS_IN deve ser do CDA.")

        return EntityRelationship(
            relationship_id=self.relationship_id(
                holder_id,
                RelationshipType.INVESTS_IN,
                investee_id,
            ),
            source_entity_id=holder_id,
            target_entity_id=investee_id,
            relationship_type=RelationshipType.INVESTS_IN,
            provenance=provenance,
            status=RelationshipStatus.ACTIVE,
            valid_from=self.competence_datetime(competence),
            created_at=created_at,
        )

    def to_fund_entity(
        self,
        subject: FundosSubjectRecord,
        snapshot: CadastroSnapshot,
    ) -> Entity:
        """Fundo (ou classe que so existe como classe) como Entity ativa.

        So vale para o grupo em funcionamento normal, com nome e tipo
        resolvidos; o servico confere antes e conta os motivos.
        created_at e updated_at = snapshot.started_at.
        """

        if self.situation_group(subject) is not SituationGroup.NORMAL:
            raise FundosAdapterError(
                "So o fundo em funcionamento normal vira entidade (D7)."
            )

        name = self.fund_name(subject)

        if name.reason is not None:
            raise FundosAdapterError(
                "Fundo sem nome valido: " + name.reason.value + "."
            )

        kind = self.fund_type(subject)

        if kind.reason is not None:
            raise FundosAdapterError(
                "Fundo sem tipo valido: " + kind.reason.value + "."
            )

        provenance = self.cadastro_provenance(
            snapshot,
            f"fundos:{subject.source_table}:{subject.source_id}",
        )

        return self._entity(
            subject.cnpj,
            name.name,
            kind.entity_type,
            EntityStatus.ACTIVE,
            provenance,
            snapshot,
        )

    def to_provider_entity(
        self,
        cnpj: str,
        links,
        snapshot: CadastroSnapshot,
    ) -> Entity:
        """Prestadora como FINANCIAL_INSTITUTION com status UNKNOWN.

        links sao as linhas de grupos em funcionamento normal (P6). A
        proveniencia aponta a menor linha em R com o nome resolvido (P5).
        created_at e updated_at = snapshot.started_at.
        """

        name = self.provider_name(links)

        if name.reason is not None:
            raise FundosAdapterError(
                "Prestadora sem nome valido: " + name.reason.value + "."
            )

        provenance = self.cadastro_provenance(
            snapshot,
            f"fundos:party_observations:{name.party_observation_id}",
        )

        return self._entity(
            cnpj,
            name.name,
            EntityType.FINANCIAL_INSTITUTION,
            EntityStatus.UNKNOWN,
            provenance,
            snapshot,
        )

    def _entity(
        self,
        cnpj: str,
        legal_name: str,
        entity_type: EntityType,
        status: EntityStatus,
        provenance: DataProvenance,
        snapshot: CadastroSnapshot,
    ) -> Entity:
        return Entity(
            entity_id=self.entity_id(cnpj),
            legal_name=legal_name,
            entity_type=entity_type,
            status=status,
            identifiers=(
                EntityIdentifier(
                    identifier_type=IdentifierType.CNPJ,
                    value=cnpj,
                    provenance=provenance,
                    is_primary=True,
                ),
            ),
            country_code="BR",
            provenance=provenance,
            created_at=snapshot.started_at,
            updated_at=snapshot.started_at,
        )
