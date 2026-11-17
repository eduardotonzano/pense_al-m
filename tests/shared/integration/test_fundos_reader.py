"""Testes do leitor do banco de Fundos e dos records do cadastro (FU7.2).

Bancos sinteticos em tmp_path, com as migrations reais do modulo de Fundos
(fundos_sintetico). So CNPJs ficticios de cnpj_amostras e nomes marcados
como ficticios. Os nomes dos testes trazem o codigo do plano (L, S, P, R).
"""

import hashlib
import os
import sqlite3
from datetime import UTC, date, datetime

import pytest

from pense_alm.shared.integration.fundos_reader import (
    CadastroNotFound,
    FundosDatabaseReader,
    FundosDatabaseUnavailable,
    FundosSchemaError,
    build_read_only_uri,
)
from pense_alm.shared.integration.fundos_records import (
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara
from .fundos_sintetico import (
    MEMBRO_CLASSE,
    MEMBRO_FUNDO,
    NORMAL,
    TIPO_CLASSE_FIAGRO,
    TIPO_CLASSE_FIDC,
    BancoFundos,
    criar_banco,
)


CNPJ_1 = cnpj_ficticio(1)
CNPJ_2 = cnpj_ficticio(2)
CNPJ_3 = cnpj_ficticio(3)
CNPJ_4 = cnpj_ficticio(4)
CNPJ_5 = cnpj_ficticio(5)
CNPJ_6 = cnpj_ficticio(6)
CNPJ_7 = cnpj_ficticio(7)
CNPJ_ALFA_1 = cnpj_ficticio(1, alfanumerico=True)
CNPJ_ALFA_2 = cnpj_ficticio(2, alfanumerico=True)

FUND_NAME = "registro_fundo.Denominacao_Social"
FUND_SITUATION = "registro_fundo.Situacao"
ANTIGA = "2026-09-30"
INICIO_ANTIGO = "2026-09-30T12:00:00.000000+00:00"


@pytest.fixture
def banco(tmp_path):
    return BancoFundos(criar_banco(tmp_path))


def ler(banco):
    return FundosDatabaseReader(banco.caminho).read_cadastro()


def contar(caminho, tabela):
    conexao = sqlite3.connect(caminho)

    try:
        return conexao.execute("SELECT COUNT(*) FROM " + tabela).fetchone()[0]
    finally:
        conexao.close()


def assinatura(caminho):
    """SHA-256 do arquivo e os arquivos com o mesmo prefixo na pasta."""

    return (
        hashlib.sha256(caminho.read_bytes()).hexdigest(),
        sorted(
            nome
            for nome in os.listdir(caminho.parent)
            if nome.startswith(caminho.name)
        ),
    )


def cadastro_minimo(banco):
    coleta = banco.coleta()
    banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO 1")
    return coleta


def exige_banco_livre(caminho):
    """Nenhuma trava ficou para tras: outra conexao consegue exclusividade."""

    outra = sqlite3.connect(caminho, timeout=0, isolation_level=None)

    try:
        outra.execute("BEGIN EXCLUSIVE")
        outra.execute("ROLLBACK")
    finally:
        outra.close()


# --- Abertura so de leitura (L1 a L7, L10, L11, P13) ---


@pytest.mark.skipif(os.name != "nt", reason="caminho no estilo do Windows")
def test_l5_uri_de_caminho_windows_tem_o_formato_exato():
    uri = build_read_only_uri(r"C:\pasta com espaço\a#b%c?d.db")

    assert uri == "file:///C:/pasta%20com%20espa%C3%A7o/a%23b%25c%3Fd.db?mode=ro"
    assert not uri.startswith("file://C:")


# No Windows, um caminho que comeca com "/" e completado com a pasta atual,
# que pode ser de rede; por isso o equivalente POSIX so roda fora do Windows.
@pytest.mark.skipif(os.name == "nt", reason="caminho no estilo POSIX")
def test_l5_uri_de_caminho_posix_tem_o_formato_exato():
    uri = build_read_only_uri("/tmp/pasta com espaço/a#b%c?d.db")

    assert uri == "file:///tmp/pasta%20com%20espa%C3%A7o/a%23b%25c%3Fd.db?mode=ro"


def test_l5_leitor_abre_pasta_com_espaco_acento_cerquilha_e_porcento(tmp_path):
    pasta = tmp_path / "pasta com espaço ç #1 %2"
    pasta.mkdir()
    banco = BancoFundos(criar_banco(pasta))
    cadastro_minimo(banco)

    snapshot = ler(banco)

    assert snapshot.funds_read == 1
    assert build_read_only_uri(banco.caminho).startswith("file:///")


@pytest.mark.parametrize(
    "caminho",
    [r"\\servidor\pasta\fundos.db", "//servidor/pasta/fundos.db"],
)
def test_l10_caminho_de_rede_e_recusado_sem_tocar_na_rede(caminho):
    with pytest.raises(FundosDatabaseUnavailable) as na_uri:
        build_read_only_uri(caminho)

    with pytest.raises(FundosDatabaseUnavailable) as no_leitor:
        FundosDatabaseReader(caminho).read_cadastro()

    for erro in (na_uri, no_leitor):
        assert "disco local" in str(erro.value)
        assert "servidor" not in str(erro.value)


def test_l1_conexao_do_leitor_nao_grava_nem_com_query_only_desligado(banco):
    cadastro_minimo(banco)

    with FundosDatabaseReader(banco.caminho).session() as conexao:
        with pytest.raises(sqlite3.OperationalError):
            conexao.execute("INSERT INTO funds (cnpj) VALUES (?)", (CNPJ_2,))

        conexao.execute("PRAGMA query_only = OFF")

        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conexao.execute("INSERT INTO funds (cnpj) VALUES (?)", (CNPJ_2,))

    assert contar(banco.caminho, "funds") == 1


def test_l2_p13_sessao_liga_query_only_e_le_dentro_de_transacao(banco):
    cadastro_minimo(banco)

    with FundosDatabaseReader(banco.caminho).session() as conexao:
        assert conexao.execute("PRAGMA query_only").fetchone()[0] == 1

        # fetchall termina a consulta: fora de uma transacao, a trava de
        # leitura seria solta aqui.
        conexao.execute("SELECT COUNT(*) FROM funds").fetchall()

        assert conexao.in_transaction

        # A leitura segura a trava de leitura ate o fim da transacao.
        outra = sqlite3.connect(banco.caminho, timeout=0, isolation_level=None)

        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                outra.execute("BEGIN EXCLUSIVE")
        finally:
            outra.close()

    with pytest.raises(sqlite3.ProgrammingError):
        conexao.execute("SELECT 1")

    exige_banco_livre(banco.caminho)


def test_p13_sessao_fecha_a_transacao_mesmo_com_erro(banco):
    cadastro_minimo(banco)

    with pytest.raises(RuntimeError):
        with FundosDatabaseReader(banco.caminho).session() as conexao:
            conexao.execute("SELECT COUNT(*) FROM funds").fetchone()
            raise RuntimeError("falha de teste")

    exige_banco_livre(banco.caminho)


def test_l3_leitura_nao_altera_o_arquivo_nem_deixa_diario(banco):
    cadastro_minimo(banco)
    antes = assinatura(banco.caminho)

    ler(banco)

    depois = assinatura(banco.caminho)

    assert depois == antes
    assert depois[1] == [banco.caminho.name]


def test_l4_caminho_inexistente_da_erro_e_nao_cria_arquivo(tmp_path):
    caminho = tmp_path / "sem_banco" / "fundos.db"

    with pytest.raises(FundosDatabaseUnavailable) as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert not caminho.exists()
    assert not caminho.parent.exists()
    assert str(tmp_path) not in str(erro.value)
    assert "fundos.db" not in str(erro.value)


def test_l6_banco_em_wal_e_recusado_sem_deixar_arquivos(tmp_path):
    caminho = criar_banco(tmp_path)
    conexao = sqlite3.connect(caminho)

    try:
        assert conexao.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    finally:
        conexao.close()

    cabecalho = caminho.read_bytes()[:100]

    assert (cabecalho[18], cabecalho[19]) == (2, 2)

    antes = assinatura(caminho)

    with pytest.raises(FundosDatabaseUnavailable, match="WAL") as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert str(tmp_path) not in str(erro.value)
    assert caminho.name not in str(erro.value)
    assert assinatura(caminho) == antes
    assert antes[1] == [caminho.name]


def test_l6_arquivo_curto_e_recusado(tmp_path):
    caminho = tmp_path / "fundos.db"
    caminho.write_bytes(b"SQLite format 3\x00")

    with pytest.raises(
        FundosDatabaseUnavailable,
        match="nao e um banco SQLite",
    ) as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert str(tmp_path) not in str(erro.value)
    assert caminho.name not in str(erro.value)


def test_l6_arquivo_que_nao_e_sqlite_e_recusado(tmp_path):
    caminho = tmp_path / "fundos.db"
    caminho.write_bytes(b"x" * 200)

    with pytest.raises(
        FundosDatabaseUnavailable,
        match="nao e um banco SQLite",
    ) as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert str(tmp_path) not in str(erro.value)
    assert caminho.name not in str(erro.value)


def test_l6_versao_de_arquivo_desconhecida_e_recusada(tmp_path):
    original = criar_banco(tmp_path)
    conteudo = bytearray(original.read_bytes())
    conteudo[18] = 3
    conteudo[19] = 3
    caminho = tmp_path / "versao.db"
    caminho.write_bytes(bytes(conteudo))

    with pytest.raises(FundosDatabaseUnavailable, match="nao reconhecida") as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert str(tmp_path) not in str(erro.value)
    assert caminho.name not in str(erro.value)


def test_l7_banco_sem_a_migration_002_e_recusado(tmp_path):
    caminho = criar_banco(tmp_path, versoes=(1,))

    with pytest.raises(FundosSchemaError, match="002") as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert str(tmp_path) not in str(erro.value)
    assert caminho.name not in str(erro.value)


def test_l7_banco_sem_schema_migrations_e_recusado(tmp_path):
    caminho = tmp_path / "outro.db"
    conexao = sqlite3.connect(caminho)

    try:
        conexao.execute("CREATE TABLE qualquer (valor TEXT)")
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(FundosSchemaError, match="schema_migrations") as erro:
        FundosDatabaseReader(caminho).read_cadastro()

    assert str(tmp_path) not in str(erro.value)
    assert caminho.name not in str(erro.value)


@pytest.mark.parametrize(
    "texto",
    [
        com_mascara(CNPJ_1),
        cnpj_ficticio(1, alfanumerico=True).lower(),
    ],
)
def test_l11_check_do_banco_recusa_cnpj_com_mascara_ou_minuscula(banco, texto):
    with pytest.raises(sqlite3.IntegrityError):
        banco.fundo(texto)


def test_banco_sem_cadastro_carregado_da_cadastro_nao_encontrado(banco):
    with pytest.raises(CadastroNotFound):
        ler(banco)


# --- Retrato do cadastro (S1 a S5, P10) ---


def test_s1_vale_a_competencia_mais_recente(banco):
    antiga = banco.coleta(inicio=INICIO_ANTIGO)
    nova = banco.coleta()
    fundo = banco.fundo_do_cadastro(
        antiga,
        CNPJ_1,
        nome="FUNDO FICTÍCIO ANTIGO",
        competencia=ANTIGA,
    )
    banco.fundo_do_cadastro(
        nova,
        CNPJ_1,
        nome="FUNDO FICTÍCIO NOVO",
        fundo_id=fundo,
    )

    snapshot = ler(banco)

    assert snapshot.reference_date == date(2026, 10, 27)
    assert snapshot.collection_run_id == nova
    assert snapshot.complete is True
    assert snapshot.started_at == datetime(2026, 10, 27, 12, tzinfo=UTC)

    (assunto,) = snapshot.subjects

    assert assunto.names == ("FUNDO FICTÍCIO NOVO",)


@pytest.mark.parametrize(
    "opcoes",
    [
        {"status": "partial"},
        {"status": "failed"},
        {"pendentes": (MEMBRO_CLASSE,)},
        {"sem_linhas": (MEMBRO_FUNDO,)},
        {"membros": (MEMBRO_FUNDO,)},
        {"fonte": "MANUAL"},
    ],
)
def test_s2_coleta_incompleta_marca_o_retrato_como_incompleto(banco, opcoes):
    coleta = banco.coleta(**opcoes)
    banco.fundo_do_cadastro(coleta, CNPJ_1)

    snapshot = ler(banco)

    assert snapshot.complete is False
    assert snapshot.collection_run_id == coleta


def test_p10_vale_a_coleta_completa_mais_recente_que_gravou_r(banco):
    completa = banco.coleta(inicio="2026-10-27T10:00:00.000000+00:00")
    incompleta = banco.coleta(
        status="partial",
        inicio="2026-10-27T11:00:00.000000+00:00",
    )
    fundo = banco.fundo_do_cadastro(completa, CNPJ_1)
    banco.fundo_do_cadastro(incompleta, CNPJ_1, fundo_id=fundo)

    snapshot = ler(banco)

    assert snapshot.collection_run_id == completa
    assert snapshot.complete is True


def test_p10_sem_coleta_completa_vale_a_mais_recente_que_gravou_r(banco):
    antiga = banco.coleta(
        status="partial",
        inicio="2026-10-27T10:00:00.000000+00:00",
    )
    nova = banco.coleta(
        status="partial",
        inicio="2026-10-27T11:00:00.000000+00:00",
    )
    fundo = banco.fundo_do_cadastro(antiga, CNPJ_1)
    banco.fundo_do_cadastro(nova, CNPJ_1, fundo_id=fundo)

    snapshot = ler(banco)

    assert snapshot.collection_run_id == nova
    assert snapshot.complete is False


def test_p10_coleta_que_nao_gravou_r_nao_conta(banco):
    completa = banco.coleta()
    posterior = banco.coleta(inicio="2026-10-28T12:00:00.000000+00:00")
    fundo = banco.fundo_do_cadastro(completa, CNPJ_1)
    banco.observacao(
        posterior,
        FUND_NAME,
        "FUNDO FICTÍCIO ANTIGO",
        fundo=fundo,
        competencia=ANTIGA,
    )

    assert ler(banco).collection_run_id == completa


def test_s3_papel_gravado_por_informe_nao_vira_prestadora(banco):
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1)
    classe = banco.classe_do_cadastro(coleta, CNPJ_1, fundo)
    banco.administrador(coleta, fundo, CNPJ_5)
    banco.papel(
        coleta,
        "administrador",
        "tab_I.CNPJ_ADMIN",
        CNPJ_6,
        fundo=fundo,
        campo_nome="tab_I.NM_ADMIN",
        nome="PRESTADORA FICTÍCIA DO INFORME",
    )
    banco.papel(
        coleta,
        "gestor",
        "inf_mensal_fiagro.CNPJ_Gestor",
        CNPJ_7,
        classe=classe,
        campo_nome="inf_mensal_fiagro.Nome_Gestor",
        nome="PRESTADORA FICTÍCIA DO INFORME",
    )

    (assunto,) = ler(banco).subjects

    assert [(link.role, link.cnpj) for link in assunto.parties] == [
        ("administrador", CNPJ_5),
    ]


def test_s4_agrupamento_por_cnpj_do_d6(banco):
    coleta = banco.coleta()
    fundo_a = banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO A")
    classe_a = banco.classe_do_cadastro(
        coleta,
        CNPJ_1,
        fundo_a,
        nome="CLASSE FICTÍCIA A",
    )
    fundo_b = banco.fundo_do_cadastro(coleta, CNPJ_2, nome="FUNDO FICTÍCIO B")
    banco.fundo_do_cadastro(
        coleta,
        CNPJ_3,
        nome="FUNDO FICTÍCIO C",
        tipo="FIAGRO",
    )
    classe_de_b_com_cnpj_de_c = banco.classe_do_cadastro(
        coleta,
        CNPJ_3,
        fundo_b,
        tipo=TIPO_CLASSE_FIAGRO,
    )
    classe_so_classe = banco.classe_do_cadastro(
        coleta,
        CNPJ_4,
        fundo_b,
        nome="CLASSE FICTÍCIA D",
    )
    banco.administrador(coleta, fundo_a, CNPJ_5)
    banco.gestor(coleta, fundo_a, CNPJ_6)
    banco.custodiante(coleta, classe_a, CNPJ_7)
    banco.administrador(coleta, fundo_b, CNPJ_5)
    banco.custodiante(coleta, classe_de_b_com_cnpj_de_c, CNPJ_ALFA_1)
    banco.custodiante(coleta, classe_so_classe, CNPJ_ALFA_2)

    snapshot = ler(banco)

    assert (
        snapshot.funds_in_table,
        snapshot.classes_in_table,
        snapshot.funds_read,
        snapshot.classes_read,
    ) == (3, 3, 3, 3)
    assert (
        snapshot.classes_same_cnpj,
        snapshot.classes_other_fund_cnpj,
        snapshot.classes_only_class,
        snapshot.classes_of_fund_without_data,
    ) == (1, 1, 1, 0)

    por_cnpj = {assunto.cnpj: assunto for assunto in snapshot.subjects}

    assert set(por_cnpj) == {CNPJ_1, CNPJ_2, CNPJ_3, CNPJ_4}

    def papeis(cnpj):
        return [(link.role, link.cnpj) for link in por_cnpj[cnpj].parties]

    grupo_a = por_cnpj[CNPJ_1]

    assert (grupo_a.source_table, grupo_a.source_id) == ("funds", fundo_a)
    assert grupo_a.names == ("FUNDO FICTÍCIO A",)
    assert grupo_a.tipos_classe == (TIPO_CLASSE_FIDC,)
    assert papeis(CNPJ_1) == [
        ("administrador", CNPJ_5),
        ("custodiante", CNPJ_7),
        ("gestor", CNPJ_6),
    ]

    assert por_cnpj[CNPJ_2].tipos_classe == ()
    assert papeis(CNPJ_2) == [("administrador", CNPJ_5)]

    assert por_cnpj[CNPJ_3].tipos_fundo == ("FIAGRO",)
    assert por_cnpj[CNPJ_3].tipos_classe == (TIPO_CLASSE_FIAGRO,)
    assert papeis(CNPJ_3) == [("custodiante", CNPJ_ALFA_1)]

    grupo_d = por_cnpj[CNPJ_4]

    assert (grupo_d.source_table, grupo_d.source_id) == (
        "fund_classes",
        classe_so_classe,
    )
    assert grupo_d.names == ("CLASSE FICTÍCIA D",)
    assert grupo_d.tipos_fundo == ()
    assert grupo_d.tipos_pessoa_gestor == ()
    assert papeis(CNPJ_4) == [("custodiante", CNPJ_ALFA_2)]


def test_s5_dados_de_outra_competencia_sao_ignorados(banco):
    antiga = banco.coleta(inicio=INICIO_ANTIGO)
    nova = banco.coleta()
    fundo = banco.fundo_do_cadastro(nova, CNPJ_1, nome="FUNDO FICTÍCIO R")
    banco.observacao(
        antiga,
        FUND_NAME,
        "FUNDO FICTÍCIO ANTIGO",
        fundo=fundo,
        competencia=ANTIGA,
    )
    banco.observacao(
        antiga,
        FUND_SITUATION,
        "Cancelado",
        fundo=fundo,
        competencia=ANTIGA,
    )
    banco.administrador(antiga, fundo, CNPJ_5, competencia=ANTIGA)

    (assunto,) = ler(banco).subjects

    assert assunto.names == ("FUNDO FICTÍCIO R",)
    assert assunto.situacoes == (NORMAL,)
    assert assunto.parties == ()


def test_fundo_e_classe_sem_dado_na_competencia_ficam_contados(banco):
    antiga = banco.coleta(inicio=INICIO_ANTIGO)
    nova = banco.coleta()
    fundo_lido = banco.fundo_do_cadastro(nova, CNPJ_1)
    banco.fundo_do_cadastro(antiga, CNPJ_2, competencia=ANTIGA)
    banco.classe_do_cadastro(antiga, CNPJ_3, fundo_lido, competencia=ANTIGA)

    snapshot = ler(banco)

    assert (snapshot.funds_in_table, snapshot.funds_read) == (2, 1)
    assert snapshot.funds_without_data == 1
    assert (snapshot.classes_in_table, snapshot.classes_read) == (1, 0)
    assert snapshot.classes_without_data == 1
    assert [assunto.cnpj for assunto in snapshot.subjects] == [CNPJ_1]


def test_classe_com_cnpj_de_fundo_sem_dado_nao_abre_grupo(banco):
    antiga = banco.coleta(inicio=INICIO_ANTIGO)
    nova = banco.coleta()
    banco.fundo_do_cadastro(antiga, CNPJ_1, competencia=ANTIGA)
    outro = banco.fundo_do_cadastro(nova, CNPJ_2)
    classe = banco.classe_do_cadastro(nova, CNPJ_1, outro)
    banco.custodiante(nova, classe, CNPJ_5)

    snapshot = ler(banco)

    assert snapshot.classes_read == 1
    assert snapshot.classes_of_fund_without_data == 1
    assert (
        snapshot.classes_same_cnpj,
        snapshot.classes_other_fund_cnpj,
        snapshot.classes_only_class,
    ) == (0, 0, 0)

    (assunto,) = snapshot.subjects

    assert assunto.cnpj == CNPJ_2
    assert assunto.parties == ()


def test_valores_distintos_da_competencia_ficam_todos_em_ordem(banco):
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO B")
    banco.observacao(coleta, FUND_NAME, "FUNDO FICTÍCIO A", fundo=fundo)
    banco.observacao(coleta, FUND_NAME, "FUNDO FICTÍCIO B", fundo=fundo)
    banco.observacao(coleta, FUND_SITUATION, "Em Liquidação", fundo=fundo)

    (assunto,) = ler(banco).subjects

    assert assunto.names == ("FUNDO FICTÍCIO A", "FUNDO FICTÍCIO B")
    assert assunto.situacoes == (NORMAL, "Em Liquidação")


def test_valor_em_branco_conta_como_ausente_sem_derrubar_a_leitura(banco):
    coleta = banco.coleta()
    # Todas as observacoes do fundo em R estao em branco. O CHECK do banco
    # usa o trim do SQLite, que so tira espacos: tabulacao e espaco nao
    # separavel passam.
    fundo = banco.fundo_do_cadastro(
        coleta,
        CNPJ_1,
        nome="\t",
        situacao="\xa0",
        tipo="\t\n",
        tipo_pessoa=" \t ",
    )
    classe = banco.classe_do_cadastro(coleta, CNPJ_2, fundo, nome="\xa0")
    banco.administrador(coleta, fundo, CNPJ_5, nome="\t")
    banco.custodiante(coleta, classe, CNPJ_6, nome="\xa0\xa0")

    # So espacos comuns nem entram no banco: por isso o teste usa os outros.
    with pytest.raises(sqlite3.IntegrityError):
        banco.observacao(coleta, FUND_NAME, "   ", fundo=fundo)

    with pytest.raises(sqlite3.IntegrityError):
        banco.administrador(coleta, fundo, CNPJ_7, nome="   ")

    snapshot = ler(banco)

    # O fundo continua lido (tem observacao em R) e as somas fecham.
    assert (snapshot.funds_in_table, snapshot.funds_read) == (1, 1)
    assert snapshot.funds_without_data == 0
    assert (snapshot.classes_in_table, snapshot.classes_read) == (1, 1)
    assert snapshot.classes_only_class == 1
    assert snapshot.classes_read == (
        snapshot.classes_same_cnpj
        + snapshot.classes_other_fund_cnpj
        + snapshot.classes_only_class
        + snapshot.classes_of_fund_without_data
    )
    assert len(snapshot.subjects) == (
        snapshot.funds_read + snapshot.classes_only_class
    )

    por_cnpj = {assunto.cnpj: assunto for assunto in snapshot.subjects}
    grupo_fundo = por_cnpj[CNPJ_1]

    assert grupo_fundo.names == ()
    assert grupo_fundo.situacoes == ()
    assert grupo_fundo.tipos_fundo == ()
    assert grupo_fundo.tipos_pessoa_gestor == ()
    assert [
        (link.role, link.cnpj, link.name) for link in grupo_fundo.parties
    ] == [("administrador", CNPJ_5, None)]

    grupo_classe = por_cnpj[CNPJ_2]

    assert grupo_classe.names == ()
    assert grupo_classe.situacoes == (NORMAL,)
    assert grupo_classe.tipos_classe == (TIPO_CLASSE_FIDC,)
    assert [
        (link.role, link.cnpj, link.name) for link in grupo_classe.parties
    ] == [("custodiante", CNPJ_6, None)]


# --- Records (R3 e validacao) ---


def test_r3_repr_dos_records_nao_mostra_cnpj_nem_nome(banco):
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO R3")
    banco.administrador(coleta, fundo, CNPJ_5, nome="PRESTADORA FICTÍCIA R3")

    snapshot = ler(banco)
    (assunto,) = snapshot.subjects
    (papel,) = assunto.parties

    for objeto in (snapshot, assunto, papel):
        texto = repr(objeto)

        for proibido in (
            CNPJ_1,
            CNPJ_5,
            com_mascara(CNPJ_1),
            "FUNDO FICTÍCIO R3",
            "PRESTADORA FICTÍCIA R3",
        ):
            assert proibido not in texto

    assert "administrador" in repr(papel)
    assert "situacoes" in repr(assunto)


def criar_papel(**muda):
    valores = {
        "role": "gestor",
        "cnpj": CNPJ_1,
        "name": "PRESTADORA FICTÍCIA",
        "party_observation_id": 1,
    }
    valores.update(muda)
    return FundosPartyLink(**valores)


def criar_assunto(**muda):
    valores = {
        "cnpj": CNPJ_2,
        "source_table": "funds",
        "source_id": 1,
        "names": ("FUNDO FICTÍCIO",),
        "situacoes": (NORMAL,),
        "tipos_fundo": ("FIDC",),
        "tipos_classe": (),
        "tipos_pessoa_gestor": ("PJ",),
        "parties": (),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def criar_retrato(**muda):
    valores = {
        "reference_date": date(2026, 10, 27),
        "collection_run_id": 1,
        "started_at": datetime(2026, 10, 27, 12, tzinfo=UTC),
        "complete": True,
        "funds_in_table": 1,
        "classes_in_table": 0,
        "funds_read": 1,
        "classes_read": 0,
        "classes_same_cnpj": 0,
        "classes_other_fund_cnpj": 0,
        "classes_only_class": 0,
        "classes_of_fund_without_data": 0,
        "subjects": (criar_assunto(),),
    }
    valores.update(muda)
    return CadastroSnapshot(**valores)


def test_records_validos_viram_tuplas():
    retrato = criar_retrato(subjects=[criar_assunto(parties=[criar_papel()])])

    assert isinstance(retrato.subjects, tuple)
    assert isinstance(retrato.subjects[0].parties, tuple)


@pytest.mark.parametrize(
    ("muda", "erro"),
    [
        ({"role": "auditor"}, ValueError),
        ({"cnpj": " "}, ValueError),
        ({"name": ""}, ValueError),
        ({"party_observation_id": True}, TypeError),
        ({"party_observation_id": 0}, ValueError),
    ],
)
def test_record_de_papel_recusa_valor_invalido(muda, erro):
    with pytest.raises(erro):
        criar_papel(**muda)


@pytest.mark.parametrize(
    ("muda", "erro"),
    [
        ({"source_table": "observations"}, ValueError),
        ({"source_id": 0}, ValueError),
        ({"names": "FUNDO FICTÍCIO"}, TypeError),
        ({"names": ("FUNDO FICTÍCIO", "FUNDO FICTÍCIO")}, ValueError),
        ({"situacoes": ("",)}, ValueError),
        ({"parties": ("papel",)}, TypeError),
        (
            {
                "source_table": "fund_classes",
                "tipos_fundo": ("FIDC",),
                "tipos_pessoa_gestor": (),
            },
            ValueError,
        ),
        (
            {
                "source_table": "fund_classes",
                "tipos_fundo": (),
                "tipos_pessoa_gestor": (),
                "parties": (criar_papel(role="administrador"),),
            },
            ValueError,
        ),
    ],
)
def test_record_de_assunto_recusa_valor_invalido(muda, erro):
    with pytest.raises(erro):
        criar_assunto(**muda)


@pytest.mark.parametrize(
    ("muda", "erro"),
    [
        ({"reference_date": datetime(2026, 10, 27, tzinfo=UTC)}, TypeError),
        ({"started_at": datetime(2026, 10, 27, 12)}, ValueError),
        ({"complete": 1}, TypeError),
        ({"funds_read": -1}, ValueError),
        ({"funds_read": True}, TypeError),
        ({"funds_in_table": 0}, ValueError),
        ({"classes_read": 1, "classes_in_table": 1}, ValueError),
        ({"funds_read": 2, "funds_in_table": 2}, ValueError),
        (
            {
                "subjects": (criar_assunto(), criar_assunto()),
                "funds_read": 2,
                "funds_in_table": 2,
            },
            ValueError,
        ),
    ],
)
def test_record_de_retrato_recusa_valor_invalido(muda, erro):
    with pytest.raises(erro):
        criar_retrato(**muda)
