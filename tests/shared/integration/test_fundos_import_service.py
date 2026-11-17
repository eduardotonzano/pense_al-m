"""Testes do servico de importacao de Fundos (FU7.2, fases 1 e 2).

O destino e um SQLite da camada em tmp_path. O retrato vem do banco de
Fundos sintetico, lido pelo leitor, ou de records montados direto (casos
que o CHECK do banco nao deixa gravar). So CNPJs ficticios de cnpj_amostras
e nomes marcados como ficticios. Os nomes dos testes trazem o codigo do
plano (E, N, T, P, S, R).
"""

from datetime import UTC, date, datetime

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityIdentifier,
    EntityStatus,
    EntityType,
    IdentifierType,
    SourceType,
)
from pense_alm.shared.integration.fundos_adapter import NORMAL, FundosAdapter
from pense_alm.shared.integration.fundos_import_service import FundosImportService
from pense_alm.shared.integration.fundos_reader import FundosDatabaseReader
from pense_alm.shared.integration.fundos_records import (
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara, dv_errado
from .fundos_sintetico import (
    TIPO_CLASSE_FIAGRO,
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
INICIO = datetime(2026, 10, 27, 12, tzinfo=UTC)
FASE_PRE = "Fase Pr\xe9-Operacional"

adaptador = FundosAdapter()


class Espiao:
    """Repositorio que registra cada save e repassa ao SQLite."""

    def __init__(self, repositorio, falha_no_save=()):
        self._repositorio = repositorio
        self._falha_no_save = set(falha_no_save)
        self.salvas = []

    def get_by_identifier(self, identifier_type, value):
        return self._repositorio.get_by_identifier(identifier_type, value)

    def get_by_id(self, entity_id):
        return self._repositorio.get_by_id(entity_id)

    def save(self, entity):
        self.salvas.append(entity.entity_id)

        if entity.entity_id in self._falha_no_save:
            raise RuntimeError("falha ficticia ao gravar " + entity.cnpj)

        return self._repositorio.save(entity)


class RepositorioQueFalhaNaBusca:
    """Repositorio cuja busca pelo CNPJ falha (falha sistemica do destino)."""

    def get_by_identifier(self, identifier_type, value):
        raise RuntimeError("falha ficticia de leitura do destino")

    def get_by_id(self, entity_id):
        raise AssertionError("nao deveria chegar aqui")

    def save(self, entity):
        raise AssertionError("nao deveria gravar")


@pytest.fixture
def destino(tmp_path):
    manager = SQLiteConnectionManager(tmp_path / "destino" / "camada.sqlite3")
    return manager, SQLiteEntityRepository(manager)


@pytest.fixture
def banco(tmp_path):
    return BancoFundos(criar_banco(tmp_path))


def ler(banco):
    return FundosDatabaseReader(banco.caminho).read_cadastro()


def importar(repositorio, snapshot):
    return FundosImportService(repositorio).import_entities(snapshot)


def proveniencia_manual():
    return DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste ficticio",
        collected_at=INICIO,
    )


def entidade_existente(cnpj, entity_type=EntityType.COMPANY, **muda):
    proveniencia = proveniencia_manual()
    valores = {
        "legal_name": "EMPRESA FICTÍCIA",
        "entity_type": entity_type,
        "status": EntityStatus.INACTIVE,
        "provenance": proveniencia,
        "identifiers": (
            EntityIdentifier(
                identifier_type=IdentifierType.CNPJ,
                value=cnpj,
                provenance=proveniencia,
                is_primary=True,
            ),
        ),
        "created_at": INICIO,
        "updated_at": INICIO,
    }
    valores.update(muda)
    return Entity(**valores)


def linhas_da_entidade(manager, entity_id):
    with manager.read_connection() as conexao:
        entidade = conexao.execute(
            "SELECT * FROM entities WHERE entity_id = ?",
            (str(entity_id),),
        ).fetchall()
        identificadores = conexao.execute(
            "SELECT * FROM entity_identifiers WHERE entity_id = ? ORDER BY identifier_id",
            (str(entity_id),),
        ).fetchall()

    return [tuple(linha) for linha in entidade], [
        tuple(linha) for linha in identificadores
    ]


def assunto(cnpj, source_id, **muda):
    valores = {
        "cnpj": cnpj,
        "source_table": "funds",
        "source_id": source_id,
        "names": ("FUNDO FICTÍCIO " + str(source_id),),
        "situacoes": (NORMAL,),
        "tipos_fundo": ("FIDC",),
        "tipos_classe": (),
        "tipos_pessoa_gestor": ("PJ",),
        "parties": (),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def assunto_classe(cnpj, source_id, **muda):
    valores = {
        "cnpj": cnpj,
        "source_table": "fund_classes",
        "source_id": source_id,
        "names": ("CLASSE FICTÍCIA " + str(source_id),),
        "situacoes": (NORMAL,),
        "tipos_fundo": (),
        "tipos_classe": ("Classes de Cotas de Fundos FIDC",),
        "tipos_pessoa_gestor": (),
        "parties": (),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def papel(cnpj, party_observation_id, nome="PRESTADORA FICTÍCIA", role="administrador"):
    return FundosPartyLink(
        role=role,
        cnpj=cnpj,
        name=nome,
        party_observation_id=party_observation_id,
    )


def retrato(*assuntos):
    fundos = sum(1 for item in assuntos if item.source_table == "funds")
    classes = len(assuntos) - fundos
    return CadastroSnapshot(
        reference_date=date(2026, 10, 27),
        collection_run_id=1,
        started_at=INICIO,
        complete=True,
        funds_in_table=fundos,
        classes_in_table=classes,
        funds_read=fundos,
        classes_read=classes,
        classes_same_cnpj=0,
        classes_other_fund_cnpj=0,
        classes_only_class=classes,
        classes_of_fund_without_data=0,
        subjects=assuntos,
    )


# --- Cenario completo, do banco de Fundos ao relatorio ---


def test_cenario_completo_leitor_e_servico(banco, destino):
    manager, repositorio = destino
    coleta = banco.coleta()
    fundo_a = banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO A")
    classe_a = banco.classe_do_cadastro(coleta, CNPJ_1, fundo_a)
    banco.administrador(coleta, fundo_a, CNPJ_5, nome="ADMINISTRADORA FICTÍCIA")
    banco.gestor(coleta, fundo_a, CNPJ_6, nome="GESTORA FICTÍCIA")
    banco.custodiante(coleta, classe_a, CNPJ_7, nome="CUSTODIANTE FICTÍCIA")
    fundo_b = banco.fundo_do_cadastro(
        coleta,
        CNPJ_2,
        nome="FUNDO FICTÍCIO B",
        tipo="FIAGRO",
        tipo_pessoa="PF",
    )
    banco.administrador(coleta, fundo_b, CNPJ_5, nome="ADMINISTRADORA FICTÍCIA")
    fundo_c = banco.fundo_do_cadastro(
        coleta,
        CNPJ_3,
        nome="FUNDO FICTÍCIO C",
        situacao="Cancelado",
    )
    banco.administrador(coleta, fundo_c, CNPJ_ALFA_1, nome="SO DO BACKLOG FICTÍCIA")
    classe_d = banco.classe_do_cadastro(coleta, CNPJ_4, fundo_c, nome="CLASSE FICTÍCIA D")
    banco.custodiante(coleta, classe_d, CNPJ_ALFA_2, nome="CUSTODIANTE FICTÍCIA D")

    fase = importar(repositorio, ler(banco))
    report = fase.report

    assert (report.fundos_na_tabela, report.fundos_lidos) == (3, 3)
    assert (report.classes_na_tabela, report.classes_lidas) == (2, 2)
    assert (report.classes_unidas_ao_fundo, report.classes_so_como_classe) == (1, 1)
    assert report.cnpjs_lidos == 4
    assert report.gestor_pessoa_fisica == 1
    assert report.em_funcionamento_normal == 3
    assert report.backlog.cancelado == 1
    assert report.fundos_criados == 3
    assert report.fundos_nao_criados.total == 0
    assert report.prestadoras_candidatas == 4
    assert report.prestadoras_ligadas == 4
    assert report.prestadoras_criadas == 4
    assert report.erros == ()

    assert set(fase.funds) == {CNPJ_1, CNPJ_2, CNPJ_4}
    assert set(fase.providers) == {CNPJ_5, CNPJ_6, CNPJ_7, CNPJ_ALFA_2}
    assert fase.funds[CNPJ_1].entity_type is EntityType.FIDC
    assert fase.funds[CNPJ_2].entity_type is EntityType.FIAGRO
    assert fase.funds[CNPJ_4].entity_type is EntityType.FIDC
    assert all(
        entidade.entity_type is EntityType.FINANCIAL_INSTITUTION
        and entidade.status is EntityStatus.UNKNOWN
        for entidade in fase.providers.values()
    )
    assert repositorio.count() == 7

    # Nenhuma relacao e gravada no B1.
    assert SQLiteRelationshipRepository(manager).count() == 0


# --- E: entidade existente nunca e regravada ---


def test_e1_e2_entidade_existente_e_reutilizada_sem_save_e_sem_mudanca(banco, destino):
    manager, repositorio = destino
    existente = entidade_existente(CNPJ_1)
    repositorio.save(existente)
    antes = linhas_da_entidade(manager, existente.entity_id)
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1)
    banco.administrador(coleta, fundo, CNPJ_5)
    espiao = Espiao(repositorio)

    fase = importar(espiao, ler(banco))

    assert existente.entity_id not in espiao.salvas
    assert espiao.salvas == [adaptador.entity_id(CNPJ_5)]
    assert fase.report.fundos_reutilizados == 1
    assert fase.report.fundos_criados == 0
    assert fase.funds[CNPJ_1].entity_id == existente.entity_id
    assert fase.funds[CNPJ_1].entity_type is EntityType.COMPANY
    assert linhas_da_entidade(manager, existente.entity_id) == antes


def test_e3_segunda_execucao_nao_faz_nenhum_save(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1)
    banco.administrador(coleta, fundo, CNPJ_5)
    snapshot = ler(banco)

    primeira = importar(repositorio, snapshot).report
    espiao = Espiao(repositorio)
    segunda = importar(espiao, snapshot).report

    assert espiao.salvas == []
    assert segunda.fundos_reutilizados == primeira.fundos_criados == 1
    assert segunda.prestadoras_reutilizadas == primeira.prestadoras_criadas == 1
    assert repositorio.count() == 2


def test_e4_administradora_e_gestora_de_mesmo_cnpj_viram_uma_entidade(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1)
    banco.administrador(coleta, fundo, CNPJ_5)
    banco.gestor(coleta, fundo, CNPJ_5)

    fase = importar(repositorio, ler(banco))

    assert fase.report.prestadoras_candidatas == 1
    assert fase.report.prestadoras_criadas == 1
    assert fase.providers[CNPJ_5].entity_type is EntityType.FINANCIAL_INSTITUTION
    assert repositorio.count() == 2


def test_e5_id_ocupado_bloqueia_sem_gravar(destino):
    manager, repositorio = destino
    ocupante_fundo = Entity(
        entity_id=adaptador.entity_id(CNPJ_1),
        legal_name="OCUPANTE FICTÍCIO",
        entity_type=EntityType.OTHER,
        provenance=proveniencia_manual(),
        created_at=INICIO,
        updated_at=INICIO,
    )
    ocupante_prestadora = Entity(
        entity_id=adaptador.entity_id(CNPJ_6),
        legal_name="OCUPANTE FICTÍCIO",
        entity_type=EntityType.OTHER,
        provenance=proveniencia_manual(),
        created_at=INICIO,
        updated_at=INICIO,
    )
    repositorio.save(ocupante_fundo)
    repositorio.save(ocupante_prestadora)
    antes = linhas_da_entidade(manager, ocupante_fundo.entity_id)
    espiao = Espiao(repositorio)
    snapshot = retrato(
        assunto(CNPJ_1, 1, parties=(papel(CNPJ_5, 1),)),
        assunto(CNPJ_2, 2, parties=(papel(CNPJ_6, 2),)),
    )

    report = importar(espiao, snapshot).report

    assert report.fundos_nao_criados.id_ocupado == 1
    assert report.fundos_criados == 1
    assert report.prestadoras_so_de_fundo_nao_resolvido == 1
    assert report.prestadoras_nao_criadas.id_ocupado == 1
    assert ocupante_fundo.entity_id not in espiao.salvas
    assert ocupante_prestadora.entity_id not in espiao.salvas
    assert linhas_da_entidade(manager, ocupante_fundo.entity_id) == antes


# --- N: nomes e colisao ---


def test_n1_fundo_sem_nome_nao_entra_e_a_prestadora_so_dele_tambem_nao(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1, nome=None)
    banco.administrador(coleta, fundo, CNPJ_5)

    report = importar(repositorio, ler(banco)).report

    assert report.fundos_nao_criados.sem_nome == 1
    assert report.prestadoras_candidatas == 1
    assert report.prestadoras_so_de_fundo_nao_resolvido == 1
    assert report.prestadoras_ligadas == 0
    assert repositorio.count() == 0


def test_n2_fundo_com_dois_nomes_nao_entra(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO A")
    banco.observacao(
        coleta,
        "registro_fundo.Denominacao_Social",
        "FUNDO FICTÍCIO B",
        fundo=fundo,
    )

    report = importar(repositorio, ler(banco)).report

    assert report.fundos_nao_criados.nome_divergente == 1
    assert repositorio.count() == 0


def test_n3_prestadora_com_dois_nomes_nao_entra(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo_a = banco.fundo_do_cadastro(coleta, CNPJ_1)
    fundo_b = banco.fundo_do_cadastro(coleta, CNPJ_2)
    banco.administrador(coleta, fundo_a, CNPJ_5, nome="PRESTADORA FICTÍCIA")
    banco.administrador(coleta, fundo_b, CNPJ_5, nome="PRESTADORA FICTÍCIA LTDA")

    report = importar(repositorio, ler(banco)).report

    assert report.fundos_criados == 2
    assert report.prestadoras_ligadas == 1
    assert report.prestadoras_nao_criadas.nome_divergente == 1
    assert repositorio.count() == 2


def test_n4_prestadora_sem_nome_mas_ja_existente_e_reutilizada(banco, destino):
    _, repositorio = destino
    existente = entidade_existente(CNPJ_5, EntityType.FINANCIAL_INSTITUTION)
    repositorio.save(existente)
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1)
    banco.papel(
        coleta,
        "administrador",
        "registro_fundo.CNPJ_Administrador",
        CNPJ_5,
        fundo=fundo,
    )
    espiao = Espiao(repositorio)

    fase = importar(espiao, ler(banco))

    assert fase.report.prestadoras_reutilizadas == 1
    assert fase.providers[CNPJ_5].entity_id == existente.entity_id
    assert existente.entity_id not in espiao.salvas


def test_n5_colisao_de_cnpj_canonico_nao_cria_nada(destino):
    _, repositorio = destino
    espiao = Espiao(repositorio)
    snapshot = retrato(
        assunto(CNPJ_1, 1),
        assunto(com_mascara(CNPJ_1), 2),
    )

    report = importar(espiao, snapshot).report

    assert report.fundos_nao_criados.cnpj_colisao == 2
    assert espiao.salvas == []


def test_n5_duas_classes_so_como_classe_com_o_mesmo_cnpj_colidem(destino):
    _, repositorio = destino
    espiao = Espiao(repositorio)
    snapshot = retrato(
        assunto_classe(CNPJ_4, 1),
        assunto_classe(CNPJ_4, 2),
    )

    report = importar(espiao, snapshot).report

    assert report.fundos_nao_criados.cnpj_colisao == 2
    assert espiao.salvas == []


def test_cnpj_recusado_no_fundo_e_na_prestadora(destino):
    _, repositorio = destino
    snapshot = retrato(
        assunto(dv_errado(CNPJ_1), 1),
        assunto(CNPJ_2, 2, parties=(papel(dv_errado(CNPJ_5), 1),)),
    )

    report = importar(repositorio, snapshot).report

    assert report.fundos_nao_criados.cnpj_recusado == 1
    assert report.fundos_criados == 1
    assert report.prestadoras_candidatas == 1
    assert report.prestadoras_ligadas == 1
    assert report.prestadoras_nao_criadas.cnpj_recusado == 1


# --- T: tipo ---


def test_t1_par_com_tipo_divergente_nao_entra(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1, tipo="FIDC")
    banco.classe_do_cadastro(coleta, CNPJ_1, fundo, tipo=TIPO_CLASSE_FIAGRO)

    report = importar(repositorio, ler(banco)).report

    assert report.fundos_nao_criados.tipo_divergente == 1
    assert repositorio.count() == 0


def test_t2_tipo_fora_do_mapa_nao_entra(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    banco.fundo_do_cadastro(coleta, CNPJ_1, tipo="FII")

    report = importar(repositorio, ler(banco)).report

    assert report.fundos_nao_criados.tipo_fora_do_mapa == 1
    assert repositorio.count() == 0


# --- P: gestor pessoa fisica, prestadoras e backlog ---


def test_p1_gestor_pessoa_fisica_so_com_o_conjunto_exato(destino):
    _, repositorio = destino
    snapshot = retrato(
        assunto(CNPJ_1, 1, tipos_pessoa_gestor=("PF",)),
        assunto(CNPJ_2, 2, tipos_pessoa_gestor=("PF", "PJ")),
        assunto(CNPJ_3, 3, tipos_pessoa_gestor=("PJ",)),
        assunto(CNPJ_4, 4, tipos_pessoa_gestor=()),
    )

    report = importar(repositorio, snapshot).report

    assert report.gestor_pessoa_fisica == 1
    assert report.gestor_tipo_conflitante == 1
    assert report.prestadoras_candidatas == 0


def test_p6_linha_de_backlog_nao_bloqueia_a_prestadora(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    normal = banco.fundo_do_cadastro(coleta, CNPJ_1)
    cancelado = banco.fundo_do_cadastro(coleta, CNPJ_2, situacao="Cancelado")
    banco.administrador(coleta, normal, CNPJ_5, nome="PRESTADORA FICTÍCIA")
    banco.administrador(coleta, cancelado, CNPJ_5, nome="OUTRO NOME FICTÍCIO")

    fase = importar(repositorio, ler(banco))

    assert fase.report.prestadoras_nao_criadas.nome_divergente == 0
    assert fase.report.prestadoras_criadas == 1
    assert fase.providers[CNPJ_5].legal_name == "PRESTADORA FICTÍCIA"


def test_p9_candidatas_sao_ligadas_mais_so_de_fundo_nao_resolvido(destino):
    _, repositorio = destino
    snapshot = retrato(
        assunto(CNPJ_1, 1, parties=(papel(CNPJ_5, 1),)),
        assunto(CNPJ_2, 2, names=(), parties=(papel(CNPJ_6, 2),)),
    )

    report = importar(repositorio, snapshot).report

    assert report.prestadoras_candidatas == 2
    assert report.prestadoras_ligadas == 1
    assert report.prestadoras_so_de_fundo_nao_resolvido == 1


def test_p8_conta_backlog_ja_na_camada_so_se_for_fidc_ou_fiagro(destino):
    _, repositorio = destino
    repositorio.save(entidade_existente(CNPJ_1, EntityType.FIDC))
    repositorio.save(entidade_existente(CNPJ_2, EntityType.FINANCIAL_INSTITUTION))
    snapshot = retrato(
        assunto(CNPJ_1, 1, situacoes=("Cancelado",)),
        assunto(CNPJ_2, 2, situacoes=("Cancelado",)),
        assunto(CNPJ_3, 3, situacoes=("Cancelado",)),
    )
    espiao = Espiao(repositorio)

    report = importar(espiao, snapshot).report

    assert report.backlog.cancelado == 3
    assert report.fora_do_normal_ja_na_camada == 1
    assert espiao.salvas == []


def test_p8_falha_na_busca_do_backlog_propaga():
    snapshot = retrato(assunto(CNPJ_1, 1, situacoes=("Cancelado",)))

    with pytest.raises(RuntimeError, match="falha ficticia de leitura"):
        importar(RepositorioQueFalhaNaBusca(), snapshot)


class RepositorioQueFalhaNoId:
    """Repositorio cuja checagem de id falha (falha sistemica do destino)."""

    def get_by_identifier(self, identifier_type, value):
        return None

    def get_by_id(self, entity_id):
        raise RuntimeError("falha ficticia de leitura do destino")

    def save(self, entity):
        raise AssertionError("nao deveria gravar")


class RepositorioQueFalhaParaUmCnpj:
    """Repassa ao SQLite, mas a busca pelo CNPJ falha para um CNPJ so."""

    def __init__(self, repositorio, cnpj):
        self._repositorio = repositorio
        self._cnpj = cnpj

    def get_by_identifier(self, identifier_type, value):
        if value == self._cnpj:
            raise RuntimeError("falha ficticia de leitura do destino")

        return self._repositorio.get_by_identifier(identifier_type, value)

    def get_by_id(self, entity_id):
        return self._repositorio.get_by_id(entity_id)

    def save(self, entity):
        return self._repositorio.save(entity)


def test_falha_na_busca_do_fundo_normal_propaga():
    snapshot = retrato(assunto(CNPJ_1, 1))

    with pytest.raises(RuntimeError, match="falha ficticia de leitura"):
        importar(RepositorioQueFalhaNaBusca(), snapshot)


def test_falha_na_checagem_de_id_do_fundo_propaga():
    snapshot = retrato(assunto(CNPJ_1, 1))

    with pytest.raises(RuntimeError, match="falha ficticia de leitura"):
        importar(RepositorioQueFalhaNoId(), snapshot)


def test_falha_na_busca_da_prestadora_propaga(destino):
    _, repositorio = destino
    snapshot = retrato(assunto(CNPJ_1, 1, parties=(papel(CNPJ_5, 1),)))

    with pytest.raises(RuntimeError, match="falha ficticia de leitura"):
        importar(RepositorioQueFalhaParaUmCnpj(repositorio, CNPJ_5), snapshot)


class RepositorioQueFalhaNoIdDaPrestadora:
    """Busca nunca acha; a checagem de id falha so para a prestadora."""

    def __init__(self, id_da_prestadora):
        self._id_da_prestadora = id_da_prestadora
        self.salvas = []

    def get_by_identifier(self, identifier_type, value):
        return None

    def get_by_id(self, entity_id):
        if entity_id == self._id_da_prestadora:
            raise RuntimeError("falha ficticia de leitura do destino")

        return None

    def save(self, entity):
        self.salvas.append(entity.entity_id)

        if len(self.salvas) > 1:
            raise AssertionError("nao deveria gravar depois do fundo")

        return entity


def test_falha_na_checagem_de_id_da_prestadora_propaga():
    repositorio = RepositorioQueFalhaNoIdDaPrestadora(adaptador.entity_id(CNPJ_5))
    snapshot = retrato(assunto(CNPJ_1, 1, parties=(papel(CNPJ_5, 1),)))

    with pytest.raises(RuntimeError, match="falha ficticia de leitura"):
        importar(repositorio, snapshot)

    assert repositorio.salvas == [adaptador.entity_id(CNPJ_1)]


# --- S: situacao ---


def test_s6_so_o_funcionamento_normal_entra_e_o_backlog_e_contado(destino):
    _, repositorio = destino
    snapshot = retrato(
        assunto(cnpj_ficticio(1), 1),
        assunto(cnpj_ficticio(2), 2, situacoes=("Cancelado",)),
        assunto(cnpj_ficticio(3), 3, situacoes=(FASE_PRE,)),
        assunto(cnpj_ficticio(4), 4, situacoes=("Em Liquida\xe7\xe3o",)),
        assunto(cnpj_ficticio(5), 5, situacoes=("Incorpora\xe7\xe3o",)),
        assunto(cnpj_ficticio(6), 6, situacoes=("Em Situa\xe7\xe3o Especial",)),
        assunto(cnpj_ficticio(7), 7, situacoes=("Em funcionamento normal",)),
        assunto(cnpj_ficticio(8), 8, situacoes=()),
        assunto(cnpj_ficticio(9), 9, situacoes=(NORMAL, "Cancelado")),
    )

    report = importar(repositorio, snapshot).report

    assert report.em_funcionamento_normal == 1
    assert report.fundos_criados == 1
    assert report.backlog == type(report.backlog)(
        fase_pre_operacional=1,
        em_liquidacao=1,
        cancelado=1,
        incorporacao=1,
        em_situacao_especial=1,
        situacao_fora_da_tabela=1,
        sem_situacao=1,
        situacao_conflitante=1,
    )
    assert report.backlog.total == 8
    assert report.cnpjs_lidos == 9


def test_s7_situacao_do_lado_que_decide(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo_a = banco.fundo_do_cadastro(coleta, CNPJ_1)
    banco.classe_do_cadastro(coleta, CNPJ_1, fundo_a, situacao=FASE_PRE)
    fundo_b = banco.fundo_do_cadastro(coleta, CNPJ_2, situacao=FASE_PRE)
    banco.classe_do_cadastro(coleta, CNPJ_2, fundo_b)
    banco.classe_do_cadastro(coleta, CNPJ_4, fundo_b)

    fase = importar(repositorio, ler(banco))

    assert set(fase.funds) == {CNPJ_1, CNPJ_4}
    assert fase.report.backlog.fase_pre_operacional == 1


# --- Erros e repr ---


def test_erro_e_contado_pelo_tipo_sem_mensagem_e_a_execucao_segue(destino):
    _, repositorio = destino
    espiao = Espiao(
        repositorio,
        falha_no_save=(adaptador.entity_id(CNPJ_1), adaptador.entity_id(CNPJ_6)),
    )
    snapshot = retrato(
        assunto(CNPJ_1, 1, parties=(papel(CNPJ_5, 1),)),
        assunto(CNPJ_2, 2, parties=(papel(CNPJ_5, 2), papel(CNPJ_6, 3))),
    )

    fase = importar(espiao, snapshot)
    report = fase.report

    assert [(erro.fase, erro.tipo, erro.quantidade) for erro in report.erros] == [
        ("fundos", "RuntimeError", 1),
        ("prestadoras", "RuntimeError", 1),
    ]
    assert report.fundos_criados == 1
    assert report.prestadoras_criadas == 1
    assert set(fase.funds) == {CNPJ_2}
    assert CNPJ_1 not in repr(report)
    assert CNPJ_6 not in repr(report)


def test_r3_repr_da_fase_nao_mostra_cnpj_nem_nome(banco, destino):
    _, repositorio = destino
    coleta = banco.coleta()
    fundo = banco.fundo_do_cadastro(coleta, CNPJ_1, nome="FUNDO FICTÍCIO R3")
    banco.administrador(coleta, fundo, CNPJ_5, nome="PRESTADORA FICTÍCIA R3")

    fase = importar(repositorio, ler(banco))
    texto = repr(fase)

    for proibido in (
        CNPJ_1,
        CNPJ_5,
        "FUNDO FICTÍCIO R3",
        "PRESTADORA FICTÍCIA R3",
    ):
        assert proibido not in texto

    assert "report" in texto
    assert dict(fase.funds) and dict(fase.providers)


def test_mapas_da_fase_sao_somente_leitura(destino):
    _, repositorio = destino
    fase = importar(repositorio, retrato(assunto(CNPJ_1, 1)))

    with pytest.raises(TypeError):
        fase.funds[CNPJ_2] = None


def test_servico_recusa_o_que_nao_e_retrato(destino):
    _, repositorio = destino

    with pytest.raises(TypeError):
        FundosImportService(repositorio).import_entities(object())
