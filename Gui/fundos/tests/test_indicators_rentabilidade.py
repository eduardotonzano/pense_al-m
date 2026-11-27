import dataclasses
from decimal import Decimal

import pytest

from apoio import T0
from apoio import T1
from apoio import make_test_cnpj
from apoio_quota_classes import SyntheticSeries

from fundos.indicators.reading import check_field_names
from fundos.indicators.rentabilidade import FIELD
from fundos.indicators.rentabilidade import OFFICIAL_NAME
from fundos.indicators.rentabilidade import OPEN_CONFLICT
from fundos.indicators.rentabilidade import UNIT
from fundos.indicators.rentabilidade import ReturnResult
from fundos.indicators.rentabilidade import fields
from fundos.indicators.rentabilidade import rentabilidade
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.informe_fidc.columns import HEADERS


SEP = "2026-09-30"
OCT = "2026-10-31"


@pytest.fixture
def informe(full_connection):
    return SyntheticSeries(full_connection)


def series(informe, parent, label, value, reference_date=SEP, value_type="numeric", collected_at=T0, source="cvm"):
    """Serie ficticia com o rotulo e a rentabilidade (value None = sem o campo)."""

    series_id = informe.series(parent, label, reference_date=reference_date, quantity=None, unit_value=None)

    if value is not None:
        informe.series_field(series_id, FIELD, value, value_type=value_type, reference_date=reference_date, collected_at=collected_at, source=source)

    return series_id


def only(results):
    assert len(results) == 1
    return results[0]


def test_field_name_and_unit():
    assert fields() == (FIELD,)
    assert "TAB_X_VL_RENTAB_MES" in HEADERS["tab_X_3"]
    assert check_field_names(fields()) == fields()
    assert OFFICIAL_NAME == "Rentabilidade Apurada no Mes"
    assert UNIT == "unidade nao confirmada"


def test_series_of_a_parent_as_informed_with_provenance(informe):
    _, klass = informe.fund_and_class(1)
    senior = series(informe, klass, "Subclasse Senior Serie 1", "1.15")
    junior = series(informe, klass, "Subclasse Subordinada Subordinada 1", "-3.2")
    zero = series(informe, klass, "Subclasse Subordinada Mezanino 1", "0")

    result = only(rentabilidade(informe.connection, SEP))

    assert (result.subject, result.reference_date, result.name, result.unit) == (klass, SEP, OFFICIAL_NAME, UNIT)
    assert [line.series_id for line in result.series] == sorted([senior, junior, zero])
    assert result.line(senior).value.value == Decimal("1.15")
    assert result.line(junior).value.value == Decimal("-3.2")
    assert (result.line(zero).value.state, result.line(zero).value.value) == (PRESENT, Decimal(0))
    assert result.line(senior).label_key == "subclasse senior serie 1"
    assert result.line(senior).value.source_code == "CVM_DADOS_ABERTOS"
    assert result.line(senior).value.observation_id is not None
    assert result.flags == ()


def test_series_without_the_field_is_not_read(informe):
    _, klass = informe.fund_and_class(1)
    series(informe, klass, "Subclasse Senior Serie 1", None)

    assert rentabilidade(informe.connection, SEP) == ()


def test_text_value_is_unexpected_type_and_never_repeated(informe):
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", "texto ficticio", value_type="text")

    result = only(rentabilidade(informe.connection, SEP))

    assert (result.line(series_id).value.state, result.line(series_id).value.reason) == (NO_DATA, REASON_UNEXPECTED_TYPE)
    assert "texto ficticio" not in repr(result) + str(result)


def test_fund_and_class_parents_competences_and_filter(informe):
    fund, klass = informe.fund_and_class(1)
    series(informe, klass, "Subclasse Senior Serie 1", "1", reference_date=SEP)
    series(informe, klass, "Subclasse Senior Serie 1", "2", reference_date=OCT)
    series(informe, fund, "Cota Senior", "3", reference_date=SEP)

    september = rentabilidade(informe.connection, SEP)
    october = only(rentabilidade(informe.connection, OCT, [klass]))

    assert [result.subject for result in september] == [klass, fund]
    assert [result.subject.kind for result in september] == [CLASS_SUBJECT, FUND_SUBJECT]
    assert october.series[0].value.value == Decimal(2)
    assert rentabilidade(informe.connection, SEP, [fund])[0].series[0].value.value == Decimal(3)
    assert rentabilidade(informe.connection, SEP, []) == ()
    assert rentabilidade(informe.connection, "2026-07-31") == ()


def test_priority_source_latest_collection_and_open_conflict(informe):
    _, klass = informe.fund_and_class(1)
    first_series = series(informe, klass, "Subclasse Senior Serie 1", "1")
    informe.series_field(first_series, FIELD, "5", source="manual")
    second_series = series(informe, klass, "Subclasse Senior Serie 2", "1")
    old = informe.connection.execute(
        "SELECT id FROM observations WHERE quota_series_id = ? AND field_name = ?", (second_series, FIELD)
    ).fetchone()[0]
    new = informe.series_field(second_series, FIELD, "1.5", collected_at=T1)
    informe.open_conflict(FIELD, SEP, old, new)

    result = only(rentabilidade(informe.connection, SEP))

    assert (result.line(first_series).value.value, result.line(first_series).value.source_code) == (Decimal(5), "MANUAL")
    assert (result.line(second_series).value.value, result.line(second_series).value.collected_at) == (Decimal("1.5"), T1)
    assert result.line(second_series).flags == (OPEN_CONFLICT,)
    assert result.line(first_series).flags == ()
    assert result.flags == (OPEN_CONFLICT,)


def test_exact_decimal_with_25_digits(informe):
    # Montado por codigo: 23 noves e 2 casas.
    big = "9" * 23 + ".25"
    _, klass = informe.fund_and_class(1)
    series_id = series(informe, klass, "Subclasse Senior Serie 1", big)

    assert only(rentabilidade(informe.connection, SEP)).line(series_id).value.value == Decimal(big)


def test_nothing_is_annualized_compared_or_aggregated():
    names = [item.name for item in dataclasses.fields(ReturnResult)]

    assert names == ["subject", "reference_date", "series", "flags", "name", "unit"]


def test_competence_must_be_month_end(informe):
    with pytest.raises(ValueError):
        rentabilidade(informe.connection, "2026-09-29")


def test_no_cnpj_in_repr_and_only_reads(informe):
    for n in (1, 2):
        _, klass = informe.fund_and_class(n)
        series(informe, klass, "Subclasse Senior Serie 1", "1")

    before = informe.connection.total_changes
    results = rentabilidade(informe.connection, SEP)

    assert informe.connection.total_changes == before
    assert len(results) == 2

    for n in (1, 2):
        assert make_test_cnpj(n) not in repr(results) + str(results)
