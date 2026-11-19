"""Testes das regras de INVESTS_IN a partir do CDA (FU7.2, PR C, commit 1).

Funcoes puras, sem banco: records e entidades montados direto. So CNPJs
ficticios de cnpj_amostras e nomes marcados como ficticios. Os nomes dos
testes trazem o codigo do plano (IR1 a IR13).
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
from pense_alm.shared.integration.fundos_adapter import (
    FundosAdapter,
    FundosAdapterError,
)
from pense_alm.shared.persistence.serialization import provenance_id

from ..cnpj_amostras import cnpj_ficticio


CNPJ_DETENTOR = cnpj_ficticio(1)
CNPJ_INVESTIDO = cnpj_ficticio(2)

SETEMBRO = date(2026, 9, 30)
OUTUBRO = date(2026, 10, 31)
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
