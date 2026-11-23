"""Testes do relatorio da fase 4 de Fundos (FU7.2, PR C2, commit 3a).

Relatorios montados direto, sem banco: um relatorio base coerente e as
variacoes que quebram cada soma ou regra. Os nomes dos testes trazem o
codigo do plano (IP1 a IP9).
"""

from dataclasses import fields
from datetime import UTC, date, datetime
from enum import Enum

import pytest

from pense_alm.shared.integration.fundos_investment_report import (
    COUNTERS,
    AtrasoEmMeses,
    FundosInvestmentError,
    FundosInvestmentReport,
    InvestimentosNaoCriados,
)
from pense_alm.shared.integration.fundos_records import (
    CdaIncompleteReason,
    CdaUnavailableReason,
)
from pense_alm.shared.integration.fundos_relation_rules import RelationOperation


CRIAR = RelationOperation.CRIAR
REABRIR = RelationOperation.REABRIR
FECHAR = RelationOperation.FECHAR
OUTUBRO = date(2026, 10, 31)
PARCIAL = CdaIncompleteReason.STATUS_NAO_SUCCESS

ERRO_CRIAR = FundosInvestmentError(CRIAR, "RuntimeError", 1)
ERRO_REABRIR = FundosInvestmentError(REABRIR, "RuntimeError", 1)
ERRO_FECHAR = FundosInvestmentError(FECHAR, "ValueError", 1)

# Relatorio base coerente: 6 detentores, 13 pares lidos e 13 gravadas, com
# um erro em cada operacao, S8 e um detentor atrasado 2 meses.
BASE = dict(
    cda_disponivel=True,
    leitura_completa=True,
    competencia_mais_nova_completa=OUTUBRO,
    detentores_lidos=6,
    detentores_na_camada=2,
    detentores_fora_do_normal_na_camada=1,
    detentores_fora_da_camada=1,
    detentores_fora_do_retrato=1,
    detentores_cnpj_recusado=1,
    pares_lidos=13,
    gravadas=13,
    criadas=2,
    mantidas=1,
    reabertas=1,
    outra_fonte_presente=1,
    status_inesperado_presente=1,
    vigencia_posterior_presente=1,
    nao_criadas=InvestimentosNaoCriados(1, 1, 1, 1),
    fechadas=1,
    suspensa_por_confidencial=1,
    inativa_ausente=1,
    outra_fonte_ausente=1,
    status_inesperado_ausente=1,
    vigencia_posterior_ausente=1,
    detentores_fora_do_normal_com_relacao=1,
    relacoes_de_detentor_fora_do_normal_intactas=2,
    pares_com_investido_fora_do_normal=1,
    relacoes_de_detentor_ausente_do_cda=1,
    detentores_atrasados=1,
    relacoes_de_detentor_atrasado=3,
    atraso=(AtrasoEmMeses(2, 1, 3),),
    erros=(ERRO_FECHAR, ERRO_CRIAR, ERRO_REABRIR),
)


def relatorio(**muda):
    return FundosInvestmentReport(**{**BASE, **muda})


def mais_um(campo):
    return {campo: BASE.get(campo, 0) + 1}


# --- IP1: somas 1 e 2 ---


def test_ip1_relatorio_base_fecha_as_somas_e_ordena_os_erros():
    base = relatorio()
    assert [erro.operacao for erro in base.erros] == [CRIAR, FECHAR, REABRIR]
    assert (base.erros_de(CRIAR), base.erros_de(REABRIR), base.erros_de(FECHAR)) == (1, 1, 1)
    assert base.erros_total == 3
    assert base.nao_criadas.total == 4


@pytest.mark.parametrize(
    "campo, soma",
    [
        ("pares_lidos", 1),
        ("criadas", 1),
        ("mantidas", 1),
        ("reabertas", 1),
        ("outra_fonte_presente", 1),
        ("status_inesperado_presente", 1),
        ("vigencia_posterior_presente", 1),
        ("gravadas", 2),
        ("fechadas", 2),
        ("fechamento_suspenso", 2),
        ("suspensa_por_confidencial", 2),
        ("inativa_ausente", 2),
        ("outra_fonte_ausente", 2),
        ("status_inesperado_ausente", 2),
        ("vigencia_posterior_ausente", 2),
    ],
)
def test_ip1_cada_parcela_fora_do_lugar_quebra_a_soma(campo, soma):
    with pytest.raises(ValueError, match=f"Soma {soma}"):
        relatorio(**mais_um(campo))


def test_ip1_nao_criadas_e_erros_de_reabrir_entram_nas_somas():
    with pytest.raises(ValueError, match="Soma 1"):
        relatorio(nao_criadas=InvestimentosNaoCriados(2, 1, 1, 1))

    # O erro de reabrir conta nas duas somas: sem ele, as duas caem 1.
    with pytest.raises(ValueError, match="Soma 2"):
        relatorio(erros=(ERRO_CRIAR, ERRO_FECHAR), pares_lidos=12)

    assert relatorio(erros=(ERRO_CRIAR, ERRO_FECHAR), pares_lidos=12, gravadas=12)


# --- IP2: soma 3 ---


@pytest.mark.parametrize(
    "muda",
    [
        dict(motivo_incompleto=PARCIAL),
        dict(leitura_completa=False),
        dict(detentores_em_cda_incompleto=1),
        dict(leitura_completa=False, motivo_incompleto=PARCIAL, detentores_em_cda_incompleto=3),
        dict(leitura_completa=False, motivo_incompleto=PARCIAL, fechamento_suspenso=1, gravadas=14),
    ],
)
def test_ip2_soma_3_recusa_leitura_incoerente(muda):
    with pytest.raises(ValueError, match="Soma 3"):
        relatorio(**muda)


def test_ip2_leitura_incompleta_ainda_fecha_por_detentor():
    incompleta = relatorio(
        leitura_completa=False,
        motivo_incompleto=PARCIAL,
        detentores_em_cda_incompleto=1,
        fechamento_suspenso=1,
        gravadas=14,
    )
    assert (incompleta.fechadas, incompleta.fechamento_suspenso) == (1, 1)


# --- IP3: sem dados de CDA ---


def test_ip3_sem_cda_so_o_motivo():
    sem = FundosInvestmentReport.sem_cda(CdaUnavailableReason.SEM_MIGRATION_004)
    assert (sem.cda_disponivel, sem.leitura_completa) == (False, False)
    assert sem.motivo_sem_cda is CdaUnavailableReason.SEM_MIGRATION_004
    assert all(getattr(sem, nome) == 0 for nome in COUNTERS)
    assert (sem.nao_criadas.total, sem.atraso, sem.erros_total) == (0, (), 0)


@pytest.mark.parametrize(
    "muda",
    [
        dict(),
        dict(motivo_sem_cda=CdaUnavailableReason.SEM_COLETA_DE_CDA, detentores_lidos=1, detentores_fora_da_camada=1),
        dict(motivo_sem_cda=CdaUnavailableReason.SEM_COLETA_DE_CDA, leitura_completa=True),
        dict(motivo_sem_cda=CdaUnavailableReason.SEM_COLETA_DE_CDA, competencia_mais_nova_completa=OUTUBRO),
        dict(motivo_sem_cda=CdaUnavailableReason.SEM_COLETA_DE_CDA, erros=(ERRO_CRIAR,)),
    ],
)
def test_ip3_sem_cda_todo_o_resto_e_zero(muda):
    with pytest.raises(ValueError, match="Sem CDA"):
        FundosInvestmentReport(**{"cda_disponivel": False, "leitura_completa": False, **muda})


def test_ip3_com_cda_nao_ha_motivo_de_sem_cda():
    with pytest.raises(ValueError, match="Sem CDA"):
        relatorio(motivo_sem_cda=CdaUnavailableReason.SEM_MIGRATION_004)


# --- IP4 e IP5: S8 e detentores ---


@pytest.mark.parametrize(
    "muda",
    [
        dict(detentores_fora_do_normal_com_relacao=0),
        dict(relacoes_de_detentor_fora_do_normal_intactas=0),
        dict(detentores_fora_do_normal_com_relacao=2, relacoes_de_detentor_fora_do_normal_intactas=3),
    ],
)
def test_ip4_s8_recusa_formas_incoerentes(muda):
    with pytest.raises(ValueError, match="Soma 4"):
        relatorio(**muda)


@pytest.mark.parametrize("campo", ["detentores_lidos", "detentores_fora_da_camada", "detentores_cnpj_recusado"])
def test_ip5_detentores_lidos_e_a_soma_das_categorias(campo):
    with pytest.raises(ValueError, match="Soma 5"):
        relatorio(**mais_um(campo))


# --- IP6: atraso (C4) ---


@pytest.mark.parametrize(
    "muda",
    [
        dict(atraso=(AtrasoEmMeses(2, 1, 1), AtrasoEmMeses(2, 1, 2)), detentores_atrasados=2),
        dict(atraso=(AtrasoEmMeses(3, 1, 1), AtrasoEmMeses(1, 1, 2)), detentores_atrasados=2),
        dict(detentores_atrasados=2),
        dict(relacoes_de_detentor_atrasado=4),
        dict(atraso=(AtrasoEmMeses(1, 3, 3),), detentores_atrasados=3),
        dict(competencia_mais_nova_completa=None),
    ],
)
def test_ip6_atraso_recusa_distribuicao_incoerente(muda):
    with pytest.raises(ValueError, match="Soma 6"):
        relatorio(**muda)


@pytest.mark.parametrize("meses, detentores", [(0, 1), (1, 0)])
def test_ip6_cada_atraso_tem_mes_e_detentor(meses, detentores):
    with pytest.raises(ValueError, match="Soma 6"):
        AtrasoEmMeses(meses, detentores, 0)


def test_ip6_atraso_em_varios_meses_e_sem_competencia_completa():
    varios = relatorio(
        atraso=(AtrasoEmMeses(1, 1, 0), AtrasoEmMeses(4, 1, 3)),
        detentores_atrasados=2,
    )
    assert [item.meses for item in varios.atraso] == [1, 4]

    sem_c_max = relatorio(
        competencia_mais_nova_completa=None,
        atraso=(),
        detentores_atrasados=0,
        relacoes_de_detentor_atrasado=0,
    )
    assert sem_c_max.atraso == ()


# --- IP7 e IP8: erros e tipos ---


@pytest.mark.parametrize(
    "erros, excecao",
    [
        ((ERRO_CRIAR, FundosInvestmentError(CRIAR, "RuntimeError", 2)), ValueError),
        ("RuntimeError", TypeError),
        ((("criar", "RuntimeError", 1),), TypeError),
    ],
)
def test_ip7_erros_recusados(erros, excecao):
    with pytest.raises(excecao, match="Regra 7"):
        relatorio(erros=erros)


@pytest.mark.parametrize(
    "montar, excecao",
    [
        (lambda: FundosInvestmentError(CRIAR, "RuntimeError", 0), ValueError),
        (lambda: FundosInvestmentError(CRIAR, " ", 1), ValueError),
        (lambda: FundosInvestmentError("criar", "RuntimeError", 1), TypeError),
        (lambda: FundosInvestmentError(CRIAR, "RuntimeError", True), TypeError),
    ],
)
def test_ip7_erro_mal_formado(montar, excecao):
    with pytest.raises(excecao, match="Regra 7"):
        montar()


@pytest.mark.parametrize(
    "muda, excecao",
    [
        (dict(cda_disponivel=1), TypeError),
        (dict(motivo_incompleto="status_nao_success"), TypeError),
        (dict(motivo_sem_cda="sem_migration_004"), TypeError),
        (dict(competencia_mais_nova_completa=datetime(2026, 10, 31, tzinfo=UTC)), TypeError),
        (dict(criadas=True), TypeError),
        (dict(detentores_fora_da_camada=-1), ValueError),
        (dict(nao_criadas=(1, 1, 1, 1)), TypeError),
        (dict(atraso=((2, 1, 3),)), TypeError),
    ],
)
def test_ip8_tipos_errados_sao_recusados(muda, excecao):
    with pytest.raises(excecao, match="Regra 8"):
        relatorio(**muda)


def test_ip8_nao_criadas_recusa_contagem_invalida():
    with pytest.raises(ValueError, match="Regra 8"):
        InvestimentosNaoCriados(cnpj_recusado=-1)


# --- IP9: so contagens, datas e motivos ---


def test_ip9_relatorio_so_tem_contagens_datas_e_motivos():
    base = relatorio()
    permitidos = (bool, int, date, Enum, InvestimentosNaoCriados, tuple, type(None))

    for item in fields(base):
        assert isinstance(getattr(base, item.name), permitidos), item.name

    assert all(isinstance(valor, int) for valor in (base.atraso[0].meses, base.erros[0].quantidade))
