"""Testes do servico da fase 3 de Fundos (FU7.2): relacoes de prestadora.

O destino e um SQLite da camada em tmp_path. O retrato e montado direto com
records, em ate tres competencias (R1 < R2 < R3), com coleta completa ou
nao. As fases 1 e 2 rodam pelo servico do B1 e a fase 3 pelo servico novo.
So CNPJs ficticios de cnpj_amostras e nomes marcados como ficticios. Os
nomes dos testes trazem o codigo do plano (C1 a C6, E3, E4, N1, N3, P1, S8).
"""

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
from pense_alm.shared.integration.fundos_records import (
    CadastroIncompleteReason,
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)
from pense_alm.shared.integration.fundos_relation_report import (
    TYPE_COUNTERS,
    FundosRelationError,
)
from pense_alm.shared.integration.fundos_relation_rules import RelationOperation
from pense_alm.shared.integration.fundos_relation_service import FundosRelationService
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)

from ..cnpj_amostras import cnpj_ficticio


ADMINISTERED_BY = RelationshipType.ADMINISTERED_BY
CUSTODIED_BY = RelationshipType.CUSTODIED_BY
MANAGES = RelationshipType.MANAGES
ACTIVE = RelationshipStatus.ACTIVE
INACTIVE = RelationshipStatus.INACTIVE

CNPJ_FUNDO = cnpj_ficticio(1)
CNPJ_FUNDO_2 = cnpj_ficticio(2)
CNPJ_ADMIN = cnpj_ficticio(5)
CNPJ_CUSTODIANTE = cnpj_ficticio(6)
CNPJ_GESTORA = cnpj_ficticio(7)
CNPJ_ADMIN_2 = cnpj_ficticio(8)
NOMES = {
    CNPJ_ADMIN: "ADMINISTRADORA FICTÍCIA",
    CNPJ_CUSTODIANTE: "CUSTODIANTE FICTÍCIA",
    CNPJ_GESTORA: "GESTORA FICTÍCIA",
    CNPJ_ADMIN_2: "ADMINISTRADORA FICTÍCIA 2",
}

R1 = date(2026, 9, 30)
R2 = date(2026, 10, 27)
R3 = date(2026, 11, 26)
INICIO = {
    R1: datetime(2026, 9, 30, 12, tzinfo=UTC),
    R2: datetime(2026, 10, 27, 12, tzinfo=UTC),
    R3: datetime(2026, 11, 26, 12, tzinfo=UTC),
}
COLETA = {R1: 1, R2: 2, R3: 3}

adaptador = FundosAdapter()
FUNDO_ID = adaptador.entity_id(CNPJ_FUNDO)
ADMIN_ID = adaptador.entity_id(CNPJ_ADMIN)
ADMIN_2_ID = adaptador.entity_id(CNPJ_ADMIN_2)
CUSTODIANTE_ID = adaptador.entity_id(CNPJ_CUSTODIANTE)
GESTORA_ID = adaptador.entity_id(CNPJ_GESTORA)


def meia_noite(competencia):
    return datetime.combine(competencia, time(0, 0), tzinfo=UTC)


def papel(role, cnpj, linha, nome=None):
    return FundosPartyLink(
        role=role,
        cnpj=cnpj,
        name=nome or NOMES[cnpj],
        party_observation_id=linha,
    )


def assunto(cnpj=CNPJ_FUNDO, source_id=1, parties=(), **muda):
    valores = {
        "cnpj": cnpj,
        "source_table": "funds",
        "source_id": source_id,
        "names": ("FUNDO FICTÍCIO " + str(source_id),),
        "situacoes": (NORMAL,),
        "tipos_fundo": ("FIDC",),
        "tipos_classe": (),
        "tipos_pessoa_gestor": ("PJ",),
        "parties": tuple(parties),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def fundo_completo(base=100, **muda):
    """Fundo com administradora, custodiante e gestora (linhas base + 1 a 3)."""

    return assunto(
        parties=(
            papel("administrador", CNPJ_ADMIN, base + 1),
            papel("custodiante", CNPJ_CUSTODIANTE, base + 2),
            papel("gestor", CNPJ_GESTORA, base + 3),
        ),
        **muda,
    )


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


class EspiaoRelacoes:
    """Repassa ao SQLite; registra cada save e pode falhar em ids escolhidos."""

    def __init__(self, repositorio, falha_no_save=(), falha_na_leitura=False):
        self._repositorio = repositorio
        self._falha_no_save = set(falha_no_save)
        self._falha_na_leitura = falha_na_leitura
        self.salvas = []

    def save(self, relationship):
        self.salvas.append(relationship.relationship_id)

        if relationship.relationship_id in self._falha_no_save:
            raise RuntimeError("falha ficticia ao gravar")

        return self._repositorio.save(relationship)

    def list_by_source(self, entity_id):
        return self._repositorio.list_by_source(entity_id)

    def list_by_target(self, entity_id):
        if self._falha_na_leitura:
            raise RuntimeError("falha ficticia de leitura do destino")

        return self._repositorio.list_by_target(entity_id)

    def list_active_at(self, reference_datetime, relationship_type=None):
        return self._repositorio.list_active_at(reference_datetime, relationship_type)


class EspiaoEntidades:
    """Repassa ao SQLite e registra cada save."""

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


@pytest.fixture
def destino(tmp_path):
    manager = SQLiteConnectionManager(tmp_path / "destino" / "camada.sqlite3")
    return manager, SQLiteEntityRepository(manager), SQLiteRelationshipRepository(manager)


def executar(destino, snapshot, relacoes=None, entidades=None):
    _, repositorio_entidades, repositorio_relacoes = destino
    entidades = entidades or repositorio_entidades
    relacoes = relacoes or repositorio_relacoes
    fase = FundosImportService(entidades).import_entities(snapshot)
    return FundosRelationService(entidades, relacoes).import_relationships(snapshot, fase)


def relacao(destino, origem, tipo, alvo):
    return destino[2].get_by_canonical_key(f"{origem}:{tipo.value}:{alvo}")


def linhas_relacoes(destino):
    with destino[0].read_connection() as conexao:
        return [
            tuple(linha)
            for linha in conexao.execute(
                "SELECT * FROM entity_relationships ORDER BY relationship_id"
            )
        ]


def nao_zero(contagens):
    """Os contadores diferentes de zero de um tipo de relacao."""

    valores = {name: getattr(contagens, name) for name in TYPE_COUNTERS}
    valores["prestadora_sem_entidade"] = contagens.nao_criadas.prestadora_sem_entidade
    valores["autorrelacao"] = contagens.nao_criadas.autorrelacao
    return {name: valor for name, valor in valores.items() if valor}


def manual(origem, tipo, alvo):
    """Relacao de outra fonte (MANUAL), com relationship_id aleatorio."""

    return EntityRelationship(
        relationship_id=uuid4(),
        source_entity_id=origem,
        target_entity_id=alvo,
        relationship_type=tipo,
        provenance=DataProvenance(
            source_type=SourceType.MANUAL,
            source_name="Teste ficticio",
            collected_at=INICIO[R1],
        ),
        status=ACTIVE,
        created_at=INICIO[R1],
    )


def tipos(report):
    return (report.administered_by, report.custodied_by, report.manages)


# --- Decisao 2 e E3: segunda execucao ---


def test_segunda_execucao_mantem_as_tres_sem_gravar_nada(destino):
    snapshot = retrato(fundo_completo())

    primeira = executar(destino, snapshot)

    for contagens in tipos(primeira):
        assert nao_zero(contagens) == {"pares_lidos": 1, "criadas": 1}

    assert relacao(destino, GESTORA_ID, MANAGES, FUNDO_ID) is not None
    assert destino[2].count() == 3

    antes = linhas_relacoes(destino)
    espiao_relacoes = EspiaoRelacoes(destino[2])
    espiao_entidades = EspiaoEntidades(destino[1])

    segunda = executar(
        destino,
        snapshot,
        relacoes=espiao_relacoes,
        entidades=espiao_entidades,
    )

    for contagens in tipos(segunda):
        assert nao_zero(contagens) == {"pares_lidos": 1, "gravadas": 1, "mantidas": 1}

    assert sum(contagens.mantidas for contagens in tipos(segunda)) == 3
    assert sum(contagens.criadas for contagens in tipos(segunda)) == 0
    assert espiao_relacoes.salvas == []
    assert espiao_entidades.salvas == []
    assert linhas_relacoes(destino) == antes


# --- C1 a C4: fechar e reabrir ---


def test_c1_troca_de_administradora_fecha_a_antiga_e_cria_a_nova(destino):
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)), competencia=R1),
    )
    antiga = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)

    report = executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN_2, 201),)), competencia=R2),
    )
    fechada = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)
    nova = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_2_ID)

    assert nao_zero(report.administered_by) == {
        "pares_lidos": 1,
        "gravadas": 1,
        "criadas": 1,
        "fechadas": 1,
    }
    assert fechada.relationship_id == antiga.relationship_id
    assert fechada.created_at == antiga.created_at == INICIO[R1]
    assert fechada.status is INACTIVE
    assert fechada.valid_from == meia_noite(R1)
    assert fechada.valid_to == meia_noite(R2)
    assert fechada.provenance.source_reference == "fundos:collection_runs:2"
    assert fechada.provenance.collected_at == INICIO[R2]
    assert fechada.provenance.reference_date == meia_noite(R2)
    assert nova.status is ACTIVE
    assert nova.valid_from == meia_noite(R2)


def test_c2_leitura_incompleta_nao_fecha_e_diz_por_que(destino):
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)), competencia=R1),
    )
    antes = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)

    report = executar(
        destino,
        retrato(
            assunto(parties=(papel("administrador", CNPJ_ADMIN_2, 201),)),
            competencia=R2,
            motivo=CadastroIncompleteReason.MEMBRO_NAO_PROCESSADO,
        ),
    )
    depois = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)

    assert report.leitura_completa is False
    assert report.motivo_nao_fechar is CadastroIncompleteReason.MEMBRO_NAO_PROCESSADO
    assert nao_zero(report.administered_by) == {
        "pares_lidos": 1,
        "gravadas": 1,
        "criadas": 1,
        "fechamento_suspenso": 1,
    }
    assert depois.status is ACTIVE
    assert depois.valid_to is None
    assert depois.provenance == antes.provenance


def test_c3_volta_da_administradora_reabre_com_o_mesmo_id(destino):
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)), competencia=R1),
    )
    original = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN_2, 201),)), competencia=R2),
    )

    report = executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 301),)), competencia=R3),
    )
    reaberta = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)

    assert nao_zero(report.administered_by) == {
        "pares_lidos": 1,
        "gravadas": 2,
        "reabertas": 1,
        "fechadas": 1,
    }
    assert reaberta.relationship_id == original.relationship_id
    assert reaberta.created_at == INICIO[R1]
    assert reaberta.status is ACTIVE
    assert reaberta.valid_from == meia_noite(R3)
    assert reaberta.valid_to is None
    assert reaberta.provenance.source_reference == "fundos:party_observations:301"
    assert reaberta.provenance.collected_at == INICIO[R3]
    assert reaberta.provenance.reference_date == meia_noite(R3)
    assert relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_2_ID).status is INACTIVE


def test_c4_fechamento_guarda_as_proveniencias_antigas(destino):
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)), competencia=R1),
    )
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN_2, 201),)), competencia=R2),
    )

    with destino[0].read_connection() as conexao:
        referencias = {
            linha[0]
            for linha in conexao.execute(
                "SELECT source_reference FROM data_provenance WHERE source_name = ?",
                ("Fundos - CVM Cadastro",),
            )
        }

    assert {"fundos:party_observations:101", "fundos:collection_runs:2"} <= referencias


# --- C5 e C6: relacao de outra fonte ---


def test_c5_relacao_manual_ausente_fica_intacta(destino):
    snapshot = retrato(
        assunto(
            parties=(
                papel("administrador", CNPJ_ADMIN, 101),
                papel("custodiante", CNPJ_CUSTODIANTE, 102),
            )
        )
    )
    executar(destino, snapshot)
    outra = manual(FUNDO_ID, ADMINISTERED_BY, CUSTODIANTE_ID)
    destino[2].save(outra)
    antes = linhas_relacoes(destino)

    report = executar(destino, snapshot)

    assert nao_zero(report.administered_by) == {
        "pares_lidos": 1,
        "gravadas": 2,
        "mantidas": 1,
        "outra_fonte_ausente": 1,
    }
    assert linhas_relacoes(destino) == antes


def test_c6_outra_fonte_com_outro_id_no_par_lido_sem_erro(destino):
    executar(destino, retrato(assunto(parties=(papel("gestor", CNPJ_ADMIN, 101),))))
    outra = manual(FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)
    destino[2].save(outra)
    antes = linhas_relacoes(destino)

    report = executar(
        destino,
        retrato(
            assunto(
                parties=(
                    papel("administrador", CNPJ_ADMIN, 101),
                    papel("gestor", CNPJ_ADMIN, 102),
                )
            )
        ),
    )

    assert nao_zero(report.administered_by) == {
        "pares_lidos": 1,
        "gravadas": 1,
        "outra_fonte_presente": 1,
    }
    assert nao_zero(report.manages) == {"pares_lidos": 1, "gravadas": 1, "mantidas": 1}
    assert report.erros == ()
    assert destino[2].count() == 2
    assert linhas_relacoes(destino) == antes


# --- E4, N1, N3 e P1 (a parte de relacoes) ---


def test_e4_mesma_prestadora_administra_e_gere_o_fundo(destino):
    report = executar(
        destino,
        retrato(
            assunto(
                parties=(
                    papel("administrador", CNPJ_ADMIN, 101),
                    papel("gestor", CNPJ_ADMIN, 102),
                )
            )
        ),
    )

    assert nao_zero(report.administered_by) == {"pares_lidos": 1, "criadas": 1}
    assert nao_zero(report.manages) == {"pares_lidos": 1, "criadas": 1}
    assert relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID) is not None
    assert relacao(destino, ADMIN_ID, MANAGES, FUNDO_ID) is not None
    assert destino[1].count() == 2


def test_n1_fundo_sem_nome_nao_tem_relacao_e_os_pares_sao_contados(destino):
    report = executar(
        destino,
        retrato(
            assunto(
                names=(),
                parties=(
                    papel("administrador", CNPJ_ADMIN, 101),
                    papel("administrador", CNPJ_ADMIN, 102),
                    papel("gestor", CNPJ_ADMIN, 103),
                    papel("custodiante", CNPJ_CUSTODIANTE, 104),
                ),
            )
        ),
    )

    assert report.pares_de_fundo_nao_resolvido == 3
    assert all(nao_zero(contagens) == {} for contagens in tipos(report))
    assert destino[2].count() == 0


def test_n3_prestadora_com_dois_nomes_fica_sem_entidade(destino):
    report = executar(
        destino,
        retrato(
            assunto(
                parties=(papel("administrador", CNPJ_ADMIN, 101, "NOME A FICTÍCIO"),),
            ),
            assunto(
                CNPJ_FUNDO_2,
                2,
                parties=(papel("administrador", CNPJ_ADMIN, 201, "NOME B FICTÍCIO"),),
            ),
        ),
    )

    assert nao_zero(report.administered_by) == {
        "pares_lidos": 2,
        "prestadora_sem_entidade": 2,
    }
    assert destino[2].count() == 0


def test_n3_prestadora_ja_na_camada_com_nome_conflitante_continua_resolvida(destino):
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)), competencia=R1),
    )
    antes = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)
    snapshot = retrato(
        assunto(
            parties=(papel("administrador", CNPJ_ADMIN, 201, "NOME A FICTÍCIO"),),
        ),
        assunto(
            CNPJ_FUNDO_2,
            2,
            parties=(papel("administrador", CNPJ_ADMIN, 202, "NOME B FICTÍCIO"),),
        ),
        competencia=R2,
    )
    _, entidades, relacoes = destino

    fase = FundosImportService(entidades).import_entities(snapshot)
    report = FundosRelationService(entidades, relacoes).import_relationships(
        snapshot,
        fase,
    )
    depois = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)
    administradas = report.administered_by

    assert fase.report.prestadoras_reutilizadas == 1
    assert fase.report.prestadoras_nao_criadas.nome_divergente == 0
    assert nao_zero(administradas) == {
        "pares_lidos": 2,
        "gravadas": 1,
        "mantidas": 1,
        "criadas": 1,
    }
    assert administradas.pares_lidos == administradas.mantidas + administradas.criadas
    assert administradas.gravadas == administradas.mantidas
    assert administradas.nao_criadas.total == 0
    assert report.erros == ()
    assert depois.relationship_id == antes.relationship_id
    assert depois.status is ACTIVE
    assert depois.valid_to is None
    assert depois.provenance == antes.provenance
    assert relacao(
        destino,
        adaptador.entity_id(CNPJ_FUNDO_2),
        ADMINISTERED_BY,
        ADMIN_ID,
    ) is not None


def test_p1_gestora_pessoa_fisica_nao_gera_manages(destino):
    report = executar(
        destino,
        retrato(
            assunto(
                tipos_pessoa_gestor=("PF",),
                parties=(papel("administrador", CNPJ_ADMIN, 101),),
            )
        ),
    )

    assert nao_zero(report.manages) == {}
    assert nao_zero(report.administered_by) == {"pares_lidos": 1, "criadas": 1}
    assert destino[2].count(MANAGES) == 0


# --- S8 e fundo ausente do retrato: so contam ---


def test_s8_fundo_do_backlog_tem_as_relacoes_intactas_e_so_as_nossas_contam(destino):
    executar(destino, retrato(fundo_completo(), competencia=R1))
    destino[2].save(manual(FUNDO_ID, ADMINISTERED_BY, GESTORA_ID))
    antes = linhas_relacoes(destino)

    report = executar(
        destino,
        retrato(fundo_completo(base=200, situacoes=("Cancelado",)), competencia=R2),
    )

    assert report.fundos_fora_do_normal_com_relacao == 1
    assert report.relacoes_de_fundo_fora_do_normal_intactas == 3
    assert report.relacoes_de_fundo_ausente_do_retrato == 0
    assert all(nao_zero(contagens) == {} for contagens in tipos(report))
    assert linhas_relacoes(destino) == antes


def test_s8_relacao_manual_em_fundo_do_backlog_nao_conta(destino):
    executar(
        destino,
        retrato(
            assunto(),
            assunto(CNPJ_FUNDO_2, 2, parties=(papel("gestor", CNPJ_GESTORA, 101),)),
            competencia=R1,
        ),
    )
    destino[2].save(manual(FUNDO_ID, ADMINISTERED_BY, GESTORA_ID))
    antes = linhas_relacoes(destino)

    report = executar(
        destino,
        retrato(
            assunto(situacoes=("Cancelado",)),
            assunto(CNPJ_FUNDO_2, 2, parties=(papel("gestor", CNPJ_GESTORA, 201),)),
            competencia=R2,
        ),
    )

    assert report.fundos_fora_do_normal_com_relacao == 0
    assert report.relacoes_de_fundo_fora_do_normal_intactas == 0
    assert linhas_relacoes(destino) == antes


def test_fundo_ausente_do_retrato_e_contado_e_intacto(destino):
    executar(
        destino,
        retrato(
            assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)),
            assunto(CNPJ_FUNDO_2, 2, parties=(papel("administrador", CNPJ_ADMIN, 102),)),
            competencia=R1,
        ),
    )
    antes = linhas_relacoes(destino)

    report = executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 201),)), competencia=R2),
    )

    assert report.relacoes_de_fundo_ausente_do_retrato == 1
    assert nao_zero(report.administered_by) == {
        "pares_lidos": 1,
        "gravadas": 1,
        "mantidas": 1,
    }
    assert linhas_relacoes(destino) == antes


def test_fundo_de_outro_tipo_no_backlog_nao_conta_como_ausente(destino):
    proveniencia = DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste ficticio",
        collected_at=INICIO[R1],
    )
    destino[1].save(
        Entity(
            legal_name="EMPRESA FICTÍCIA",
            entity_type=EntityType.COMPANY,
            status=EntityStatus.ACTIVE,
            provenance=proveniencia,
            identifiers=(
                EntityIdentifier(
                    identifier_type=IdentifierType.CNPJ,
                    value=CNPJ_FUNDO,
                    provenance=proveniencia,
                    is_primary=True,
                ),
            ),
            created_at=INICIO[R1],
            updated_at=INICIO[R1],
        )
    )
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 101),)), competencia=R1),
    )
    antes = linhas_relacoes(destino)

    report = executar(
        destino,
        retrato(
            assunto(
                situacoes=("Cancelado",),
                parties=(papel("administrador", CNPJ_ADMIN, 201),),
            ),
            competencia=R2,
        ),
    )

    assert destino[2].count() == 1
    assert report.fundos_fora_do_normal_com_relacao == 0
    assert report.relacoes_de_fundo_ausente_do_retrato == 0
    assert linhas_relacoes(destino) == antes


# --- Erros: contados por tipo e operacao, sem mensagem ---


def test_erro_1_criacao_com_save_falhando_e_contada_e_segue(destino):
    custodia = adaptador.relationship_id(FUNDO_ID, CUSTODIED_BY, CUSTODIANTE_ID)
    espiao = EspiaoRelacoes(destino[2], falha_no_save={custodia})

    report = executar(destino, retrato(fundo_completo()), relacoes=espiao)

    assert nao_zero(report.administered_by) == {"pares_lidos": 1, "criadas": 1}
    assert nao_zero(report.custodied_by) == {"pares_lidos": 1}
    assert nao_zero(report.manages) == {"pares_lidos": 1, "criadas": 1}
    assert report.erros == (
        FundosRelationError(CUSTODIED_BY, RelationOperation.CRIAR, "RuntimeError", 1),
    )
    assert destino[2].count() == 2
    assert relacao(destino, FUNDO_ID, CUSTODIED_BY, CUSTODIANTE_ID) is None
    assert relacao(destino, GESTORA_ID, MANAGES, FUNDO_ID) is not None


def test_erro_2_reabertura_com_save_falhando_e_contada(destino):
    executar(
        destino,
        retrato(
            assunto(
                parties=(
                    papel("administrador", CNPJ_ADMIN, 101),
                    papel("custodiante", CNPJ_CUSTODIANTE, 102),
                )
            ),
            competencia=R1,
        ),
    )
    executar(
        destino,
        retrato(assunto(parties=(papel("custodiante", CNPJ_CUSTODIANTE, 202),)), competencia=R2),
    )
    administracao = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)
    espiao = EspiaoRelacoes(destino[2], falha_no_save={administracao.relationship_id})

    report = executar(
        destino,
        retrato(
            assunto(
                parties=(
                    papel("administrador", CNPJ_ADMIN, 301),
                    papel("custodiante", CNPJ_CUSTODIANTE, 302),
                )
            ),
            competencia=R3,
        ),
        relacoes=espiao,
    )
    depois = relacao(destino, FUNDO_ID, ADMINISTERED_BY, ADMIN_ID)

    assert nao_zero(report.administered_by) == {"pares_lidos": 1, "gravadas": 1}
    assert nao_zero(report.custodied_by) == {"pares_lidos": 1, "gravadas": 1, "mantidas": 1}
    assert nao_zero(report.manages) == {}
    assert report.erros == (
        FundosRelationError(ADMINISTERED_BY, RelationOperation.REABRIR, "RuntimeError", 1),
    )
    assert depois.status is INACTIVE
    assert depois.valid_to == meia_noite(R2)


def test_erro_3_fechamento_recusado_pelo_modelo_e_contado(destino):
    executar(
        destino,
        retrato(assunto(parties=(papel("administrador", CNPJ_ADMIN, 301),)), competencia=R3),
    )
    antes = linhas_relacoes(destino)

    report = executar(destino, retrato(assunto(), competencia=R2))

    assert nao_zero(report.administered_by) == {"gravadas": 1}
    assert report.erros == (
        FundosRelationError(
            ADMINISTERED_BY,
            RelationOperation.FECHAR,
            "EntityValidationError",
            1,
        ),
    )
    assert linhas_relacoes(destino) == antes


def test_falha_de_leitura_do_destino_propaga(destino):
    espiao = EspiaoRelacoes(destino[2], falha_na_leitura=True)

    with pytest.raises(RuntimeError, match="falha ficticia de leitura"):
        executar(destino, retrato(fundo_completo()), relacoes=espiao)


def test_relatorio_sem_cnpj_nome_nem_mensagem(destino):
    custodia = adaptador.relationship_id(FUNDO_ID, CUSTODIED_BY, CUSTODIANTE_ID)
    espiao = EspiaoRelacoes(destino[2], falha_no_save={custodia})

    texto = repr(executar(destino, retrato(fundo_completo()), relacoes=espiao))

    for proibido in (
        CNPJ_FUNDO,
        CNPJ_ADMIN,
        CNPJ_CUSTODIANTE,
        CNPJ_GESTORA,
        "FICTÍCI",
        "falha ficticia",
        str(FUNDO_ID),
    ):
        assert proibido not in texto


def test_servico_recusa_o_que_nao_e_retrato_nem_fase(destino):
    _, entidades, relacoes = destino
    servico = FundosRelationService(entidades, relacoes)
    snapshot = retrato(assunto())
    fase = FundosImportService(entidades).import_entities(snapshot)

    with pytest.raises(TypeError):
        servico.import_relationships(object(), fase)

    with pytest.raises(TypeError):
        servico.import_relationships(snapshot, object())
