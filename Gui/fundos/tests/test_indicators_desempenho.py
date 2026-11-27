import dataclasses
from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_quota_classes import SyntheticSeries

from fundos.indicators.desempenho import CORRESPONDENCE
from fundos.indicators.desempenho import DIFFERS_FROM_RETURN
from fundos.indicators.desempenho import EXPECTED
from fundos.indicators.desempenho import EXPECTED_NAME
from fundos.indicators.desempenho import EXPECTED_NEGATIVE
from fundos.indicators.desempenho import EXPECTED_ZERO
from fundos.indicators.desempenho import OPEN_CONFLICT
from fundos.indicators.desempenho import REALIZED
from fundos.indicators.desempenho import REALIZED_NAME
from fundos.indicators.desempenho import RETURN
from fundos.indicators.desempenho import UNIT
from fundos.indicators.desempenho import SeriesPerformance
from fundos.indicators.desempenho import desempenho
from fundos.indicators.desempenho import fields
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
    return SyntheticSeries(full_connection)


def series(informe, parent, label, expected=None, realized=None, monthly=None, reference_date=SEP):
    """Serie ficticia: o rotulo, a tab_X_6 e a tab_X_3 (None = sem o campo)."""

    series_id = informe.series(parent, label, reference_date=reference_date, quantity=None, unit_value=None)

    for field_name, value in ((EXPECTED, expected), (REALIZED, realized), (RETURN, monthly)):
        if value is not None:
            informe.series_field(series_id, field_name, value, reference_date=reference_date)

    return series_id


def only(results):
    assert len(results) == 1
    return results[0]


def state(field_value):
    return (field_value.state, field_value.value, field_value.reason)


def test_fields_names_correspondence_and_unit():
    assert fields() == (EXPECTED, REALIZED)
    assert check_field_names(fields() + (RETURN,)) == fields() + (RETURN,)
    assert {"TAB_X_PR_DESEMP_ESPERADO", "TAB_X_PR_DESEMP_REAL"} <= set(HEADERS["tab_X_6"])
    assert RETURN == "tab_X_3.TAB_X_VL_RENTAB_MES"
    assert (EXPECTED_NAME, REALIZED_NAME) == (
        "Desempenho Esperado (Benchmark)",
        "Desempenho Realizado (Rentabilidade no Mes)",
    )
    assert CORRESPONDENCE == "Suplemento G, correspondencia pelo nome do campo"
    assert UNIT == "unidade nao confirmada"


def test_series_as_informed_with_the_tab_x_3_of_the_same_series(informe):
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", expected="1.1", realized="1.25", monthly="1.25")

    result = only(desempenho(informe.connection, SEP))
    line = result.line(series_id)

    assert (result.subject, result.reference_date, result.correspondence) == (klass, SEP, CORRESPONDENCE)
    assert state(line.expected) == (PRESENT, Decimal("1.1"), None)
    assert state(line.realized) == (PRESENT, Decimal("1.25"), None)
    assert state(line.monthly_return) == (PRESENT, Decimal("1.25"), None)
    assert line.expected.field_name == EXPECTED and line.expected.observation_id is not None
    assert line.label_key == "subclasse senior serie 1"
    assert (line.flags, result.flags) == ((), ())


def test_expected_zero_and_negative_are_kept_and_flagged(informe):
    _, klass = informe.fund_and_class(1)
    zero = series(informe, klass, "Subclasse Senior Serie 1", expected="0", realized="1", monthly="1")
    negative = series(informe, klass, "Subclasse Senior Serie 2", expected="-0.5", realized="1", monthly="1")

    result = only(desempenho(informe.connection, SEP))

    assert state(result.line(zero).expected) == (PRESENT, Decimal(0), None)
    assert result.line(zero).flags == (EXPECTED_ZERO,)
    assert result.line(negative).expected.value == Decimal("-0.5")
    assert result.line(negative).flags == (EXPECTED_NEGATIVE,)
    assert result.flags == (EXPECTED_ZERO, EXPECTED_NEGATIVE)


def test_realized_different_from_the_tab_x_3_is_flagged(informe):
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", expected="1", realized="1.2", monthly="1.3")

    line = only(desempenho(informe.connection, SEP)).line(series_id)

    assert (line.realized.value, line.monthly_return.value) == (Decimal("1.2"), Decimal("1.3"))
    assert line.flags == (DIFFERS_FROM_RETURN,)


def test_series_without_tab_x_3_or_without_realized(informe):
    _, klass = informe.fund_and_class(1)
    no_return = series(informe, klass, "Subclasse Senior Serie 1", expected="1", realized="1.2")
    no_realized = series(informe, klass, "Subclasse Senior Serie 2", expected="1", monthly="1.3")
    only_return = series(informe, klass, "Subclasse Senior Serie 3", monthly="1.4")

    result = only(desempenho(informe.connection, SEP))

    assert state(result.line(no_return).monthly_return) == (NO_DATA, None, REASON_MISSING)
    assert result.line(no_return).flags == ()
    assert state(result.line(no_realized).realized) == (NO_DATA, None, REASON_MISSING)
    assert result.line(no_realized).flags == ()
    assert result.line(only_return) is None


def test_text_value_is_unexpected_type_and_never_repeated(informe):
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", realized="1")
    informe.series_field(series_id, EXPECTED, "texto ficticio", value_type="text")

    result = only(desempenho(informe.connection, SEP))

    assert state(result.line(series_id).expected) == (NO_DATA, None, REASON_UNEXPECTED_TYPE)
    assert "texto ficticio" not in repr(result) + str(result)


def test_nothing_is_calculated_between_the_two_fields():
    names = [item.name for item in dataclasses.fields(SeriesPerformance)]

    assert names == ["series_id", "label_key", "expected", "realized", "monthly_return", "flags"]


def test_competences_do_not_mix_and_subject_filter(informe):
    fund, klass = informe.fund_and_class(1)
    august = series(informe, klass, "Subclasse Senior Serie 1", expected="1", realized="9", monthly="9", reference_date=AUG)
    informe.series_field(august, REALIZED, "2")
    series(informe, fund, "Cota Senior", expected="1", realized="3", monthly="3")

    september = desempenho(informe.connection, SEP)
    by_klass = only(desempenho(informe.connection, SEP, [klass]))

    assert [result.subject for result in september] == [klass, fund]
    assert state(by_klass.line(august).realized) == (PRESENT, Decimal(2), None)
    assert state(by_klass.line(august).expected) == (NO_DATA, None, REASON_MISSING)
    assert state(by_klass.line(august).monthly_return) == (NO_DATA, None, REASON_MISSING)
    assert only(desempenho(informe.connection, AUG)).line(august).flags == ()
    assert desempenho(informe.connection, SEP, []) == ()
    assert desempenho(informe.connection, "2026-07-31") == ()


def test_priority_source_latest_collection_and_open_conflict(informe):
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", expected="1", realized="1", monthly="1")
    informe.series_field(series_id, EXPECTED, "1.5", source="manual")
    old = informe.connection.execute(
        "SELECT id FROM observations WHERE quota_series_id = ? AND field_name = ?", (series_id, RETURN)
    ).fetchone()[0]
    new = informe.series_field(series_id, RETURN, "1", collected_at=T1)
    informe.open_conflict(RETURN, SEP, old, new)

    line = only(desempenho(informe.connection, SEP)).line(series_id)

    assert (line.expected.value, line.expected.source_code) == (Decimal("1.5"), "MANUAL")
    assert line.monthly_return.collected_at == T1
    assert line.flags == (OPEN_CONFLICT,)


def test_exact_decimal_with_25_digits(informe):
    # Montado por codigo: 23 noves e 2 casas.
    big = "9" * 23 + ".25"
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", expected=big, realized=big, monthly=big)

    line = only(desempenho(informe.connection, SEP)).line(series_id)

    assert line.expected.value == line.realized.value == Decimal(big)
    assert line.flags == ()


def test_competence_must_be_month_end(informe):
    with pytest.raises(ValueError):
        desempenho(informe.connection, "2026-09-29")


def test_no_cnpj_in_repr_and_only_reads(informe):
    for n in (1, 2):
        _, klass = informe.fund_and_class(n)
        series(informe, klass, "Subclasse Senior Serie 1", expected="1", realized="1", monthly="1")

    before = informe.connection.total_changes
    results = desempenho(informe.connection, SEP)

    assert informe.connection.total_changes == before
    assert informe.connection.in_transaction is False
    assert len(results) == 2

    for n in (1, 2):
        assert make_test_cnpj(n) not in repr(results) + str(results)
