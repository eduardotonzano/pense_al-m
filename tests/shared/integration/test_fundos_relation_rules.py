"""Testes das regras de relacao de Fundos (FU7.2, fase 3): funcoes puras.

Records e entidades montados direto; o C6 usa SQLite em tmp_path so com os
repositorios, sem servico. So CNPJs ficticios de cnpj_amostras e nomes
marcados como ficticios. Os nomes dos testes trazem o codigo do plano (C1,
C3, C6).
"""

from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    DuplicateRelationshipError,
    Entity,
    EntityIdentifier,
    EntityRelationship,
    EntityStatus,
    EntityType,
    EntityValidationError,
    IdentifierType,
    RelationshipStatus,
    RelationshipType,
    SourceType,
)
from pense_alm.shared.integration.fundos_adapter import NORMAL, FundosAdapter
from pense_alm.shared.integration.fundos_records import (
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)
from pense_alm.shared.integration.fundos_relation_rules import (
    FundPairs,
    PairSkip,
    RelationDecision,
    RelationOperation,
    RelationOutcome,
    RelationPair,
    SkippedPair,
    classify,
    collect_pairs,
    relationship_to_save,
)
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara, dv_errado


ADMINISTERED_BY = RelationshipType.ADMINISTERED_BY
CUSTODIED_BY = RelationshipType.CUSTODIED_BY
MANAGES = RelationshipType.MANAGES
ACTIVE = RelationshipStatus.ACTIVE
INACTIVE = RelationshipStatus.INACTIVE
OUTROS_STATUS = (
    RelationshipStatus.PENDING_REVIEW,
    RelationshipStatus.DISPUTED,
    RelationshipStatus.UNKNOWN,
)

CNPJ_FUNDO = cnpj_ficticio(1)
CNPJ_OUTRO_FUNDO = cnpj_ficticio(2)
CNPJ_ADMIN = cnpj_ficticio(5)
CNPJ_CUSTODIANTE = cnpj_ficticio(6)
CNPJ_GESTORA = cnpj_ficticio(7)
CNPJ_SEM_ENTIDADE = cnpj_ficticio(8)

CRIADA_EM = datetime(2026, 9, 27, 12, tzinfo=UTC)
INICIO = datetime(2026, 10, 27, 12, tzinfo=UTC)
INICIO_NOVO = datetime(2026, 11, 26, 12, tzinfo=UTC)
R_ANTIGO = datetime(2026, 9, 27, tzinfo=UTC)
R = datetime(2026, 10, 27, tzinfo=UTC)
R_NOVO = datetime(2026, 11, 26, tzinfo=UTC)

adaptador = FundosAdapter()


def proveniencia_manual():
    return DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste ficticio",
        collected_at=INICIO,
    )


def entidade(cnpj, entity_type=EntityType.FINANCIAL_INSTITUTION, nome="PRESTADORA FICTÍCIA"):
    """Entidade com o id que o adaptador da ao CNPJ."""

    proveniencia = proveniencia_manual()
    return Entity(
        entity_id=adaptador.entity_id(cnpj),
        legal_name=nome,
        entity_type=entity_type,
        status=EntityStatus.ACTIVE,
        provenance=proveniencia,
        identifiers=(
            EntityIdentifier(
                identifier_type=IdentifierType.CNPJ,
                value=cnpj,
                provenance=proveniencia,
                is_primary=True,
            ),
        ),
        created_at=INICIO,
        updated_at=INICIO,
    )


FUNDO = entidade(CNPJ_FUNDO, EntityType.FIDC, "FUNDO FICTÍCIO")
OUTRO_FUNDO = entidade(CNPJ_OUTRO_FUNDO, EntityType.FIDC, "FUNDO FICTÍCIO 2")
ADMIN = entidade(CNPJ_ADMIN)
CUSTODIANTE = entidade(CNPJ_CUSTODIANTE)
GESTORA = entidade(CNPJ_GESTORA)
PRESTADORAS = {
    CNPJ_ADMIN: ADMIN,
    CNPJ_CUSTODIANTE: CUSTODIANTE,
    CNPJ_GESTORA: GESTORA,
}


def papel(role, cnpj, party_observation_id, nome="PRESTADORA FICTÍCIA"):
    return FundosPartyLink(
        role=role,
        cnpj=cnpj,
        name=nome,
        party_observation_id=party_observation_id,
    )


def assunto(*parties, **muda):
    valores = {
        "cnpj": CNPJ_FUNDO,
        "source_table": "funds",
        "source_id": 1,
        "names": ("FUNDO FICTÍCIO",),
        "situacoes": (NORMAL,),
        "tipos_fundo": ("FIDC",),
        "tipos_classe": (),
        "tipos_pessoa_gestor": ("PJ",),
        "parties": tuple(parties),
    }
    valores.update(muda)
    return FundosSubjectRecord(**valores)


def retrato(complete=True, inicio=INICIO, competencia=date(2026, 10, 27), coleta=7):
    return CadastroSnapshot(
        reference_date=competencia,
        collection_run_id=coleta,
        started_at=inicio,
        complete=complete,
        funds_in_table=1,
        classes_in_table=0,
        funds_read=1,
        classes_read=0,
        classes_same_cnpj=0,
        classes_other_fund_cnpj=0,
        classes_only_class=0,
        classes_of_fund_without_data=0,
        subjects=(assunto(),),
    )


RETRATO = retrato()
RETRATO_INCOMPLETO = retrato(complete=False)
RETRATO_NOVO = retrato(inicio=INICIO_NOVO, competencia=date(2026, 11, 26), coleta=8)


def pontas(tipo, prestadora, fundo=FUNDO):
    if tipo is MANAGES:
        return prestadora.entity_id, fundo.entity_id

    return fundo.entity_id, prestadora.entity_id


def par(tipo=ADMINISTERED_BY, prestadora=ADMIN, linha=10):
    return RelationPair(tipo, *pontas(tipo, prestadora), linha)


def gravada(
    tipo=ADMINISTERED_BY,
    prestadora=ADMIN,
    status=ACTIVE,
    nossa=True,
    relationship_id=None,
    valid_from=R_ANTIGO,
    valid_to=None,
    fundo=FUNDO,
):
    origem, destino = pontas(tipo, prestadora, fundo)
    proveniencia = (
        adaptador.relationship_provenance(RETRATO, 10) if nossa else proveniencia_manual()
    )
    return EntityRelationship(
        relationship_id=relationship_id or adaptador.relationship_id(origem, tipo, destino),
        source_entity_id=origem,
        target_entity_id=destino,
        relationship_type=tipo,
        provenance=proveniencia,
        status=status,
        valid_from=valid_from,
        valid_to=valid_to,
        confidence_score=90,
        notes="nota ficticia",
        created_at=CRIADA_EM,
    )


def decidir(pares=(), guardadas=(), snapshot=RETRATO):
    return classify(FUNDO.entity_id, FundPairs(pairs=tuple(pares)), guardadas, snapshot, adaptador)


# --- collect_pairs ---


def test_tres_papeis_dao_tres_pares_nas_direcoes_certas():
    resultado = collect_pairs(
        assunto(
            papel("administrador", CNPJ_ADMIN, 10),
            papel("custodiante", CNPJ_CUSTODIANTE, 11),
            papel("gestor", CNPJ_GESTORA, 12),
        ),
        FUNDO,
        PRESTADORAS,
        adaptador,
    )
    por_tipo = {
        item.relationship_type: (
            item.source_entity_id,
            item.target_entity_id,
            item.party_observation_id,
        )
        for item in resultado.pairs
    }

    assert por_tipo == {
        ADMINISTERED_BY: (FUNDO.entity_id, ADMIN.entity_id, 10),
        CUSTODIED_BY: (FUNDO.entity_id, CUSTODIANTE.entity_id, 11),
        MANAGES: (GESTORA.entity_id, FUNDO.entity_id, 12),
    }
    assert resultado.skipped == ()


def test_par_repetido_vira_um_com_a_menor_linha():
    resultado = collect_pairs(
        assunto(
            papel("administrador", CNPJ_ADMIN, 30),
            papel("administrador", com_mascara(CNPJ_ADMIN), 20),
            papel("custodiante", CNPJ_CUSTODIANTE, 41),
            papel("custodiante", CNPJ_CUSTODIANTE, 40),
        ),
        FUNDO,
        PRESTADORAS,
        adaptador,
    )

    chaves = [item.canonical_key for item in resultado.pairs]

    assert {
        (item.relationship_type, item.party_observation_id)
        for item in resultado.pairs
    } == {(ADMINISTERED_BY, 20), (CUSTODIED_BY, 40)}
    assert len(resultado.pairs) == 2
    assert chaves == sorted(chaves)


def test_prestadora_sem_entidade_conta_uma_vez_por_tipo_e_prestadora():
    resultado = collect_pairs(
        assunto(
            papel("administrador", CNPJ_SEM_ENTIDADE, 1),
            papel("administrador", CNPJ_SEM_ENTIDADE, 2),
            papel("custodiante", dv_errado(CNPJ_CUSTODIANTE), 3),
            papel("gestor", CNPJ_SEM_ENTIDADE, 4),
        ),
        FUNDO,
        PRESTADORAS,
        adaptador,
    )

    assert resultado.pairs == ()
    assert resultado.skipped == (
        SkippedPair(ADMINISTERED_BY, PairSkip.PRESTADORA_SEM_ENTIDADE),
        SkippedPair(CUSTODIED_BY, PairSkip.PRESTADORA_SEM_ENTIDADE),
        SkippedPair(MANAGES, PairSkip.PRESTADORA_SEM_ENTIDADE),
    )


def test_autorrelacao_nao_vira_par():
    resultado = collect_pairs(
        assunto(
            papel("administrador", CNPJ_FUNDO, 1),
            papel("custodiante", CNPJ_CUSTODIANTE, 2),
        ),
        FUNDO,
        {**PRESTADORAS, CNPJ_FUNDO: FUNDO},
        adaptador,
    )

    assert [item.relationship_type for item in resultado.pairs] == [CUSTODIED_BY]
    assert resultado.skipped == (SkippedPair(ADMINISTERED_BY, PairSkip.AUTORRELACAO),)


def test_gestor_pessoa_fisica_nao_gera_relacao():
    resultado = collect_pairs(
        assunto(
            papel("administrador", CNPJ_ADMIN, 1),
            papel("custodiante", CNPJ_CUSTODIANTE, 2),
            tipos_pessoa_gestor=("PF",),
        ),
        FUNDO,
        PRESTADORAS,
        adaptador,
    )

    assert {item.relationship_type for item in resultado.pairs} == {
        ADMINISTERED_BY,
        CUSTODIED_BY,
    }
    assert resultado.skipped == ()


def test_repr_nao_mostra_cnpj_nome_nem_id_de_entidade():
    resultado = collect_pairs(
        assunto(
            papel("administrador", CNPJ_ADMIN, 1),
            papel("gestor", CNPJ_SEM_ENTIDADE, 2),
        ),
        FUNDO,
        PRESTADORAS,
        adaptador,
    )
    decisoes = decidir(resultado.pairs, [gravada(CUSTODIED_BY, CUSTODIANTE)])
    texto = repr(resultado) + repr(decisoes)

    for proibido in (
        CNPJ_FUNDO,
        CNPJ_ADMIN,
        CNPJ_CUSTODIANTE,
        CNPJ_SEM_ENTIDADE,
        "FICTÍCI",
        str(FUNDO.entity_id),
        str(ADMIN.entity_id),
        str(CUSTODIANTE.entity_id),
    ):
        assert proibido not in texto


# --- classify ---


def test_criada_e_mantida():
    decisoes = decidir(
        [par(ADMINISTERED_BY, ADMIN, 10), par(CUSTODIED_BY, CUSTODIANTE, 11)],
        [gravada(ADMINISTERED_BY, ADMIN)],
    )
    por_tipo = {item.relationship_type: item.outcome for item in decisoes}

    assert por_tipo == {
        ADMINISTERED_BY: RelationOutcome.MANTIDA,
        CUSTODIED_BY: RelationOutcome.CRIADA,
    }


def test_reaberta_quando_a_nossa_inativa_volta():
    (decisao,) = decidir([par()], [gravada(status=INACTIVE, valid_to=R)])

    assert decisao.outcome is RelationOutcome.REABERTA


@pytest.mark.parametrize("status", [ACTIVE, INACTIVE, *OUTROS_STATUS])
def test_outra_fonte_presente_fica_intacta(status):
    (decisao,) = decidir([par()], [gravada(status=status, nossa=False)])

    assert decisao.outcome is RelationOutcome.OUTRA_FONTE_PRESENTE
    assert relationship_to_save(decisao, RETRATO, adaptador) is None


def test_fechada_com_leitura_completa():
    (decisao,) = decidir([], [gravada()])

    assert decisao.outcome is RelationOutcome.FECHADA


def test_fechamento_suspenso_com_leitura_incompleta():
    (decisao,) = decidir([], [gravada()], snapshot=RETRATO_INCOMPLETO)

    assert decisao.outcome is RelationOutcome.FECHAMENTO_SUSPENSO
    assert relationship_to_save(decisao, RETRATO_INCOMPLETO, adaptador) is None


def test_inativa_ausente_fica_intacta():
    (decisao,) = decidir([], [gravada(status=INACTIVE, valid_to=R)])

    assert decisao.outcome is RelationOutcome.INATIVA_AUSENTE


@pytest.mark.parametrize("status", [ACTIVE, INACTIVE, *OUTROS_STATUS])
def test_outra_fonte_ausente_fica_intacta(status):
    (decisao,) = decidir([], [gravada(status=status, nossa=False)])

    assert decisao.outcome is RelationOutcome.OUTRA_FONTE_AUSENTE
    assert relationship_to_save(decisao, RETRATO, adaptador) is None


@pytest.mark.parametrize("status", OUTROS_STATUS)
@pytest.mark.parametrize("lido", [True, False])
def test_status_inesperado_na_nossa_fica_intacta(status, lido):
    (decisao,) = decidir([par()] if lido else [], [gravada(status=status)])

    assert decisao.outcome is RelationOutcome.STATUS_INESPERADO
    assert (decisao.pair is not None) is lido
    assert decisao.stored is not None
    assert decisao.operation is None
    assert relationship_to_save(decisao, RETRATO, adaptador) is None


def test_issues_e_direcao_trocada_sao_ignoradas():
    issues = EntityRelationship(
        source_entity_id=FUNDO.entity_id,
        target_entity_id=OUTRO_FUNDO.entity_id,
        relationship_type=RelationshipType.ISSUES,
        provenance=adaptador.relationship_provenance(RETRATO, 1),
        status=ACTIVE,
        created_at=CRIADA_EM,
    )
    fundo_como_administrador = gravada(ADMINISTERED_BY, FUNDO, fundo=OUTRO_FUNDO)
    fundo_como_gestor = gravada(MANAGES, FUNDO, fundo=OUTRO_FUNDO)

    assert decidir([], [issues, fundo_como_administrador, fundo_como_gestor]) == ()


def test_saida_estavel_lidos_e_depois_ausentes():
    decisoes = decidir(
        [par(CUSTODIED_BY, CUSTODIANTE, 2), par(ADMINISTERED_BY, ADMIN, 1)],
        [gravada(MANAGES, GESTORA)],
    )
    chaves_lidas = sorted(
        [
            par(CUSTODIED_BY, CUSTODIANTE).canonical_key,
            par(ADMINISTERED_BY, ADMIN).canonical_key,
        ]
    )

    assert [item.pair.canonical_key for item in decisoes[:2]] == chaves_lidas
    assert decisoes[2].outcome is RelationOutcome.FECHADA
    assert decisoes[2].relationship_type is MANAGES


def test_chave_repetida_nas_gravadas_e_erro():
    with pytest.raises(ValueError, match="Chave canonica repetida"):
        decidir([], [gravada(), gravada(relationship_id=uuid4())])


@pytest.mark.parametrize(
    ("pares", "mensagem"),
    [
        ([par(), par(linha=11)], "Par repetido"),
        (
            [RelationPair(ADMINISTERED_BY, OUTRO_FUNDO.entity_id, ADMIN.entity_id, 1)],
            "Par de outro fundo",
        ),
    ],
)
def test_par_invalido_para_o_fundo_e_erro(pares, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        decidir(pares, [])


# --- relationship_to_save ---


def test_criada_monta_relacao_nova_com_a_linha():
    (decisao,) = decidir([par(CUSTODIED_BY, CUSTODIANTE, 33)], [])
    relacao = relationship_to_save(decisao, RETRATO, adaptador)

    assert relacao.relationship_id == uuid5(
        NAMESPACE_URL,
        par(CUSTODIED_BY, CUSTODIANTE).canonical_key,
    )
    assert relacao.status is ACTIVE
    assert relacao.valid_from == R
    assert relacao.valid_to is None
    assert relacao.created_at == INICIO
    assert relacao.provenance.source_reference == "fundos:party_observations:33"
    assert decisao.operation is RelationOperation.CRIAR


def test_c3_reaberta_preserva_id_e_created_at_e_troca_a_proveniencia():
    guardada = gravada(status=INACTIVE, valid_from=R_ANTIGO, valid_to=R)
    (decisao,) = decidir([par(linha=40)], [guardada], snapshot=RETRATO_NOVO)

    relacao = relationship_to_save(decisao, RETRATO_NOVO, adaptador)

    assert relacao.relationship_id == guardada.relationship_id
    assert relacao.created_at == CRIADA_EM
    assert relacao.status is ACTIVE
    assert relacao.valid_to is None
    assert relacao.valid_from == R_NOVO
    assert relacao.provenance.collected_at == INICIO_NOVO
    assert relacao.provenance.reference_date == R_NOVO
    assert relacao.provenance.source_reference == "fundos:party_observations:40"
    assert (relacao.confidence_score, relacao.notes) == (90, "nota ficticia")
    assert decisao.operation is RelationOperation.REABRIR


def test_c1_fechada_preserva_id_e_created_at_e_poe_valid_to():
    guardada = gravada(valid_from=R_ANTIGO)
    (decisao,) = decidir([], [guardada], snapshot=RETRATO_NOVO)

    relacao = relationship_to_save(decisao, RETRATO_NOVO, adaptador)

    assert relacao.relationship_id == guardada.relationship_id
    assert relacao.created_at == CRIADA_EM
    assert relacao.status is INACTIVE
    assert relacao.valid_from == R_ANTIGO
    assert relacao.valid_to == R_NOVO
    assert relacao.provenance.source_reference == "fundos:collection_runs:8"
    assert relacao.provenance.collected_at == INICIO_NOVO
    assert relacao.provenance.reference_date == R_NOVO
    assert (relacao.confidence_score, relacao.notes) == (90, "nota ficticia")
    assert decisao.operation is RelationOperation.FECHAR


def test_fechar_com_r_igual_ao_valid_from_e_permitido():
    (decisao,) = decidir([], [gravada(valid_from=R)])

    relacao = relationship_to_save(decisao, RETRATO, adaptador)

    assert relacao.valid_to == relacao.valid_from == R


def test_fechar_com_r_anterior_ao_valid_from_e_recusado_pelo_modelo():
    (decisao,) = decidir([], [gravada(valid_from=R_NOVO)])

    with pytest.raises(EntityValidationError):
        relationship_to_save(decisao, RETRATO, adaptador)


@pytest.mark.parametrize(
    "outcome",
    [
        RelationOutcome.MANTIDA,
        RelationOutcome.OUTRA_FONTE_PRESENTE,
        RelationOutcome.FECHAMENTO_SUSPENSO,
        RelationOutcome.INATIVA_AUSENTE,
        RelationOutcome.OUTRA_FONTE_AUSENTE,
        RelationOutcome.STATUS_INESPERADO,
    ],
)
def test_resultados_que_nao_gravam_dao_none(outcome):
    com_par = outcome in (
        RelationOutcome.MANTIDA,
        RelationOutcome.OUTRA_FONTE_PRESENTE,
    )
    decisao = RelationDecision(
        outcome,
        ADMINISTERED_BY,
        pair=par() if com_par else None,
        stored=gravada(),
    )

    assert relationship_to_save(decisao, RETRATO, adaptador) is None


# --- RelationDecision: coerencia e operacao ---


@pytest.mark.parametrize(
    ("outcome", "com_par", "com_gravada"),
    [
        (RelationOutcome.CRIADA, False, False),
        (RelationOutcome.CRIADA, True, True),
        (RelationOutcome.FECHADA, True, True),
        (RelationOutcome.FECHADA, False, False),
        (RelationOutcome.OUTRA_FONTE_AUSENTE, True, True),
        (RelationOutcome.MANTIDA, True, False),
        (RelationOutcome.REABERTA, False, True),
        (RelationOutcome.STATUS_INESPERADO, True, False),
        (RelationOutcome.STATUS_INESPERADO, False, False),
    ],
)
def test_resultado_incoerente_e_recusado(outcome, com_par, com_gravada):
    with pytest.raises(ValueError, match="incoerente"):
        RelationDecision(
            outcome,
            ADMINISTERED_BY,
            pair=par() if com_par else None,
            stored=gravada() if com_gravada else None,
        )


@pytest.mark.parametrize("com_par", [True, False])
def test_status_inesperado_aceita_com_e_sem_par(com_par):
    decisao = RelationDecision(
        RelationOutcome.STATUS_INESPERADO,
        ADMINISTERED_BY,
        pair=par() if com_par else None,
        stored=gravada(status=RelationshipStatus.DISPUTED),
    )

    assert decisao.operation is None


def test_tipo_do_resultado_igual_ao_do_par_e_da_gravada():
    with pytest.raises(ValueError, match="tipo do resultado"):
        RelationDecision(RelationOutcome.CRIADA, CUSTODIED_BY, pair=par())

    with pytest.raises(ValueError, match="tipo do resultado"):
        RelationDecision(RelationOutcome.FECHADA, MANAGES, stored=gravada())


@pytest.mark.parametrize(
    ("outcome", "com_par", "com_gravada", "esperado"),
    [
        (RelationOutcome.CRIADA, True, False, RelationOperation.CRIAR),
        (RelationOutcome.REABERTA, True, True, RelationOperation.REABRIR),
        (RelationOutcome.FECHADA, False, True, RelationOperation.FECHAR),
        (RelationOutcome.MANTIDA, True, True, None),
        (RelationOutcome.OUTRA_FONTE_PRESENTE, True, True, None),
        (RelationOutcome.FECHAMENTO_SUSPENSO, False, True, None),
        (RelationOutcome.INATIVA_AUSENTE, False, True, None),
        (RelationOutcome.OUTRA_FONTE_AUSENTE, False, True, None),
        (RelationOutcome.STATUS_INESPERADO, True, True, None),
        (RelationOutcome.STATUS_INESPERADO, False, True, None),
    ],
)
def test_operation_de_cada_resultado(outcome, com_par, com_gravada, esperado):
    decisao = RelationDecision(
        outcome,
        ADMINISTERED_BY,
        pair=par() if com_par else None,
        stored=gravada() if com_gravada else None,
    )

    assert decisao.operation == esperado


@pytest.mark.parametrize(
    "campos",
    [
        {"relationship_type": RelationshipType.ISSUES},
        {"party_observation_id": 0},
        {"party_observation_id": True},
        {"target_entity_id": FUNDO.entity_id},
    ],
)
def test_par_recusa_valor_invalido(campos):
    valores = {
        "relationship_type": ADMINISTERED_BY,
        "source_entity_id": FUNDO.entity_id,
        "target_entity_id": ADMIN.entity_id,
        "party_observation_id": 1,
    }
    valores.update(campos)

    with pytest.raises((TypeError, ValueError)):
        RelationPair(**valores)


# --- C6: relacao gravada com outro relationship_id (SQLite em tmp_path) ---


@pytest.fixture
def repositorios(tmp_path):
    manager = SQLiteConnectionManager(tmp_path / "destino" / "camada.sqlite3")
    entidades = SQLiteEntityRepository(manager)
    relacoes = SQLiteRelationshipRepository(manager)
    entidades.save(FUNDO)
    entidades.save(ADMIN)
    return relacoes


def test_c6_relacao_de_outra_fonte_com_outro_id_nao_e_gravada(repositorios):
    relacoes = repositorios
    manual = gravada(nossa=False, relationship_id=uuid4())
    relacoes.save(manual)
    pares = [par(linha=10)]

    (decisao,) = decidir(pares, relacoes.list_by_source(FUNDO.entity_id))

    assert decisao.outcome is RelationOutcome.OUTRA_FONTE_PRESENTE
    assert relationship_to_save(decisao, RETRATO, adaptador) is None

    # Contraste: gravar o uuid5 do par conflitaria com a relacao de outra fonte.
    nova = relationship_to_save(
        RelationDecision(RelationOutcome.CRIADA, ADMINISTERED_BY, pair=pares[0]),
        RETRATO,
        adaptador,
    )

    with pytest.raises(DuplicateRelationshipError):
        relacoes.save(nova)

    lida = relacoes.get_by_id(manual.relationship_id)

    assert relacoes.count() == 1
    assert lida.provenance.source_type is SourceType.MANUAL
    assert lida.status is ACTIVE


def test_c6_relacao_nossa_com_outro_id_e_reutilizada_por_replace(repositorios):
    relacoes = repositorios
    nossa = gravada(status=INACTIVE, relationship_id=uuid4(), valid_to=R)
    relacoes.save(nossa)

    (decisao,) = decidir(
        [par(linha=40)],
        relacoes.list_by_source(FUNDO.entity_id),
        snapshot=RETRATO_NOVO,
    )

    assert decisao.outcome is RelationOutcome.REABERTA

    relacoes.save(relationship_to_save(decisao, RETRATO_NOVO, adaptador))
    lida = relacoes.get_by_id(nossa.relationship_id)

    assert relacoes.count() == 1
    assert lida.relationship_id == nossa.relationship_id
    assert lida.relationship_id != adaptador.relationship_id(
        FUNDO.entity_id,
        ADMINISTERED_BY,
        ADMIN.entity_id,
    )
    assert lida.created_at == CRIADA_EM
    assert lida.status is ACTIVE
    assert lida.valid_to is None
    assert lida.valid_from == R_NOVO
    assert lida.provenance.source_reference == "fundos:party_observations:40"
