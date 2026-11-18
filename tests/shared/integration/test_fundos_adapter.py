"""Testes do adaptador do cadastro de Fundos (FU7.2): A1 a A5, motivos e mapas.

Records montados direto, sem banco. So CNPJs ficticios de cnpj_amostras e
nomes marcados como ficticios.
"""

from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid5

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    Entity,
    EntityStatus,
    EntityType,
    IdentifierType,
    IdentifierValidationError,
    RelationshipStatus,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration.fundos_adapter import (
    CLASS_TYPES,
    FUND_SOURCE_TYPES,
    FUND_TARGET_TYPES,
    FUND_TYPES,
    NORMAL,
    RELATION_TYPES,
    ROLE_RELATIONS,
    SITUATIONS,
    FundosAdapter,
    FundosAdapterError,
    FundosReason,
    NameResolution,
    SituationGroup,
    TypeResolution,
)
from pense_alm.shared.integration.fundos_records import (
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)
from pense_alm.shared.persistence.serialization import provenance_id

from ..cnpj_amostras import cnpj_ficticio, com_mascara, dv_errado


CNPJ_FUNDO = cnpj_ficticio(1)
CNPJ_CLASSE = cnpj_ficticio(2)
CNPJ_PRESTADORA = cnpj_ficticio(5)
INICIO = datetime(2026, 10, 27, 12, tzinfo=UTC)
TIPO_CLASSE_FIDC = "Classes de Cotas de Fundos FIDC"
TIPO_CLASSE_FIAGRO = "Classes de Cotas de Fundos FIAGRO"

adaptador = FundosAdapter()


def assunto(**muda):
    """Grupo de fundo em funcionamento normal, FIDC, com nome."""

    valores = {
        "cnpj": CNPJ_FUNDO,
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


def assunto_classe(**muda):
    """Classe que so existe como classe, em funcionamento normal."""

    valores = {
        "cnpj": CNPJ_CLASSE,
        "source_table": "fund_classes",
        "source_id": 3,
        "names": ("CLASSE FICTÍCIA",),
        "situacoes": (NORMAL,),
        "tipos_fundo": (),
        "tipos_classe": (TIPO_CLASSE_FIDC,),
        "tipos_pessoa_gestor": (),
        "parties": (),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def retrato(*assuntos):
    fundos = sum(1 for item in assuntos if item.source_table == "funds")
    classes = len(assuntos) - fundos
    return CadastroSnapshot(
        reference_date=date(2026, 10, 27),
        collection_run_id=7,
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


def papel(party_observation_id, nome="PRESTADORA FICTÍCIA", role="administrador"):
    return FundosPartyLink(
        role=role,
        cnpj=CNPJ_PRESTADORA,
        name=nome,
        party_observation_id=party_observation_id,
    )


# --- A1: entity_id ---


def test_a1_entity_id_e_o_uuid5_do_cnpj_canonico():
    esperado = uuid5(NAMESPACE_URL, "pense-alm:fundos:cnpj:" + CNPJ_FUNDO)

    assert FundosAdapter.ENTITY_NAMESPACE == "pense-alm:fundos:cnpj:"
    assert adaptador.entity_id(CNPJ_FUNDO) == esperado
    assert adaptador.entity_id(com_mascara(CNPJ_FUNDO)) == esperado
    assert adaptador.entity_id(CNPJ_FUNDO) != adaptador.entity_id(CNPJ_CLASSE)


def test_a1_cnpj_alfanumerico_usa_a_forma_canonica():
    alfanumerico = cnpj_ficticio(1, alfanumerico=True)

    assert adaptador.entity_id(alfanumerico.lower()) == uuid5(
        NAMESPACE_URL,
        "pense-alm:fundos:cnpj:" + alfanumerico,
    )


def test_a1_cnpj_invalido_nao_gera_entity_id():
    with pytest.raises(IdentifierValidationError):
        adaptador.entity_id(dv_errado(CNPJ_FUNDO))


def test_a1_fundo_e_prestadora_de_mesmo_cnpj_tem_o_mesmo_entity_id():
    fundo = assunto(cnpj=CNPJ_PRESTADORA)
    snapshot = retrato(fundo)

    entidade_fundo = adaptador.to_fund_entity(fundo, snapshot)
    entidade_prestadora = adaptador.to_provider_entity(
        CNPJ_PRESTADORA,
        (papel(1),),
        snapshot,
    )

    assert entidade_fundo.entity_id == entidade_prestadora.entity_id


# --- A2 e T: tipo pelo par, nunca pelo nome ---


@pytest.mark.parametrize(
    ("tipos_fundo", "tipos_classe", "esperado"),
    [
        (("FIDC",), (), EntityType.FIDC),
        (("FIAGRO",), (), EntityType.FIAGRO),
        (("FIDC",), (TIPO_CLASSE_FIDC,), EntityType.FIDC),
        (("FIAGRO",), (TIPO_CLASSE_FIAGRO,), EntityType.FIAGRO),
    ],
)
def test_a2_tipo_do_fundo_pelo_par(tipos_fundo, tipos_classe, esperado):
    subject = assunto(tipos_fundo=tipos_fundo, tipos_classe=tipos_classe)

    assert adaptador.fund_type(subject) == TypeResolution(entity_type=esperado)


def test_a2_nome_do_fundo_nunca_decide_o_tipo():
    subject = assunto(names=("FIAGRO FICTÍCIO DO AGRONEGÓCIO",))

    assert adaptador.fund_type(subject).entity_type is EntityType.FIDC
    assert (
        adaptador.to_fund_entity(subject, retrato(subject)).entity_type
        is EntityType.FIDC
    )


def test_a2_classe_que_so_existe_como_classe_usa_o_tipo_da_classe():
    subject = assunto_classe(tipos_classe=(TIPO_CLASSE_FIAGRO,))

    assert adaptador.fund_type(subject).entity_type is EntityType.FIAGRO


@pytest.mark.parametrize(
    ("muda", "motivo"),
    [
        ({"tipos_fundo": ()}, FundosReason.TIPO_FORA_DO_MAPA),
        ({"tipos_fundo": ("FII",)}, FundosReason.TIPO_FORA_DO_MAPA),
        ({"tipos_fundo": ("fidc",)}, FundosReason.TIPO_FORA_DO_MAPA),
        ({"tipos_fundo": ("FIDC ",)}, FundosReason.TIPO_FORA_DO_MAPA),
        (
            {"tipos_classe": ("Classes de Cotas de Fundos FII",)},
            FundosReason.TIPO_FORA_DO_MAPA,
        ),
        (
            {"tipos_classe": (TIPO_CLASSE_FIAGRO,)},
            FundosReason.TIPO_DIVERGENTE,
        ),
        (
            {"tipos_fundo": ("FIAGRO", "FIDC")},
            FundosReason.TIPO_DIVERGENTE,
        ),
    ],
)
def test_t_motivos_de_tipo_como_unidade(muda, motivo):
    assert adaptador.fund_type(assunto(**muda)) == TypeResolution(reason=motivo)


def test_t_classe_que_so_existe_como_classe_sem_tipo_fica_fora_do_mapa():
    subject = assunto_classe(tipos_classe=())

    assert adaptador.fund_type(subject).reason is FundosReason.TIPO_FORA_DO_MAPA


# --- Mapas e situacao (D7) ---


def test_mapas_usam_o_texto_exato_da_cvm():
    assert FUND_TYPES == {"FIDC": EntityType.FIDC, "FIAGRO": EntityType.FIAGRO}
    assert CLASS_TYPES == {
        "Classes de Cotas de Fundos FIDC": EntityType.FIDC,
        "Classes de Cotas de Fundos FIAGRO": EntityType.FIAGRO,
    }
    # Os mesmos codigos de caractere medidos com ascii() em 17/11/2026.
    assert SITUATIONS == {
        "Em Funcionamento Normal": SituationGroup.NORMAL,
        "Fase Pr\xe9-Operacional": SituationGroup.FASE_PRE_OPERACIONAL,
        "Em Liquida\xe7\xe3o": SituationGroup.EM_LIQUIDACAO,
        "Cancelado": SituationGroup.CANCELADO,
        "Incorpora\xe7\xe3o": SituationGroup.INCORPORACAO,
        "Em Situa\xe7\xe3o Especial": SituationGroup.EM_SITUACAO_ESPECIAL,
    }


@pytest.mark.parametrize(
    ("situacoes", "grupo"),
    [
        ((NORMAL,), SituationGroup.NORMAL),
        (("Cancelado",), SituationGroup.CANCELADO),
        (("Fase Pr\xe9-Operacional",), SituationGroup.FASE_PRE_OPERACIONAL),
        (("Em Liquida\xe7\xe3o",), SituationGroup.EM_LIQUIDACAO),
        (("Incorpora\xe7\xe3o",), SituationGroup.INCORPORACAO),
        (("Em Situa\xe7\xe3o Especial",), SituationGroup.EM_SITUACAO_ESPECIAL),
        (("Em funcionamento normal",), SituationGroup.SITUACAO_FORA_DA_TABELA),
        (("Em Liquidacao",), SituationGroup.SITUACAO_FORA_DA_TABELA),
        (("Fase Pre" + chr(0x0301) + "-Operacional",), SituationGroup.SITUACAO_FORA_DA_TABELA),
        ((), SituationGroup.SEM_SITUACAO),
        ((NORMAL, "Em Liquida\xe7\xe3o"), SituationGroup.SITUACAO_CONFLITANTE),
    ],
)
def test_situacao_pelo_texto_exato(situacoes, grupo):
    assert adaptador.situation_group(assunto(situacoes=situacoes)) is grupo


# --- Nome (P6) ---


@pytest.mark.parametrize(
    "texto",
    [
        "FUNDO\tFICTÍCIO",
        "FUNDO\nFICTÍCIO",
        "FUNDO\xa0FICTÍCIO",
        "  FUNDO   FICTÍCIO  ",
        "  Fundo \t Fictício\nÁgil  ",
    ],
)
def test_nome_do_adaptador_e_o_legal_name_que_o_entity_produz(texto):
    entidade = Entity(
        legal_name=texto,
        entity_type=EntityType.FUND,
        provenance=DataProvenance(
            source_type=SourceType.MANUAL,
            source_name="Teste ficticio",
        ),
    )

    assert adaptador.fund_name(assunto(names=(texto,))).name == entidade.legal_name
    assert adaptador.provider_name((papel(1, texto),)).name == entidade.legal_name


@pytest.mark.parametrize(
    ("nomes", "esperado"),
    [
        (("FUNDO  FICTÍCIO",), NameResolution(name="FUNDO FICTÍCIO")),
        (
            ("FUNDO FICTÍCIO", " FUNDO\tFICTÍCIO "),
            NameResolution(name="FUNDO FICTÍCIO"),
        ),
        (
            ("FUNDO FICTÍCIO", "Fundo Fictício"),
            NameResolution(reason=FundosReason.NOME_DIVERGENTE),
        ),
        (
            ("FUNDO FICTÍCIO", "FUNDO FICTICIO"),
            NameResolution(reason=FundosReason.NOME_DIVERGENTE),
        ),
        ((), NameResolution(reason=FundosReason.SEM_NOME)),
    ],
)
def test_nome_do_fundo_depois_de_juntar_espacos(nomes, esperado):
    assert adaptador.fund_name(assunto(names=nomes)) == esperado


def test_nome_da_prestadora_vem_da_menor_linha_com_esse_nome():
    links = (
        papel(5, None),
        papel(30, "PRESTADORA  FICTÍCIA"),
        papel(12, "PRESTADORA FICTÍCIA"),
        papel(25, "PRESTADORA FICTÍCIA", role="gestor"),
    )

    assert adaptador.provider_name(links) == NameResolution(
        name="PRESTADORA FICTÍCIA",
        party_observation_id=12,
    )


@pytest.mark.parametrize(
    ("links", "motivo"),
    [
        ((), FundosReason.SEM_NOME),
        ((papel(1, None), papel(2, None)), FundosReason.SEM_NOME),
        (
            (papel(1, "PRESTADORA FICTÍCIA"), papel(2, "PRESTADORA FICTÍCIA LTDA")),
            FundosReason.NOME_DIVERGENTE,
        ),
        (
            (papel(1, "PRESTADORA FICTÍCIA"), papel(2, "Prestadora Fictícia")),
            FundosReason.NOME_DIVERGENTE,
        ),
    ],
)
def test_motivos_de_nome_da_prestadora(links, motivo):
    assert adaptador.provider_name(links) == NameResolution(reason=motivo)


def test_resolucao_exige_o_valor_ou_o_motivo():
    with pytest.raises(ValueError):
        NameResolution()

    with pytest.raises(ValueError):
        NameResolution(name="FUNDO FICTÍCIO", reason=FundosReason.SEM_NOME)

    with pytest.raises(ValueError):
        NameResolution(reason=FundosReason.SEM_NOME, party_observation_id=1)

    with pytest.raises(ValueError):
        TypeResolution()

    with pytest.raises(ValueError):
        TypeResolution(
            entity_type=EntityType.FIDC,
            reason=FundosReason.TIPO_DIVERGENTE,
        )


def test_repr_da_resolucao_de_nome_nao_mostra_o_nome():
    resolucao = NameResolution(
        name="PRESTADORA FICTÍCIA R3",
        party_observation_id=1,
    )

    assert "PRESTADORA FICTÍCIA R3" not in repr(resolucao)


# --- A3: prestadora ---


def test_a3_prestadora_e_instituicao_financeira_com_status_unknown():
    entidade = adaptador.to_provider_entity(
        CNPJ_PRESTADORA,
        (papel(12),),
        retrato(assunto()),
    )

    assert entidade.entity_type is EntityType.FINANCIAL_INSTITUTION
    assert entidade.status is EntityStatus.UNKNOWN
    assert entidade.legal_name == "PRESTADORA FICTÍCIA"
    assert entidade.cnpj == CNPJ_PRESTADORA
    assert entidade.get_identifier(IdentifierType.CNPJ).is_primary
    assert entidade.provenance.source_reference == "fundos:party_observations:12"
    assert entidade.provenance.source_type is SourceType.CVM
    assert entidade.provenance.source_name == "Fundos - CVM Cadastro"
    assert entidade.provenance.reference_date == datetime(2026, 10, 27, tzinfo=UTC)
    assert entidade.provenance.collected_at == INICIO
    assert entidade.created_at == INICIO
    assert entidade.updated_at == INICIO


def test_a3_prestadora_sem_nome_nao_vira_entidade():
    with pytest.raises(FundosAdapterError) as erro:
        adaptador.to_provider_entity(
            CNPJ_PRESTADORA,
            (papel(1, None),),
            retrato(assunto()),
        )

    assert CNPJ_PRESTADORA not in str(erro.value)


# --- A4: proveniencia e datas ---


def test_a4_proveniencia_e_datas_do_fundo():
    subject = assunto(source_id=42)
    entidade = adaptador.to_fund_entity(subject, retrato(subject))
    proveniencia = entidade.provenance

    assert proveniencia.source_type is SourceType.CVM
    assert proveniencia.source_name == "Fundos - CVM Cadastro"
    assert proveniencia.source_reference == "fundos:funds:42"
    assert proveniencia.reference_date == datetime(2026, 10, 27, tzinfo=UTC)
    assert proveniencia.collected_at == INICIO
    assert entidade.created_at == INICIO
    assert entidade.updated_at == INICIO
    assert entidade.status is EntityStatus.ACTIVE
    assert entidade.entity_type is EntityType.FIDC
    assert entidade.legal_name == "FUNDO FICTÍCIO"
    assert entidade.identifiers[0].provenance == proveniencia
    assert FundosAdapter.SOURCE_NAME_CDA == "Fundos - CVM CDA"


def test_a4_classe_que_so_existe_como_classe_aponta_fund_classes():
    subject = assunto_classe(source_id=9)
    entidade = adaptador.to_fund_entity(subject, retrato(subject))

    assert entidade.provenance.source_reference == "fundos:fund_classes:9"
    assert entidade.legal_name == "CLASSE FICTÍCIA"


def test_a4_duas_montagens_dao_a_mesma_entidade_e_a_mesma_proveniencia():
    subject = assunto()
    snapshot = retrato(subject)

    primeira = adaptador.to_fund_entity(subject, snapshot)
    segunda = adaptador.to_fund_entity(subject, snapshot)

    assert primeira == segunda
    assert provenance_id(primeira.provenance) == provenance_id(
        segunda.provenance
    )


@pytest.mark.parametrize(
    "muda",
    [
        {"situacoes": ("Cancelado",)},
        {"situacoes": ()},
        {"names": ()},
        {"tipos_fundo": ("FII",)},
    ],
)
def test_fundo_que_nao_entra_nao_vira_entidade(muda):
    subject = assunto(**muda)

    with pytest.raises(FundosAdapterError) as erro:
        adaptador.to_fund_entity(subject, retrato(subject))

    assert CNPJ_FUNDO not in str(erro.value)
    assert "FUNDO FICTÍCIO" not in str(erro.value)


# --- A5: relacoes de prestadora (direcao, id e proveniencia) ---


FUNDO_ID = adaptador.entity_id(CNPJ_FUNDO)
PRESTADORA_ID = adaptador.entity_id(CNPJ_PRESTADORA)
ADMINISTERED_BY = RelationshipType.ADMINISTERED_BY
CUSTODIED_BY = RelationshipType.CUSTODIED_BY
MANAGES = RelationshipType.MANAGES


def test_a5_papeis_e_tipos_de_relacao():
    assert ROLE_RELATIONS == {
        "administrador": ADMINISTERED_BY,
        "custodiante": CUSTODIED_BY,
        "gestor": MANAGES,
    }
    assert FUND_SOURCE_TYPES == (ADMINISTERED_BY, CUSTODIED_BY)
    assert FUND_TARGET_TYPES == (MANAGES,)
    assert set(RELATION_TYPES) == set(ROLE_RELATIONS.values())


@pytest.mark.parametrize(
    ("role", "tipo", "fundo_e_origem"),
    [
        ("administrador", ADMINISTERED_BY, True),
        ("custodiante", CUSTODIED_BY, True),
        ("gestor", MANAGES, False),
    ],
)
def test_a5_direcao_por_papel(role, tipo, fundo_e_origem):
    kind, origem, destino = adaptador.relation_ends(role, FUNDO_ID, PRESTADORA_ID)

    assert kind is tipo

    if fundo_e_origem:
        assert (origem, destino) == (FUNDO_ID, PRESTADORA_ID)
    else:
        assert (origem, destino) == (PRESTADORA_ID, FUNDO_ID)


def test_a5_papel_sem_relacao_e_recusado():
    with pytest.raises(FundosAdapterError):
        adaptador.relation_ends("auditor", FUNDO_ID, PRESTADORA_ID)


def test_a5_relationship_id_e_o_uuid5_da_chave_canonica():
    snapshot = retrato(assunto())
    esperado = uuid5(NAMESPACE_URL, f"{FUNDO_ID}:administered_by:{PRESTADORA_ID}")
    relacao = adaptador.build_relationship(
        ADMINISTERED_BY,
        FUNDO_ID,
        PRESTADORA_ID,
        adaptador.relationship_provenance(snapshot, 3),
        snapshot,
    )

    assert adaptador.relationship_id(FUNDO_ID, ADMINISTERED_BY, PRESTADORA_ID) == esperado
    assert relacao.relationship_id == esperado
    assert relacao.relationship_id == uuid5(NAMESPACE_URL, relacao.canonical_key)
    assert adaptador.relationship_id(PRESTADORA_ID, ADMINISTERED_BY, FUNDO_ID) != esperado
    assert adaptador.relationship_id(FUNDO_ID, CUSTODIED_BY, PRESTADORA_ID) != esperado


def test_a5_build_relationship_ativa_desde_a_competencia():
    snapshot = retrato(assunto())
    proveniencia = adaptador.relationship_provenance(snapshot, 3)

    relacao = adaptador.build_relationship(
        MANAGES,
        PRESTADORA_ID,
        FUNDO_ID,
        proveniencia,
        snapshot,
    )

    assert relacao.relationship_type is MANAGES
    assert relacao.source_entity_id == PRESTADORA_ID
    assert relacao.target_entity_id == FUNDO_ID
    assert relacao.status is RelationshipStatus.ACTIVE
    assert relacao.valid_from == datetime(2026, 10, 27, tzinfo=UTC)
    assert relacao.valid_to is None
    assert relacao.created_at == INICIO
    assert relacao.provenance == proveniencia
    assert relacao == adaptador.build_relationship(
        MANAGES,
        PRESTADORA_ID,
        FUNDO_ID,
        proveniencia,
        snapshot,
    )


@pytest.mark.parametrize(
    "tipo",
    [RelationshipType.ISSUES, RelationshipType.INVESTS_IN, "manages"],
)
def test_a5_build_relationship_recusa_tipo_fora_do_adaptador(tipo):
    snapshot = retrato(assunto())

    with pytest.raises(FundosAdapterError):
        adaptador.build_relationship(
            tipo,
            FUNDO_ID,
            PRESTADORA_ID,
            adaptador.closing_provenance(snapshot),
            snapshot,
        )


def test_a5_proveniencia_de_relacao_e_de_fechamento():
    snapshot = retrato(assunto())
    linha = adaptador.relationship_provenance(snapshot, 12)
    coleta = adaptador.closing_provenance(snapshot)

    for proveniencia in (linha, coleta):
        assert proveniencia.source_type is SourceType.CVM
        assert proveniencia.source_name == "Fundos - CVM Cadastro"
        assert proveniencia.reference_date == datetime(2026, 10, 27, tzinfo=UTC)
        assert proveniencia.collected_at == INICIO

    assert linha.source_reference == "fundos:party_observations:12"
    assert coleta.source_reference == "fundos:collection_runs:7"
    assert provenance_id(linha) == provenance_id(
        adaptador.relationship_provenance(snapshot, 12)
    )
    assert provenance_id(coleta) == provenance_id(adaptador.closing_provenance(snapshot))
    assert adaptador.reference_datetime(snapshot) == datetime(2026, 10, 27, tzinfo=UTC)


def test_a5_is_cadastro_provenance_so_para_a_deste_adaptador():
    snapshot = retrato(assunto())
    manual = DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Fundos - CVM Cadastro",
        collected_at=INICIO,
    )
    cda = DataProvenance(
        source_type=SourceType.CVM,
        source_name="Fundos - CVM CDA",
        collected_at=INICIO,
    )

    assert adaptador.is_cadastro_provenance(adaptador.closing_provenance(snapshot))
    assert adaptador.is_cadastro_provenance(adaptador.relationship_provenance(snapshot, 1))
    assert not adaptador.is_cadastro_provenance(manual)
    assert not adaptador.is_cadastro_provenance(cda)
