"""Testes do relatorio de relacoes de Fundos (FU7.2, fase 3): regras e somas.

Cada soma do __post_init__ tem um caso que a quebra sozinha; a mensagem diz
qual soma falhou. So numeros e tipos: o relatorio nao guarda CNPJ, nome,
caminho nem mensagem de excecao.
"""

from dataclasses import fields

import pytest

from pense_alm.shared.entities import RelationshipType
from pense_alm.shared.integration.fundos_records import CadastroIncompleteReason
from pense_alm.shared.integration.fundos_relation_report import (
    TYPE_COUNTERS,
    TYPE_FIELDS,
    FundosRelationError,
    FundosRelationReport,
    RelacoesNaoCriadas,
    RelacoesPorTipo,
)
from pense_alm.shared.integration.fundos_relation_rules import RelationOperation


ADMINISTERED_BY = RelationshipType.ADMINISTERED_BY
CUSTODIED_BY = RelationshipType.CUSTODIED_BY
MANAGES = RelationshipType.MANAGES
CRIAR = RelationOperation.CRIAR
REABRIR = RelationOperation.REABRIR
FECHAR = RelationOperation.FECHAR


def administradas(**muda):
    """5 pares lidos e 4 gravadas; fecha com 1 erro de criar e 1 de fechar."""

    valores = {
        "pares_lidos": 5,
        "gravadas": 4,
        "criadas": 1,
        "mantidas": 1,
        "reabertas": 1,
        "nao_criadas": RelacoesNaoCriadas(prestadora_sem_entidade=1),
        "fechadas": 1,
    }
    valores.update(muda)
    return RelacoesPorTipo(**valores)


def geridas(**muda):
    """2 pares lidos e 3 gravadas, sem erro."""

    valores = {
        "pares_lidos": 2,
        "gravadas": 3,
        "mantidas": 1,
        "status_inesperado_presente": 1,
        "outra_fonte_ausente": 1,
    }
    valores.update(muda)
    return RelacoesPorTipo(**valores)


def erros_validos():
    return (
        FundosRelationError(ADMINISTERED_BY, CRIAR, "RuntimeError", 1),
        FundosRelationError(ADMINISTERED_BY, FECHAR, "EntityValidationError", 1),
    )


def relatorio(**muda):
    valores = {
        "leitura_completa": True,
        "motivo_nao_fechar": None,
        "administered_by": administradas(),
        "custodied_by": RelacoesPorTipo(),
        "manages": geridas(),
        "pares_de_fundo_nao_resolvido": 2,
        "fundos_fora_do_normal_com_relacao": 1,
        "relacoes_de_fundo_fora_do_normal_intactas": 3,
        "relacoes_de_fundo_ausente_do_retrato": 1,
        "erros": erros_validos(),
    }
    valores.update(muda)
    return FundosRelationReport(**valores)


def test_relatorio_valido_e_contas_de_erro():
    report = relatorio()

    assert report.erros_total == 2
    assert report.erros_de(ADMINISTERED_BY, CRIAR) == 1
    assert report.erros_de(ADMINISTERED_BY, FECHAR) == 1
    assert report.erros_de(ADMINISTERED_BY, REABRIR) == 0
    assert report.erros_de(MANAGES, CRIAR) == 0
    assert report.por_tipo(MANAGES) is report.manages
    assert report.administered_by.nao_criadas.total == 1


def test_campos_por_tipo_e_contadores():
    assert set(TYPE_FIELDS) == {ADMINISTERED_BY, CUSTODIED_BY, MANAGES}
    assert set(TYPE_COUNTERS) == {
        item.name for item in fields(RelacoesPorTipo)
    } - {"nao_criadas"}
    assert {item.name for item in fields(FundosRelationError)} == {
        "tipo_relacao",
        "operacao",
        "tipo",
        "quantidade",
    }


@pytest.mark.parametrize(
    ("muda", "soma"),
    [
        ({"administered_by": administradas(pares_lidos=6)}, r"Soma 1 \(administered_by\)"),
        ({"custodied_by": RelacoesPorTipo(pares_lidos=1)}, r"Soma 1 \(custodied_by\)"),
        ({"manages": geridas(pares_lidos=3)}, r"Soma 1 \(manages\)"),
        ({"administered_by": administradas(gravadas=5)}, r"Soma 2 \(administered_by\)"),
        ({"custodied_by": RelacoesPorTipo(gravadas=1)}, r"Soma 2 \(custodied_by\)"),
        ({"manages": geridas(gravadas=2)}, r"Soma 2 \(manages\)"),
    ],
)
def test_somas_1_e_2_que_nao_fecham_sao_recusadas(muda, soma):
    with pytest.raises(ValueError, match=soma):
        relatorio(**muda)


def test_erro_de_reabrir_entra_nas_somas_1_e_2():
    report = relatorio(
        administered_by=administradas(reabertas=0),
        erros=erros_validos()
        + (FundosRelationError(ADMINISTERED_BY, REABRIR, "RuntimeError", 1),),
    )

    assert report.erros_de(ADMINISTERED_BY, REABRIR) == 1


@pytest.mark.parametrize(
    ("muda", "mensagem"),
    [
        (
            {"motivo_nao_fechar": CadastroIncompleteReason.STATUS_NAO_SUCCESS},
            "Soma 3: a leitura e completa",
        ),
        ({"leitura_completa": False}, "Soma 3: a leitura e completa"),
        (
            {"manages": geridas(gravadas=4, fechamento_suspenso=1)},
            "Soma 3: leitura completa",
        ),
        (
            {
                "leitura_completa": False,
                "motivo_nao_fechar": CadastroIncompleteReason.MEMBRO_AUSENTE,
            },
            "Soma 3: leitura incompleta",
        ),
    ],
)
def test_soma_3_leitura_e_fechamento(muda, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        relatorio(**muda)


def test_soma_3_leitura_incompleta_valida_suspende_o_fechamento():
    report = relatorio(
        leitura_completa=False,
        motivo_nao_fechar=CadastroIncompleteReason.LINE_COUNT_NULO,
        administered_by=administradas(fechadas=0, fechamento_suspenso=1),
    )

    assert report.motivo_nao_fechar is CadastroIncompleteReason.LINE_COUNT_NULO


@pytest.mark.parametrize(
    ("fundos", "relacoes"),
    [(4, 3), (0, 3), (1, 0)],
)
def test_soma_4_fundos_e_relacoes_fora_do_normal(fundos, relacoes):
    with pytest.raises(ValueError, match="Soma 4"):
        relatorio(
            fundos_fora_do_normal_com_relacao=fundos,
            relacoes_de_fundo_fora_do_normal_intactas=relacoes,
        )


def test_soma_4_aceita_zero_e_zero():
    report = relatorio(
        fundos_fora_do_normal_com_relacao=0,
        relacoes_de_fundo_fora_do_normal_intactas=0,
    )

    assert report.relacoes_de_fundo_fora_do_normal_intactas == 0


@pytest.mark.parametrize(
    ("erro", "excecao"),
    [
        ((RelationshipType.ISSUES, CRIAR, "RuntimeError", 1), ValueError),
        ((ADMINISTERED_BY, "criar", "RuntimeError", 1), TypeError),
        ((ADMINISTERED_BY, CRIAR, " ", 1), ValueError),
        ((ADMINISTERED_BY, CRIAR, "RuntimeError", 0), ValueError),
        ((ADMINISTERED_BY, CRIAR, "RuntimeError", True), TypeError),
    ],
)
def test_regra_5_erro_invalido_e_recusado(erro, excecao):
    with pytest.raises(excecao, match="Regra 5"):
        FundosRelationError(*erro)


def test_regra_5_trio_repetido_e_recusado():
    with pytest.raises(ValueError, match="Regra 5"):
        relatorio(
            erros=erros_validos()
            + (FundosRelationError(ADMINISTERED_BY, CRIAR, "RuntimeError", 1),)
        )


def test_regra_5_erros_ficam_ordenados():
    report = relatorio(
        administered_by=RelacoesPorTipo(),
        manages=geridas(pares_lidos=4, gravadas=5),
        erros=(
            FundosRelationError(MANAGES, REABRIR, "RuntimeError", 1),
            FundosRelationError(MANAGES, FECHAR, "RuntimeError", 1),
            FundosRelationError(MANAGES, CRIAR, "KeyError", 1),
        ),
    )

    assert [(erro.operacao, erro.tipo) for erro in report.erros] == [
        (CRIAR, "KeyError"),
        (FECHAR, "RuntimeError"),
        (REABRIR, "RuntimeError"),
    ]


@pytest.mark.parametrize(
    ("muda", "excecao"),
    [
        ({"leitura_completa": 1}, TypeError),
        ({"motivo_nao_fechar": "status_nao_success"}, TypeError),
        ({"custodied_by": {"pares_lidos": 0}}, TypeError),
        ({"pares_de_fundo_nao_resolvido": -1}, ValueError),
        ({"relacoes_de_fundo_ausente_do_retrato": True}, TypeError),
        ({"erros": "RuntimeError"}, TypeError),
        ({"erros": ("RuntimeError",)}, TypeError),
    ],
)
def test_regra_6_tipos_invalidos_sao_recusados(muda, excecao):
    with pytest.raises(excecao):
        relatorio(**muda)


@pytest.mark.parametrize(
    ("parte", "muda", "excecao"),
    [
        (RelacoesPorTipo, {"criadas": -1}, ValueError),
        (RelacoesPorTipo, {"fechadas": True}, TypeError),
        (RelacoesPorTipo, {"nao_criadas": {}}, TypeError),
        (RelacoesNaoCriadas, {"autorrelacao": True}, TypeError),
        (RelacoesNaoCriadas, {"prestadora_sem_entidade": -1}, ValueError),
    ],
)
def test_partes_recusam_contador_invalido(parte, muda, excecao):
    with pytest.raises(excecao):
        parte(**muda)


def test_repr_so_com_numeros_e_tipos():
    texto = repr(relatorio())

    assert "RuntimeError" in texto
    assert "administered_by" in texto
    assert "falha" not in texto
