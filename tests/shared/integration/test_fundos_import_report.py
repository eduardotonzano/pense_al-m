"""Testes do relatorio de entidades de Fundos (FU7.2): regras e somas.

Cada soma do __post_init__ tem um caso que a quebra sozinha; a mensagem diz
qual soma falhou. So numeros: o relatorio nao guarda CNPJ nem nome.
"""

from datetime import UTC, date, datetime

import pytest

from pense_alm.shared.integration.fundos_import_report import (
    FundosBacklog,
    FundosEntityReport,
    FundosImportError,
    FundosNaoCriados,
    PrestadorasNaoCriadas,
)


def relatorio(**muda):
    """Relatorio valido: 3 fundos e 2 classes lidos, 4 CNPJs, 1 no backlog."""

    valores = {
        "competencia_cadastro": date(2026, 10, 27),
        "leitura_completa": True,
        "fundos_na_tabela": 3,
        "fundos_lidos": 3,
        "fundos_sem_dado_na_competencia": 0,
        "classes_na_tabela": 2,
        "classes_lidas": 2,
        "classes_sem_dado_na_competencia": 0,
        "classes_unidas_ao_fundo": 1,
        "classes_com_cnpj_de_outro_fundo": 0,
        "classes_so_como_classe": 1,
        "classes_de_fundo_sem_dado": 0,
        "cnpjs_lidos": 4,
        "gestor_pessoa_fisica": 1,
        "gestor_tipo_conflitante": 0,
        "em_funcionamento_normal": 3,
        "backlog": FundosBacklog(cancelado=1),
        "fora_do_normal_ja_na_camada": 0,
        "fundos_criados": 1,
        "fundos_reutilizados": 1,
        "fundos_nao_criados": FundosNaoCriados(sem_nome=1),
        "prestadoras_candidatas": 3,
        "prestadoras_ligadas": 2,
        "prestadoras_so_de_fundo_nao_resolvido": 1,
        "prestadoras_criadas": 1,
        "prestadoras_reutilizadas": 0,
        "prestadoras_nao_criadas": PrestadorasNaoCriadas(),
        "erros": (FundosImportError("prestadoras", "RuntimeError", 1),),
    }
    valores.update(muda)
    return FundosEntityReport(**valores)


def test_relatorio_valido_e_contas_de_erro():
    report = relatorio()

    assert report.erros_total == 1
    assert report.erros_da_fase("prestadoras") == 1
    assert report.erros_da_fase("fundos") == 0


def test_backlog_total_inclui_a_situacao_conflitante():
    backlog = FundosBacklog(cancelado=2, situacao_conflitante=3, sem_situacao=1)

    assert backlog.total == 6


def test_totais_dos_motivos():
    assert FundosNaoCriados(cnpj_colisao=2, id_ocupado=1).total == 3
    assert PrestadorasNaoCriadas(cnpj_recusado=1, sem_nome=2).total == 3


@pytest.mark.parametrize(
    ("muda", "soma"),
    [
        ({"fundos_sem_dado_na_competencia": 1}, "Soma 2"),
        ({"classes_sem_dado_na_competencia": 1}, "Soma 3"),
        ({"classes_de_fundo_sem_dado": 1}, "Soma 4"),
        ({"cnpjs_lidos": 5}, "Soma 5"),
        ({"backlog": FundosBacklog(cancelado=2)}, "Soma 6"),
        ({"fora_do_normal_ja_na_camada": 2}, "Soma 7: fora_do_normal"),
        ({"gestor_tipo_conflitante": 3}, "Soma 7: gestor"),
        ({"fundos_criados": 2}, "Soma 8"),
        ({"prestadoras_candidatas": 4}, "Soma 9: prestadoras_candidatas"),
        ({"prestadoras_criadas": 2}, "Soma 9: prestadoras_ligadas"),
    ],
)
def test_cada_soma_que_nao_fecha_e_recusada(muda, soma):
    with pytest.raises(ValueError, match=soma):
        relatorio(**muda)


def test_erros_entram_na_soma_da_fase_de_fundos():
    report = relatorio(
        fundos_criados=0,
        erros=(FundosImportError("fundos", "DuplicateEntityError", 1),),
        prestadoras_criadas=2,
    )

    assert report.erros_da_fase("fundos") == 1


@pytest.mark.parametrize(
    "erro",
    [
        {"fase": "relacoes", "tipo": "RuntimeError", "quantidade": 1},
        {"fase": "fundos", "tipo": " ", "quantidade": 1},
        {"fase": "fundos", "tipo": "RuntimeError", "quantidade": 0},
    ],
)
def test_regra_10_erro_invalido_e_recusado(erro):
    with pytest.raises(ValueError, match="Regra 10"):
        FundosImportError(**erro)


def test_regra_10_quantidade_booleana_e_recusada():
    with pytest.raises(TypeError, match="Regra 10"):
        FundosImportError("fundos", "RuntimeError", True)


def test_regra_10_par_repetido_e_recusado():
    with pytest.raises(ValueError, match="Regra 10"):
        relatorio(
            erros=(
                FundosImportError("prestadoras", "RuntimeError", 1),
                FundosImportError("prestadoras", "RuntimeError", 1),
            ),
            prestadoras_criadas=0,
        )


def test_regra_10_erros_ficam_ordenados():
    report = relatorio(
        fundos_criados=0,
        prestadoras_criadas=0,
        erros=(
            FundosImportError("prestadoras", "ValueError", 1),
            FundosImportError("fundos", "RuntimeError", 1),
            FundosImportError("prestadoras", "KeyError", 1),
        ),
    )

    assert [(erro.fase, erro.tipo) for erro in report.erros] == [
        ("fundos", "RuntimeError"),
        ("prestadoras", "KeyError"),
        ("prestadoras", "ValueError"),
    ]


@pytest.mark.parametrize(
    ("muda", "erro"),
    [
        ({"competencia_cadastro": datetime(2026, 10, 27, tzinfo=UTC)}, TypeError),
        ({"leitura_completa": 1}, TypeError),
        ({"fundos_criados": True}, TypeError),
        ({"fundos_lidos": -1}, ValueError),
        ({"backlog": {"cancelado": 1}}, TypeError),
        ({"erros": "RuntimeError"}, TypeError),
    ],
)
def test_regra_1_tipos_invalidos_sao_recusados(muda, erro):
    with pytest.raises(erro):
        relatorio(**muda)


@pytest.mark.parametrize(
    "parte",
    [FundosBacklog, FundosNaoCriados, PrestadorasNaoCriadas],
)
def test_partes_recusam_contador_invalido(parte):
    primeiro = next(iter(parte.__dataclass_fields__))

    with pytest.raises(TypeError):
        parte(**{primeiro: True})

    with pytest.raises(ValueError):
        parte(**{primeiro: -1})
