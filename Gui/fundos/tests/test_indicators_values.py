from decimal import Decimal

import pytest

from apoio import make_test_cnpj

from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCK_TOTAL
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_NEGATIVE_DENOMINATOR
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.indicators.values import REASON_ZERO_DENOMINATOR
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject
from fundos.indicators.values import bucket_blocks
from fundos.indicators.values import difference
from fundos.indicators.values import percentage
from fundos.indicators.values import reported
from fundos.indicators.values import summed


REF = "2026-09-30"


def present(name, value, conflict=False):
    return FieldValue(name, REF, PRESENT, Decimal(value), open_conflict=conflict)


def test_subject_keeps_the_cnpj_out_of_repr_and_comparison():
    cnpj = make_test_cnpj(1)
    subject = Subject(CLASS_SUBJECT, 7, cnpj)

    assert subject.cnpj == cnpj
    assert cnpj not in repr(subject)
    assert cnpj not in str(subject)
    assert subject == Subject(CLASS_SUBJECT, 7, make_test_cnpj(2))


def test_missing_field_value_has_no_value_and_a_reason():
    value = FieldValue.missing("tab_V.X", REF)

    assert value.state == NO_DATA
    assert value.value is None
    assert value.reason == REASON_MISSING


def test_reported_keeps_the_exact_value_and_the_source():
    amount = reported(present("tab_V.X", "10.05"))

    assert amount.state == PRESENT
    assert amount.value == Decimal("10.05")
    assert amount.fields == ("tab_V.X",)


def test_sum_needs_every_part_and_keeps_the_first_missing_reason():
    missing = FieldValue.missing("tab_VI.Y", REF, REASON_UNEXPECTED_TYPE)

    total = summed(present("tab_V.X", "10"), missing)
    other = summed(present("tab_V.X", "10"), present("tab_VI.Y", "0"))

    assert (total.state, total.value, total.reason) == (NO_DATA, None, REASON_UNEXPECTED_TYPE)
    assert total.fields == ("tab_V.X", "tab_VI.Y")
    assert (other.state, other.value) == (PRESENT, Decimal("10"))


def test_sum_without_parts_is_refused():
    with pytest.raises(ValueError):
        summed()


def test_open_conflict_of_any_part_marks_the_amount():
    amount = summed(present("tab_V.X", "1"), present("tab_VI.Y", "2", conflict=True))

    assert amount.open_conflict is True
    assert reported(present("tab_V.X", "1")).open_conflict is False


def test_percentage_is_exact_and_can_pass_100():
    ratio = percentage(reported(present("a.x", "25")), reported(present("b.y", "200")))
    above = percentage(reported(present("a.x", "300")), reported(present("b.y", "200")))
    zero = percentage(reported(present("a.x", "0")), reported(present("b.y", "200")))

    assert (ratio.state, ratio.value) == (PRESENT, Decimal("12.5"))
    assert above.value == Decimal("150")
    assert (zero.state, zero.value) == (PRESENT, Decimal("0"))


def test_percentage_uses_28_significant_digits_without_rounding_for_display():
    ratio = percentage(reported(present("a.x", "1")), reported(present("b.y", "3")))

    assert len(ratio.value.as_tuple().digits) == 28
    assert str(ratio.value).startswith("33.3333333333")


@pytest.mark.parametrize(
    ("denominator", "reason"),
    (("0", REASON_ZERO_DENOMINATOR), ("0.00", REASON_ZERO_DENOMINATOR), ("-5", REASON_NEGATIVE_DENOMINATOR)),
)
def test_percentage_without_positive_denominator_is_no_data(denominator, reason):
    numerator = reported(present("a.x", "10"))

    ratio = percentage(numerator, reported(present("b.y", denominator)))

    assert (ratio.state, ratio.value, ratio.reason) == (NO_DATA, None, reason)
    assert ratio.numerator.value == Decimal("10")


def test_percentage_with_a_missing_side_is_no_data_and_never_zero():
    missing = reported(FieldValue.missing("b.y", REF))

    over_missing = percentage(reported(present("a.x", "10")), missing)
    of_missing = percentage(missing, reported(present("a.x", "10")))

    for ratio in (over_missing, of_missing):
        assert (ratio.state, ratio.value, ratio.reason) == (NO_DATA, None, REASON_MISSING)


def test_difference_is_current_minus_previous_and_needs_both_sides():
    change = difference(reported(present("a.x", "10")), reported(present("a.x", "7.5")))
    missing = difference(reported(FieldValue.missing("a.x", REF)), reported(present("a.x", "7")))

    assert (change.state, change.value) == (PRESENT, Decimal("-2.5"))
    assert (missing.state, missing.value, missing.reason) == (NO_DATA, None, REASON_MISSING)


def test_bucket_blocks_keep_the_reported_total_and_sum_the_same_bucket_of_both_blocks():
    specs = {
        BLOCK_A: ("tab_V.TOTAL", (("1 a 30 dias", "tab_V.F1"), ("31 a 60 dias", "tab_V.F2"))),
        BLOCK_B: ("tab_VI.TOTAL", (("1 a 30 dias", "tab_VI.F1"), ("31 a 60 dias", "tab_VI.F2"))),
    }
    values = {
        "tab_V.TOTAL": present("tab_V.TOTAL", "100"),
        "tab_V.F1": present("tab_V.F1", "40"),
        "tab_V.F2": present("tab_V.F2", "50"),
        "tab_VI.TOTAL": present("tab_VI.TOTAL", "0"),
        "tab_VI.F1": present("tab_VI.F1", "0"),
        "tab_VI.F2": FieldValue.missing("tab_VI.F2", REF),
    }

    block_a, block_b, total = bucket_blocks(values, specs)

    assert [b.block for b in (block_a, block_b, total)] == [BLOCK_A, BLOCK_B, BLOCK_TOTAL]
    assert block_a.total.value == Decimal("100")
    assert [b.share.value for b in block_a.buckets] == [Decimal("40"), Decimal("50")]
    assert [b.share.reason for b in block_b.buckets] == [REASON_ZERO_DENOMINATOR, REASON_MISSING]
    assert total.total.value == Decimal("100")
    assert total.buckets[0].amount.fields == ("tab_V.F1", "tab_VI.F1")
    assert total.buckets[0].amount.value == Decimal("40")
    assert (total.buckets[1].amount.state, total.buckets[1].amount.reason) == (NO_DATA, REASON_MISSING)
