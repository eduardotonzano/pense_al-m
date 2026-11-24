from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme

from fundos.indicators.overdue import BUCKET_FIELDS
from fundos.indicators.overdue import BUCKET_LABELS
from fundos.indicators.overdue import CREDIT_RIGHTS
from fundos.indicators.overdue import OVERDUE_TOTAL
from fundos.indicators.overdue import PORTFOLIO
from fundos.indicators.overdue import TAB_I_DETAILS
from fundos.indicators.overdue import Denominator
from fundos.indicators.overdue import bucket_evolution
from fundos.indicators.overdue import bucket_fields
from fundos.indicators.overdue import delinquency_buckets
from fundos.indicators.overdue import overdue_fields
from fundos.indicators.overdue import overdue_in_portfolio
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCK_TOTAL
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_NEGATIVE_DENOMINATOR
from fundos.indicators.values import REASON_PREVIOUS_NOT_LOADED
from fundos.indicators.values import REASON_ZERO_DENOMINATOR


SEP = "2026-09-30"
AUG = "2026-08-31"
JUL = "2026-07-31"

# Valores ficticios, so para os testes.
DEFAULT = {
    OVERDUE_TOTAL[BLOCK_A]: "30",
    OVERDUE_TOTAL[BLOCK_B]: "10",
    "tab_I.TAB_I2A2_VL_CRED_VENC_INAD": "40",
    "tab_I.TAB_I2A21_VL_TOTAL_PARCELA_INAD": "6",
    "tab_I.TAB_I2A3_VL_CRED_INAD": "24",
    "tab_I.TAB_I2B2_VL_CRED_VENC_INAD": "8",
    "tab_I.TAB_I2B21_VL_TOTAL_PARCELA_INAD": "2",
    "tab_I.TAB_I2B3_VL_CRED_INAD": "8",
    PORTFOLIO: "200",
    CREDIT_RIGHTS[BLOCK_A]: "100",
    CREDIT_RIGHTS[BLOCK_B]: "50",
}


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def put_overdue(informe, subject, reference_date=SEP, skip=(), **changes):
    values = {name: value for name, value in DEFAULT.items() if name not in skip}
    values.update({_KEYS[key]: value for key, value in changes.items()})
    return informe.put(subject, values, reference_date=reference_date)


_KEYS = {
    "overdue_a": OVERDUE_TOTAL[BLOCK_A],
    "overdue_b": OVERDUE_TOTAL[BLOCK_B],
    "portfolio": PORTFOLIO,
    "rights_a": CREDIT_RIGHTS[BLOCK_A],
    "rights_b": CREDIT_RIGHTS[BLOCK_B],
}


def put_buckets(informe, subject, block, total, buckets, reference_date=SEP, **kwargs):
    """buckets: {posicao de 1 a 10: valor}; as posicoes fora ficam sem linha."""

    values = {OVERDUE_TOTAL[block]: total} if total is not None else {}
    values.update({BUCKET_FIELDS[block][index - 1]: value for index, value in buckets.items()})
    return informe.put(subject, values, reference_date=reference_date, **kwargs)


ALL_ZERO = {index: "0" for index in range(1, 11)}


def only(results):
    assert len(results) == 1
    return results[0]


def test_fields_are_a_closed_list_without_provision_cedente_or_fiagro():
    for denominator in Denominator:
        fields = overdue_fields(denominator) + bucket_fields()

        assert not any("REDUCAO_RECUP" in name or "CEDENTE" in name for name in fields)
        assert not any(name.startswith(("inf_mensal_fiagro", "tab_IV")) for name in fields)

    assert PORTFOLIO in overdue_fields(Denominator.PORTFOLIO)
    assert CREDIT_RIGHTS[BLOCK_A] not in overdue_fields(Denominator.PORTFOLIO)
    assert set(CREDIT_RIGHTS.values()) <= set(overdue_fields(Denominator.CREDIT_RIGHTS))
    assert PORTFOLIO not in overdue_fields(Denominator.CREDIT_RIGHTS)


def test_bucket_fields_are_the_cvm_columns():
    assert BUCKET_FIELDS[BLOCK_A][0] == "tab_V.TAB_V_B1_VL_INAD_30"
    assert BUCKET_FIELDS[BLOCK_A][8] == "tab_V.TAB_V_B9_VL_INAD_1080"
    assert BUCKET_FIELDS[BLOCK_A][9] == "tab_V.TAB_V_B10_VL_INAD_MAIOR_1080"
    assert BUCKET_FIELDS[BLOCK_B][0] == "tab_VI.TAB_VI_B1_VL_INAD_30"
    assert BUCKET_FIELDS[BLOCK_B][9] == "tab_VI.TAB_VI_B10_VL_INAD_MAIOR_1080"
    assert len(BUCKET_LABELS) == len(BUCKET_FIELDS[BLOCK_A]) == len(BUCKET_FIELDS[BLOCK_B]) == 10
    assert BUCKET_LABELS[0] == "Vencidos e nao Pagos entre 1 e 30 dias"
    assert BUCKET_LABELS[9] == "Vencidos e nao Pagos acima de 1080 dias"


@pytest.mark.parametrize("denominator", ("carteira", "pl", None, "PL"))
def test_denominator_has_no_default_and_pl_is_not_an_option(informe, full_connection, denominator):
    with pytest.raises(ValueError):
        overdue_in_portfolio(full_connection, SEP, denominator)

    assert {d.name for d in Denominator} == {"PORTFOLIO", "CREDIT_RIGHTS"}


def test_two_blocks_over_the_portfolio(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass)

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))
    block_a, block_b, total = (result.block(BLOCK_A), result.block(BLOCK_B), result.block(BLOCK_TOTAL))

    assert (result.subject, result.reference_date, result.denominator) == (klass, SEP, Denominator.PORTFOLIO)
    assert (block_a.overdue.value, block_a.share.value) == (Decimal("30"), Decimal("15"))
    assert (block_b.overdue.value, block_b.share.value) == (Decimal("10"), Decimal("5"))
    assert (total.overdue.value, total.share.value) == (Decimal("40"), Decimal("20"))
    assert total.overdue.fields == (OVERDUE_TOTAL[BLOCK_A], OVERDUE_TOTAL[BLOCK_B])
    assert block_a.share.denominator.fields == total.share.denominator.fields == (PORTFOLIO,)


def test_two_blocks_over_credit_rights(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass)

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.CREDIT_RIGHTS))
    total = result.block(BLOCK_TOTAL)

    assert result.block(BLOCK_A).share.value == Decimal("30")
    assert result.block(BLOCK_B).share.value == Decimal("20")
    assert total.share.denominator.value == Decimal("150")
    assert total.share.denominator.fields == (CREDIT_RIGHTS[BLOCK_A], CREDIT_RIGHTS[BLOCK_B])
    assert str(total.share.value).startswith("26.66666666")


def test_tab_i_items_come_separately_and_are_never_summed(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    ids = put_overdue(informe, klass)

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))
    details_a = result.block(BLOCK_A).details
    details_b = result.block(BLOCK_B).details

    assert [item for item, _ in details_a] == ["a.2", "a.2.1", "a.3"]
    assert [item for item, _ in details_b] == ["b.2", "b.2.1", "b.3"]
    assert [value.value for _, value in details_a] == [Decimal("40"), Decimal("6"), Decimal("24")]
    assert [value.observation_id for _, value in details_a] == [ids[name] for _, name in TAB_I_DETAILS[BLOCK_A]]
    assert result.block(BLOCK_TOTAL).details == ()
    assert result.block(BLOCK_A).overdue.fields == (OVERDUE_TOTAL[BLOCK_A],)


def test_real_zero_is_zero_percent(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, overdue_a="0", overdue_b="0")

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))

    for block in result.blocks:
        assert (block.overdue.state, block.overdue.value) == (PRESENT, Decimal("0"))
        assert (block.share.state, block.share.value) == (PRESENT, Decimal("0"))


@pytest.mark.parametrize(("portfolio", "reason"), (("0", REASON_ZERO_DENOMINATOR), ("-10", REASON_NEGATIVE_DENOMINATOR)))
def test_zero_or_negative_denominator_keeps_the_amount_and_drops_the_percent(informe, full_connection, portfolio, reason):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, portfolio=portfolio)

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))

    for block in result.blocks:
        assert block.overdue.state == PRESENT
        assert (block.share.state, block.share.value, block.share.reason) == (NO_DATA, None, reason)


def test_credit_rights_zero_in_one_block_only(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, rights_b="0")

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.CREDIT_RIGHTS))

    assert result.block(BLOCK_A).share.value == Decimal("30")
    assert result.block(BLOCK_B).share.reason == REASON_ZERO_DENOMINATOR
    assert result.block(BLOCK_TOTAL).share.value == Decimal("40")


def test_missing_block_b_makes_the_total_no_data(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, skip=(OVERDUE_TOTAL[BLOCK_B],))

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))

    assert result.block(BLOCK_A).share.value == Decimal("15")
    assert (result.block(BLOCK_B).overdue.state, result.block(BLOCK_B).overdue.reason) == (NO_DATA, REASON_MISSING)
    assert (result.block(BLOCK_B).share.state, result.block(BLOCK_B).share.reason) == (NO_DATA, REASON_MISSING)
    assert (result.block(BLOCK_TOTAL).overdue.state, result.block(BLOCK_TOTAL).overdue.reason) == (NO_DATA, REASON_MISSING)
    assert result.block(BLOCK_TOTAL).share.state == NO_DATA


def test_block_b_all_zero_leaves_the_total_equal_to_block_a(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, overdue_b="0")

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))

    assert result.block(BLOCK_TOTAL).overdue.value == result.block(BLOCK_A).overdue.value == Decimal("30")


def test_missing_credit_rights_of_block_b_makes_the_total_percent_no_data(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, skip=(CREDIT_RIGHTS[BLOCK_B],))

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.CREDIT_RIGHTS))

    assert result.block(BLOCK_A).share.value == Decimal("30")
    assert (result.block(BLOCK_B).share.state, result.block(BLOCK_B).share.reason) == (NO_DATA, REASON_MISSING)
    assert result.block(BLOCK_TOTAL).overdue.value == Decimal("40")
    assert (result.block(BLOCK_TOTAL).share.state, result.block(BLOCK_TOTAL).share.reason) == (NO_DATA, REASON_MISSING)


def test_missing_portfolio_is_no_data_never_zero(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_overdue(informe, klass, skip=(PORTFOLIO,))

    result = only(overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO))

    for block in result.blocks:
        assert (block.share.state, block.share.value, block.share.reason) == (NO_DATA, None, REASON_MISSING)
        assert block.share.denominator.value is None


def test_provision_cedente_and_fiagro_rows_change_nothing(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    _, other = informe.fund_and_class(2)
    put_overdue(informe, klass)
    before = overdue_in_portfolio(full_connection, SEP, Denominator.CREDIT_RIGHTS)

    informe.put(klass, {"tab_I.TAB_I2A11_VL_REDUCAO_RECUP": "999", "tab_I.TAB_I2B11_VL_REDUCAO_RECUP": "999"})
    informe.put(klass, {"tab_I.TAB_I2A12_PR_CEDENTE_1": "50"})
    informe.put(klass, {"tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1": make_test_cnpj(3)}, value_type="text")
    informe.put(other, {"inf_mensal_fiagro.Vencidos": "77", "inf_mensal_fiagro.A_Vencer": "88"})

    assert overdue_in_portfolio(full_connection, SEP, Denominator.CREDIT_RIGHTS) == before
    assert [r.subject for r in delinquency_buckets(full_connection, SEP)] == [klass]


def test_fund_and_class_subjects(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    put_overdue(informe, klass)
    put_overdue(informe, fund, overdue_a="60")

    results = overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO)

    assert [r.subject for r in results] == [klass, fund]
    assert [r.block(BLOCK_A).share.value for r in results] == [Decimal("15"), Decimal("30")]
    assert [r.subject for r in overdue_in_portfolio(full_connection, SEP, Denominator.PORTFOLIO, [fund])] == [fund]


def test_buckets_keep_the_reported_total_and_compute_each_share(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_buckets(informe, klass, BLOCK_A, "100", {1: "40", 2: "50", **{i: "0" for i in range(3, 11)}})
    put_buckets(informe, klass, BLOCK_B, "20", {1: "5", **{i: "0" for i in range(2, 10)}, 10: "15"})

    result = only(delinquency_buckets(full_connection, SEP))
    block_a, block_b, total = result.block(BLOCK_A), result.block(BLOCK_B), result.block(BLOCK_TOTAL)

    assert block_a.total.value == Decimal("100")
    assert [b.label for b in block_a.buckets] == list(BUCKET_LABELS)
    assert [b.amount.fields for b in block_a.buckets] == [(name,) for name in BUCKET_FIELDS[BLOCK_A]]
    assert [b.share.value for b in block_a.buckets[:2]] == [Decimal("40"), Decimal("50")]
    assert block_b.buckets[9].share.value == Decimal("75")
    assert total.total.value == Decimal("120")
    assert total.buckets[0].amount.value == Decimal("45")
    assert total.buckets[0].share.value == Decimal("37.5")


def test_bucket_total_zero_gives_no_share(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_buckets(informe, klass, BLOCK_A, "0", ALL_ZERO)
    put_buckets(informe, klass, BLOCK_B, "0", ALL_ZERO)

    result = only(delinquency_buckets(full_connection, SEP))

    for block in result.blocks:
        assert block.total.value == Decimal("0")
        assert all(b.amount.value == 0 and b.share.reason == REASON_ZERO_DENOMINATOR for b in block.buckets)


def test_missing_bucket_is_no_data_and_the_total_is_not_rebuilt(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_buckets(informe, klass, BLOCK_A, None, {1: "10", 2: "20"})
    put_buckets(informe, klass, BLOCK_B, "5", {1: "5"})

    result = only(delinquency_buckets(full_connection, SEP))

    assert (result.block(BLOCK_A).total.state, result.block(BLOCK_A).total.reason) == (NO_DATA, REASON_MISSING)
    assert result.block(BLOCK_A).buckets[0].amount.value == Decimal("10")
    assert result.block(BLOCK_A).buckets[0].share.reason == REASON_MISSING
    assert result.block(BLOCK_A).buckets[2].amount.reason == REASON_MISSING
    assert result.block(BLOCK_B).buckets[1].amount.reason == REASON_MISSING


def test_evolution_between_two_consecutive_months(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_buckets(informe, klass, BLOCK_A, "100", {1: "10", 2: "90", **{i: "0" for i in range(3, 11)}}, reference_date=AUG)
    put_buckets(informe, klass, BLOCK_B, "0", ALL_ZERO, reference_date=AUG)
    put_buckets(informe, klass, BLOCK_A, "125", {1: "25", 2: "100", **{i: "0" for i in range(3, 11)}}, reference_date=SEP)
    put_buckets(informe, klass, BLOCK_B, "0", ALL_ZERO, reference_date=SEP)

    result = only(bucket_evolution(full_connection, SEP))
    block_a = result.block(BLOCK_A)
    first, second = block_a.buckets[0], block_a.buckets[1]

    assert (result.reference_date, result.previous_reference_date) == (SEP, AUG)
    assert (block_a.previous_total.value, block_a.current_total.value, block_a.total_change.value) == (
        Decimal("100"),
        Decimal("125"),
        Decimal("25"),
    )
    assert (first.previous.amount.value, first.current.amount.value, first.amount_change.value) == (
        Decimal("10"),
        Decimal("25"),
        Decimal("15"),
    )
    assert (first.previous.share.value, first.current.share.value, first.share_change.value) == (
        Decimal("10"),
        Decimal("20"),
        Decimal("10"),
    )
    assert (second.amount_change.value, second.share_change.value) == (Decimal("10"), Decimal("-10"))
    assert first.previous.amount.parts[0].reference_date == AUG
    assert result.block(BLOCK_B).buckets[0].share_change.reason == REASON_ZERO_DENOMINATOR
    assert result.block(BLOCK_TOTAL).buckets[0].amount_change.value == Decimal("15")


def test_evolution_does_not_jump_over_a_missing_month(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put_buckets(informe, klass, BLOCK_A, "100", ALL_ZERO, reference_date=JUL)
    put_buckets(informe, klass, BLOCK_A, "125", ALL_ZERO, reference_date=SEP)

    result = only(bucket_evolution(full_connection, SEP))

    assert result.previous_reference_date == AUG

    for block in result.blocks:
        assert (block.total_change.state, block.total_change.reason) == (NO_DATA, REASON_PREVIOUS_NOT_LOADED)
        assert all(b.amount_change.reason == REASON_PREVIOUS_NOT_LOADED for b in block.buckets)


def test_evolution_with_a_bucket_missing_in_one_month(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    august = dict(ALL_ZERO)
    del august[3]
    put_buckets(informe, klass, BLOCK_A, "0", august, reference_date=AUG)
    put_buckets(informe, klass, BLOCK_A, "0", ALL_ZERO, reference_date=SEP)

    block_a = only(bucket_evolution(full_connection, SEP)).block(BLOCK_A)

    assert (block_a.buckets[2].amount_change.state, block_a.buckets[2].amount_change.reason) == (NO_DATA, REASON_MISSING)
    assert block_a.buckets[1].amount_change.value == Decimal("0")
    assert block_a.total_change.value == Decimal("0")


def test_evolution_uses_the_latest_collection_of_each_month(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    later = informe.new_raw("reapresentado", T1)
    put_buckets(informe, klass, BLOCK_A, "10", {1: "10"}, reference_date=AUG)
    put_buckets(informe, klass, BLOCK_A, "20", {1: "20"}, reference_date=SEP)
    put_buckets(informe, klass, BLOCK_A, "30", {1: "30"}, reference_date=SEP, collected_at=T1, raw=later)

    first = only(bucket_evolution(full_connection, SEP)).block(BLOCK_A).buckets[0]

    assert (first.previous.amount.value, first.current.amount.value, first.amount_change.value) == (
        Decimal("10"),
        Decimal("30"),
        Decimal("20"),
    )


def test_evolution_only_for_subjects_of_the_current_month(informe, full_connection):
    _, first = informe.fund_and_class(1)
    _, second = informe.fund_and_class(2)
    put_buckets(informe, first, BLOCK_A, "10", ALL_ZERO, reference_date=AUG)
    put_buckets(informe, second, BLOCK_A, "10", ALL_ZERO, reference_date=AUG)
    put_buckets(informe, second, BLOCK_A, "10", ALL_ZERO, reference_date=SEP)

    assert [r.subject for r in bucket_evolution(full_connection, SEP)] == [second]
    assert bucket_evolution(full_connection, AUG)[0].previous_reference_date == JUL


@pytest.mark.parametrize("value", ("2026-09-15", "30/09/2026"))
def test_evolution_needs_a_month_end(informe, full_connection, value):
    with pytest.raises(ValueError):
        bucket_evolution(full_connection, value)
