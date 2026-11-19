"""Testes das regras de INVESTS_IN a partir do CDA (FU7.2, PR C, commit 1).

Funcoes puras, sem banco: records e entidades montados direto. So CNPJs
ficticios de cnpj_amostras e nomes marcados como ficticios. Os nomes dos
testes trazem o codigo do plano (IR1 a IR13).
"""

from collections import Counter
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

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
from pense_alm.shared.integration.fundos_adapter import (
    FundosAdapter,
    FundosAdapterError,
)
from pense_alm.shared.integration.fundos_investment_rules import (
    HolderPairs,
    HolderReading,
    InvestmentDecision,
    InvestmentPair,
    InvestmentSkip,
    classify_investments,
    collect_investment_pairs,
    investment_to_save,
)
from pense_alm.shared.integration.fundos_records import CdaHoldingLink
from pense_alm.shared.integration.fundos_relation_rules import (
    RelationOperation,
    RelationOutcome,
    operation_for,
)
from pense_alm.shared.persistence.serialization import provenance_id

from ..cnpj_amostras import cnpj_ficticio, com_mascara, dv_errado


INVESTS_IN = RelationshipType.INVESTS_IN
ACTIVE = RelationshipStatus.ACTIVE
INACTIVE = RelationshipStatus.INACTIVE
OUTROS_STATUS = (
    RelationshipStatus.PENDING_REVIEW,
    RelationshipStatus.DISPUTED,
    RelationshipStatus.UNKNOWN,
)
O = RelationOutcome

CNPJ_DETENTOR = cnpj_ficticio(1)
CNPJ_INVESTIDO = cnpj_ficticio(2)
CNPJ_INVESTIDO_2 = cnpj_ficticio(3)
CNPJ_EMPRESA = cnpj_ficticio(4)
CNPJ_PRESTADORA = cnpj_ficticio(5)
CNPJ_FORA = cnpj_ficticio(6)
CNPJ_INVESTIDO_3 = cnpj_ficticio(7)

AGOSTO = date(2026, 8, 31)
SETEMBRO = date(2026, 9, 30)
OUTUBRO = date(2026, 10, 31)
NOVEMBRO = date(2026, 11, 30)
CRIADA_EM = datetime(2026, 9, 29, 12, tzinfo=UTC)
COLETA_SET = datetime(2026, 10, 29, 12, tzinfo=UTC)
COLETA_OUT = datetime(2026, 11, 28, 12, tzinfo=UTC)

adaptador = FundosAdapter()


def meia_noite(dia):
    return datetime(dia.year, dia.month, dia.day, tzinfo=UTC)


def proveniencia_manual():
    return DataProvenance(
        source_type=SourceType.MANUAL,
        source_name="Teste ficticio",
        collected_at=COLETA_SET,
    )


def proveniencia_cadastro(referencia=SETEMBRO):
    return DataProvenance(
        source_type=SourceType.CVM,
        source_name="Fundos - CVM Cadastro",
        source_reference="fundos:party_observations:5",
        collected_at=COLETA_SET,
        reference_date=meia_noite(referencia),
    )


def entidade(cnpj, tipo=EntityType.FIDC, nome="FUNDO FICTICIO"):
    proveniencia = proveniencia_manual()
    return Entity(
        entity_id=adaptador.entity_id(cnpj),
        legal_name=nome,
        entity_type=tipo,
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
        created_at=COLETA_SET,
        updated_at=COLETA_SET,
    )


DETENTOR = entidade(CNPJ_DETENTOR)
INVESTIDO = entidade(CNPJ_INVESTIDO)
INVESTIDO_2 = entidade(CNPJ_INVESTIDO_2, EntityType.FIAGRO)
INVESTIDO_3 = entidade(CNPJ_INVESTIDO_3)
EMPRESA = entidade(CNPJ_EMPRESA, EntityType.COMPANY, "EMPRESA FICTICIA")
PRESTADORA = entidade(CNPJ_PRESTADORA, EntityType.FINANCIAL_INSTITUTION, "PRESTADORA FICTICIA")
NA_CAMADA = {
    entity.identifiers[0].value: entity
    for entity in (DETENTOR, INVESTIDO, INVESTIDO_2, INVESTIDO_3, EMPRESA, PRESTADORA)
}


def linha(cnpj=CNPJ_INVESTIDO, holding_id=10, coleta=COLETA_OUT):
    return CdaHoldingLink(investee_cnpj=cnpj, holding_id=holding_id, collected_at=coleta)


def leitura(competencia=OUTUBRO, completa=True, confidencial=False):
    return HolderReading(
        competence=competencia,
        complete=completa,
        has_confidential=confidencial,
        closing_run_id=8,
        closing_collected_at=COLETA_OUT,
    )


def par(investido=INVESTIDO, holding_id=10, competencia=OUTUBRO, coleta=COLETA_OUT):
    return InvestmentPair(DETENTOR.entity_id, investido.entity_id, holding_id, competencia, coleta)


def gravada(
    investido=INVESTIDO,
    status=ACTIVE,
    fonte="cda",
    valid_from=None,
    valid_to=None,
    referencia=SETEMBRO,
    relationship_id=None,
):
    origem, destino = DETENTOR.entity_id, investido.entity_id
    proveniencia = {
        "cda": lambda: adaptador.holding_provenance(referencia, COLETA_SET, 5),
        "cadastro": lambda: proveniencia_cadastro(referencia),
        "manual": proveniencia_manual,
    }[fonte]()
    return EntityRelationship(
        relationship_id=relationship_id or adaptador.relationship_id(origem, INVESTS_IN, destino),
        source_entity_id=origem,
        target_entity_id=destino,
        relationship_type=INVESTS_IN,
        provenance=proveniencia,
        status=status,
        valid_from=valid_from or meia_noite(SETEMBRO),
        valid_to=valid_to,
        confidence_score=90,
        notes="nota ficticia",
        created_at=CRIADA_EM,
    )


def decidir(pares=(), guardadas=(), lida=None):
    return classify_investments(
        DETENTOR.entity_id,
        HolderPairs(pairs=tuple(pares)),
        guardadas,
        lida or leitura(),
        adaptador,
    )


def unica(decisoes):
    assert len(decisoes) == 1
    return decisoes[0]


def gravar(decisao, lida=None):
    return investment_to_save(decisao, lida or leitura(), adaptador)


# --- IR1 a IR4: criar, manter, reabrir e fechar ---


def test_ir1_criada_monta_invests_in_ativa_desde_a_competencia():
    decisao = unica(decidir([par()]))
    assert decisao.outcome is O.CRIADA and decisao.stored is None
    assert decisao.operation is RelationOperation.CRIAR

    nova = gravar(decisao)
    chave = f"{DETENTOR.entity_id}:invests_in:{INVESTIDO.entity_id}"
    assert nova.relationship_type is INVESTS_IN
    assert nova.canonical_key == chave
    assert nova.relationship_id == uuid5(NAMESPACE_URL, chave)
    assert (nova.source_entity_id, nova.target_entity_id) == (DETENTOR.entity_id, INVESTIDO.entity_id)
    assert nova.status is ACTIVE and nova.valid_to is None
    assert nova.valid_from == meia_noite(OUTUBRO)
    assert nova.created_at == COLETA_OUT
    proveniencia = nova.provenance
    assert (
        proveniencia.source_type,
        proveniencia.source_name,
        proveniencia.source_reference,
        proveniencia.reference_date,
        proveniencia.collected_at,
    ) == (SourceType.CVM, "Fundos - CVM CDA", "fundos:holdings:10", meia_noite(OUTUBRO), COLETA_OUT)


def test_ir2_mantida_nao_grava():
    guardada = gravada()
    decisao = unica(decidir([par()], [guardada]))
    assert decisao.outcome is O.MANTIDA and decisao.stored is guardada
    assert decisao.operation is None
    assert gravar(decisao) is None


@pytest.mark.parametrize("relationship_id", [None, uuid4()])
def test_ir3_reaberta_preserva_id_e_created_at(relationship_id):
    guardada = gravada(
        status=INACTIVE,
        valid_from=meia_noite(AGOSTO),
        valid_to=meia_noite(SETEMBRO),
        relationship_id=relationship_id,
    )
    decisao = unica(decidir([par(holding_id=20)], [guardada]))
    assert decisao.outcome is O.REABERTA
    assert decisao.operation is RelationOperation.REABRIR

    reaberta = gravar(decisao)
    assert reaberta.relationship_id == guardada.relationship_id
    assert reaberta.created_at == CRIADA_EM
    assert reaberta.status is ACTIVE and reaberta.valid_to is None
    assert reaberta.valid_from == meia_noite(OUTUBRO)
    assert (reaberta.confidence_score, reaberta.notes) == (90, "nota ficticia")
    assert reaberta.provenance.source_reference == "fundos:holdings:20"
    assert reaberta.provenance.reference_date == meia_noite(OUTUBRO)
    assert reaberta.provenance.collected_at == COLETA_OUT


def test_ir4_fechada_com_leitura_completa_e_sem_confidencial():
    guardada = gravada()
    decisao = unica(decidir([], [guardada]))
    assert decisao.outcome is O.FECHADA and decisao.pair is None
    assert decisao.operation is RelationOperation.FECHAR

    fechada = gravar(decisao)
    assert fechada.status is INACTIVE
    assert fechada.valid_to == meia_noite(OUTUBRO)
    assert fechada.valid_from == meia_noite(SETEMBRO)
    assert fechada.relationship_id == guardada.relationship_id
    assert fechada.created_at == CRIADA_EM
    proveniencia = fechada.provenance
    assert (
        proveniencia.source_name,
        proveniencia.source_reference,
        proveniencia.reference_date,
        proveniencia.collected_at,
    ) == ("Fundos - CVM CDA", "fundos:collection_runs:8", meia_noite(OUTUBRO), COLETA_OUT)


def test_ir4_fechar_na_competencia_do_valid_from_passa():
    guardada = gravada(valid_from=meia_noite(OUTUBRO), referencia=OUTUBRO)
    fechada = gravar(unica(decidir([], [guardada])))
    assert fechada.valid_to == fechada.valid_from == meia_noite(OUTUBRO)


# --- IR5 e IR6: o que suspende o fechamento ---


@pytest.mark.parametrize("confidencial", [False, True])
def test_ir5_leitura_incompleta_suspende_o_fechamento_da_nossa_ativa(confidencial):
    decisao = unica(decidir([], [gravada()], leitura(completa=False, confidencial=confidencial)))
    assert decisao.outcome is O.FECHAMENTO_SUSPENSO
    assert decisao.operation is None
    assert gravar(decisao) is None


AUSENTES_SEM_SUSPENSAO = [
    (dict(fonte="manual"), O.OUTRA_FONTE_AUSENTE),
    (dict(fonte="cadastro"), O.OUTRA_FONTE_AUSENTE),
    (dict(status=INACTIVE, valid_from=meia_noite(AGOSTO), valid_to=meia_noite(SETEMBRO)), O.INATIVA_AUSENTE),
] + [(dict(status=status), O.STATUS_INESPERADO) for status in OUTROS_STATUS]


@pytest.mark.parametrize("campos, esperado", AUSENTES_SEM_SUSPENSAO)
@pytest.mark.parametrize("completa, confidencial", [(False, False), (False, True), (True, True)])
def test_ir5_suspensao_vale_so_para_a_nossa_ativa(campos, esperado, completa, confidencial):
    lida = leitura(completa=completa, confidencial=confidencial)
    decisao = unica(decidir([], [gravada(**campos)], lida))
    assert decisao.outcome is esperado
    assert gravar(decisao, lida) is None


def test_ir6_confidencial_nao_fecha_e_os_presentes_seguem():
    ausente = gravada(investido=INVESTIDO_2)
    presente = gravada()
    lida = leitura(confidencial=True)
    decisoes = decidir([par(), par(INVESTIDO_3, holding_id=11)], [ausente, presente], lida)
    resultado = {decisao.outcome: decisao for decisao in decisoes}
    assert set(resultado) == {O.CRIADA, O.MANTIDA, O.SUSPENSA_POR_CONFIDENCIAL}
    suspensa = resultado[O.SUSPENSA_POR_CONFIDENCIAL]
    assert suspensa.stored is ausente and suspensa.pair is None
    assert suspensa.operation is None and gravar(suspensa, lida) is None
    assert gravar(resultado[O.CRIADA], lida).target_entity_id == INVESTIDO_3.entity_id


# --- IR7 a IR9: o que fica intacto ---


@pytest.mark.parametrize("fonte", ["manual", "cadastro"])
@pytest.mark.parametrize("status", (ACTIVE, INACTIVE) + OUTROS_STATUS)
def test_ir7_outra_fonte_fica_intacta(fonte, status):
    guardada = gravada(fonte=fonte, status=status)
    presente = unica(decidir([par()], [guardada]))
    ausente = unica(decidir([], [guardada]))
    assert presente.outcome is O.OUTRA_FONTE_PRESENTE
    assert ausente.outcome is O.OUTRA_FONTE_AUSENTE
    assert gravar(presente) is None and gravar(ausente) is None


@pytest.mark.parametrize("status", OUTROS_STATUS)
def test_ir8_status_inesperado_fica_intacto(status):
    guardada = gravada(status=status)
    presente = unica(decidir([par()], [guardada]))
    ausente = unica(decidir([], [guardada]))
    assert presente.outcome is ausente.outcome is O.STATUS_INESPERADO
    assert presente.pair is not None and ausente.pair is None
    assert gravar(presente) is None and gravar(ausente) is None


@pytest.mark.parametrize("lido", [True, False])
@pytest.mark.parametrize("status", [ACTIVE, INACTIVE])
def test_ir9_referencia_posterior_a_competencia_fica_intacta(lido, status):
    guardada = gravada(status=status, referencia=NOVEMBRO)
    decisao = unica(decidir([par()] if lido else [], [guardada]))
    assert decisao.outcome is O.VIGENCIA_POSTERIOR
    assert (decisao.pair is not None) == lido
    assert decisao.operation is None and gravar(decisao) is None


@pytest.mark.parametrize("lido", [True, False])
def test_ir9_valid_from_posterior_nao_fecha_nem_gera_valid_to_anterior(lido):
    guardada = gravada(valid_from=meia_noite(NOVEMBRO), referencia=SETEMBRO)
    decisao = unica(decidir([par()] if lido else [], [guardada]))
    assert decisao.outcome is O.VIGENCIA_POSTERIOR
    assert gravar(decisao) is None


def test_ir9_a_mesma_competencia_nao_e_posterior():
    guardada = gravada(valid_from=meia_noite(OUTUBRO), referencia=OUTUBRO)
    assert unica(decidir([par()], [guardada])).outcome is O.MANTIDA


@pytest.mark.parametrize("status", OUTROS_STATUS)
def test_ir9_status_inesperado_vem_antes_da_vigencia(status):
    guardada = gravada(status=status, referencia=NOVEMBRO)
    assert unica(decidir([par()], [guardada])).outcome is O.STATUS_INESPERADO
    assert unica(decidir([], [guardada])).outcome is O.STATUS_INESPERADO


def test_ir9_outra_fonte_vem_antes_da_vigencia():
    guardada = gravada(fonte="cadastro", referencia=NOVEMBRO)
    assert unica(decidir([par()], [guardada])).outcome is O.OUTRA_FONTE_PRESENTE
    assert unica(decidir([], [guardada])).outcome is O.OUTRA_FONTE_AUSENTE


# --- IR10: pares lidos ---


def test_ir10_varias_linhas_viram_um_par_com_a_menor_e_a_direcao_do_detentor():
    linhas = [
        linha(holding_id=30, coleta=COLETA_SET),
        linha(holding_id=12),
        linha(com_mascara(CNPJ_INVESTIDO), holding_id=20, coleta=COLETA_SET),
    ]
    lidos = collect_investment_pairs(DETENTOR, linhas, NA_CAMADA, OUTUBRO)
    assert lidos.skipped == ()
    (lido,) = lidos.pairs
    assert (lido.holder_entity_id, lido.investee_entity_id) == (DETENTOR.entity_id, INVESTIDO.entity_id)
    assert (lido.holding_id, lido.competence, lido.collected_at) == (12, OUTUBRO, COLETA_OUT)
    assert lido.relationship_type is INVESTS_IN
    inverso = InvestmentPair(INVESTIDO.entity_id, DETENTOR.entity_id, 12, OUTUBRO, COLETA_OUT)
    assert inverso.canonical_key != lido.canonical_key
    assert adaptador.relationship_id(
        INVESTIDO.entity_id, INVESTS_IN, DETENTOR.entity_id
    ) != adaptador.relationship_id(DETENTOR.entity_id, INVESTS_IN, INVESTIDO.entity_id)


def test_ir10_motivos_contados_uma_vez_por_investido():
    linhas = [
        linha(dv_errado(CNPJ_INVESTIDO_2), 11),
        linha(dv_errado(CNPJ_INVESTIDO_2), 12),
        linha(CNPJ_FORA, 13),
        linha(com_mascara(CNPJ_FORA), 14),
        linha(CNPJ_EMPRESA, 15),
        linha(CNPJ_PRESTADORA, 16),
        linha(CNPJ_DETENTOR, 17),
        linha(com_mascara(CNPJ_DETENTOR), 18),
        linha(CNPJ_INVESTIDO, 19),
        linha(CNPJ_INVESTIDO_2, 20),
    ]
    lidos = collect_investment_pairs(DETENTOR, linhas, NA_CAMADA, OUTUBRO)
    assert [lido.investee_entity_id for lido in lidos.pairs] == sorted(
        [INVESTIDO.entity_id, INVESTIDO_2.entity_id],
        key=lambda entity_id: f"{DETENTOR.entity_id}:invests_in:{entity_id}",
    )
    assert Counter(item.reason for item in lidos.skipped) == {
        InvestmentSkip.CNPJ_RECUSADO: 1,
        InvestmentSkip.INVESTIDO_FORA_DA_CAMADA: 1,
        InvestmentSkip.INVESTIDO_DE_OUTRO_TIPO: 2,
        InvestmentSkip.AUTORRELACAO: 1,
    }


# --- IR11 e IR12: proveniencias e fontes ---


def test_ir11_proveniencias_do_cda():
    linha_cda = adaptador.holding_provenance(OUTUBRO, COLETA_OUT, 10)
    coleta = adaptador.cda_closing_provenance(OUTUBRO, COLETA_OUT, 8)

    for proveniencia, referencia in ((linha_cda, "fundos:holdings:10"), (coleta, "fundos:collection_runs:8")):
        assert proveniencia.source_type is SourceType.CVM
        assert proveniencia.source_name == FundosAdapter.SOURCE_NAME_CDA == "Fundos - CVM CDA"
        assert proveniencia.source_reference == referencia
        assert proveniencia.reference_date == meia_noite(OUTUBRO)
        assert proveniencia.collected_at == COLETA_OUT

    assert provenance_id(linha_cda) == provenance_id(adaptador.holding_provenance(OUTUBRO, COLETA_OUT, 10))
    assert provenance_id(coleta) == provenance_id(adaptador.cda_closing_provenance(OUTUBRO, COLETA_OUT, 8))
    assert FundosAdapter.competence_datetime(OUTUBRO) == meia_noite(OUTUBRO)


@pytest.mark.parametrize("valor", [0, -1, True, "10", 10.0])
def test_ir11_id_de_linha_ou_de_coleta_invalido_e_recusado(valor):
    with pytest.raises(FundosAdapterError):
        adaptador.holding_provenance(OUTUBRO, COLETA_OUT, valor)

    with pytest.raises(FundosAdapterError):
        adaptador.cda_closing_provenance(OUTUBRO, COLETA_OUT, valor)


@pytest.mark.parametrize("valor", [meia_noite(OUTUBRO), "2026-10-31", None])
def test_ir11_competencia_deve_ser_data(valor):
    with pytest.raises(FundosAdapterError):
        FundosAdapter.competence_datetime(valor)


@pytest.mark.parametrize("proveniencia", [proveniencia_cadastro(), proveniencia_manual()])
def test_ir11_build_investment_recusa_proveniencia_fora_do_cda(proveniencia):
    with pytest.raises(FundosAdapterError):
        adaptador.build_investment(
            DETENTOR.entity_id, INVESTIDO.entity_id, proveniencia, OUTUBRO, COLETA_OUT
        )


def test_ir12_is_cda_provenance_so_para_a_nossa():
    nossa = adaptador.holding_provenance(OUTUBRO, COLETA_OUT, 10)
    assert FundosAdapter.is_cda_provenance(nossa)
    assert not FundosAdapter.is_cda_provenance(proveniencia_cadastro())
    assert not FundosAdapter.is_cda_provenance(proveniencia_manual())
    assert not FundosAdapter.is_cadastro_provenance(nossa)


def test_ir12_classify_ignora_outros_tipos_e_a_invests_in_de_entrada():
    administrada = EntityRelationship(
        relationship_id=uuid4(),
        source_entity_id=DETENTOR.entity_id,
        target_entity_id=PRESTADORA.entity_id,
        relationship_type=RelationshipType.ADMINISTERED_BY,
        provenance=proveniencia_cadastro(),
        status=ACTIVE,
        created_at=CRIADA_EM,
    )
    de_entrada = EntityRelationship(
        relationship_id=uuid4(),
        source_entity_id=INVESTIDO.entity_id,
        target_entity_id=DETENTOR.entity_id,
        relationship_type=INVESTS_IN,
        provenance=adaptador.holding_provenance(SETEMBRO, COLETA_SET, 5),
        status=ACTIVE,
        valid_from=meia_noite(SETEMBRO),
        created_at=CRIADA_EM,
    )
    assert decidir([], [administrada, de_entrada]) == ()


# --- IR13: coerencia, repr e entradas ---


def test_ir13_formas_validas_e_operacao():
    guardada, lido = gravada(), par()
    validas = [
        (O.CRIADA, lido, None, RelationOperation.CRIAR),
        (O.MANTIDA, lido, guardada, None),
        (O.REABERTA, lido, guardada, RelationOperation.REABRIR),
        (O.OUTRA_FONTE_PRESENTE, lido, guardada, None),
        (O.FECHADA, None, guardada, RelationOperation.FECHAR),
        (O.FECHAMENTO_SUSPENSO, None, guardada, None),
        (O.SUSPENSA_POR_CONFIDENCIAL, None, guardada, None),
        (O.INATIVA_AUSENTE, None, guardada, None),
        (O.OUTRA_FONTE_AUSENTE, None, guardada, None),
        (O.STATUS_INESPERADO, lido, guardada, None),
        (O.STATUS_INESPERADO, None, guardada, None),
        (O.VIGENCIA_POSTERIOR, lido, guardada, None),
        (O.VIGENCIA_POSTERIOR, None, guardada, None),
    ]

    for resultado, com_par, com_gravada, operacao in validas:
        decisao = InvestmentDecision(resultado, pair=com_par, stored=com_gravada)
        assert decisao.operation is operacao
        assert decisao.relationship_type is INVESTS_IN

    assert operation_for(O.SUSPENSA_POR_CONFIDENCIAL) is None
    assert operation_for(O.VIGENCIA_POSTERIOR) is None


@pytest.mark.parametrize(
    "resultado, com_par, com_gravada",
    [
        (O.CRIADA, True, True),
        (O.CRIADA, False, False),
        (O.FECHADA, True, True),
        (O.SUSPENSA_POR_CONFIDENCIAL, True, True),
        (O.SUSPENSA_POR_CONFIDENCIAL, False, False),
        (O.MANTIDA, True, False),
        (O.VIGENCIA_POSTERIOR, True, False),
        (O.STATUS_INESPERADO, False, False),
    ],
)
def test_ir13_formas_incoerentes_sao_recusadas(resultado, com_par, com_gravada):
    with pytest.raises(ValueError):
        InvestmentDecision(
            resultado,
            pair=par() if com_par else None,
            stored=gravada() if com_gravada else None,
        )


def test_ir13_gravada_deve_ser_invests_in_e_da_mesma_chave():
    administrada = EntityRelationship(
        relationship_id=uuid4(),
        source_entity_id=DETENTOR.entity_id,
        target_entity_id=PRESTADORA.entity_id,
        relationship_type=RelationshipType.ADMINISTERED_BY,
        provenance=proveniencia_cadastro(),
        status=ACTIVE,
        created_at=CRIADA_EM,
    )

    with pytest.raises(ValueError):
        InvestmentDecision(O.FECHADA, stored=administrada)

    with pytest.raises(ValueError):
        InvestmentDecision(O.MANTIDA, pair=par(INVESTIDO_2), stored=gravada())

    with pytest.raises(TypeError):
        InvestmentDecision("criada", pair=par())


def test_ir13_repr_sem_cnpj_nome_nem_id():
    objetos = [
        par(),
        linha(),
        InvestmentDecision(O.MANTIDA, pair=par(), stored=gravada()),
        collect_investment_pairs(DETENTOR, [linha(), linha(CNPJ_FORA, 11)], NA_CAMADA, OUTUBRO),
    ]
    texto = " ".join(repr(objeto) for objeto in objetos)

    for proibido in (
        CNPJ_DETENTOR,
        CNPJ_INVESTIDO,
        CNPJ_FORA,
        str(DETENTOR.entity_id),
        str(INVESTIDO.entity_id),
        "FICTICIO",
    ):
        assert proibido not in texto


def test_ir13_chave_repetida_competencia_divergente_e_par_repetido():
    with pytest.raises(ValueError, match="repetida"):
        decidir([], [gravada(), gravada(relationship_id=uuid4())])

    with pytest.raises(ValueError, match="competencia"):
        decidir([par(competencia=SETEMBRO)])

    with pytest.raises(ValueError, match="repetido"):
        decidir([par(), par(holding_id=11)])

    outro = InvestmentPair(INVESTIDO.entity_id, INVESTIDO_2.entity_id, 10, OUTUBRO, COLETA_OUT)

    with pytest.raises(ValueError, match="detentor"):
        decidir([outro])


def test_ir13_entradas_invalidas_sao_recusadas():
    with pytest.raises(ValueError):
        CdaHoldingLink(investee_cnpj=" ", holding_id=1, collected_at=COLETA_OUT)

    with pytest.raises(ValueError):
        CdaHoldingLink(investee_cnpj=CNPJ_INVESTIDO, holding_id=0, collected_at=COLETA_OUT)

    with pytest.raises(ValueError):
        CdaHoldingLink(investee_cnpj=CNPJ_INVESTIDO, holding_id=1, collected_at=datetime(2026, 11, 28))

    with pytest.raises(TypeError):
        HolderReading(OUTUBRO, 1, False, 8, COLETA_OUT)

    with pytest.raises(TypeError):
        HolderReading(meia_noite(OUTUBRO), True, False, 8, COLETA_OUT)

    with pytest.raises(ValueError):
        InvestmentPair(DETENTOR.entity_id, DETENTOR.entity_id, 10, OUTUBRO, COLETA_OUT)

    with pytest.raises(TypeError):
        collect_investment_pairs(DETENTOR, ["texto"], NA_CAMADA, OUTUBRO)
