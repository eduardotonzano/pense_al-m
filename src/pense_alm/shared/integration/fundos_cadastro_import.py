"""Orquestracao da importacao de Fundos (FU7.2): as duas travas e as fases 1 a 4.

FundosCadastroImport.run(snapshot, cda), com o CDA obrigatorio (D2 de
23/11/2026). As duas travas vem antes da fase 1, e qualquer uma aborta tudo
antes de qualquer gravacao (C5 de 19/11/2026):

1. trava B6: le a maior competencia do cadastro ja aplicada no destino
   (FundosTargetState); se R as 00:00 UTC for menor, levanta
   SnapshotOlderThanApplied. R igual passa (e reexecucao) e R maior passa;
2. trava do CDA: le a maior competencia do CDA ja aplicada no destino e a
   compara com a maior competencia com posicao lida, completa ou nao
   (CdaSnapshot.latest_competence, as 00:00 UTC). Sem CDA aplicado, passa.
   Com CDA aplicado: banco de Fundos sem dados de CDA levanta
   CdaUnavailableButApplied; sem competencia com posicao, ou com ela menor,
   levanta CdaOlderThanApplied; igual (e reexecucao, ainda que a competencia
   esteja incompleta) ou maior passa;
3. fases 1 e 2 (FundosImportService): fundos, classes e prestadoras;
4. fase 3 (FundosRelationService): relacoes de prestadora;
5. fase 4 (FundosInvestmentService): INVESTS_IN a partir do CDA.

FundosCadastroRun junta os tres relatorios e confere as somas entre eles.
Uma transacao por escrita, sem transacao unica para a execucao (decisao de
17/11/2026): uma falha no meio deixa o que ja foi gravado, e a reexecucao
converge.
"""

from dataclasses import dataclass

from .fundos_adapter import FundosAdapter
from .fundos_import_report import FundosEntityReport
from .fundos_import_service import FundosImportService
from .fundos_investment_report import FundosInvestmentReport
from .fundos_investment_service import FundosInvestmentService
from .fundos_records import CadastroSnapshot, CdaSnapshot
from .fundos_relation_report import FundosRelationReport
from .fundos_relation_service import FundosRelationService
from .fundos_target_state import FundosTargetState


class SnapshotOlderThanApplied(Exception):
    """O retrato e mais antigo que o ja aplicado no destino (trava B6)."""


class CdaOlderThanApplied(Exception):
    """O CDA lido e mais antigo que o ja aplicado no destino (trava do CDA)."""


class CdaUnavailableButApplied(Exception):
    """O banco de Fundos nao tem dados de CDA e o destino ja tem (trava do CDA)."""


@dataclass(frozen=True, slots=True)
class FundosCadastroRun:
    """Os relatorios das fases 1 e 2 (entidades), 3 (relacoes) e 4 (CDA)."""

    entities: FundosEntityReport
    relations: FundosRelationReport
    investments: FundosInvestmentReport

    def __post_init__(self) -> None:
        if not isinstance(self.entities, FundosEntityReport):
            raise TypeError("entities deve ser FundosEntityReport.")

        if not isinstance(self.relations, FundosRelationReport):
            raise TypeError("relations deve ser FundosRelationReport.")

        if not isinstance(self.investments, FundosInvestmentReport):
            raise TypeError("investments deve ser FundosInvestmentReport.")

        if (
            self.relations.fundos_fora_do_normal_com_relacao
            > self.entities.fora_do_normal_ja_na_camada
        ):
            raise ValueError(
                "Soma entre relatorios 1: fundos_fora_do_normal_com_relacao "
                "nao pode passar de fora_do_normal_ja_na_camada."
            )

        if self.relations.leitura_completa != self.entities.leitura_completa:
            raise ValueError(
                "Soma entre relatorios 2: a leitura_completa dos dois "
                "relatorios deve ser a mesma."
            )

        # Os detentores processados saem de phase.funds, e os do S8 de
        # phase.backlog_funds, um por CNPJ canonico.
        if (
            self.investments.detentores_na_camada
            > self.entities.fundos_criados + self.entities.fundos_reutilizados
        ):
            raise ValueError(
                "Soma entre relatorios 3: detentores_na_camada nao pode passar "
                "de fundos_criados + fundos_reutilizados."
            )

        if (
            self.investments.detentores_fora_do_normal_na_camada
            > self.entities.fora_do_normal_ja_na_camada
        ):
            raise ValueError(
                "Soma entre relatorios 4: detentores_fora_do_normal_na_camada "
                "nao pode passar de fora_do_normal_ja_na_camada."
            )

    @property
    def leitura_completa(self) -> bool:
        """O cadastro completo e, se ha dados de CDA, o CDA completo (C6)."""

        return self.entities.leitura_completa and (
            not self.investments.cda_disponivel or self.investments.leitura_completa
        )

    @property
    def id_ocupado(self) -> int:
        """id_ocupado de fundos e de prestadoras."""

        return (
            self.entities.fundos_nao_criados.id_ocupado
            + self.entities.prestadoras_nao_criadas.id_ocupado
        )

    @property
    def cnpj_colisao(self) -> int:
        return self.entities.fundos_nao_criados.cnpj_colisao

    @property
    def erros_total(self) -> int:
        """Erros contados das quatro fases."""

        return (
            self.entities.erros_total
            + self.relations.erros_total
            + self.investments.erros_total
        )


class FundosCadastroImport:
    """As duas travas e as fases 1 a 4 sobre os repositorios do destino."""

    def __init__(
        self,
        entity_repository,
        relationship_repository,
        target_state: FundosTargetState,
        adapter: FundosAdapter | None = None,
    ):
        if not isinstance(target_state, FundosTargetState):
            raise TypeError("target_state deve ser FundosTargetState.")

        self._entities = entity_repository
        self._relationships = relationship_repository
        self._target_state = target_state
        self._adapter = adapter if adapter is not None else FundosAdapter()

    def _check_cda(self, cda: CdaSnapshot) -> None:
        """Trava do CDA (ajuste 1 de 23/11/2026); nada e gravado antes."""

        applied = self._target_state.latest_applied_cda_reference()

        if applied is None:
            return

        if not cda.available:
            raise CdaUnavailableButApplied(
                "O banco de Fundos nao tem dados de CDA e o destino ja tem."
            )

        latest = cda.latest_competence

        if latest is None or self._adapter.competence_datetime(latest) < applied:
            raise CdaOlderThanApplied(
                "O CDA lido e mais antigo que o ja aplicado no destino."
            )

    def run(self, snapshot: CadastroSnapshot, cda: CdaSnapshot) -> FundosCadastroRun:
        """As duas travas, depois as fases 1 a 4; devolve os tres relatorios."""

        if not isinstance(snapshot, CadastroSnapshot):
            raise TypeError("snapshot deve ser CadastroSnapshot.")

        if not isinstance(cda, CdaSnapshot):
            raise TypeError("cda deve ser CdaSnapshot.")

        applied = self._target_state.latest_applied_reference()

        if applied is not None and self._adapter.reference_datetime(snapshot) < applied:
            raise SnapshotOlderThanApplied(
                "O retrato e mais antigo que o ja aplicado no destino."
            )

        self._check_cda(cda)
        phase = FundosImportService(self._entities, self._adapter).import_entities(
            snapshot
        )
        relations = FundosRelationService(
            self._entities,
            self._relationships,
            self._adapter,
        ).import_relationships(snapshot, phase)
        investments = FundosInvestmentService(
            self._entities,
            self._relationships,
            self._adapter,
        ).import_investments(cda, snapshot, phase)

        return FundosCadastroRun(
            entities=phase.report,
            relations=relations,
            investments=investments,
        )
