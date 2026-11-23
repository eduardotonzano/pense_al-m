"""Testes do servico da fase 4 de Fundos: INVESTS_IN a partir do CDA (FU7.2, PR C2).

O destino e um SQLite da camada em tmp_path. O retrato do cadastro e o CDA
sao montados direto com records; as fases 1 e 2 rodam pelo servico do B1 e
a fase 4 pelo servico novo. So CNPJs ficticios de cnpj_amostras e nomes
marcados como ficticios. Os nomes dos testes trazem o codigo do plano (IS1
a IS17).
"""

from dataclasses import fields, replace
from datetime import UTC, date, datetime, time
from uuid import uuid4

import pytest

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
)
from pense_alm.shared.integration.fundos_adapter import NORMAL, FundosAdapter
from pense_alm.shared.integration.fundos_import_service import FundosImportService
from pense_alm.shared.integration.fundos_investment_report import (
    COUNTERS,
    AtrasoEmMeses,
    FundosInvestmentError,
    FundosInvestmentReport,
)
from pense_alm.shared.integration.fundos_investment_service import FundosInvestmentService
from pense_alm.shared.integration.fundos_reader import FundosDatabaseReader
from pense_alm.shared.integration.fundos_records import (
    CadastroSnapshot,
    CdaCompetence,
    CdaHolderRecord,
    CdaHoldingLink,
    CdaIncompleteReason,
    CdaSnapshot,
    CdaUnavailableReason,
    FundosPartyLink,
    FundosSubjectRecord,
)
from pense_alm.shared.integration.fundos_relation_rules import RelationOperation
from pense_alm.shared.integration.fundos_relation_service import FundosRelationService
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara, dv_errado
from .cda_sintetico import BancoCda
from .fundos_sintetico import criar_banco


INVESTS_IN = RelationshipType.INVESTS_IN
ACTIVE = RelationshipStatus.ACTIVE
INACTIVE = RelationshipStatus.INACTIVE
PARCIAL = CdaIncompleteReason.STATUS_NAO_SUCCESS

CNPJ_A = cnpj_ficticio(1)
CNPJ_B = cnpj_ficticio(2)
CNPJ_C = cnpj_ficticio(3)
CNPJ_D = cnpj_ficticio(4)
CNPJ_EMPRESA = cnpj_ficticio(5)
CNPJ_FORA = cnpj_ficticio(6)
CNPJ_CAMADA = cnpj_ficticio(7)
CNPJS = (CNPJ_A, CNPJ_B, CNPJ_C, CNPJ_D, CNPJ_EMPRESA, CNPJ_FORA, CNPJ_CAMADA)

JULHO = date(2026, 7, 31)
AGOSTO = date(2026, 8, 31)
SETEMBRO = date(2026, 9, 30)
OUTUBRO = date(2026, 10, 31)
INICIO = {
    JULHO: datetime(2026, 8, 28, 12, tzinfo=UTC),
    AGOSTO: datetime(2026, 9, 28, 12, tzinfo=UTC),
    SETEMBRO: datetime(2026, 10, 29, 12, tzinfo=UTC),
    OUTUBRO: datetime(2026, 11, 20, 12, tzinfo=UTC),
}
COLETA = {JULHO: 7, AGOSTO: 8, SETEMBRO: 9, OUTUBRO: 10}
CADASTRO = date(2026, 10, 27)
INICIO_CADASTRO = datetime(2026, 10, 27, 12, tzinfo=UTC)

adaptador = FundosAdapter()
ID = {cnpj: adaptador.entity_id(cnpj) for cnpj in CNPJS}


def meia_noite(dia):
    return datetime.combine(dia, time(0, 0), tzinfo=UTC)


def assunto(cnpj, source_id, situacao=NORMAL):
    return FundosSubjectRecord(
        cnpj=cnpj,
        source_table="funds",
        source_id=source_id,
        names=("FUNDO FICTICIO " + str(source_id),),
        situacoes=(situacao,),
        tipos_fundo=("FIDC",),
        tipos_classe=(),
        tipos_pessoa_gestor=("PJ",),
        parties=(),
    )


def retrato(*assuntos):
    return CadastroSnapshot(
        reference_date=CADASTRO,
        collection_run_id=1,
        started_at=INICIO_CADASTRO,
        complete=True,
        incomplete_reason=None,
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


FUNDOS = retrato(*(assunto(cnpj, indice) for indice, cnpj in enumerate(CNPJS[:4], 1)))


def detentor(cnpj, dia, *investidos, base=10, confidencial=False):
    """Detentor no L_H dia, com uma linha por investido (ids base, base + 1...)."""

    links = tuple(
        CdaHoldingLink(investee_cnpj=investido, holding_id=base + indice, collected_at=INICIO[dia])
        for indice, investido in enumerate(investidos)
    )
    return CdaHolderRecord(cnpj, dia, bool(links), confidencial, links)


def cda(*detentores, incompletas=None, outras=()):
    """CDA com as competencias dos detentores e as outras; incompletas: {dia: motivo}."""

    incompletas = incompletas or {}
    dias = sorted({item.competence for item in detentores} | set(incompletas) | set(outras))
    competencias = tuple(
        CdaCompetence(dia, (COLETA[dia],), COLETA[dia], INICIO[dia], incompletas.get(dia))
        for dia in dias
    )
    return CdaSnapshot(True, None, competencias, (), tuple(detentores))


def entidade(cnpj, tipo=EntityType.FIDC, nome="FUNDO FICTICIO"):
    proveniencia = DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste ficticio",
        collected_at=INICIO_CADASTRO,
    )
    return Entity(
        entity_id=ID[cnpj],
        legal_name=nome,
        entity_type=tipo,
        status=EntityStatus.ACTIVE,
        provenance=proveniencia,
        identifiers=(
            EntityIdentifier(
                identifier_type=IdentifierType.CNPJ,
                value=cnpj,
                provenance=proveniencia,
                is_primary=True,
            ),
        ),
        created_at=INICIO_CADASTRO,
        updated_at=INICIO_CADASTRO,
    )


def manual(origem, alvo):
    """INVESTS_IN de outra fonte (MANUAL), com relationship_id aleatorio."""

    return EntityRelationship(
        relationship_id=uuid4(),
        source_entity_id=ID[origem],
        target_entity_id=ID[alvo],
        relationship_type=INVESTS_IN,
        provenance=DataProvenance(
            source_type=SourceType.MANUAL,
            source_name="Teste ficticio",
            collected_at=INICIO_CADASTRO,
        ),
        status=ACTIVE,
        created_at=INICIO_CADASTRO,
    )


class EspiaoRelacoes:
    """Repassa ao SQLite; registra leituras e saves e pode falhar em ids escolhidos."""

    def __init__(self, repositorio, falha_no_save=(), falha_na_leitura=False):
        self._repositorio = repositorio
        self._falha_no_save = set(falha_no_save)
        self._falha_na_leitura = falha_na_leitura
        self.salvas = []
        self.lidas = []

    def save(self, relationship):
        self.salvas.append(relationship.relationship_id)

        if relationship.relationship_id in self._falha_no_save:
            raise RuntimeError("falha ficticia ao gravar")

        return self._repositorio.save(relationship)

    def list_by_source(self, entity_id):
        if self._falha_na_leitura:
            raise RuntimeError("falha ficticia de leitura do destino")

        self.lidas.append(entity_id)
        return self._repositorio.list_by_source(entity_id)

    def list_active_at(self, reference_datetime, relationship_type=None):
        return self._repositorio.list_active_at(reference_datetime, relationship_type)


class EspiaoEntidades:
    """Repassa ao SQLite e conta as buscas por CNPJ."""

    def __init__(self, repositorio):
        self._repositorio = repositorio
        self.buscas = 0

    def get_by_identifier(self, identifier_type, value):
        self.buscas += 1
        return self._repositorio.get_by_identifier(identifier_type, value)


class Proibido:
    """Destino que nao pode ser lido nem escrito."""

    def __getattr__(self, name):
        raise AssertionError("o destino nao deveria ser usado")


@pytest.fixture
def destino(tmp_path):
    manager = SQLiteConnectionManager(tmp_path / "destino" / "camada.sqlite3")
    return manager, SQLiteEntityRepository(manager), SQLiteRelationshipRepository(manager)


def executar(destino, leitura, snapshot=FUNDOS, relacoes=None, entidades=None):
    fase = FundosImportService(destino[1]).import_entities(snapshot)
    servico = FundosInvestmentService(entidades or destino[1], relacoes or destino[2])
    return servico.import_investments(leitura, snapshot, fase)


def relacao(destino, origem, alvo):
    return destino[2].get_by_canonical_key(f"{ID[origem]}:invests_in:{ID[alvo]}")


def linhas_relacoes(destino):
    with destino[0].read_connection() as conexao:
        return [
            tuple(linha)
            for linha in conexao.execute(
                "SELECT * FROM entity_relationships ORDER BY relationship_id"
            )
        ]


def nao_zero(report):
    """Os contadores diferentes de zero do relatorio, com os nao criados."""

    valores = {nome: getattr(report, nome) for nome in COUNTERS}
    valores.update(
        {
            "nao_criadas." + item.name: getattr(report.nao_criadas, item.name)
            for item in fields(report.nao_criadas)
        }
    )
    return {nome: valor for nome, valor in valores.items() if valor}


UM_NA_CAMADA = {"detentores_lidos": 1, "detentores_na_camada": 1}


# --- IS10: ciclo de uma relacao ---


def test_is10_ciclo_cria_mantem_fecha_e_reabre(destino):
    primeira = executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B, CNPJ_B)))
    assert nao_zero(primeira) == {**UM_NA_CAMADA, "pares_lidos": 1, "criadas": 1}
    criada = relacao(destino, CNPJ_A, CNPJ_B)
    assert (criada.status, criada.valid_from, criada.valid_to) == (ACTIVE, meia_noite(JULHO), None)
    assert criada.provenance.source_reference == "fundos:holdings:10"
    assert criada.created_at == INICIO[JULHO]

    antes = linhas_relacoes(destino)
    espiao = EspiaoRelacoes(destino[2])
    segunda = executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B)), relacoes=espiao)
    assert nao_zero(segunda) == {**UM_NA_CAMADA, "pares_lidos": 1, "gravadas": 1, "mantidas": 1}
    assert espiao.salvas == [] and linhas_relacoes(destino) == antes

    terceira = executar(destino, cda(detentor(CNPJ_A, AGOSTO, CNPJ_C, base=20)))
    assert nao_zero(terceira) == {
        **UM_NA_CAMADA,
        "pares_lidos": 1,
        "gravadas": 1,
        "criadas": 1,
        "fechadas": 1,
    }
    fechada = relacao(destino, CNPJ_A, CNPJ_B)
    assert (fechada.status, fechada.valid_from, fechada.valid_to) == (
        INACTIVE,
        meia_noite(JULHO),
        meia_noite(AGOSTO),
    )
    assert fechada.provenance.source_reference == f"fundos:collection_runs:{COLETA[AGOSTO]}"
    assert fechada.provenance.collected_at == INICIO[AGOSTO]
    assert (fechada.relationship_id, fechada.created_at) == (criada.relationship_id, criada.created_at)

    quarta = executar(destino, cda(detentor(CNPJ_A, SETEMBRO, CNPJ_B, base=30)))
    assert nao_zero(quarta) == {
        **UM_NA_CAMADA,
        "pares_lidos": 1,
        "gravadas": 2,
        "reabertas": 1,
        "fechadas": 1,
    }
    reaberta = relacao(destino, CNPJ_A, CNPJ_B)
    assert (reaberta.status, reaberta.valid_from, reaberta.valid_to) == (
        ACTIVE,
        meia_noite(SETEMBRO),
        None,
    )
    assert reaberta.provenance.source_reference == "fundos:holdings:30"
    assert (reaberta.relationship_id, reaberta.created_at) == (criada.relationship_id, criada.created_at)
    assert relacao(destino, CNPJ_A, CNPJ_C).status is INACTIVE


# --- IS1 a IS3 e IS5: o que so e contado ---


def test_is1_a_is3_investido_sem_par_e_contado_uma_vez(destino):
    destino[1].save(entidade(CNPJ_EMPRESA, EntityType.COMPANY, "EMPRESA FICTICIA"))
    espiao = EspiaoEntidades(destino[1])
    linhas = (CNPJ_FORA, CNPJ_FORA, CNPJ_EMPRESA, CNPJ_A, dv_errado(CNPJ_B), CNPJ_B)

    report = executar(destino, cda(detentor(CNPJ_A, JULHO, *linhas)), entidades=espiao)

    assert nao_zero(report) == {
        **UM_NA_CAMADA,
        "pares_lidos": 5,
        "criadas": 1,
        "nao_criadas.investido_fora_da_camada": 1,
        "nao_criadas.investido_de_outro_tipo": 1,
        "nao_criadas.autorrelacao": 1,
        "nao_criadas.cnpj_recusado": 1,
    }
    # Uma busca por CNPJ fora das fases 1 e 2, mesmo com duas linhas.
    assert espiao.buscas == 2
    assert destino[2].count(INVESTS_IN) == 1


def test_is5_detentor_fora_da_camada_do_retrato_e_cnpj_recusado_so_contam(destino):
    destino[1].save(entidade(CNPJ_CAMADA))
    destino[1].save(entidade(CNPJ_EMPRESA, EntityType.COMPANY, "EMPRESA FICTICIA"))
    espiao = EspiaoRelacoes(destino[2])
    leitura = cda(
        detentor(CNPJ_A, JULHO, CNPJ_B),
        detentor(CNPJ_FORA, JULHO, CNPJ_B),
        detentor(CNPJ_EMPRESA, JULHO, CNPJ_B),
        detentor(CNPJ_CAMADA, JULHO, CNPJ_B),
        detentor(dv_errado(CNPJ_D), JULHO, CNPJ_B),
    )

    report = executar(destino, leitura, relacoes=espiao)

    assert nao_zero(report) == {
        "detentores_lidos": 5,
        "detentores_na_camada": 1,
        "detentores_fora_da_camada": 2,
        "detentores_fora_do_retrato": 1,
        "detentores_cnpj_recusado": 1,
        "pares_lidos": 1,
        "criadas": 1,
    }
    assert espiao.lidas == [ID[CNPJ_A]]
    assert espiao.salvas == [relacao(destino, CNPJ_A, CNPJ_B).relationship_id]


# --- IS11 e IS12: leitura incompleta, confidencial, vigencia e outra fonte ---


def test_is11_l_h_incompleto_suspende_o_fechamento_e_ainda_cria(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B)))

    report = executar(
        destino,
        cda(detentor(CNPJ_A, AGOSTO, CNPJ_C, base=20), incompletas={AGOSTO: PARCIAL}),
    )

    assert (report.leitura_completa, report.motivo_incompleto) == (False, PARCIAL)
    assert nao_zero(report) == {
        **UM_NA_CAMADA,
        "detentores_em_cda_incompleto": 1,
        "pares_lidos": 1,
        "gravadas": 1,
        "criadas": 1,
        "fechamento_suspenso": 1,
    }
    assert relacao(destino, CNPJ_A, CNPJ_B).status is ACTIVE


def test_is11_confidencial_no_l_h_nao_fecha(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B)))
    antes = linhas_relacoes(destino)

    report = executar(destino, cda(detentor(CNPJ_A, AGOSTO, confidencial=True)))

    assert report.leitura_completa
    assert nao_zero(report) == {**UM_NA_CAMADA, "gravadas": 1, "suspensa_por_confidencial": 1}
    assert linhas_relacoes(destino) == antes


def test_is11_vigencia_posterior_e_outra_fonte_ficam_intactas(destino):
    executar(destino, cda(detentor(CNPJ_A, AGOSTO, CNPJ_B), detentor(CNPJ_D, AGOSTO, CNPJ_B, base=20)))
    destino[2].save(manual(CNPJ_A, CNPJ_C))
    intactas = [relacao(destino, origem, alvo) for origem, alvo in ((CNPJ_A, CNPJ_B), (CNPJ_D, CNPJ_B))]
    espiao = EspiaoRelacoes(destino[2])

    report = executar(
        destino,
        cda(detentor(CNPJ_A, JULHO, CNPJ_B), detentor(CNPJ_D, JULHO, CNPJ_C, base=20)),
        relacoes=espiao,
    )

    assert nao_zero(report) == {
        "detentores_lidos": 2,
        "detentores_na_camada": 2,
        "pares_lidos": 2,
        "gravadas": 3,
        "criadas": 1,
        "vigencia_posterior_presente": 1,
        "vigencia_posterior_ausente": 1,
        "outra_fonte_ausente": 1,
    }
    assert espiao.salvas == [relacao(destino, CNPJ_D, CNPJ_C).relationship_id]
    assert [relacao(destino, origem, alvo) for origem, alvo in ((CNPJ_A, CNPJ_B), (CNPJ_D, CNPJ_B))] == intactas


def test_is12_fechamento_por_detentor_com_cda_incompleto(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B), detentor(CNPJ_D, JULHO, CNPJ_B, base=20)))

    report = executar(
        destino,
        cda(
            detentor(CNPJ_A, AGOSTO, CNPJ_C, base=30),
            detentor(CNPJ_D, SETEMBRO, CNPJ_C, base=40),
            incompletas={SETEMBRO: PARCIAL},
        ),
    )

    assert (report.leitura_completa, report.motivo_incompleto) == (False, PARCIAL)
    assert nao_zero(report) == {
        "detentores_lidos": 2,
        "detentores_na_camada": 2,
        "detentores_em_cda_incompleto": 1,
        "pares_lidos": 2,
        "gravadas": 2,
        "criadas": 2,
        "fechadas": 1,
        "fechamento_suspenso": 1,
    }
    assert relacao(destino, CNPJ_A, CNPJ_B).status is INACTIVE
    assert relacao(destino, CNPJ_D, CNPJ_B).status is ACTIVE


# --- IS7, IS13 e IS14: erros, falha de leitura e sem CDA ---


def test_is7_erros_de_criar_reabrir_e_fechar_sao_contados_e_seguem(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B, CNPJ_C)))
    executar(destino, cda(detentor(CNPJ_A, AGOSTO, CNPJ_B, base=20)))
    antes = linhas_relacoes(destino)
    ids = [
        relacao(destino, CNPJ_A, CNPJ_C).relationship_id,
        relacao(destino, CNPJ_A, CNPJ_B).relationship_id,
        adaptador.relationship_id(ID[CNPJ_A], INVESTS_IN, ID[CNPJ_D]),
    ]
    espiao = EspiaoRelacoes(destino[2], falha_no_save=ids)

    report = executar(destino, cda(detentor(CNPJ_A, SETEMBRO, CNPJ_C, CNPJ_D, base=30)), relacoes=espiao)

    assert report.erros == (
        FundosInvestmentError(RelationOperation.CRIAR, "RuntimeError", 1),
        FundosInvestmentError(RelationOperation.FECHAR, "RuntimeError", 1),
        FundosInvestmentError(RelationOperation.REABRIR, "RuntimeError", 1),
    )
    assert nao_zero(report) == {**UM_NA_CAMADA, "pares_lidos": 2, "gravadas": 2}
    assert sorted(espiao.salvas) == sorted(ids)
    assert linhas_relacoes(destino) == antes


def test_is13_falha_de_leitura_do_destino_propaga(destino):
    espiao = EspiaoRelacoes(destino[2], falha_na_leitura=True)

    with pytest.raises(RuntimeError):
        executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B)), relacoes=espiao)


def test_is14_sem_cda_nao_le_o_destino(destino):
    fase = FundosImportService(destino[1]).import_entities(FUNDOS)
    sem = CdaSnapshot(False, CdaUnavailableReason.SEM_MIGRATION_004)

    report = FundosInvestmentService(Proibido(), Proibido()).import_investments(sem, FUNDOS, fase)

    assert report == FundosInvestmentReport.sem_cda(CdaUnavailableReason.SEM_MIGRATION_004)


# --- IS15 e guardas ---


def test_is15_relatorio_sem_cnpj_nome_nem_mensagem(destino):
    falha = [adaptador.relationship_id(ID[CNPJ_A], INVESTS_IN, ID[CNPJ_B])]
    espiao = EspiaoRelacoes(destino[2], falha_no_save=falha)

    report = executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B, CNPJ_FORA)), relacoes=espiao)
    texto = repr(report)

    assert report.erros_total == 1
    assert "falha ficticia" not in texto and "FICTICIO" not in texto

    for cnpj in CNPJS:
        assert cnpj not in texto and com_mascara(cnpj) not in texto


def test_detentor_repetido_pelo_cnpj_canonico_e_recusado(destino):
    leitura = cda(detentor(CNPJ_A, JULHO, CNPJ_B), detentor(com_mascara(CNPJ_A), JULHO, CNPJ_C))

    with pytest.raises(ValueError, match="mesmo CNPJ canonico"):
        executar(destino, leitura)


def test_servico_recusa_o_que_nao_e_cda_retrato_nem_fase(destino):
    fase = FundosImportService(destino[1]).import_entities(FUNDOS)
    servico = FundosInvestmentService(destino[1], destino[2])
    leitura = cda(detentor(CNPJ_A, JULHO, CNPJ_B))

    for argumentos in ((object(), FUNDOS, fase), (leitura, object(), fase), (leitura, FUNDOS, object())):
        with pytest.raises(TypeError):
            servico.import_investments(*argumentos)


# --- 3c: S8, investido fora do normal, atraso (C4) e detentor ausente (D5) ---


def com_situacao(cnpj, situacao="Cancelado"):
    """FUNDOS com o fundo do CNPJ fora do funcionamento normal."""

    return retrato(
        *(
            assunto(item.cnpj, item.source_id, situacao) if item.cnpj == cnpj else item
            for item in FUNDOS.subjects
        )
    )


def test_is4_s8_detentor_do_backlog_tem_as_nossas_intactas(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B, CNPJ_C)))
    destino[2].save(manual(CNPJ_A, CNPJ_D))
    antes = linhas_relacoes(destino)
    espiao = EspiaoRelacoes(destino[2])

    report = executar(
        destino,
        cda(detentor(CNPJ_A, AGOSTO, CNPJ_B, base=20)),
        snapshot=com_situacao(CNPJ_A),
        relacoes=espiao,
    )

    assert nao_zero(report) == {
        "detentores_lidos": 1,
        "detentores_fora_do_normal_na_camada": 1,
        "detentores_fora_do_normal_com_relacao": 1,
        "relacoes_de_detentor_fora_do_normal_intactas": 2,
    }
    assert espiao.salvas == [] and linhas_relacoes(destino) == antes


def test_is17_investido_fora_do_normal_cria_e_conta(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_C)))
    destino[1].save(entidade(CNPJ_CAMADA))

    report = executar(
        destino,
        cda(detentor(CNPJ_A, AGOSTO, CNPJ_B, CNPJ_C, CNPJ_CAMADA, base=20)),
        snapshot=com_situacao(CNPJ_B),
    )

    assert nao_zero(report) == {
        **UM_NA_CAMADA,
        "pares_lidos": 3,
        "gravadas": 1,
        "criadas": 2,
        "mantidas": 1,
        "pares_com_investido_fora_do_normal": 2,
    }
    assert relacao(destino, CNPJ_A, CNPJ_B).status is ACTIVE
    assert relacao(destino, CNPJ_A, CNPJ_CAMADA).status is ACTIVE


def test_is16_atraso_do_detentor_em_meses(destino):
    leitura = cda(
        detentor(CNPJ_A, JULHO, CNPJ_B, CNPJ_C),
        detentor(CNPJ_B, AGOSTO, CNPJ_FORA, base=20),
        detentor(CNPJ_D, SETEMBRO, CNPJ_B, base=30),
        incompletas={OUTUBRO: PARCIAL},
    )

    primeira = executar(destino, leitura)
    segunda = executar(destino, leitura)

    # O C_max ignora a competencia incompleta mais nova.
    assert primeira.competencia_mais_nova_completa == SETEMBRO
    assert primeira.atraso == (AtrasoEmMeses(1, 1, 0), AtrasoEmMeses(2, 1, 2))
    assert (primeira.detentores_atrasados, primeira.relacoes_de_detentor_atrasado) == (2, 2)
    # C4: a relacao do detentor atrasado fica ativa e o atraso se repete.
    assert relacao(destino, CNPJ_A, CNPJ_B).status is ACTIVE
    assert (segunda.mantidas, segunda.atraso) == (3, primeira.atraso)


def test_d5_relacoes_nossas_de_detentor_ausente_do_cda(destino):
    executar(destino, cda(detentor(CNPJ_A, JULHO, CNPJ_B, CNPJ_C), detentor(CNPJ_D, JULHO, CNPJ_B, base=20)))
    executar(destino, cda(detentor(CNPJ_A, AGOSTO, CNPJ_B, base=30), detentor(CNPJ_D, AGOSTO, CNPJ_B, base=40)))
    destino[2].save(manual(CNPJ_A, CNPJ_D))
    espiao = EspiaoRelacoes(destino[2])

    report = executar(destino, cda(detentor(CNPJ_D, SETEMBRO, CNPJ_B, base=50)), relacoes=espiao)

    # Do detentor A, so a nossa ativa conta: a fechada e a manual nao.
    assert report.relacoes_de_detentor_ausente_do_cda == 1
    assert nao_zero(report) == {
        **UM_NA_CAMADA,
        "pares_lidos": 1,
        "gravadas": 1,
        "mantidas": 1,
        "relacoes_de_detentor_ausente_do_cda": 1,
    }
    assert espiao.salvas == [] and espiao.lidas == [ID[CNPJ_D]]
    assert relacao(destino, CNPJ_A, CNPJ_B).status is ACTIVE


def test_is8_fases_3_e_4_nao_se_tocam(destino):
    admin = cnpj_ficticio(8)
    gerido = replace(
        FUNDOS.subjects[0],
        parties=(
            FundosPartyLink(
                role="administrador",
                cnpj=admin,
                name="ADMINISTRADORA FICTICIA",
                party_observation_id=101,
            ),
        ),
    )
    com_admin = retrato(gerido, *FUNDOS.subjects[1:])
    leitura = cda(detentor(CNPJ_A, JULHO, CNPJ_B), detentor(CNPJ_B, JULHO, CNPJ_A, base=20))

    def quatro_fases(snapshot):
        fase = FundosImportService(destino[1]).import_entities(snapshot)
        relacoes = FundosRelationService(destino[1], destino[2]).import_relationships(snapshot, fase)
        investimentos = FundosInvestmentService(destino[1], destino[2]).import_investments(
            leitura, snapshot, fase
        )
        return relacoes, investimentos

    quatro_fases(com_admin)
    relacoes, investimentos = quatro_fases(FUNDOS)

    # A fase 3 fecha a administracao e nao conta INVESTS_IN; a fase 4 so ve
    # as INVESTS_IN que saem de cada detentor.
    assert (relacoes.administered_by.gravadas, relacoes.administered_by.fechadas) == (1, 1)
    assert nao_zero(investimentos) == {
        "detentores_lidos": 2,
        "detentores_na_camada": 2,
        "pares_lidos": 2,
        "gravadas": 2,
        "mantidas": 2,
    }
    assert destino[2].count(INVESTS_IN) == 2
    assert destino[2].count(RelationshipType.ADMINISTERED_BY) == 1
    assert relacao(destino, CNPJ_A, CNPJ_B).status is ACTIVE


def test_is9_somas_num_cenario_misto(destino):
    executar(destino, cda(detentor(CNPJ_D, JULHO, CNPJ_B)))
    destino[1].save(entidade(CNPJ_CAMADA))

    report = executar(
        destino,
        cda(
            detentor(CNPJ_A, AGOSTO, CNPJ_B, CNPJ_C, CNPJ_FORA, base=20),
            detentor(CNPJ_D, AGOSTO, CNPJ_C, base=30),
            detentor(CNPJ_CAMADA, JULHO, CNPJ_B, base=40),
            detentor(CNPJ_FORA, JULHO, CNPJ_B, base=50),
            detentor(CNPJ_B, JULHO, CNPJ_C, base=60),
        ),
        snapshot=com_situacao(CNPJ_D),
    )

    assert nao_zero(report) == {
        "detentores_lidos": 5,
        "detentores_na_camada": 2,
        "detentores_fora_do_normal_na_camada": 1,
        "detentores_fora_da_camada": 1,
        "detentores_fora_do_retrato": 1,
        "pares_lidos": 4,
        "criadas": 3,
        "nao_criadas.investido_fora_da_camada": 1,
        "detentores_fora_do_normal_com_relacao": 1,
        "relacoes_de_detentor_fora_do_normal_intactas": 1,
        "detentores_atrasados": 1,
        "relacoes_de_detentor_atrasado": 1,
    }
    assert report.atraso == (AtrasoEmMeses(1, 1, 1),)
    assert report.leitura_completa and report.erros == ()


def test_is6_d6_ponta_a_ponta_com_o_leitor(tmp_path, destino):
    banco = BancoCda(criar_banco(tmp_path, versoes=(1, 2, 3, 4)))
    coleta = banco.coleta()
    fundo_a = banco.fundo_do_cadastro(coleta, CNPJ_A)
    classe_a = banco.classe_do_cadastro(coleta, CNPJ_A, fundo_a)
    fundo_b = banco.fundo_do_cadastro(coleta, CNPJ_B)
    so_classe = banco.classe_do_cadastro(coleta, CNPJ_C, fundo_b)
    banco.fundo_do_cadastro(coleta, CNPJ_D)
    classe_de_outro = banco.classe_do_cadastro(coleta, CNPJ_D, fundo_b)
    coleta_cda = banco.coleta_cda()
    # Classe com o CNPJ do proprio fundo, classe que so existe como classe e
    # classe com o CNPJ de outro fundo, como detentor e como investido.
    banco.posicao(coleta_cda, CNPJ_C, classe_id=classe_a)
    banco.posicao(coleta_cda, CNPJ_D, fundo_id=fundo_a)
    banco.posicao(coleta_cda, CNPJ_D, classe_id=so_classe)
    banco.posicao(coleta_cda, CNPJ_A, classe_id=classe_de_outro)

    cadastro, leitura = FundosDatabaseReader(banco.caminho).read_all()
    fase = FundosImportService(destino[1]).import_entities(cadastro)
    report = FundosInvestmentService(destino[1], destino[2]).import_investments(
        leitura, cadastro, fase
    )

    assert nao_zero(report) == {
        "detentores_lidos": 3,
        "detentores_na_camada": 3,
        "pares_lidos": 4,
        "criadas": 4,
    }
    pares = {(CNPJ_A, CNPJ_C), (CNPJ_A, CNPJ_D), (CNPJ_C, CNPJ_D), (CNPJ_D, CNPJ_A)}
    assert all(relacao(destino, origem, alvo).status is ACTIVE for origem, alvo in pares)
    assert destino[2].count(INVESTS_IN) == 4
