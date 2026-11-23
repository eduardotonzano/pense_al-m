"""Testes dos records do CDA lido pela camada (FU7.2, PR C1b, commit 2a).

Records montados direto, sem banco. So CNPJs ficticios de cnpj_amostras. Os
nomes dos testes trazem o codigo do plano (IL12).
"""

from datetime import UTC, date, datetime

import pytest

from pense_alm.shared.integration.fundos_records import (
    CdaCompetence,
    CdaEmptyPeriod,
    CdaHolderRecord,
    CdaHoldingLink,
    CdaIncompleteReason,
    CdaSnapshot,
    CdaUnavailableReason,
    months_between,
)

from ..cnpj_amostras import cnpj_ficticio


CNPJ_A = cnpj_ficticio(1)
CNPJ_B = cnpj_ficticio(2)
CNPJ_INVESTIDO = cnpj_ficticio(5)
SETEMBRO = date(2026, 9, 30)
OUTUBRO = date(2026, 10, 31)
INICIO = datetime(2026, 11, 28, 12, tzinfo=UTC)
PARCIAL = CdaIncompleteReason.STATUS_NAO_SUCCESS


def competencia(dia=OUTUBRO, motivo=None, coletas=(1,)):
    return CdaCompetence(dia, coletas, coletas[-1], INICIO, motivo)


def linha(holding_id=10):
    return CdaHoldingLink(investee_cnpj=CNPJ_INVESTIDO, holding_id=holding_id, collected_at=INICIO)


def detentor(cnpj=CNPJ_A, dia=OUTUBRO, links=None, confidencial=False):
    links = (linha(),) if links is None else links
    return CdaHolderRecord(cnpj, dia, bool(links), confidencial, links)


def retrato(competencias=(), vazios=(), detentores=()):
    return CdaSnapshot(True, None, competencias, vazios, detentores)


def test_il12_sem_dados_so_o_motivo():
    sem = CdaSnapshot(False, CdaUnavailableReason.SEM_MIGRATION_004)
    assert (sem.complete, sem.latest_complete) == (False, None)

    with pytest.raises(TypeError):
        CdaSnapshot(False)

    with pytest.raises(ValueError):
        CdaSnapshot(False, CdaUnavailableReason.SEM_COLETA_DE_CDA, (competencia(),))

    with pytest.raises(ValueError):
        CdaSnapshot(True, CdaUnavailableReason.SEM_COLETA_DE_CDA, (competencia(),))

    with pytest.raises(ValueError):
        retrato()


def test_il12_c_max_ignora_competencia_incompleta():
    cda = retrato((competencia(SETEMBRO), competencia(OUTUBRO, PARCIAL, (2,))))
    assert cda.latest_complete == SETEMBRO
    assert cda.competence(OUTUBRO).complete is False

    with pytest.raises(KeyError):
        cda.competence(date(2026, 8, 31))


@pytest.mark.parametrize(
    "competencias, vazios, detentores, esperado",
    [
        ((competencia(SETEMBRO), competencia()), (), (detentor(dia=SETEMBRO), detentor(CNPJ_B)), True),
        ((competencia(SETEMBRO, PARCIAL), competencia(coletas=(2,))), (), (detentor(dia=SETEMBRO),), False),
        ((competencia(SETEMBRO),), (CdaEmptyPeriod("202610", (2,), PARCIAL),), (detentor(dia=SETEMBRO),), False),
        ((competencia(SETEMBRO),), (CdaEmptyPeriod("202610", (2,)),), (detentor(dia=SETEMBRO),), True),
        ((competencia(SETEMBRO),), (CdaEmptyPeriod("202608", (2,), PARCIAL),), (detentor(dia=SETEMBRO),), True),
    ],
)
def test_il12_completo_exige_o_l_h_e_o_mes_mais_novo_completos(competencias, vazios, detentores, esperado):
    assert retrato(competencias, vazios, detentores).complete is esperado


@pytest.mark.parametrize(
    "cda, mais_nova, c_max",
    [
        (retrato((competencia(SETEMBRO), competencia(coletas=(2,)))), OUTUBRO, OUTUBRO),
        (retrato((competencia(SETEMBRO), competencia(OUTUBRO, PARCIAL, (2,)))), OUTUBRO, SETEMBRO),
        (retrato((competencia(OUTUBRO, PARCIAL),)), OUTUBRO, None),
        (retrato((), (CdaEmptyPeriod("202610", (1,)),)), None, None),
        (CdaSnapshot(False, CdaUnavailableReason.SEM_COLETA_DE_CDA), None, None),
    ],
)
def test_il12_competencia_mais_nova_com_posicao_em_qualquer_completude(cda, mais_nova, c_max):
    # Trava do CDA (ajuste 1 de 23/11/2026): a maior competencia com posicao.
    assert (cda.latest_competence, cda.latest_complete) == (mais_nova, c_max)


@pytest.mark.parametrize(
    "competencias, vazios, detentores, esperado",
    [
        ((competencia(),), (), (detentor(),), None),
        (
            (competencia(SETEMBRO, CdaIncompleteReason.FONTE_DIFERENTE), competencia(OUTUBRO, PARCIAL, (2,))),
            (),
            (detentor(dia=SETEMBRO), detentor(CNPJ_B)),
            PARCIAL,
        ),
        (
            (competencia(SETEMBRO),),
            (CdaEmptyPeriod("202610", (2,), CdaIncompleteReason.MEMBRO_AUSENTE),),
            (detentor(dia=SETEMBRO),),
            CdaIncompleteReason.MEMBRO_AUSENTE,
        ),
        ((competencia(SETEMBRO, PARCIAL), competencia(coletas=(2,))), (), (detentor(),), None),
    ],
)
def test_il12_motivo_do_cda_incompleto(competencias, vazios, detentores, esperado):
    cda = retrato(competencias, vazios, detentores)
    assert cda.incomplete_reason is esperado
    assert cda.complete is (esperado is None)


def test_il12_sem_dados_de_cda_nao_ha_motivo_de_incompleto():
    cda = CdaSnapshot(False, CdaUnavailableReason.SEM_MIGRATION_004)
    assert (cda.incomplete_reason, cda.complete) == (None, False)


@pytest.mark.parametrize(
    "montar",
    [
        lambda: retrato((competencia(), competencia(SETEMBRO))),
        lambda: retrato((competencia(),), (CdaEmptyPeriod("202610", (2,)),)),
        lambda: retrato((competencia(SETEMBRO),), (), (detentor(),)),
        lambda: retrato((competencia(),), (), (detentor(), detentor())),
        lambda: CdaCompetence(OUTUBRO, (1, 2), 3, INICIO),
        lambda: CdaCompetence(OUTUBRO, (2, 1), 2, INICIO),
        lambda: CdaCompetence(OUTUBRO, (1,), 1, datetime(2026, 11, 28)),
        lambda: CdaEmptyPeriod("202613", (1,)),
        lambda: CdaHolderRecord(CNPJ_A, OUTUBRO, True, False, ()),
        lambda: CdaHolderRecord(CNPJ_A, OUTUBRO, False, False, ()),
        lambda: CdaHolderRecord(CNPJ_A, OUTUBRO, True, False, (linha(11), linha(10))),
    ],
)
def test_il12_formas_incoerentes_sao_recusadas(montar):
    with pytest.raises(ValueError):
        montar()


@pytest.mark.parametrize(
    "montar",
    [
        lambda: CdaCompetence(datetime(2026, 10, 31, tzinfo=UTC), (1,), 1, INICIO),
        lambda: CdaCompetence(OUTUBRO, (True,), 1, INICIO),
        lambda: CdaCompetence(OUTUBRO, (1,), 1, INICIO, "status_nao_success"),
        lambda: CdaHolderRecord(CNPJ_A, OUTUBRO, 1, False, (linha(),)),
        lambda: CdaHolderRecord(CNPJ_A, OUTUBRO, True, False, ("linha",)),
        lambda: retrato(("competencia",)),
    ],
)
def test_il12_tipos_errados_sao_recusados(montar):
    with pytest.raises(TypeError):
        montar()


def test_il12_meses_entre_competencias():
    assert months_between(SETEMBRO, OUTUBRO) == 1
    assert months_between(OUTUBRO, date(2026, 10, 1)) == 0
    assert months_between(date(2025, 9, 30), OUTUBRO) == 13
    assert months_between(date(2026, 12, 31), date(2027, 1, 31)) == 1
    assert months_between(OUTUBRO, SETEMBRO) == -1

    with pytest.raises(TypeError):
        months_between(datetime(2026, 9, 30, tzinfo=UTC), OUTUBRO)


def test_il12_repr_sem_cnpj():
    cda = retrato((competencia(),), (), (detentor(), detentor(CNPJ_B, confidencial=True)))
    texto = repr(cda) + repr(cda.holders) + repr(linha())

    for cnpj in (CNPJ_A, CNPJ_B, CNPJ_INVESTIDO):
        assert cnpj not in texto
