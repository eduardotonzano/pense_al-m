"""Testes do leitor do CDA da camada (FU7.2, PR C1b, commit 2b).

Bancos sinteticos em tmp_path, com as migrations reais do modulo de Fundos
(fundos_sintetico e cda_sintetico); o banco de teste real nao entra. So
CNPJs ficticios de cnpj_amostras e nomes marcados como ficticios. Os nomes
dos testes trazem o codigo do plano (IL1 a IL11).
"""

import ast
import hashlib
import inspect
import os
import sqlite3
from datetime import date

import pytest

from pense_alm.shared.integration import fundos_reader as leitor
from pense_alm.shared.integration.fundos_reader import FundosDatabaseReader
from pense_alm.shared.integration.fundos_records import (
    CadastroIncompleteReason,
    CdaIncompleteReason,
    CdaUnavailableReason,
    months_between,
)

from ..cnpj_amostras import cnpj_ficticio
from .cda_sintetico import BancoCda
from .fundos_sintetico import BancoFundos, criar_banco


CNPJ_A = cnpj_ficticio(1)
CNPJ_B = cnpj_ficticio(2)
CNPJ_I = cnpj_ficticio(5)
CNPJ_J = cnpj_ficticio(6)
AGOSTO = "2026-08-31"
SETEMBRO = "2026-09-30"
INICIO_AGO = "2026-09-29T12:00:00.000000+00:00"
INICIO_SET = "2026-10-29T12:00:00.000000+00:00"
OUTUBRO_DIA = date(2026, 10, 31)
PROIBIDAS = {
    ("holdings", coluna)
    for coluna in (
        "investee_name",
        "name_field_name",
        "quantity",
        "quantity_field_name",
        "market_value",
        "value_field_name",
        "checksum",
    )
} | {
    ("confidential_holdings", coluna)
    for coluna in (
        "market_value",
        "value_field_name",
        "confidential_until",
        "confidential_until_field_name",
        "checksum",
    )
}


@pytest.fixture
def banco(tmp_path):
    return BancoCda(criar_banco(tmp_path, versoes=(1, 2, 3, 4)))


def ler(banco):
    return FundosDatabaseReader(banco.caminho).read_cda()


def por_cnpj(cda):
    return {detentor.cnpj: detentor for detentor in cda.holders}


# --- IL1 e IL2: sem dados de CDA ---


def test_il1_sem_a_004_nao_ha_dados_e_o_cadastro_nao_muda(tmp_path):
    antigo = BancoFundos(criar_banco(tmp_path))
    antigo.fundo_do_cadastro(antigo.coleta(), CNPJ_A)
    leitura = FundosDatabaseReader(antigo.caminho)

    cda = leitura.read_cda()
    assert (cda.available, cda.unavailable_reason) == (False, CdaUnavailableReason.SEM_MIGRATION_004)
    assert cda.complete is False and cda.latest_complete is None
    assert leitura.read_all() == (leitura.read_cadastro(), cda)


def test_il1_tabelas_sem_a_versao_4_contam_como_sem_a_004(banco):
    conexao = sqlite3.connect(banco.caminho)

    try:
        with conexao:
            conexao.execute("DELETE FROM schema_migrations WHERE version = 4")
    finally:
        conexao.close()

    assert ler(banco).unavailable_reason is CdaUnavailableReason.SEM_MIGRATION_004


def test_il1_dados_de_cda_nao_mudam_o_retrato_do_cadastro(tmp_path):
    retratos = []

    for nome, com_cda in (("sem_cda.db", False), ("com_cda.db", True)):
        banco = BancoCda(criar_banco(tmp_path, versoes=(1, 2, 3, 4), nome=nome))
        coleta = banco.coleta()
        fundo = banco.fundo_do_cadastro(coleta, CNPJ_A)
        banco.administrador(coleta, fundo, CNPJ_B)

        if com_cda:
            coleta_cda = banco.coleta_cda()
            banco.posicao(coleta_cda, CNPJ_I, fundo_id=fundo)
            banco.confidencial(coleta_cda, fundo_id=fundo)
            assert ler(banco).available

        retratos.append(FundosDatabaseReader(banco.caminho).read_cadastro())

    assert retratos[0] == retratos[1]


def test_il2_com_a_004_e_sem_coleta_de_cda(banco):
    banco.fundo_do_cadastro(banco.coleta(), CNPJ_A)
    cda = ler(banco)
    assert (cda.available, cda.unavailable_reason) == (False, CdaUnavailableReason.SEM_COLETA_DE_CDA)


# --- IL3 a IL6: competencia e linhas de cada detentor ---


def test_il3_l_h_e_a_competencia_mais_recente_de_cada_detentor(banco):
    a, b = banco.fundo(CNPJ_A), banco.fundo(CNPJ_B)
    setembro = banco.coleta_cda(periodo="202609", inicio=INICIO_SET)
    outubro = banco.coleta_cda()
    banco.posicao(setembro, CNPJ_I, fundo_id=a, competencia=SETEMBRO)
    banco.posicao(setembro, CNPJ_I, fundo_id=b, competencia=SETEMBRO)
    banco.posicao(outubro, CNPJ_J, fundo_id=a)

    cda = ler(banco)
    detentores = por_cnpj(cda)
    assert detentores[CNPJ_A].competence == OUTUBRO_DIA
    assert detentores[CNPJ_B].competence == date(2026, 9, 30)
    assert [link.investee_cnpj for link in detentores[CNPJ_A].links] == [CNPJ_J]
    assert [item.reference_date for item in cda.competences] == [date(2026, 9, 30), OUTUBRO_DIA]
    assert cda.latest_complete == OUTUBRO_DIA and cda.complete


def test_il4_varias_linhas_do_par_chegam_todas_com_id_e_inicio_da_coleta(banco):
    a = banco.fundo(CNPJ_A)
    coleta = banco.coleta_cda()
    ids = [banco.posicao(coleta, CNPJ_I, fundo_id=a, ordem=ordem) for ordem in (1, 2)]

    (detentor,) = ler(banco).holders
    assert [link.holding_id for link in detentor.links] == sorted(ids)
    assert {link.investee_cnpj for link in detentor.links} == {CNPJ_I}
    assert {link.collected_at.isoformat() for link in detentor.links} == {"2026-11-28T12:00:00+00:00"}


def test_il5_reapresentacao_soma_as_linhas_e_fecha_pela_coleta_mais_nova(banco):
    a = banco.fundo(CNPJ_A)
    primeira = banco.coleta_cda()
    segunda = banco.coleta_cda(inicio="2026-11-30T12:00:00.000000+00:00")
    banco.posicao(primeira, CNPJ_I, fundo_id=a)
    banco.posicao(segunda, CNPJ_J, fundo_id=a)

    cda = ler(banco)
    (competencia,) = cda.competences
    assert competencia.run_ids == (primeira, segunda)
    assert competencia.closing_run_id == segunda and competencia.complete
    assert {link.investee_cnpj for link in cda.holders[0].links} == {CNPJ_I, CNPJ_J}


def test_il5_reapresentacao_incompleta_deixa_a_competencia_incompleta(banco):
    a = banco.fundo(CNPJ_A)
    primeira = banco.coleta_cda()
    segunda = banco.coleta_cda(status="partial", inicio="2026-11-30T12:00:00.000000+00:00")
    banco.posicao(primeira, CNPJ_I, fundo_id=a)
    banco.posicao(segunda, CNPJ_I, fundo_id=a)

    cda = ler(banco)
    assert cda.competences[0].incomplete_reason is CdaIncompleteReason.STATUS_NAO_SUCCESS
    assert cda.complete is False and cda.latest_complete is None


def test_il6_fundo_e_classe_com_o_mesmo_cnpj_viram_um_detentor(banco):
    fundo = banco.fundo(CNPJ_A)
    classe = banco.classe(CNPJ_A, fundo)
    coleta = banco.coleta_cda()
    banco.posicao(coleta, CNPJ_I, fundo_id=fundo)
    banco.posicao(coleta, CNPJ_J, classe_id=classe)

    (detentor,) = ler(banco).holders
    assert detentor.cnpj == CNPJ_A
    assert {link.investee_cnpj for link in detentor.links} == {CNPJ_I, CNPJ_J}


# --- IL7: leitura incompleta ---


@pytest.mark.parametrize(
    "campos, esperado",
    [
        (dict(status="partial"), CdaIncompleteReason.STATUS_NAO_SUCCESS),
        (dict(fonte="MANUAL"), CdaIncompleteReason.FONTE_DIFERENTE),
        (dict(membros=("cda_fie",)), CdaIncompleteReason.MEMBRO_AUSENTE),
        (dict(membros=()), CdaIncompleteReason.MEMBRO_AUSENTE),
        (dict(pendentes=("cda_fie_CONFID",)), CdaIncompleteReason.MEMBRO_NAO_PROCESSADO),
        (dict(sem_linhas=("cda_fie",)), CdaIncompleteReason.LINE_COUNT_NULO),
        (dict(status="partial", fonte="MANUAL", pendentes=("cda_fie",)), CdaIncompleteReason.STATUS_NAO_SUCCESS),
        (dict(membros=("cda_fie",), pendentes=("cda_fie",)), CdaIncompleteReason.MEMBRO_AUSENTE),
    ],
)
def test_il7_motivo_da_competencia_incompleta(banco, campos, esperado):
    a = banco.fundo(CNPJ_A)
    banco.posicao(banco.coleta_cda(**campos), CNPJ_I, fundo_id=a)

    cda = ler(banco)
    (competencia,) = cda.competences
    assert competencia.incomplete_reason is esperado
    assert cda.complete is False and cda.latest_complete is None


@pytest.mark.parametrize("dias", [("2026-10-31", "2026-10-30"), ("2026-11-30",)])
def test_il7_competencia_divergente(banco, dias):
    a = banco.fundo(CNPJ_A)
    coleta = banco.coleta_cda()

    for dia in dias:
        banco.posicao(coleta, CNPJ_I, fundo_id=a, competencia=dia)

    reasons = {item.incomplete_reason for item in ler(banco).competences}
    assert reasons == {CdaIncompleteReason.COMPETENCIA_DIVERGENTE}


@pytest.mark.parametrize("status, completo", [("partial", False), ("success", True)])
def test_il7_mes_mais_novo_sem_posicao_decide_se_o_cda_e_completo(banco, status, completo):
    a = banco.fundo(CNPJ_A)
    setembro = banco.coleta_cda(periodo="202609", inicio=INICIO_SET)
    banco.posicao(setembro, CNPJ_I, fundo_id=a, competencia=SETEMBRO)
    banco.coleta_cda(status=status)

    cda = ler(banco)
    (detentor,) = cda.holders
    assert detentor.competence == date(2026, 9, 30)
    assert cda.competence(detentor.competence).complete
    assert cda.latest_complete == date(2026, 9, 30)
    (vazio,) = cda.empty_periods
    assert (vazio.period, vazio.complete) == ("202610", completo)
    assert cda.complete is completo


def test_il7_guarda_todo_motivo_do_membro_existe_no_cda(banco):
    # _cda_run_reason converte por valor o motivo do _member_reason do B2: um
    # motivo novo la, sem par no CdaIncompleteReason, estouraria em producao.
    nomes = set()

    for no in ast.walk(ast.parse(inspect.getsource(leitor._member_reason))):
        if not isinstance(no, ast.Return) or no.value is None:
            continue

        if isinstance(no.value, ast.Constant) and no.value.value is None:
            continue

        assert isinstance(no.value, ast.Attribute) and isinstance(no.value.value, ast.Name)
        assert no.value.value.id == "CadastroIncompleteReason"
        nomes.add(no.value.attr)

    motivos = {CadastroIncompleteReason[nome] for nome in nomes}
    assert len(motivos) == 3
    assert {motivo.value for motivo in motivos} <= {motivo.value for motivo in CdaIncompleteReason}

    coletas = [
        banco.coleta_cda(),
        banco.coleta_cda(membros=("cda_fie",)),
        banco.coleta_cda(pendentes=("cda_fie_CONFID",)),
        banco.coleta_cda(sem_linhas=("cda_fie_CONFID",)),
    ]
    conexao = sqlite3.connect(banco.caminho)

    try:
        vistos = [
            leitor._member_reason(conexao, coleta, "cda_fie_CONFID_202610.csv")
            for coleta in coletas
        ]
    finally:
        conexao.close()

    assert vistos[0] is None and set(vistos[1:]) == motivos
    assert [CdaIncompleteReason(motivo.value) for motivo in vistos[1:]] == [
        CdaIncompleteReason.MEMBRO_AUSENTE,
        CdaIncompleteReason.MEMBRO_NAO_PROCESSADO,
        CdaIncompleteReason.LINE_COUNT_NULO,
    ]


# --- IL8 a IL11 ---


def test_il8_confidencial_na_competencia_do_detentor(banco):
    a, b = banco.fundo(CNPJ_A), banco.fundo(CNPJ_B)
    setembro = banco.coleta_cda(periodo="202609", inicio=INICIO_SET)
    outubro = banco.coleta_cda()
    banco.posicao(setembro, CNPJ_I, fundo_id=a, competencia=SETEMBRO)
    banco.confidencial(outubro, fundo_id=a)
    banco.posicao(outubro, CNPJ_I, fundo_id=b)
    banco.confidencial(outubro, fundo_id=b)

    detentores = por_cnpj(ler(banco))
    so_confidencial, os_dois = detentores[CNPJ_A], detentores[CNPJ_B]
    assert (so_confidencial.competence, so_confidencial.has_identified) == (OUTUBRO_DIA, False)
    assert so_confidencial.has_confidential and so_confidencial.links == ()
    assert (os_dois.has_identified, os_dois.has_confidential, len(os_dois.links)) == (True, True, 1)


def test_il9_o_leitor_nunca_le_nome_nem_valor(banco, monkeypatch):
    a = banco.fundo(CNPJ_A)
    coleta = banco.coleta_cda()
    banco.posicao(coleta, CNPJ_I, fundo_id=a)
    banco.confidencial(coleta, fundo_id=a)
    conectar = sqlite3.connect
    lidas = set()

    def autorizar(acao, tabela, coluna, *_):
        if acao == sqlite3.SQLITE_READ:
            if (tabela, coluna) in PROIBIDAS:
                return sqlite3.SQLITE_DENY

            lidas.add(tabela)

        return sqlite3.SQLITE_OK

    def conectar_vigiado(*args, **kwargs):
        conexao = conectar(*args, **kwargs)
        conexao.set_authorizer(autorizar)
        return conexao

    monkeypatch.setattr(leitor.sqlite3, "connect", conectar_vigiado)
    cda = ler(banco)
    assert cda.available and cda.holders[0].has_confidential
    assert {"holdings", "confidential_holdings"} <= lidas


def test_il10_so_leitura_banco_igual_e_uma_sessao(banco, monkeypatch):
    banco.fundo_do_cadastro(banco.coleta(), CNPJ_B)
    coleta = banco.coleta_cda()
    banco.posicao(coleta, CNPJ_I, fundo_id=banco.fundo(CNPJ_A))
    antes = hashlib.sha256(banco.caminho.read_bytes()).hexdigest()
    arquivos = sorted(os.listdir(banco.caminho.parent))
    sessoes = []
    original = FundosDatabaseReader.session

    def contar(self):
        sessoes.append(1)
        return original(self)

    monkeypatch.setattr(FundosDatabaseReader, "session", contar)
    cadastro, cda = FundosDatabaseReader(banco.caminho).read_all()
    assert cadastro.subjects and cda.available
    assert len(sessoes) == 1
    assert hashlib.sha256(banco.caminho.read_bytes()).hexdigest() == antes
    assert sorted(os.listdir(banco.caminho.parent)) == arquivos


def test_il11_detentor_so_com_competencia_antiga_e_o_atraso(banco, monkeypatch):
    a, b = banco.fundo(CNPJ_A), banco.fundo(CNPJ_B)
    agosto = banco.coleta_cda(periodo="202608", inicio=INICIO_AGO)
    outubro = banco.coleta_cda()

    for ordem in (1, 2, 3):
        banco.posicao(agosto, CNPJ_I, fundo_id=a, competencia=AGOSTO, ordem=ordem)

    banco.posicao(agosto, CNPJ_J, fundo_id=b, competencia=AGOSTO)
    banco.posicao(outubro, CNPJ_J, fundo_id=b)
    criados = []
    original = leitor.CdaHoldingLink

    def contar(**campos):
        criados.append(campos["holding_id"])
        return original(**campos)

    monkeypatch.setattr(leitor, "CdaHoldingLink", contar)
    cda = ler(banco)
    detentores = por_cnpj(cda)
    assert detentores[CNPJ_A].competence == date(2026, 8, 31)
    assert len(detentores[CNPJ_A].links) == 3
    assert cda.latest_complete == OUTUBRO_DIA
    assert months_between(detentores[CNPJ_A].competence, cda.latest_complete) == 2
    assert months_between(detentores[CNPJ_B].competence, cda.latest_complete) == 0
    # So as linhas do L_H viram objeto: a linha de agosto do detentor B, nao.
    assert len(criados) == 4
