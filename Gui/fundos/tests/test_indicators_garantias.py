import dataclasses
from decimal import Decimal

import pytest

from apoio import T0
from apoio import T1
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme

from fundos.indicators.garantias import CORRESPONDENCE
from fundos.indicators.garantias import INCOHERENT
from fundos.indicators.garantias import INFORMED_ZERO
from fundos.indicators.garantias import NEGATIVE_PERCENT
from fundos.indicators.garantias import NEGATIVE_VALUE
from fundos.indicators.garantias import OPEN_CONFLICT
from fundos.indicators.garantias import PERCENT
from fundos.indicators.garantias import PERCENT_ABOVE_100
from fundos.indicators.garantias import PERCENT_ITEM
from fundos.indicators.garantias import PERCENT_NAME
from fundos.indicators.garantias import VALUE
from fundos.indicators.garantias import VALUE_ITEM
from fundos.indicators.garantias import VALUE_NAME
from fundos.indicators.garantias import GuaranteeResult
from fundos.indicators.garantias import fields
from fundos.indicators.garantias import garantias
from fundos.indicators.reading import check_field_names
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.informe_fidc.columns import HEADERS


SEP = "2026-09-30"
AUG = "2026-08-31"


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def only(results):
    assert len(results) == 1
    return results[0]


def result_for(informe, values, n=1):
    _, klass = informe.fund_and_class(n)
    informe.put(klass, values)
    return only(garantias(informe.connection, SEP, [klass]))


def state(field_value):
    return (field_value.state, field_value.value, field_value.reason)


def test_fields_names_and_correspondence():
    assert fields() == (VALUE, PERCENT)
    assert check_field_names(fields()) == fields()
    assert tuple("tab_X_7." + column for column in HEADERS["tab_X_7"][-2:]) == fields()
    assert (VALUE_ITEM, PERCENT_ITEM) == ("7.1", "7.2")
    assert VALUE_NAME == "Valor total das garantias vinculadas aos direitos creditorios"
    assert PERCENT_NAME == "Percentual dos direitos creditorios com garantias vinculadas"
    assert CORRESPONDENCE == "Suplemento G, correspondencia pelo nome do campo"


def test_value_and_percent_as_informed_with_provenance(informe):
    _, klass = informe.fund_and_class(1)
    ids = informe.put(klass, {VALUE: "1500.25", PERCENT: "37.5"})

    result = only(garantias(informe.connection, SEP))

    assert (result.subject, result.reference_date) == (klass, SEP)
    assert state(result.value) == (PRESENT, Decimal("1500.25"), None)
    assert state(result.percent) == (PRESENT, Decimal("37.5"), None)
    assert (result.value.observation_id, result.percent.observation_id) == (ids[VALUE], ids[PERCENT])
    assert (result.value.source_code, result.value.collected_at) == ("CVM_DADOS_ABERTOS", T0)
    assert (result.flags, result.correspondence) == ((), CORRESPONDENCE)


def test_informed_zero_is_zero_with_the_flag(informe):
    result = result_for(informe, {VALUE: "0", PERCENT: "0"})

    assert state(result.value) == (PRESENT, Decimal(0), None)
    assert state(result.percent) == (PRESENT, Decimal(0), None)
    assert result.flags == (INFORMED_ZERO,)


def test_percent_above_100_is_kept_as_informed(informe):
    result = result_for(informe, {VALUE: "10", PERCENT: "120.5"})

    assert result.percent.value == Decimal("120.5")
    assert result.flags == (PERCENT_ABOVE_100,)


@pytest.mark.parametrize("value, percent", [("10", "0"), ("0", "5")])
def test_one_positive_and_the_other_zero_is_incoherent(informe, value, percent):
    result = result_for(informe, {VALUE: value, PERCENT: percent})

    assert result.flags == (INCOHERENT,)
    assert (result.value.value, result.percent.value) == (Decimal(value), Decimal(percent))


def test_negatives_are_kept_and_flagged(informe):
    result = result_for(informe, {VALUE: "-1", PERCENT: "-2"})

    assert (result.value.value, result.percent.value) == (Decimal(-1), Decimal(-2))
    assert result.flags == (NEGATIVE_VALUE, NEGATIVE_PERCENT)


def test_missing_field_is_no_data_never_zero(informe):
    result = result_for(informe, {VALUE: "0"})

    assert state(result.value) == (PRESENT, Decimal(0), None)
    assert state(result.percent) == (NO_DATA, None, REASON_MISSING)
    assert result.flags == ()


def test_text_value_is_unexpected_type_and_never_repeated(informe):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {VALUE: "10"})
    informe.put(klass, {PERCENT: "texto ficticio"}, value_type="text")

    result = only(garantias(informe.connection, SEP))

    assert state(result.percent) == (NO_DATA, None, REASON_UNEXPECTED_TYPE)
    assert "texto ficticio" not in repr(result) + str(result)


def test_competence_without_data_other_tables_and_subject_filter(informe):
    fund, klass = informe.fund_and_class(1)
    informe.put(klass, {VALUE: "10", PERCENT: "20"})
    informe.put(fund, {"tab_I.TAB_I2_VL_CARTEIRA": "100", "tab_II.TAB_II_VL_CARTEIRA": "100"})

    assert [result.subject for result in garantias(informe.connection, SEP)] == [klass]
    assert garantias(informe.connection, AUG) == ()
    assert garantias(informe.connection, SEP, [fund]) == ()
    assert garantias(informe.connection, SEP, []) == ()


def test_nothing_is_calculated_between_the_two_fields():
    names = [item.name for item in dataclasses.fields(GuaranteeResult)]

    assert names == ["subject", "reference_date", "value", "percent", "flags", "correspondence"]


def test_latest_collection_wins_and_open_conflict_is_flagged(informe):
    _, klass = informe.fund_and_class(1)
    first = informe.put(klass, {VALUE: "10", PERCENT: "20"})
    later = informe.put(klass, {VALUE: "11"}, collected_at=T1, raw=informe.new_raw("reapresentacao", T1))
    informe.open_conflict(VALUE, SEP, first[VALUE], later[VALUE])

    result = only(garantias(informe.connection, SEP))

    assert (result.value.value, result.value.collected_at) == (Decimal(11), T1)
    assert result.flags == (OPEN_CONFLICT,)


def test_competence_must_be_month_end(informe):
    with pytest.raises(ValueError):
        garantias(informe.connection, "2026-09-29")


def test_no_cnpj_in_repr_and_only_reads(informe):
    for n in (1, 2):
        _, klass = informe.fund_and_class(n)
        informe.put(klass, {VALUE: "10", PERCENT: "20"})

    before = informe.connection.total_changes
    results = garantias(informe.connection, SEP)

    assert informe.connection.total_changes == before
    assert len(results) == 2

    for n in (1, 2):
        assert make_test_cnpj(n) not in repr(results) + str(results)
