import hashlib
from decimal import Decimal

import pytest

from apoio import T0
from apoio import T1
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme
from conftest import create_full_schema

from fundos.indicators.reading import check_field_names
from fundos.indicators.reading import open_read_only
from fundos.indicators.segmentos import CALCULATED
from fundos.indicators.segmentos import NEGATIVE_SEGMENT
from fundos.indicators.segmentos import OFFICIAL_NAME
from fundos.indicators.segmentos import OPEN_CONFLICT
from fundos.indicators.segmentos import SEGMENTS
from fundos.indicators.segmentos import SUBITEMS_DIFFER
from fundos.indicators.segmentos import SUM_DIFFERS
from fundos.indicators.segmentos import TOTAL
from fundos.indicators.segmentos import WITH_OTHERS
from fundos.indicators.segmentos import carteira_por_segmento
from fundos.indicators.segmentos import fields
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_NEGATIVE_DENOMINATOR
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.indicators.values import REASON_ZERO_DENOMINATOR
from fundos.informe_fidc.columns import HEADERS
from fundos.informe_fidc.columns import LEADING


SEP = "2026-09-30"
AUG = "2026-08-31"

FIELD = {item: name for item, _, name, _ in SEGMENTS}
SUBFIELD = {sub: name for _, _, _, subitems in SEGMENTS for sub, _, name in subitems}
FIRST_SUBITEM = {item: subitems[0][0] for item, _, _, subitems in SEGMENTS if subitems}


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def row(segments, total=None, subitems=None, drop=()):
    """Linha completa da tab_II (valores ficticios, em texto).

    segments: {item de topo: valor}; os demais sao 0. O valor de um segmento
    com subitens vai inteiro para o primeiro subitem, salvo subitems
    ({subitem: valor}). total: o informado; None = a soma dos segmentos.
    drop: campos sem linha.
    """

    values = {name: "0" for name in fields()}

    for item, value in segments.items():
        values[FIELD[item]] = value

        if item in FIRST_SUBITEM:
            values[SUBFIELD[FIRST_SUBITEM[item]]] = value

    for sub, value in (subitems or {}).items():
        values[SUBFIELD[sub]] = value

    values[TOTAL] = total if total is not None else str(sum(Decimal(v) for v in segments.values()))

    return {name: value for name, value in values.items() if name not in drop}


def only(results):
    assert len(results) == 1
    return results[0]


def result_for(informe, values, n=1, reference_date=SEP):
    _, klass = informe.fund_and_class(n)
    informe.put(klass, values, reference_date=reference_date)
    return only(carteira_por_segmento(informe.connection, reference_date, [klass]))


def test_fields_are_the_cvm_columns_in_the_model_order():
    columns = HEADERS["tab_II"][len(LEADING):]

    assert fields() == tuple("tab_II." + column for column in columns)
    assert len(fields()) == 33
    assert check_field_names(fields()) == fields()
    assert [item for item, _, _, _ in SEGMENTS] == ["II." + letter for letter in "abcdefghijk"]
    assert [item for item, _, _, subitems in SEGMENTS if subitems] == ["II.c", "II.d", "II.f", "II.h", "II.i"]
    assert all(name.isascii() for _, name, _, _ in SEGMENTS)


def test_single_segment_is_100_percent_and_hhi_10000(informe):
    result = result_for(informe, row({"II.e": "500"}))

    assert (result.state, result.reason, result.flags) == (CALCULATED, None, ())
    assert result.name == OFFICIAL_NAME
    assert result.total.value == Decimal(500)
    assert result.segment("II.e").share.value == Decimal(100)
    assert result.segment("II.a").share.value == Decimal(0)
    assert [segment.item for segment in result.ordered] == ["II.e"]
    assert result.largest.item == "II.e"
    assert result.nonzero_count == 1
    assert (result.hhi, result.hhi_reason) == (Decimal(10000), None)


def test_several_segments_are_ordered_with_largest_count_and_exact_hhi(informe):
    result = result_for(
        informe,
        row({"II.a": "60", "II.f": "30", "II.k": "10"}, subitems={"II.f.1": "10", "II.f.8": "20"}),
    )

    assert result.state == CALCULATED
    assert [segment.item for segment in result.ordered] == ["II.a", "II.f", "II.k"]
    assert [segment.share.value for segment in result.ordered] == [Decimal(60), Decimal(30), Decimal(10)]
    assert result.largest.item == "II.a"
    assert result.nonzero_count == 3
    assert result.hhi == Decimal(4600)
    assert result.flags == (WITH_OTHERS,)


def test_ties_keep_the_model_order(informe):
    result = result_for(informe, row({"II.k": "50", "II.b": "50"}))

    assert [segment.item for segment in result.ordered] == ["II.b", "II.k"]
    assert result.largest.item == "II.b"
    assert result.hhi == Decimal(5000)


def test_subitems_have_their_share_in_the_table_total(informe):
    result = result_for(informe, row({"II.a": "75", "II.f": "25"}, subitems={"II.f.1": "5", "II.f.5": "20"}))
    financial = result.segment("II.f")

    assert [sub.item for sub in financial.subitems] == ["II.f." + str(n) for n in range(1, 9)]
    assert financial.subitem("II.f.1").share.value == Decimal(5)
    assert financial.subitem("II.f.5").share.value == Decimal(20)
    assert financial.subitem("II.f.5").amount.fields == (SUBFIELD["II.f.5"],)
    assert result.segment("II.a").subitems == ()
    assert result.flags == ()


def test_zero_total_is_no_data_and_keeps_the_amounts(informe):
    result = result_for(informe, row({}))

    assert (result.state, result.reason) == (NO_DATA, REASON_ZERO_DENOMINATOR)
    assert (result.total.state, result.total.value) == (PRESENT, Decimal(0))
    assert result.segment("II.a").amount.value == Decimal(0)
    assert (result.segment("II.a").share.state, result.segment("II.a").share.reason) == (NO_DATA, REASON_ZERO_DENOMINATOR)
    assert (result.largest, result.hhi, result.hhi_reason) == (None, None, REASON_ZERO_DENOMINATOR)
    assert (result.ordered, result.nonzero_count) == ((), 0)


def test_negative_total_is_no_data(informe):
    result = result_for(informe, row({"II.a": "-10"}))

    assert (result.state, result.reason) == (NO_DATA, REASON_NEGATIVE_DENOMINATOR)
    assert result.segment("II.a").share.reason == REASON_NEGATIVE_DENOMINATOR
    assert NEGATIVE_SEGMENT in result.flags
    assert (result.hhi, result.hhi_reason) == (None, REASON_NEGATIVE_DENOMINATOR)


def test_negative_segment_is_shown_as_informed_and_others_can_pass_100(informe):
    result = result_for(informe, row({"II.a": "150", "II.b": "-50"}))

    assert (result.state, result.reason) == (CALCULATED, None)
    assert result.segment("II.a").share.value == Decimal(150)
    assert result.segment("II.b").share.value == Decimal(-50)
    assert result.flags == (NEGATIVE_SEGMENT,)
    assert (result.largest, result.hhi, result.hhi_reason) == (None, None, NEGATIVE_SEGMENT)
    assert [segment.item for segment in result.ordered] == ["II.a"]
    assert result.nonzero_count == 2


def test_missing_segment_is_no_data_never_zero(informe):
    result = result_for(informe, row({"II.a": "100"}, drop=(FIELD["II.e"],)))
    agro = result.segment("II.e")

    assert (result.state, result.reason) == (NO_DATA, REASON_MISSING)
    assert (agro.amount.state, agro.amount.value, agro.amount.reason) == (NO_DATA, None, REASON_MISSING)
    assert agro.share.state == NO_DATA
    assert result.segment("II.a").share.value == Decimal(100)
    assert (result.ordered, result.nonzero_count, result.largest, result.hhi) == ((), None, None, None)
    assert result.hhi_reason == REASON_MISSING
    assert SUM_DIFFERS not in result.flags


def test_missing_total_gives_no_share(informe):
    result = result_for(informe, row({"II.a": "100"}, drop=(TOTAL,)))

    assert (result.state, result.reason) == (NO_DATA, REASON_MISSING)
    assert (result.total.state, result.total.value) == (NO_DATA, None)
    assert (result.segment("II.a").amount.value, result.segment("II.a").share.reason) == (Decimal(100), REASON_MISSING)
    assert result.nonzero_count == 1
    assert result.hhi is None


def test_text_value_is_unexpected_type_and_never_repeated(informe):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, row({"II.a": "100"}, drop=(FIELD["II.g"],)))
    informe.put(klass, {FIELD["II.g"]: "texto ficticio"}, value_type="text")

    result = only(carteira_por_segmento(informe.connection, SEP))

    assert (result.state, result.reason) == (NO_DATA, REASON_UNEXPECTED_TYPE)
    assert result.segment("II.g").amount.reason == REASON_UNEXPECTED_TYPE
    assert "texto ficticio" not in repr(result) + str(result)


def test_sum_of_segments_different_from_the_total_is_flagged(informe):
    result = result_for(informe, row({"II.a": "90"}, total="100"))

    assert result.state == CALCULATED
    assert result.flags == (SUM_DIFFERS,)
    assert result.total.value == Decimal(100)
    assert result.segment("II.a").share.value == Decimal(90)
    assert result.hhi == Decimal(8100)


def test_subitems_different_from_their_segment_are_flagged(informe):
    result = result_for(informe, row({"II.a": "70", "II.f": "30"}, subitems={"II.f.1": "10"}))

    assert result.state == CALCULATED
    assert result.flags == (SUBITEMS_DIFFER,)
    assert result.segment("II.f").amount.value == Decimal(30)


def test_others_flag_comes_from_f8_or_i4(informe):
    with_i4 = result_for(informe, row({"II.i": "40", "II.a": "60"}, subitems={"II.i.1": "0", "II.i.4": "40"}), n=1)
    without = result_for(informe, row({"II.f": "40", "II.a": "60"}), n=2)

    assert with_i4.flags == (WITH_OTHERS,)
    assert without.flags == ()


def test_exact_decimal_with_25_digits(informe):
    # Montados por codigo: 23 noves e 2 casas; o total e 10 elevado a 23.
    big = "9" * 23 + ".25"
    total = "1" + "0" * 23
    result = result_for(informe, row({"II.a": big, "II.b": "0.75"}, total=total))
    first, second = result.segment("II.a"), result.segment("II.b")

    assert first.amount.value == Decimal(big)
    assert result.total.value == Decimal(total)
    assert first.share.value + second.share.value == Decimal(100)
    assert SUM_DIFFERS not in result.flags
    assert result.state == CALCULATED
    assert result.largest.item == "II.a"
    assert Decimal(9999) < result.hhi < Decimal(10000)


def test_each_competence_on_its_own_and_subject_filter(informe):
    fund, klass = informe.fund_and_class(1)
    informe.put(klass, row({"II.a": "10"}), reference_date=AUG)
    informe.put(klass, row({"II.b": "20"}), reference_date=SEP)
    informe.put(fund, row({"II.c": "30"}), reference_date=SEP)

    september = carteira_por_segmento(informe.connection, SEP)
    august = only(carteira_por_segmento(informe.connection, AUG, [klass]))

    assert [result.subject for result in september] == [klass, fund]
    assert september[0].largest.item == "II.b"
    assert september[0].reference_date == SEP
    assert (august.largest.item, august.reference_date) == ("II.a", AUG)
    assert carteira_por_segmento(informe.connection, SEP, []) == ()
    assert carteira_por_segmento(informe.connection, "2026-07-31") == ()


def test_other_tables_are_never_read(informe):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {"tab_I.TAB_I2_VL_CARTEIRA": "100", "tab_IV.TAB_IV_A_VL_PL": "100"})

    assert carteira_por_segmento(informe.connection, SEP) == ()


def test_priority_source_wins_and_open_conflict_is_flagged(informe):
    _, klass = informe.fund_and_class(1)
    first = informe.put(klass, row({"II.a": "100"}))
    informe.put(klass, {FIELD["II.a"]: "80", FIELD["II.b"]: "20"}, source="manual")
    later = informe.put(
        klass, {TOTAL: "101"}, collected_at=T1, raw=informe.new_raw("reapresentacao", T1)
    )
    informe.open_conflict(TOTAL, SEP, first[TOTAL], later[TOTAL])

    result = only(carteira_por_segmento(informe.connection, SEP))

    assert result.segment("II.a").amount.value == Decimal(80)
    assert result.segment("II.a").amount.parts[0].source_code == "MANUAL"
    assert result.total.value == Decimal(101)
    assert result.total.parts[0].collected_at == T1
    assert result.segment("II.c").amount.parts[0].collected_at == T0
    assert result.flags == (SUM_DIFFERS, OPEN_CONFLICT)


def test_competence_must_be_month_end(informe):
    with pytest.raises(ValueError):
        carteira_por_segmento(informe.connection, "2026-09-29")


def test_no_cnpj_in_repr_and_only_reads(informe):
    for n in (1, 2):
        _, klass = informe.fund_and_class(n)
        informe.put(klass, row({"II.a": "60", "II.d": "40"}))

    before = informe.connection.total_changes
    results = carteira_por_segmento(informe.connection, SEP)

    assert informe.connection.total_changes == before
    assert len(results) == 2

    for n in (1, 2):
        assert make_test_cnpj(n) not in repr(results) + str(results)


def test_reading_through_open_read_only_leaves_the_file_unchanged(tmp_path):
    path = tmp_path / "fundos.db"
    writer = create_full_schema(path).connect()

    try:
        informe = SyntheticInforme(writer)
        _, klass = informe.fund_and_class(1)
        informe.put(klass, row({"II.h": "100"}))
    finally:
        writer.close()

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = open_read_only(path)

    try:
        assert only(carteira_por_segmento(connection, SEP)).largest.item == "II.h"
        assert connection.in_transaction is False
    finally:
        connection.close()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fundos.db"]
