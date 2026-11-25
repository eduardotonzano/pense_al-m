import hashlib
from decimal import Decimal

import pytest

from apoio_indicadores import SyntheticInforme
from conftest import create_full_schema

from fundos.indicators.overdue import OVERDUE_TOTAL
from fundos.indicators.reading import check_field_names
from fundos.indicators.reading import open_read_only
from fundos.indicators.reducao_valor_recuperacao import OFFICIAL_NAME
from fundos.indicators.reducao_valor_recuperacao import PROVISION
from fundos.indicators.reducao_valor_recuperacao import PROVISION_WITHOUT_OVERDUE
from fundos.indicators.reducao_valor_recuperacao import REASON_NEGATIVE_OVERDUE
from fundos.indicators.reducao_valor_recuperacao import REASON_NEGATIVE_PROVISION
from fundos.indicators.reducao_valor_recuperacao import fields
from fundos.indicators.reducao_valor_recuperacao import provisao_reducao_valor_recuperacao
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCK_TOTAL
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.indicators.values import REASON_ZERO_DENOMINATOR


SEP = "2026-09-30"
AUG = "2026-08-31"


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def put(informe, subject, prov_a=None, venc_a=None, prov_b=None, venc_b=None, reference_date=SEP):
    """Grava so os valores informados (None = sem linha); valores ficticios."""

    values = {
        PROVISION[BLOCK_A]: prov_a,
        OVERDUE_TOTAL[BLOCK_A]: venc_a,
        PROVISION[BLOCK_B]: prov_b,
        OVERDUE_TOTAL[BLOCK_B]: venc_b,
    }
    informe.put(
        subject,
        {name: value for name, value in values.items() if value is not None},
        reference_date=reference_date,
    )


def only(results):
    assert len(results) == 1
    return results[0]


def state(item):
    return (item.state, item.value, item.reason)


def test_closed_list_of_fields():
    assert fields() == (
        "tab_I.TAB_I2A11_VL_REDUCAO_RECUP",
        "tab_I.TAB_I2B11_VL_REDUCAO_RECUP",
        "tab_V.TAB_V_B_VL_DIRCRED_INAD",
        "tab_VI.TAB_VI_B_VL_DIRCRED_INAD",
    )
    assert check_field_names(fields()) == fields()

    for forbidden in (
        "TAB_I2_COTA_FIDC",
        "TAB_I2_DEBENTURE_CRI",
        "TAB_I2_VL_OUTRO_ATIVO",
        "CPF",
        "CNPJ",
        "CEDENTE",
        "TAB_I2A21",
        "TAB_I2A3",
        "TAB_I2A_VL_DIRCRED",
        "inf_mensal_fiagro",
    ):
        assert not any(forbidden in name for name in fields())


def test_zero_provision_with_overdue_is_zero_percent(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="0", venc_a="50", prov_b="0", venc_b="0")

    block = only(provisao_reducao_valor_recuperacao(full_connection, SEP)).block(BLOCK_A)

    assert state(block.cobertura) == (PRESENT, Decimal("0"), None)
    assert block.flags == ()


def test_overdue_zero_keeps_the_provision_and_flags_it(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="30", venc_a="0", prov_b="0", venc_b="0")

    result = only(provisao_reducao_valor_recuperacao(full_connection, SEP))
    block_a, block_b, total = result.block(BLOCK_A), result.block(BLOCK_B), result.block(BLOCK_TOTAL)

    assert state(block_a.provisao) == (PRESENT, Decimal("30"), None)
    assert state(block_a.cobertura) == (NO_DATA, None, REASON_ZERO_DENOMINATOR)
    assert block_a.flags == (PROVISION_WITHOUT_OVERDUE,)
    assert state(block_b.cobertura) == (NO_DATA, None, REASON_ZERO_DENOMINATOR)
    assert block_b.flags == ()
    assert total.flags == (PROVISION_WITHOUT_OVERDUE,)
    assert total.provisao.value == Decimal("30")


def test_both_zero_is_zero_denominator_without_flag(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="0", venc_a="0", prov_b="0", venc_b="0")

    for block in only(provisao_reducao_valor_recuperacao(full_connection, SEP)).blocks:
        assert state(block.cobertura) == (NO_DATA, None, REASON_ZERO_DENOMINATOR)
        assert state(block.provisao) == (PRESENT, Decimal("0"), None)
        assert block.flags == ()


def test_coverage_above_100_is_not_cut(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="250", venc_a="100", prov_b="0", venc_b="0")

    block = only(provisao_reducao_valor_recuperacao(full_connection, SEP)).block(BLOCK_A)

    assert state(block.cobertura) == (PRESENT, Decimal("250"), None)
    assert block.cobertura.numerator.fields == (PROVISION[BLOCK_A],)
    assert block.cobertura.denominator.fields == (OVERDUE_TOTAL[BLOCK_A],)


def test_negative_provision_is_kept_as_informed_and_never_used(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="-5", venc_a="50", prov_b="10", venc_b="20")

    result = only(provisao_reducao_valor_recuperacao(full_connection, SEP))
    block_a, total = result.block(BLOCK_A), result.block(BLOCK_TOTAL)

    assert state(block_a.provisao) == (PRESENT, Decimal("-5"), None)
    assert state(block_a.cobertura) == (NO_DATA, None, REASON_NEGATIVE_PROVISION)
    assert state(total.provisao) == (NO_DATA, None, REASON_NEGATIVE_PROVISION)
    assert state(total.cobertura) == (NO_DATA, None, REASON_NEGATIVE_PROVISION)
    assert result.block(BLOCK_B).cobertura.value == Decimal("50")


def test_negative_overdue_is_never_used(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="10", venc_a="20", prov_b="5", venc_b="-1")

    result = only(provisao_reducao_valor_recuperacao(full_connection, SEP))

    assert state(result.block(BLOCK_B).cobertura) == (NO_DATA, None, REASON_NEGATIVE_OVERDUE)
    assert state(result.block(BLOCK_TOTAL).vencidos) == (NO_DATA, None, REASON_NEGATIVE_OVERDUE)
    assert state(result.block(BLOCK_TOTAL).cobertura) == (NO_DATA, None, REASON_NEGATIVE_OVERDUE)
    assert result.block(BLOCK_A).cobertura.value == Decimal("50")


def test_missing_field_is_no_data_never_zero(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    _, other = informe.fund_and_class(2)
    put(informe, klass, venc_a="50", prov_b="5", venc_b="10")
    put(informe, other, prov_a="5", prov_b="1", venc_b="10")

    first, second = provisao_reducao_valor_recuperacao(full_connection, SEP)

    assert state(first.block(BLOCK_A).provisao) == (NO_DATA, None, REASON_MISSING)
    assert state(first.block(BLOCK_A).cobertura) == (NO_DATA, None, REASON_MISSING)
    assert state(second.block(BLOCK_A).vencidos) == (NO_DATA, None, REASON_MISSING)
    assert state(second.block(BLOCK_A).cobertura) == (NO_DATA, None, REASON_MISSING)
    assert first.block(BLOCK_A).flags == second.block(BLOCK_A).flags == ()


def test_value_that_is_not_a_number_is_no_data(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {PROVISION[BLOCK_A]: "valor ficticio"}, value_type="text")
    put(informe, klass, venc_a="10")

    block = only(provisao_reducao_valor_recuperacao(full_connection, SEP)).block(BLOCK_A)

    assert state(block.cobertura) == (NO_DATA, None, REASON_UNEXPECTED_TYPE)
    assert "ficticio" not in repr(block)


def test_block_a_without_block_b(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="10", venc_a="40")

    result = only(provisao_reducao_valor_recuperacao(full_connection, SEP))

    assert result.block(BLOCK_A).cobertura.value == Decimal("25")
    assert state(result.block(BLOCK_B).cobertura) == (NO_DATA, None, REASON_MISSING)
    assert state(result.block(BLOCK_TOTAL).provisao) == (NO_DATA, None, REASON_MISSING)
    assert state(result.block(BLOCK_TOTAL).cobertura) == (NO_DATA, None, REASON_MISSING)


def test_both_blocks_sum_the_same_measure(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="30", venc_a="60", prov_b="10", venc_b="20")

    total = only(provisao_reducao_valor_recuperacao(full_connection, SEP)).block(BLOCK_TOTAL)

    assert total.provisao.value == Decimal("40")
    assert total.vencidos.value == Decimal("80")
    assert total.cobertura.value == Decimal("50")
    assert total.provisao.fields == (PROVISION[BLOCK_A], PROVISION[BLOCK_B])
    assert total.vencidos.fields == (OVERDUE_TOTAL[BLOCK_A], OVERDUE_TOTAL[BLOCK_B])


def test_fund_and_class_subjects_and_filter(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="10", venc_a="20", prov_b="0", venc_b="0")
    put(informe, fund, prov_a="30", venc_a="20", prov_b="0", venc_b="0")

    results = provisao_reducao_valor_recuperacao(full_connection, SEP)

    assert [r.subject for r in results] == [klass, fund]
    assert [r.block(BLOCK_A).cobertura.value for r in results] == [Decimal("50"), Decimal("150")]
    assert [r.name for r in results] == [OFFICIAL_NAME, OFFICIAL_NAME]
    assert [r.subject for r in provisao_reducao_valor_recuperacao(full_connection, SEP, [fund])] == [fund]
    assert provisao_reducao_valor_recuperacao(full_connection, SEP, []) == ()


def test_each_competence_on_its_own(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="10", venc_a="20", reference_date=AUG)
    put(informe, klass, venc_a="40", reference_date=SEP)

    september = only(provisao_reducao_valor_recuperacao(full_connection, SEP)).block(BLOCK_A)
    august = only(provisao_reducao_valor_recuperacao(full_connection, AUG)).block(BLOCK_A)

    assert state(september.provisao) == (NO_DATA, None, REASON_MISSING)
    assert august.cobertura.value == Decimal("50")


def test_other_provisions_change_nothing(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="10", venc_a="20", prov_b="1", venc_b="2")
    before = provisao_reducao_valor_recuperacao(full_connection, SEP)

    informe.put(
        klass,
        {
            "tab_I.TAB_I2_COTA_FIDC": "999",
            "tab_I.TAB_I2_DEBENTURE_CRI": "888",
            "tab_I.TAB_I2_VL_OUTRO_ATIVO": "777",
            "tab_I.TAB_I2A21_VL_TOTAL_PARCELA_INAD": "6",
            "tab_I.TAB_I2A3_VL_CRED_INAD": "14",
        },
    )

    assert provisao_reducao_valor_recuperacao(full_connection, SEP) == before


def test_cnpj_never_shows_in_repr(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    put(informe, klass, prov_a="10", venc_a="20", prov_b="0", venc_b="0")
    put(informe, fund, prov_a="10", venc_a="20", prov_b="0", venc_b="0")

    for result in provisao_reducao_valor_recuperacao(full_connection, SEP):
        assert result.subject.cnpj not in repr(result)
        assert result.subject.cnpj not in str(result)


def test_reading_through_open_read_only_leaves_the_file_unchanged(tmp_path):
    path = tmp_path / "fundos.db"
    writer = create_full_schema(path).connect()

    try:
        informe = SyntheticInforme(writer)
        _, klass = informe.fund_and_class(1)
        put(informe, klass, prov_a="10", venc_a="20", prov_b="0", venc_b="0")
    finally:
        writer.close()

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = open_read_only(path)

    try:
        assert only(provisao_reducao_valor_recuperacao(connection, SEP)).block(BLOCK_A).cobertura.value == Decimal("50")
        assert connection.in_transaction is False
    finally:
        connection.close()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fundos.db"]
