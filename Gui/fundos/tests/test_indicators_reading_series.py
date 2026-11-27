from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_quota_classes import OCT
from apoio_quota_classes import SEP
from apoio_quota_classes import SyntheticSeries

from fundos.indicators.reading import read_series_competence
from fundos.indicators.reading import subjects_with_table
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE


QT = "tab_X_2.TAB_X_QT_COTA"
VL = "tab_X_2.TAB_X_VL_COTA"
FIELDS = (QT, VL)


@pytest.fixture
def informe(full_connection):
    return SyntheticSeries(full_connection)


def test_values_by_parent_and_series_with_provenance(informe):
    _, fund_class = informe.fund_and_class(1)
    senior = informe.series(fund_class, "Subclasse Senior", quantity="100", unit_value="1.25")
    junior = informe.series(fund_class, "Subclasse Subordinada Subordinada 1 |", quantity="10", unit_value="2")

    result = read_series_competence(informe.connection, SEP, FIELDS)

    assert list(result) == [fund_class]
    by_series = result[fund_class]
    assert list(by_series) == [senior, junior]
    assert by_series[senior].label_key == "subclasse senior"
    assert by_series[junior].label_key == "subclasse subordinada subordinada 1"
    assert by_series[senior].values[QT].value == Decimal("100")
    assert by_series[senior].values[VL].value == Decimal("1.25")

    for name in FIELDS:
        field = by_series[senior].values[name]
        assert field.state == PRESENT
        assert field.field_name == name
        assert field.reference_date == SEP
        assert field.source_code == "CVM_DADOS_ABERTOS"
        assert field.observation_id is not None
        assert field.open_conflict is False


def test_source_priority_and_latest_collection_inside_the_competence(informe):
    _, fund_class = informe.fund_and_class(1)
    series_id = informe.series(fund_class, "Subclasse Senior", quantity="100")
    latest = informe.series_field(series_id, QT, "110", collected_at=T1)
    manual = informe.series_field(series_id, VL, "9", source="manual")

    values = read_series_competence(informe.connection, SEP, FIELDS)[fund_class][series_id].values

    assert values[QT].value == Decimal("110")
    assert values[QT].observation_id == latest
    assert values[VL].value == Decimal("9")
    assert values[VL].source_code == "MANUAL"
    assert values[VL].observation_id == manual


def test_competences_never_mix(informe):
    _, fund_class = informe.fund_and_class(1)
    series_id = informe.series(fund_class, "Subclasse Senior", quantity="100", reference_date=SEP)
    informe.series_field(series_id, QT, "200", reference_date=OCT)

    september = read_series_competence(informe.connection, SEP, FIELDS)[fund_class][series_id]
    october = read_series_competence(informe.connection, OCT, FIELDS)[fund_class][series_id]

    assert september.values[QT].value == Decimal("100")
    assert october.values[QT].value == Decimal("200")
    assert october.values[VL].reason == REASON_MISSING


def test_missing_and_unexpected_type(informe):
    _, fund_class = informe.fund_and_class(1)
    series_id = informe.series(fund_class, "Subclasse Senior", unit_value=None)
    informe.series_field(series_id, VL, "texto ficticio", value_type="text")
    other = informe.series(fund_class, "Subclasse Subordinada |", unit_value=None)

    result = read_series_competence(informe.connection, SEP, FIELDS)[fund_class]

    assert result[series_id].values[VL].state == NO_DATA
    assert result[series_id].values[VL].reason == REASON_UNEXPECTED_TYPE
    assert "texto ficticio" not in repr(result)
    assert result[other].values[VL].reason == REASON_MISSING


def test_open_conflict_is_flagged(informe):
    _, fund_class = informe.fund_and_class(1)
    series_id = informe.series(fund_class, "Subclasse Senior", quantity="100")
    first = informe.connection.execute(
        "SELECT id FROM observations WHERE quota_series_id = ? AND field_name = ?", (series_id, QT)
    ).fetchone()[0]
    second = informe.series_field(series_id, QT, "101", collected_at=T1)
    informe.open_conflict(QT, SEP, first, second)

    values = read_series_competence(informe.connection, SEP, FIELDS)[fund_class][series_id].values

    assert values[QT].open_conflict is True
    assert values[VL].open_conflict is False


def test_parents_class_and_fund_and_subject_filter(informe):
    fund, fund_class = informe.fund_and_class(1)
    class_series = informe.series(fund_class, "Subclasse Senior")
    fund_series = informe.series(fund, "Subclasse Senior")
    _, other_class = informe.fund_and_class(2)
    informe.series(other_class, "Subclasse Senior")

    everything = read_series_competence(informe.connection, SEP, FIELDS)
    only_fund = read_series_competence(informe.connection, SEP, FIELDS, [fund])

    assert {(p.kind, p.id) for p in everything} == {
        (FUND_SUBJECT, fund.id),
        (CLASS_SUBJECT, fund_class.id),
        (CLASS_SUBJECT, other_class.id),
    }
    assert list(only_fund) == [fund]
    assert list(only_fund[fund]) == [fund_series]
    assert list(everything[fund_class]) == [class_series]
    assert read_series_competence(informe.connection, SEP, FIELDS, []) == {}


def test_subject_level_observations_are_not_series(informe):
    _, fund_class = informe.fund_and_class(1)
    informe.put(fund_class, {QT: "100"})

    assert read_series_competence(informe.connection, SEP, FIELDS) == {}


def test_identification_fields_are_refused(informe):
    with pytest.raises(ValueError):
        read_series_competence(informe.connection, SEP, ("tab_I.CNPJ_CLASSE",))


def test_subjects_with_table(informe):
    _, first = informe.fund_and_class(1)
    informe.put(first, {"tab_I.TAB_I_VL_ATIVO": "100"})
    _, second = informe.fund_and_class(2)
    informe.put(second, {"tab_II.TAB_II_VL_CARTEIRA": "100"})
    informe.series(second, "Subclasse Senior")

    assert list(subjects_with_table(informe.connection, SEP, "tab_I")) == [(CLASS_SUBJECT, first.id)]
    assert list(subjects_with_table(informe.connection, SEP, "tab_II")) == [(CLASS_SUBJECT, second.id)]
    # As series ficam de fora: tab_X_2 so tem campos de serie aqui.
    assert subjects_with_table(informe.connection, SEP, "tab_X_2") == {}

    with pytest.raises(ValueError):
        subjects_with_table(informe.connection, SEP, "tab_I.%")


def test_no_cnpj_in_repr_and_reading_only_reads(informe):
    _, fund_class = informe.fund_and_class(1)
    informe.series(fund_class, "Subclasse Senior")
    before = informe.connection.total_changes

    result = read_series_competence(informe.connection, SEP, FIELDS)

    assert informe.connection.total_changes == before
    assert make_test_cnpj(1) not in repr(result)
