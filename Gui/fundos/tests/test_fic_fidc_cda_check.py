from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_fic_fidc import FIAGRO
from apoio_fic_fidc import OCT
from apoio_fic_fidc import SEP
from apoio_fic_fidc import SyntheticFicFidc

from fundos.cda.loader import MIXED
from fundos.cda.loader import OUTSIDE
from fundos.fic_fidc.cda_check import CDA_FIELD
from fundos.fic_fidc.cda_check import CONFIDENTIAL_FIELD
from fundos.fic_fidc.cda_check import HAS_CONFIDENTIAL
from fundos.fic_fidc.cda_check import HOLDING_CONFLICT
from fundos.fic_fidc.cda_check import INFORME_FIELD
from fundos.fic_fidc.cda_check import MIXED_INVESTEE
from fundos.fic_fidc.cda_check import NOTHING_ON_EITHER_SIDE
from fundos.fic_fidc.cda_check import OUTSIDE_INVESTEE
from fundos.fic_fidc.cda_check import OUTSIDE_TOLERANCE
from fundos.fic_fidc.cda_check import REASON_NEGATIVE
from fundos.fic_fidc.cda_check import REASON_NO_CDA
from fundos.fic_fidc.cda_check import REASON_NO_HOLDINGS_TABLE
from fundos.fic_fidc.cda_check import REASON_NO_POSITION
from fundos.fic_fidc.cda_check import REASON_ONLY_CONFIDENTIAL
from fundos.fic_fidc.cda_check import TOLERANCE
from fundos.fic_fidc.cda_check import WITHIN
from fundos.fic_fidc.cda_check import Tolerance
from fundos.fic_fidc.cda_check import cda_competences
from fundos.fic_fidc.cda_check import cda_vs_informe
from fundos.fic_fidc.cda_check import within_tolerance
from fundos.fic_fidc.classification import OPEN_CONFLICT
from fundos.fic_fidc.classification import REASON_NO_INFORME
from fundos.indicators.reading import open_read_only
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING


@pytest.fixture
def informe(full_connection):
    return SyntheticFicFidc(full_connection)


def only(results):
    assert len(results) == 1
    return results[0]


def holder_with(informe, cotas, n=1, ativo="1000", reference_date=SEP):
    """Detentor ficticio com o informe (cotas de FIDC e ativo) na competencia."""

    holder = informe.typed_class(n)
    informe.put_ratio(holder, cotas, ativo, reference_date=reference_date)
    return holder


def test_equal_sum_is_within_with_both_dates_and_provenance(informe):
    holder = holder_with(informe, "300")
    first = informe.holding(holder, informe.investee(1), "100")
    second = informe.holding(holder, informe.investee(2), "200")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == WITHIN
    assert result.reason is None
    assert result.difference == Decimal(0)
    assert result.informe_reference_date == SEP
    assert result.cda_reference_date == SEP
    assert result.informe.value == Decimal(300)
    assert result.informe.parts[0].field_name == INFORME_FIELD
    assert result.informe.parts[0].source_code == "CVM_DADOS_ABERTOS"
    assert result.cda_fidc.value == Decimal(300)
    assert result.cda_fidc.field_name == CDA_FIELD
    assert result.cda_fidc.holding_ids == (first.holding.id, second.holding.id)
    assert result.cda_fidc.lines == 2
    assert result.cda_fidc.source_codes == ("CVM_DADOS_ABERTOS",)
    assert result.tolerance == TOLERANCE
    assert result.flags == ()


@pytest.mark.parametrize(
    "informe_value, cda_value, expected",
    [
        ("1000", "1010", WITHIN),  # 1% exato acima
        ("1000", "1010.01", OUTSIDE_TOLERANCE),  # 1% mais R$ 0,01
        ("1000", "990", WITHIN),  # CDA menor: modulo da diferenca
        ("1000", "989.99", OUTSIDE_TOLERANCE),
        ("50", "50.99", WITHIN),  # piso de R$ 1
        ("50", "51.01", OUTSIDE_TOLERANCE),
        ("0", "0", WITHIN),
        ("0", "1", WITHIN),
        ("0", "2", OUTSIDE_TOLERANCE),
    ],
)
def test_tolerance_edges(informe, informe_value, cda_value, expected):
    holder = holder_with(informe, informe_value)
    informe.holding(holder, informe.investee(1), cda_value)

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == expected
    assert result.difference == Decimal(cda_value) - Decimal(informe_value)


def test_within_tolerance_takes_only_decimal():
    assert within_tolerance(Decimal("105"), Decimal("100"), Tolerance(percent=Decimal(5)))
    assert not within_tolerance(Decimal("105.01"), Decimal("100"), Tolerance(percent=Decimal(5)))

    with pytest.raises(TypeError):
        within_tolerance(1.0, Decimal(1))

    with pytest.raises(ValueError):
        within_tolerance(Decimal(1), Decimal(-1))

    with pytest.raises(TypeError):
        cda_vs_informe(None, SEP, tolerance=0.01)


def test_competences_are_never_compared_across_months(informe):
    holder = holder_with(informe, "100", reference_date=SEP)
    informe.holding(holder, informe.investee(1), "100", reference_date=OCT)

    september = only(cda_vs_informe(informe.connection, SEP))
    october = only(cda_vs_informe(informe.connection, OCT))

    assert september.state == NO_DATA
    assert september.reason == REASON_NO_CDA
    assert september.informe_reference_date == SEP
    assert september.cda_reference_date is None
    assert september.cda_fidc.reason == REASON_NO_CDA
    assert october.state == NO_DATA
    assert october.reason == REASON_NO_INFORME
    assert october.informe_reference_date == OCT
    assert october.cda_reference_date == OCT
    assert october.difference is None
    assert cda_competences(informe.connection) == (OCT,)


def test_only_fidc_investees_enter_the_sum(informe):
    holder = holder_with(informe, "100")
    informe.holding(holder, informe.investee(1), "100")
    informe.holding(holder, informe.investee(2, class_kind=FIAGRO, fund_kind=FIAGRO), "50")
    informe.holding(holder, informe.investee(3, class_kind="FIDC", fund_kind=FIAGRO), "20")
    informe.holding(holder, make_test_cnpj(9, alphanumeric=True), "30")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == WITHIN
    assert result.cda_fidc.value == Decimal(100)
    others = {label: item.value for label, item in result.cda_others}
    assert others == {"FIAGRO": Decimal(50), MIXED: Decimal(20), OUTSIDE: Decimal(30)}
    assert result.flags == (MIXED_INVESTEE, OUTSIDE_INVESTEE)
    assert result.cda_lines == 4


def test_fidc_only_as_a_fund_record_counts_as_fidc(informe):
    holder = holder_with(informe, "70")
    informe.holding(holder, informe.investee(1, with_class=False), "70")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == WITHIN
    assert result.cda_fidc.value == Decimal(70)


def test_repeated_lines_of_the_same_investee_are_summed(informe):
    holder = holder_with(informe, "150")
    investee = informe.investee(1)
    informe.holding(holder, investee, "100", line_order=1)
    informe.holding(holder, investee, "50", line_order=2)

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.cda_fidc.value == Decimal(150)
    assert result.cda_fidc.lines == 2
    assert result.state == WITHIN


def test_only_confidential_position_is_no_data_with_the_consolidated_value(informe):
    holder = holder_with(informe, "500")
    informe.confidential(holder, "480")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == NO_DATA
    assert result.reason == REASON_ONLY_CONFIDENTIAL
    assert result.confidential.value == Decimal(480)
    assert result.confidential.field_name == CONFIDENTIAL_FIELD
    assert result.cda_fidc.state == NO_DATA
    assert result.flags == (HAS_CONFIDENTIAL,)


def test_identified_and_confidential_compares_only_the_identified(informe):
    holder = holder_with(informe, "100")
    informe.holding(holder, informe.investee(1), "100")
    informe.confidential(holder, "900")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == WITHIN
    assert result.cda_fidc.value == Decimal(100)
    assert result.flags == (HAS_CONFIDENTIAL,)


def test_subject_without_position_in_a_loaded_cda(informe):
    other = holder_with(informe, "10", n=1)
    informe.holding(other, informe.investee(1), "10")
    with_quotas = holder_with(informe, "200", n=2)
    without_quotas = holder_with(informe, "0", n=3)

    results = {r.subject: r for r in cda_vs_informe(informe.connection, SEP)}

    assert results[with_quotas].state == NO_DATA
    assert results[with_quotas].reason == REASON_NO_POSITION
    assert results[with_quotas].flags == ()
    assert results[without_quotas].reason == REASON_NO_POSITION
    assert results[without_quotas].flags == (NOTHING_ON_EITHER_SIDE,)
    assert results[other].state == WITHIN


def test_only_other_types_gives_zero_in_fidc(informe):
    holder = holder_with(informe, "0", n=1)
    informe.holding(holder, make_test_cnpj(9, alphanumeric=True), "300")
    second = holder_with(informe, "100", n=2)
    informe.holding(second, make_test_cnpj(9, alphanumeric=True), "300")

    results = cda_vs_informe(informe.connection, SEP)

    assert [r.cda_fidc.state for r in results] == [PRESENT, PRESENT]
    assert [r.cda_fidc.value for r in results] == [Decimal(0), Decimal(0)]
    assert [r.state for r in results] == [WITHIN, OUTSIDE_TOLERANCE]


def test_reapresented_position_uses_the_latest_and_flags_the_conflict(informe):
    holder = holder_with(informe, "120")
    investee = informe.investee(1)
    informe.holding(holder, investee, "100")
    later = informe.new_raw("reapresentacao", T1)
    second = informe.holding(holder, investee, "120", collected_at=T1, raw=later)

    assert second.conflicts

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.cda_fidc.value == Decimal(120)
    assert result.cda_fidc.holding_ids == (second.holding.id,)
    assert result.flags == (HOLDING_CONFLICT,)
    assert result.state == WITHIN


def test_negative_values_are_no_data(informe):
    negative_informe = holder_with(informe, "-5", n=1)
    informe.holding(negative_informe, informe.investee(1), "10")
    negative_cda = holder_with(informe, "10", n=2)
    informe.holding(negative_cda, informe.investee(2), "-10")

    results = cda_vs_informe(informe.connection, SEP)

    assert [(r.state, r.reason) for r in results] == [
        (NO_DATA, REASON_NEGATIVE),
        (NO_DATA, REASON_NEGATIVE),
    ]


def test_informe_without_the_field_is_missing(informe):
    holder = holder_with(informe, None, ativo="100")
    informe.holding(holder, informe.investee(1), "10")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.state == NO_DATA
    assert result.reason == REASON_MISSING


def test_open_conflict_in_the_informe_is_flagged(informe):
    holder = informe.typed_class(1)
    first = informe.put_ratio(holder, "100", "1000")
    second = informe.put_ratio(holder, "101", "1000", collected_at=T1)
    informe.open_conflict(INFORME_FIELD, SEP, first[INFORME_FIELD], second[INFORME_FIELD])
    informe.holding(holder, informe.investee(1), "101")

    result = only(cda_vs_informe(informe.connection, SEP))

    assert result.informe.value == Decimal(101)
    assert result.flags == (OPEN_CONFLICT,)


def test_fiagro_holder_without_the_fidc_informe(informe):
    fidc_holder = holder_with(informe, "10", n=1)
    informe.holding(fidc_holder, informe.investee(1), "10")
    fiagro_holder = informe.typed_class(2, kind=FIAGRO, fund_kind=FIAGRO)
    informe.holding(fiagro_holder, informe.investee(2), "40")

    results = {r.subject: r for r in cda_vs_informe(informe.connection, SEP)}

    assert results[fiagro_holder].state == NO_DATA
    assert results[fiagro_holder].reason == REASON_NO_INFORME
    assert results[fiagro_holder].holder_type == "FIAGRO"
    assert results[fiagro_holder].cda_lines == 1
    assert results[fidc_holder].holder_type == "FIDC"


def test_database_without_the_holdings_table(connection):
    informe = SyntheticFicFidc(connection)
    holder = holder_with(informe, "100")

    result = only(cda_vs_informe(connection, SEP))

    assert result.subject == holder
    assert result.state == NO_DATA
    assert result.reason == REASON_NO_HOLDINGS_TABLE
    assert result.cda_fidc.reason == REASON_NO_HOLDINGS_TABLE
    assert cda_competences(connection) is None


def test_subject_filter(informe):
    first = holder_with(informe, "10", n=1)
    informe.holding(first, informe.investee(1), "10")
    second = holder_with(informe, "20", n=2)
    informe.holding(second, informe.investee(2), "20")

    assert [r.subject for r in cda_vs_informe(informe.connection, SEP, [second])] == [second]
    assert cda_vs_informe(informe.connection, SEP, []) == ()


def test_no_cnpj_in_repr_or_str(informe):
    holder = holder_with(informe, "100")
    investees = [informe.investee(n) for n in (1, 2)]

    for investee in investees:
        informe.holding(holder, investee, "50")

    informe.confidential(holder_with(informe, "10", n=2), "10")
    results = cda_vs_informe(informe.connection, SEP)
    text = repr(results) + str(results)

    assert len(results) == 2

    for cnpj in [make_test_cnpj(1), make_test_cnpj(2)] + investees:
        assert cnpj not in text


def test_check_only_reads(full_db):
    connection = full_db.connect()

    try:
        informe = SyntheticFicFidc(connection)
        holder = holder_with(informe, "100")
        informe.holding(holder, informe.investee(1), "100")
    finally:
        connection.close()

    reader = open_read_only(full_db.database_path)

    try:
        before = reader.total_changes
        result = only(cda_vs_informe(reader, SEP))
        assert reader.total_changes == before
        assert reader.in_transaction is False
    finally:
        reader.close()

    assert result.state == WITHIN
