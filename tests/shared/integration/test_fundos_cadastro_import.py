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
    SourceType,
)
from pense_alm.shared.integration.fundos_adapter import NORMAL, FundosAdapter
from pense_alm.shared.integration.fundos_cadastro_import import (
    FundosCadastroImport,
    FundosCadastroRun,
    SnapshotOlderThanApplied,
)
from pense_alm.shared.integration.fundos_records import (
    CadastroIncompleteReason,
    CadastroSnapshot,
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


def importar(destino, snapshot, entidades=None, relacoes=None):
    manager, repositorio_entidades, repositorio_relacoes = destino
    return FundosCadastroImport(
        entidades or repositorio_entidades,
        relacoes or repositorio_relacoes,
        FundosTargetState(manager),
    ).run(snapshot)


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
        FundosCadastroRun(entities=run.entities, relations=fora)

    with pytest.raises(ValueError, match="Soma entre relatorios 2"):
        FundosCadastroRun(entities=run.entities, relations=incompleta)


def test_tipos_sao_conferidos(destino):
    manager, entidades, relacoes = destino
    run = importar(destino, retrato(assunto()))

    with pytest.raises(TypeError):
        FundosCadastroRun(entities=object(), relations=run.relations)

    with pytest.raises(TypeError):
        FundosCadastroRun(entities=run.entities, relations=object())

    with pytest.raises(TypeError):
        FundosCadastroImport(entidades, relacoes, object())

    with pytest.raises(TypeError):
        FundosCadastroImport(entidades, relacoes, FundosTargetState(manager)).run(object())
