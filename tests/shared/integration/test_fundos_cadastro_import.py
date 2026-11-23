"""Testes do orquestrador do cadastro de Fundos (FU7.2): trava B6 e somas.

O destino e um SQLite da camada em tmp_path; o retrato e montado direto com
records. So CNPJs ficticios de cnpj_amostras e nomes marcados como
ficticios. C7 e o retrato mais antigo que o ja aplicado.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityType,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration.fundos_adapter import NORMAL, FundosAdapter
from pense_alm.shared.integration.fundos_cadastro_import import (
    CdaOlderThanApplied,
    CdaUnavailableButApplied,
    FundosCadastroImport,
    FundosCadastroRun,
    SnapshotOlderThanApplied,
)
from pense_alm.shared.integration.fundos_investment_report import FundosInvestmentReport
from pense_alm.shared.integration.fundos_records import (
    CadastroIncompleteReason,
    CadastroSnapshot,
    CdaCompetence,
    CdaEmptyPeriod,
    CdaHolderRecord,
    CdaHoldingLink,
    CdaIncompleteReason,
    CdaSnapshot,
    CdaUnavailableReason,
    FundosPartyLink,
    FundosSubjectRecord,
)
from pense_alm.shared.integration.fundos_target_state import (
    FundosTargetState,
    FundosTargetStateError,
)
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara


CNPJ_FUNDO = cnpj_ficticio(1)
CNPJ_FUNDO_2 = cnpj_ficticio(2)
CNPJ_ADMIN = cnpj_ficticio(5)
R1 = date(2026, 9, 30)
R2 = date(2026, 10, 27)
R3 = date(2026, 11, 26)
INICIO = {
    R1: datetime(2026, 9, 30, 12, tzinfo=UTC),
    R2: datetime(2026, 10, 27, 12, tzinfo=UTC),
    R3: datetime(2026, 11, 26, 12, tzinfo=UTC),
}
COLETA = {R1: 1, R2: 2, R3: 3}
# Banco de Fundos sem a migration 004: a fase 4 so informa o motivo.
SEM_CDA = CdaSnapshot(False, CdaUnavailableReason.SEM_MIGRATION_004)

adaptador = FundosAdapter()


def assunto(cnpj=CNPJ_FUNDO, source_id=1, linha=101, **muda):
    valores = {
        "cnpj": cnpj,
        "source_table": "funds",
        "source_id": source_id,
        "names": ("FUNDO FICTÍCIO " + str(source_id),),
        "situacoes": (NORMAL,),
        "tipos_fundo": ("FIDC",),
        "tipos_classe": (),
        "tipos_pessoa_gestor": ("PJ",),
        "parties": (
            FundosPartyLink(
                role="administrador",
                cnpj=CNPJ_ADMIN,
                name="ADMINISTRADORA FICTÍCIA",
                party_observation_id=linha,
            ),
        ),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def retrato(*assuntos, competencia=R2, motivo=None):
    return CadastroSnapshot(
        reference_date=competencia,
        collection_run_id=COLETA[competencia],
        started_at=INICIO[competencia],
        complete=motivo is None,
        incomplete_reason=motivo,
        funds_in_table=len(assuntos),
        classes_in_table=0,
        funds_read=len(assuntos),
        classes_read=0,
        classes_same_cnpj=0,
        classes_other_fund_cnpj=0,
        classes_only_class=0,
        classes_of_fund_without_data=0,
        subjects=assuntos,
    )


class EspiaoEntidades:
    def __init__(self, repositorio):
        self._repositorio = repositorio
        self.salvas = []

    def get_by_identifier(self, identifier_type, value):
        return self._repositorio.get_by_identifier(identifier_type, value)

    def get_by_id(self, entity_id):
        return self._repositorio.get_by_id(entity_id)

    def save(self, entity):
        self.salvas.append(entity.entity_id)
        return self._repositorio.save(entity)


class EspiaoRelacoes:
    def __init__(self, repositorio):
        self._repositorio = repositorio
        self.salvas = []

    def save(self, relationship):
        self.salvas.append(relationship.relationship_id)
        return self._repositorio.save(relationship)

    def list_by_source(self, entity_id):
        return self._repositorio.list_by_source(entity_id)

    def list_by_target(self, entity_id):
        return self._repositorio.list_by_target(entity_id)

    def list_active_at(self, reference_datetime, relationship_type=None):
        return self._repositorio.list_active_at(reference_datetime, relationship_type)


@pytest.fixture
def destino(tmp_path):
    manager = SQLiteConnectionManager(tmp_path / "destino" / "camada.sqlite3")
    return manager, SQLiteEntityRepository(manager), SQLiteRelationshipRepository(manager)


def importar(destino, snapshot, entidades=None, relacoes=None, cda=SEM_CDA):
    manager, repositorio_entidades, repositorio_relacoes = destino
    return FundosCadastroImport(
        entidades or repositorio_entidades,
        relacoes or repositorio_relacoes,
        FundosTargetState(manager),
    ).run(snapshot, cda)


def linhas(destino):
    with destino[0].read_connection() as conexao:
        return {
            tabela: [
                tuple(linha)
                for linha in conexao.execute(f"SELECT * FROM {tabela} ORDER BY 1")
            ]
            for tabela in (
                "entities",
                "entity_identifiers",
                "entity_relationships",
                "data_provenance",
            )
        }


def test_roda_as_tres_fases_e_junta_os_relatorios(destino):
    run = importar(destino, retrato(assunto()))

    assert run.entities.fundos_criados == 1
    assert run.entities.prestadoras_criadas == 1
    assert run.relations.administered_by.criadas == 1
    assert (run.id_ocupado, run.cnpj_colisao, run.erros_total) == (0, 0, 0)
    assert destino[2].count() == 1


def test_c7_retrato_mais_antigo_aborta_antes_de_gravar(destino):
    importar(destino, retrato(assunto(linha=201), competencia=R2))
    antes = linhas(destino)
    entidades = EspiaoEntidades(destino[1])
    relacoes = EspiaoRelacoes(destino[2])

    with pytest.raises(SnapshotOlderThanApplied):
        importar(
            destino,
            retrato(assunto(CNPJ_FUNDO_2, 2, linha=101), competencia=R1),
            entidades=entidades,
            relacoes=relacoes,
        )

    assert entidades.salvas == []
    assert relacoes.salvas == []
    assert linhas(destino) == antes


def test_retrato_igual_passa_como_reexecucao(destino):
    snapshot = retrato(assunto(), competencia=R2)
    importar(destino, snapshot)

    run = importar(destino, snapshot)

    assert run.relations.administered_by.mantidas == 1
    assert run.relations.administered_by.criadas == 0


def test_retrato_maior_passa(destino):
    importar(destino, retrato(assunto(linha=101), competencia=R1))

    run = importar(destino, retrato(assunto(linha=301), competencia=R3))

    assert run.relations.administered_by.mantidas == 1


def test_formato_inesperado_no_destino_aborta_antes_de_gravar(destino):
    manager, repositorio, _ = destino
    proveniencia = DataProvenance(
        source_type=SourceType.CVM,
        source_name="Fundos - CVM Cadastro",
        source_reference="fundos:funds:9",
        collected_at=INICIO[R1],
        reference_date=datetime(2026, 9, 30, 3, tzinfo=UTC),
    )
    repositorio.save(
        Entity(
            legal_name="FUNDO FICTÍCIO 9",
            entity_type=EntityType.FIDC,
            provenance=proveniencia,
            created_at=INICIO[R1],
            updated_at=INICIO[R1],
        )
    )
    antes = linhas(destino)
    entidades = EspiaoEntidades(repositorio)

    with pytest.raises(FundosTargetStateError):
        importar(destino, retrato(assunto()), entidades=entidades)

    assert entidades.salvas == []
    assert linhas(destino) == antes


def test_id_ocupado_e_cnpj_colisao_somam_as_partes(destino):
    _, repositorio, _ = destino
    repositorio.save(
        Entity(
            entity_id=adaptador.entity_id(CNPJ_ADMIN),
            legal_name="OCUPANTE FICTÍCIO",
            entity_type=EntityType.OTHER,
            provenance=DataProvenance(
                source_type=SourceType.MANUAL,
                source_name="Teste ficticio",
                collected_at=INICIO[R1],
            ),
            created_at=INICIO[R1],
            updated_at=INICIO[R1],
        )
    )

    run = importar(
        destino,
        retrato(
            assunto(),
            assunto(CNPJ_FUNDO_2, 2, linha=102),
            assunto(com_mascara(CNPJ_FUNDO_2), 3, linha=103),
        ),
    )

    assert run.entities.prestadoras_nao_criadas.id_ocupado == 1
    assert run.id_ocupado == 1
    assert run.cnpj_colisao == 2


def test_somas_entre_relatorios(destino):
    run = importar(destino, retrato(assunto()))
    fora = replace(
        run.relations,
        fundos_fora_do_normal_com_relacao=1,
        relacoes_de_fundo_fora_do_normal_intactas=1,
    )
    incompleta = replace(
        run.relations,
        leitura_completa=False,
        motivo_nao_fechar=CadastroIncompleteReason.STATUS_NAO_SUCCESS,
    )

    with pytest.raises(ValueError, match="Soma entre relatorios 1"):
        FundosCadastroRun(entities=run.entities, relations=fora, investments=run.investments)

    with pytest.raises(ValueError, match="Soma entre relatorios 2"):
        FundosCadastroRun(entities=run.entities, relations=incompleta, investments=run.investments)


def test_tipos_sao_conferidos(destino):
    manager, entidades, relacoes = destino
    run = importar(destino, retrato(assunto()))

    with pytest.raises(TypeError):
        FundosCadastroRun(entities=object(), relations=run.relations, investments=run.investments)

    with pytest.raises(TypeError):
        FundosCadastroRun(entities=run.entities, relations=object(), investments=run.investments)

    with pytest.raises(TypeError):
        FundosCadastroImport(entidades, relacoes, object())

    with pytest.raises(TypeError):
        FundosCadastroImport(entidades, relacoes, FundosTargetState(manager)).run(object(), SEM_CDA)


# --- PR C2: trava do CDA (IC1) e fase 4 na execucao ---


CNPJ_FUNDO_3 = cnpj_ficticio(3)
SETEMBRO = date(2026, 9, 30)
OUTUBRO = date(2026, 10, 31)
INICIO_CDA = {
    SETEMBRO: datetime(2026, 10, 29, 12, tzinfo=UTC),
    OUTUBRO: datetime(2026, 11, 20, 12, tzinfo=UTC),
}
COLETA_CDA = {SETEMBRO: 9, OUTUBRO: 10}
PARCIAL = CdaIncompleteReason.STATUS_NAO_SUCCESS
# CDA com coleta, mas sem nenhuma competencia com posicao.
SO_MES_VAZIO = CdaSnapshot(True, None, (), (CdaEmptyPeriod("202610", (11,)),), ())


def fundos(*mais):
    """O detentor (CNPJ_FUNDO) e o investido (CNPJ_FUNDO_2) no retrato R2."""

    return retrato(assunto(), assunto(CNPJ_FUNDO_2, 2, linha=102), *mais)


def leitura_cda(dia=OUTUBRO, motivo=None):
    """CDA ficticio: CNPJ_FUNDO investe em CNPJ_FUNDO_2 no L_H dia."""

    link = CdaHoldingLink(
        investee_cnpj=CNPJ_FUNDO_2,
        holding_id=COLETA_CDA[dia] * 10,
        collected_at=INICIO_CDA[dia],
    )
    competencia = CdaCompetence(
        dia, (COLETA_CDA[dia],), COLETA_CDA[dia], INICIO_CDA[dia], motivo
    )
    detentor = CdaHolderRecord(CNPJ_FUNDO, dia, True, False, (link,))
    return CdaSnapshot(True, None, (competencia,), (), (detentor,))


def meia_noite(dia):
    return adaptador.competence_datetime(dia)


def aplicado(destino):
    return FundosTargetState(destino[0]).latest_applied_cda_reference()


def abortar(destino, cda, excecao, snapshot=None):
    """Aborta com a excecao antes da fase 1: nenhum save e o destino igual.

    O retrato padrao traz um fundo novo, que a fase 1 criaria.
    """

    antes = linhas(destino)
    entidades = EspiaoEntidades(destino[1])
    relacoes = EspiaoRelacoes(destino[2])

    with pytest.raises(excecao):
        importar(
            destino,
            snapshot or fundos(assunto(CNPJ_FUNDO_3, 3, linha=103)),
            entidades=entidades,
            relacoes=relacoes,
            cda=cda,
        )

    assert (entidades.salvas, relacoes.salvas) == ([], [])
    assert linhas(destino) == antes


@pytest.mark.parametrize("cda", [SEM_CDA, SO_MES_VAZIO, leitura_cda(SETEMBRO)])
def test_ic1_sem_cda_aplicado_na_camada_passa(destino, cda):
    run = importar(destino, fundos(), cda=cda)

    assert run.erros_total == 0
    assert run.investments.cda_disponivel is cda.available
    assert run.investments.criadas == len(cda.holders)


@pytest.mark.parametrize("primeiro, segundo", [(OUTUBRO, OUTUBRO), (SETEMBRO, OUTUBRO)])
def test_ic1_cda_igual_ou_mais_novo_que_o_aplicado_passa(destino, primeiro, segundo):
    importar(destino, fundos(), cda=leitura_cda(primeiro))
    assert aplicado(destino) == meia_noite(primeiro)

    run = importar(destino, fundos(), cda=leitura_cda(segundo))

    assert (run.investments.criadas, run.investments.mantidas) == (0, 1)


def test_ic1_aplicado_de_competencia_incompleta_a_reexecucao_passa(destino):
    incompleto = leitura_cda(OUTUBRO, PARCIAL)

    primeira = importar(destino, fundos(), cda=incompleto)
    segunda = importar(destino, fundos(), cda=incompleto)

    # Sem competencia completa: uma trava pelo C_max abortaria aqui.
    assert (incompleto.latest_complete, incompleto.latest_competence) == (None, OUTUBRO)
    assert aplicado(destino) == meia_noite(OUTUBRO)
    assert (primeira.investments.criadas, segunda.investments.mantidas) == (1, 1)
    assert not segunda.leitura_completa


@pytest.mark.parametrize(
    "depois, excecao",
    [
        (leitura_cda(SETEMBRO), CdaOlderThanApplied),
        (leitura_cda(SETEMBRO, PARCIAL), CdaOlderThanApplied),
        (SO_MES_VAZIO, CdaOlderThanApplied),
        (SEM_CDA, CdaUnavailableButApplied),
        (CdaSnapshot(False, CdaUnavailableReason.SEM_COLETA_DE_CDA), CdaUnavailableButApplied),
    ],
)
def test_ic1_cda_atras_do_aplicado_aborta_antes_de_gravar(destino, depois, excecao):
    importar(destino, fundos(), cda=leitura_cda(OUTUBRO))

    abortar(destino, depois, excecao)


def test_ic1_formato_inesperado_do_cda_no_destino_aborta(destino):
    importar(destino, fundos())
    proveniencia = DataProvenance(
        source_type=SourceType.CVM,
        source_name="Fundos - CVM CDA",
        source_reference="fundos:holdings:9",
        collected_at=INICIO_CDA[OUTUBRO],
        reference_date=datetime(2026, 10, 31, 3, tzinfo=UTC),
    )
    destino[1].save(
        Entity(
            legal_name="FUNDO FICTICIO 9",
            entity_type=EntityType.FIDC,
            provenance=proveniencia,
            created_at=INICIO_CDA[OUTUBRO],
            updated_at=INICIO_CDA[OUTUBRO],
        )
    )

    abortar(destino, leitura_cda(OUTUBRO), FundosTargetStateError)


def test_ic1_trava_b6_vem_antes_da_trava_do_cda(destino):
    importar(destino, fundos(), cda=leitura_cda(OUTUBRO))

    abortar(destino, SEM_CDA, SnapshotOlderThanApplied, snapshot=retrato(assunto(), competencia=R1))


def test_quatro_fases_juntam_os_relatorios_e_os_erros(destino):
    class FalhaNoInvesteEm(EspiaoRelacoes):
        def save(self, relationship):
            if relationship.relationship_type is RelationshipType.INVESTS_IN:
                raise RuntimeError("falha ficticia")

            return super().save(relationship)

    run = importar(destino, fundos(), cda=leitura_cda(OUTUBRO))
    com_erro = importar(
        destino,
        fundos(assunto(CNPJ_FUNDO_3, 3, linha=103)),
        relacoes=FalhaNoInvesteEm(destino[2]),
        cda=CdaSnapshot(
            True,
            None,
            leitura_cda(OUTUBRO).competences,
            (),
            (
                *leitura_cda(OUTUBRO).holders,
                CdaHolderRecord(
                    CNPJ_FUNDO_3,
                    OUTUBRO,
                    True,
                    False,
                    (CdaHoldingLink(CNPJ_FUNDO, 101, INICIO_CDA[OUTUBRO]),),
                ),
            ),
        ),
    )

    assert run.relations.administered_by.criadas == 2
    assert (run.investments.detentores_na_camada, run.investments.criadas) == (1, 1)
    assert (run.erros_total, run.leitura_completa) == (0, True)
    # O erro da fase 4 entra no erros_total da execucao.
    assert (
        com_erro.entities.erros_total,
        com_erro.relations.erros_total,
        com_erro.investments.erros_total,
        com_erro.erros_total,
    ) == (0, 0, 1, 1)
    assert destino[2].count(RelationshipType.INVESTS_IN) == 1


@pytest.mark.parametrize(
    "motivo, cda, esperado",
    [
        (None, SEM_CDA, True),
        (None, leitura_cda(OUTUBRO), True),
        (None, leitura_cda(OUTUBRO, PARCIAL), False),
        (CadastroIncompleteReason.STATUS_NAO_SUCCESS, leitura_cda(OUTUBRO), False),
        (CadastroIncompleteReason.STATUS_NAO_SUCCESS, SEM_CDA, False),
    ],
)
def test_leitura_completa_junta_cadastro_e_cda(destino, motivo, cda, esperado):
    snapshot = retrato(assunto(), assunto(CNPJ_FUNDO_2, 2, linha=102), motivo=motivo)

    run = importar(destino, snapshot, cda=cda)

    assert run.leitura_completa is esperado
    assert run.investments.criadas == (0 if cda is SEM_CDA else 1)


def test_somas_entre_relatorios_da_fase_4(destino):
    run = importar(destino, fundos(), cda=leitura_cda(OUTUBRO))
    # Dois fundos na camada: tres detentores processados nao cabem.
    demais = replace(run.investments, detentores_lidos=3, detentores_na_camada=3)
    # Nenhum fundo fora do normal ja na camada: nenhum detentor do S8 cabe.
    fora = replace(run.investments, detentores_lidos=2, detentores_fora_do_normal_na_camada=1)

    with pytest.raises(ValueError, match="Soma entre relatorios 3"):
        FundosCadastroRun(entities=run.entities, relations=run.relations, investments=demais)

    with pytest.raises(ValueError, match="Soma entre relatorios 4"):
        FundosCadastroRun(entities=run.entities, relations=run.relations, investments=fora)


def test_tipos_da_fase_4(destino):
    manager, entidades, relacoes = destino
    run = importar(destino, fundos())
    orquestrador = FundosCadastroImport(entidades, relacoes, FundosTargetState(manager))

    assert run.investments == FundosInvestmentReport.sem_cda(CdaUnavailableReason.SEM_MIGRATION_004)

    with pytest.raises(TypeError):
        FundosCadastroRun(entities=run.entities, relations=run.relations, investments=object())

    with pytest.raises(TypeError):
        orquestrador.run(fundos(), object())

    # O CDA e obrigatorio (D2 de 23/11/2026).
    with pytest.raises(TypeError):
        orquestrador.run(fundos())
