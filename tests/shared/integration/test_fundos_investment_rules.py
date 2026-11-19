"""Testes das regras de INVESTS_IN a partir do CDA (FU7.2, PR C, commit 1).

Funcoes puras, sem banco: records e entidades montados direto. So CNPJs
ficticios de cnpj_amostras e nomes marcados como ficticios. Os nomes dos
testes trazem o codigo do plano (IR1 a IR13).
"""

from collections import Counter
from datetime import UTC, date, datetime
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
from pense_alm.shared.integration.fundos_adapter import (
    FundosAdapter,
    FundosAdapterError,
)
from pense_alm.shared.integration.fundos_investment_rules import (
    HolderReading,
    InvestmentDecision,
    InvestmentPair,
    InvestmentSkip,
    collect_investment_pairs,
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
O = RelationOutcome

CNPJ_DETENTOR = cnpj_ficticio(1)
CNPJ_INVESTIDO = cnpj_ficticio(2)
CNPJ_INVESTIDO_2 = cnpj_ficticio(3)
CNPJ_EMPRESA = cnpj_ficticio(4)
CNPJ_PRESTADORA = cnpj_ficticio(5)
CNPJ_FORA = cnpj_ficticio(6)
CNPJ_INVESTIDO_3 = cnpj_ficticio(7)

SETEMBRO = date(2026, 9, 30)
OUTUBRO = date(2026, 10, 31)
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
