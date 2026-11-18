"""Importacao de fundos, classes e prestadoras para a camada (FU7.2).

Fases 1 e 2 do ADR-012 e do ADR-013: cria ou reutiliza as entidades a partir
do retrato do cadastro lido por fundos_reader. Nao grava relacao (fica para
o B2) e nao roda por linha de comando.

Regra principal (ADR-012, D2): a entidade que ja existe na camada, achada
pelo CNPJ, e reutilizada como esta. O servico nunca chama save nela e nunca
muda tipo, status ou nome.

Grupo em funcionamento normal, na ordem de checagem (cada grupo cai em um
resultado so): CNPJ canonico, colisao, busca pelo CNPJ (achou: reutiliza),
nome, tipo, id ocupado, criar. A leitura do destino (busca pelo CNPJ e
checagem de id) nao e protegida: falha de leitura e sistemica e interrompe
a execucao. Uma excecao na montagem ou na gravacao de uma entidade vira erro
contado pelo tipo da excecao, sem a mensagem, e a execucao segue.

Prestadoras: agregadas pela chave canonica (o mesmo CNPJ e a mesma
prestadora); o nome vem so das linhas de grupos em funcionamento normal
(P6). A prestadora so vira entidade se algum grupo ligado a ela foi
resolvido na fase 1 (D7).
"""

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pense_alm.shared.entities import (
    Entity,
    EntityType,
    IdentifierType,
    IdentifierValidationError,
)

from .fundos_adapter import FundosAdapter, SituationGroup
from .fundos_import_report import (
    FundosBacklog,
    FundosEntityReport,
    FundosImportError,
    FundosNaoCriados,
    PrestadorasNaoCriadas,
)
from .fundos_records import CadastroSnapshot


FUND_ENTITY_TYPES = (EntityType.FIDC, EntityType.FIAGRO)
NATURAL_PERSON = "PF"

_CREATED = "criado"
_REUSED = "reutilizado"
_REASON = "motivo"
_ERROR = "erro"


@dataclass(frozen=True, slots=True)
class FundosEntityPhase:
    """Resultado das fases 1 e 2: o relatorio e as entidades resolvidas.

    funds e providers vao do CNPJ canonico para a entidade. backlog_funds
    leva o CNPJ canonico do grupo fora do funcionamento normal ate a entidade
    FIDC ou FIAGRO ja na camada (o que fora_do_normal_ja_na_camada conta),
    para o S8 da fase de relacoes. Ficam so em memoria e fora do repr.
    """

    report: FundosEntityReport
    funds: Mapping[str, Entity] = field(repr=False)
    providers: Mapping[str, Entity] = field(repr=False)
    backlog_funds: Mapping[str, Entity] = field(repr=False)


class FundosImportService:
    """Cria ou reutiliza fundos, classes e prestadoras na camada."""

    def __init__(self, entity_repository, adapter: FundosAdapter | None = None):
        self._entities = entity_repository
        self._adapter = adapter if adapter is not None else FundosAdapter()

    def _canonical(self, cnpj: str) -> str | None:
        try:
            return self._adapter.canonical_cnpj(cnpj)
        except IdentifierValidationError:
            return None

    def _fund_in_layer(self, cnpj: str) -> Entity | None:
        # Sem try de proposito: falha de leitura do destino e sistemica. A
        # excecao propaga e a execucao para, em vez de virar erro contado,
        # para que a soma 7 (fora_do_normal_ja_na_camada <= backlog) continue
        # fechando com numeros verdadeiros.
        existing = self._entities.get_by_identifier(IdentifierType.CNPJ, cnpj)

        if existing is not None and existing.entity_type in FUND_ENTITY_TYPES:
            return existing

        return None

    def _resolve_fund(self, subject, cnpj, repeated, snapshot):
        if cnpj is None:
            return _REASON, "cnpj_recusado"

        if repeated[cnpj] > 1:
            return _REASON, "cnpj_colisao"

        existing = self._entities.get_by_identifier(IdentifierType.CNPJ, cnpj)

        if existing is not None:
            return _REUSED, existing

        try:
            name = self._adapter.fund_name(subject)

            if name.reason is not None:
                return _REASON, name.reason.value

            kind = self._adapter.fund_type(subject)

            if kind.reason is not None:
                return _REASON, kind.reason.value
        except Exception as error:
            return _ERROR, type(error).__name__

        if self._entities.get_by_id(self._adapter.entity_id(cnpj)) is not None:
            return _REASON, "id_ocupado"

        try:
            entity = self._adapter.to_fund_entity(subject, snapshot)
            self._entities.save(entity)
        except Exception as error:
            return _ERROR, type(error).__name__

        return _CREATED, entity

    def _resolve_provider(self, cnpj, links, snapshot):
        existing = self._entities.get_by_identifier(IdentifierType.CNPJ, cnpj)

        if existing is not None:
            return _REUSED, existing

        try:
            name = self._adapter.provider_name(links)

            if name.reason is not None:
                return _REASON, name.reason.value
        except Exception as error:
            return _ERROR, type(error).__name__

        if self._entities.get_by_id(self._adapter.entity_id(cnpj)) is not None:
            return _REASON, "id_ocupado"

        try:
            entity = self._adapter.to_provider_entity(cnpj, links, snapshot)
            self._entities.save(entity)
        except Exception as error:
            return _ERROR, type(error).__name__

        return _CREATED, entity

    def import_entities(self, snapshot: CadastroSnapshot) -> FundosEntityPhase:
        """Fases 1 e 2: fundos e classes, depois prestadoras."""

        if not isinstance(snapshot, CadastroSnapshot):
            raise TypeError("snapshot deve ser CadastroSnapshot.")

        subjects = snapshot.subjects
        canonical = [self._canonical(subject.cnpj) for subject in subjects]
        repeated = Counter(cnpj for cnpj in canonical if cnpj is not None)

        backlog = Counter()
        fund_reasons = Counter()
        errors = Counter()
        funds = {}
        backlog_funds = {}
        counts = Counter()
        normal = []
        resolved = set()

        for index, subject in enumerate(subjects):
            if subject.source_table == "funds":
                person_types = set(subject.tipos_pessoa_gestor)

                if person_types == {NATURAL_PERSON}:
                    counts["gestor_pessoa_fisica"] += 1
                elif len(person_types) > 1:
                    counts["gestor_tipo_conflitante"] += 1

            group = self._adapter.situation_group(subject)

            if group is not SituationGroup.NORMAL:
                backlog[group.value] += 1

                if canonical[index] is not None:
                    existing = self._fund_in_layer(canonical[index])

                    if existing is not None:
                        counts["fora_do_normal_ja_na_camada"] += 1
                        backlog_funds[canonical[index]] = existing

                continue

            normal.append(index)
            outcome, value = self._resolve_fund(
                subject,
                canonical[index],
                repeated,
                snapshot,
            )

            if outcome == _CREATED:
                counts["fundos_criados"] += 1
            elif outcome == _REUSED:
                counts["fundos_reutilizados"] += 1
            elif outcome == _REASON:
                fund_reasons[value] += 1
            else:
                errors[("fundos", value)] += 1

            if outcome in (_CREATED, _REUSED):
                funds[canonical[index]] = value
                resolved.add(index)

        # Fase 2: so as linhas de grupos em funcionamento normal (P6).
        links_by_provider = defaultdict(list)
        provider_resolved = defaultdict(bool)

        for index in normal:
            for link in subjects[index].parties:
                cnpj = self._canonical(link.cnpj)
                key = ("cnpj", cnpj) if cnpj is not None else ("texto", link.cnpj)
                links_by_provider[key].append(link)

                if index in resolved:
                    provider_resolved[key] = True

        provider_reasons = Counter()
        providers = {}

        for key in sorted(links_by_provider):
            if not provider_resolved[key]:
                counts["prestadoras_so_de_fundo_nao_resolvido"] += 1
                continue

            counts["prestadoras_ligadas"] += 1
            kind, cnpj = key

            if kind == "texto":
                provider_reasons["cnpj_recusado"] += 1
                continue

            outcome, value = self._resolve_provider(
                cnpj,
                links_by_provider[key],
                snapshot,
            )

            if outcome == _CREATED:
                counts["prestadoras_criadas"] += 1
                providers[cnpj] = value
            elif outcome == _REUSED:
                counts["prestadoras_reutilizadas"] += 1
                providers[cnpj] = value
            elif outcome == _REASON:
                provider_reasons[value] += 1
            else:
                errors[("prestadoras", value)] += 1

        report = FundosEntityReport(
            competencia_cadastro=snapshot.reference_date,
            leitura_completa=snapshot.complete,
            fundos_na_tabela=snapshot.funds_in_table,
            fundos_lidos=snapshot.funds_read,
            fundos_sem_dado_na_competencia=snapshot.funds_without_data,
            classes_na_tabela=snapshot.classes_in_table,
            classes_lidas=snapshot.classes_read,
            classes_sem_dado_na_competencia=snapshot.classes_without_data,
            classes_unidas_ao_fundo=snapshot.classes_same_cnpj,
            classes_com_cnpj_de_outro_fundo=snapshot.classes_other_fund_cnpj,
            classes_so_como_classe=snapshot.classes_only_class,
            classes_de_fundo_sem_dado=snapshot.classes_of_fund_without_data,
            cnpjs_lidos=len(subjects),
            gestor_pessoa_fisica=counts["gestor_pessoa_fisica"],
            gestor_tipo_conflitante=counts["gestor_tipo_conflitante"],
            em_funcionamento_normal=len(normal),
            backlog=FundosBacklog(**backlog),
            fora_do_normal_ja_na_camada=counts["fora_do_normal_ja_na_camada"],
            fundos_criados=counts["fundos_criados"],
            fundos_reutilizados=counts["fundos_reutilizados"],
            fundos_nao_criados=FundosNaoCriados(**fund_reasons),
            prestadoras_candidatas=len(links_by_provider),
            prestadoras_ligadas=counts["prestadoras_ligadas"],
            prestadoras_so_de_fundo_nao_resolvido=counts[
                "prestadoras_so_de_fundo_nao_resolvido"
            ],
            prestadoras_criadas=counts["prestadoras_criadas"],
            prestadoras_reutilizadas=counts["prestadoras_reutilizadas"],
            prestadoras_nao_criadas=PrestadorasNaoCriadas(**provider_reasons),
            erros=tuple(
                FundosImportError(fase=fase, tipo=tipo, quantidade=quantidade)
                for (fase, tipo), quantidade in sorted(errors.items())
            ),
        )

        return FundosEntityPhase(
            report=report,
            funds=MappingProxyType(funds),
            providers=MappingProxyType(providers),
            backlog_funds=MappingProxyType(backlog_funds),
        )
