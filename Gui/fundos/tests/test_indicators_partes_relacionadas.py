from decimal import Decimal

import pytest

from apoio_indicadores import SyntheticInforme

from fundos.indicators.partes_relacionadas import GROUPS
from fundos.indicators.partes_relacionadas import alienacoes_partes_relacionadas
from fundos.indicators.partes_relacionadas import fields
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING


SEP = "2026-09-30"
AUG = "2026-08-31"

B1 = {
    "Quantidade": "tab_VII.TAB_VII_B1_1_QT_CEDENTE",
    "Valor": "tab_VII.TAB_VII_B1_2_VL_CEDENTE",
    "Valor Contabil": "tab_VII.TAB_VII_B1_3_VL_CONTAB_CEDENTE",
}
B2 = {
    "Quantidade": "tab_VII.TAB_VII_B2_1_QT_PREST",
    "Valor": "tab_VII.TAB_VII_B2_2_VL_PREST",
    "Valor Contabil": "tab_VII.TAB_VII_B2_3_VL_CONTAB_PREST",
}


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def test_only_the_sales_to_related_parties_are_read():
    assert fields() == tuple(B1.values()) + tuple(B2.values())
    assert [item for item, _, _ in GROUPS] == ["VII.b.1", "VII.b.2"]
    assert GROUPS[0][1] == "Alienacoes para o Cedente e Partes Relacionadas aos Cedentes"
    assert GROUPS[1][1] == (
        "Alienacoes para os Prestadores de Servicos e Partes Relacionadas aos Prestadores de Servicos"
    )

    for prefix in ("TAB_VII_A", "TAB_VII_B3", "TAB_VII_C", "TAB_VII_D"):
        assert not any(name.split(".")[1].startswith(prefix) for name in fields())


def test_values_as_informed_with_real_zero_and_missing_field(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    ids = informe.put(
        klass,
        {B1["Quantidade"]: "3", B1["Valor"]: "1500.25", B1["Valor Contabil"]: "1400", B2["Quantidade"]: "0"},
    )

    [result] = alienacoes_partes_relacionadas(full_connection, SEP)
    b1, b2 = result.group("VII.b.1"), result.group("VII.b.2")

    assert (result.subject, result.reference_date) == (klass, SEP)
    assert [label for label, _ in b1.values] == ["Quantidade", "Valor", "Valor Contabil"]
    assert [v.value for _, v in b1.values] == [Decimal("3"), Decimal("1500.25"), Decimal("1400")]
    assert b1.value("Valor").observation_id == ids[B1["Valor"]]
    assert (b2.value("Quantidade").state, b2.value("Quantidade").value) == (PRESENT, Decimal("0"))
    assert (b2.value("Valor").state, b2.value("Valor").value, b2.value("Valor").reason) == (NO_DATA, None, REASON_MISSING)


def test_other_tab_vii_rows_are_never_read(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(
        klass,
        {
            "tab_VII.TAB_VII_A1_2_VL_DIRCRED_RISCO": "900",
            "tab_VII.TAB_VII_B3_2_VL_TERCEIRO": "800",
            "tab_VII.TAB_VII_C_2_VL_SUBST": "700",
            "tab_VII.TAB_VII_D_2_VL_RECOMPRA": "600",
        },
    )

    assert alienacoes_partes_relacionadas(full_connection, SEP) == ()


def test_each_competence_and_subject_filter(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    informe.put(klass, {B1["Valor"]: "10"}, reference_date=AUG)
    informe.put(klass, {B1["Valor"]: "20"}, reference_date=SEP)
    informe.put(fund, {B2["Valor"]: "30"}, reference_date=SEP)

    september = alienacoes_partes_relacionadas(full_connection, SEP)
    august = alienacoes_partes_relacionadas(full_connection, AUG, [klass])

    assert [r.subject for r in september] == [klass, fund]
    assert september[0].group("VII.b.1").value("Valor").value == Decimal("20")
    assert august[0].group("VII.b.1").value("Valor").value == Decimal("10")
    assert alienacoes_partes_relacionadas(full_connection, SEP, []) == ()
