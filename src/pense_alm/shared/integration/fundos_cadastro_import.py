"""Orquestracao da importacao do cadastro de Fundos (FU7.2): B6 e fases 1 a 3.

FundosCadastroImport.run(snapshot):

1. trava B6: le a maior competencia ja aplicada no destino
   (FundosTargetState); se R as 00:00 UTC for menor, levanta
   SnapshotOlderThanApplied antes de qualquer gravacao. R igual passa (e
   reexecucao) e R maior passa;
2. fases 1 e 2 (FundosImportService): fundos, classes e prestadoras;
3. fase 3 (FundosRelationService): relacoes de prestadora.

FundosCadastroRun junta os dois relatorios e confere as somas entre eles.
Uma transacao por escrita, sem transacao unica para a execucao (decisao de
17/11/2026): uma falha no meio deixa o que ja foi gravado, e a reexecucao
converge.
"""

from dataclasses import dataclass

from .fundos_adapter import FundosAdapter
from .fundos_import_report import FundosEntityReport
from .fundos_import_service import FundosImportService
from .fundos_records import CadastroSnapshot
from .fundos_relation_report import FundosRelationReport
from .fundos_relation_service import FundosRelationService
from .fundos_target_state import FundosTargetState


class SnapshotOlderThanApplied(Exception):
    """O retrato e mais antigo que o ja aplicado no destino (trava B6)."""


@dataclass(frozen=True, slots=True)
class FundosCadastroRun:
    """Os relatorios das fases 1 e 2 (entidades) e da fase 3 (relacoes)."""

    entities: FundosEntityReport
    relations: FundosRelationReport

    def __post_init__(self) -> None:
        if not isinstance(self.entities, FundosEntityReport):
            raise TypeError("entities deve ser FundosEntityReport.")

        if not isinstance(self.relations, FundosRelationReport):
            raise TypeError("relations deve ser FundosRelationReport.")

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
        """Erros contados das tres fases."""

        return self.entities.erros_total + self.relations.erros_total


class FundosCadastroImport:
    """Trava B6 e fases 1 a 3 sobre os repositorios do destino."""

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

    def run(self, snapshot: CadastroSnapshot) -> FundosCadastroRun:
        """B6, depois as fases 1 a 3; devolve os dois relatorios."""

        if not isinstance(snapshot, CadastroSnapshot):
            raise TypeError("snapshot deve ser CadastroSnapshot.")

        applied = self._target_state.latest_applied_reference()

        if applied is not None and self._adapter.reference_datetime(snapshot) < applied:
            raise SnapshotOlderThanApplied(
                "O retrato e mais antigo que o ja aplicado no destino."
            )

        phase = FundosImportService(self._entities, self._adapter).import_entities(
            snapshot
        )
        relations = FundosRelationService(
            self._entities,
            self._relationships,
            self._adapter,
        ).import_relationships(snapshot, phase)

        return FundosCadastroRun(entities=phase.report, relations=relations)
