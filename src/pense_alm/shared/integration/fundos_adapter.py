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
  da coleta usada no retrato.

created_at e updated_at de toda entidade sao o inicio da coleta usada na
proveniencia (snapshot.started_at), igual para todas: a entidade sai
deterministica, sem depender do relogio. As mensagens de erro nunca trazem
CNPJ nem nome.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityStatus,
    EntityType,
    IdentifierType,
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
            reference_date=datetime.combine(
                snapshot.reference_date,
                time(0, 0),
                tzinfo=UTC,
            ),
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
