import hashlib
from decimal import Decimal

import pytest

from apoio import T0
from apoio import T1
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme
from conftest import MIGRATIONS_DIR
from conftest import create_full_schema
from conftest import create_schema

from fundos.indicators.cedentes import ABOVE_100
from fundos.indicators.cedentes import BLOCK_TOTALS
from fundos.indicators.cedentes import FULL_LIST
from fundos.indicators.cedentes import MISSING_POSITION
from fundos.indicators.cedentes import NEGATIVE
from fundos.indicators.cedentes import NO_CEDENTE_STORED
from fundos.indicators.cedentes import REPEATED_CNPJ
from fundos.indicators.cedentes import SEVERAL_CNPJ_IN_POSITION
from fundos.indicators.cedentes import UP_TO_10
from fundos.indicators.cedentes import ZERO
from fundos.indicators.cedentes import share_qualifier
from fundos.indicators.cedentes import stored_cedentes
from fundos.indicators.reading import IndicatorDatabaseError
from fundos.indicators.reading import open_read_only
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING


SEP = "2026-09-30"
AUG = "2026-08-31"


def cedente_cnpj(n):
    """CNPJ ficticio de cedente (alfanumerico, para nao coincidir com o assunto)."""

    return make_test_cnpj(n, alphanumeric=True)


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def with_totals(informe, subject, total_a="100", total_b="0", reference_date=SEP):
    informe.put(
        subject,
        {BLOCK_TOTALS[BLOCK_A]: total_a, BLOCK_TOTALS[BLOCK_B]: total_b},
        reference_date=reference_date,
    )


def only(results):
    assert len(results) == 1
    return results[0]


@pytest.mark.parametrize(
    ("value", "qualifier"),
    (
        (None, None),
        (Decimal("-1"), NEGATIVE),
        (Decimal("0"), ZERO),
        (Decimal("0.0001"), UP_TO_10),
        (Decimal("10"), UP_TO_10),
        (Decimal("10.01"), None),
        (Decimal("100"), None),
        (Decimal("100.01"), ABOVE_100),
    ),
)
def test_share_qualifier(value, qualifier):
    assert share_qualifier(value) == qualifier


def test_cnpj_never_shows_in_repr(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "50")

    result = only(stored_cedentes(full_connection, SEP))
    cedente = result.block(BLOCK_A).cedentes[0]

    assert cedente.cnpj == cedente_cnpj(1)

    for text in (repr(result), str(result), repr(cedente)):
        assert cedente_cnpj(1) not in text
        assert klass.cnpj not in text


def test_block_without_stored_cedente_is_never_zero(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass, total_a="100", total_b="0")

    result = only(stored_cedentes(full_connection, SEP))

    for block in result.blocks:
        assert block.state == NO_CEDENTE_STORED
        assert block.cedentes == ()
        assert (block.stored_count.state, block.stored_count.value, block.stored_count.reason) == (
            NO_DATA,
            None,
            NO_CEDENTE_STORED,
        )
        assert (block.largest_share.state, block.largest_share.value, block.largest_share.reason) == (
            NO_DATA,
            None,
            NO_CEDENTE_STORED,
        )
        assert block.flags == ()

    assert result.block(BLOCK_A).block_total.value == Decimal("100")
    assert result.block(BLOCK_B).block_total.value == Decimal("0")


def test_full_list_of_nine_positions(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass, total_b="500")

    for position in range(1, 10):
        informe.put_cedente(klass, "b", position, cedente_cnpj(position), "11")

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_B)

    assert block.state == PRESENT
    assert [c.position for c in block.cedentes] == list(range(1, 10))
    assert block.stored_count.value == 9
    assert block.flags == (FULL_LIST,)
    assert block.missing_positions == ()


def test_shares_keep_the_informed_value_and_get_a_qualifier(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    shares = ("150", "0", "5", "10", "10.01", "-1")

    for position, share in enumerate(shares, start=1):
        informe.put_cedente(klass, "a", position, cedente_cnpj(position), share)

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert [c.share.value for c in block.cedentes] == [Decimal(s) for s in shares]
    assert [c.qualifier for c in block.cedentes] == [ABOVE_100, ZERO, UP_TO_10, UP_TO_10, None, NEGATIVE]
    assert [c.share.field_name for c in block.cedentes] == [
        "tab_I.TAB_I2A12_PR_CEDENTE_" + str(p) for p in range(1, 7)
    ]


def test_largest_share_is_the_largest_informed_value_without_any_sum(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "60")
    informe.put_cedente(klass, "a", 2, cedente_cnpj(2), "150")
    informe.put_cedente(klass, "a", 3, cedente_cnpj(3), "40")

    largest = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A).largest_share

    assert (largest.state, largest.value, largest.qualifier, largest.position) == (
        PRESENT,
        Decimal("150"),
        ABOVE_100,
        2,
    )
    assert largest.field_name == "tab_I.TAB_I2A12_PR_CEDENTE_2"


def test_cedente_in_both_blocks_is_flagged_and_blocks_are_never_joined(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass, total_b="50")
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "60")
    informe.put_cedente(klass, "a", 2, cedente_cnpj(2), "20")
    informe.put_cedente(klass, "b", 1, cedente_cnpj(1), "30")

    result = only(stored_cedentes(full_connection, SEP))
    block_a, block_b = result.block(BLOCK_A), result.block(BLOCK_B)

    assert [c.in_other_block for c in block_a.cedentes] == [True, False]
    assert [c.in_other_block for c in block_b.cedentes] == [True]
    assert (block_a.stored_count.value, block_b.stored_count.value) == (2, 1)
    assert (block_a.largest_share.value, block_b.largest_share.value) == (Decimal("60"), Decimal("30"))


def test_same_cnpj_in_two_positions_counts_once_and_is_flagged(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "30")
    informe.put_cedente(klass, "a", 2, cedente_cnpj(1), "20")

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert [c.position for c in block.cedentes] == [1, 2]
    assert block.stored_count.value == 1
    assert block.flags == (REPEATED_CNPJ,)


def test_position_without_stored_cnpj_is_flagged(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "30")
    informe.put_cedente(klass, "a", 4, cedente_cnpj(4), "20")

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert block.flags == (MISSING_POSITION,)
    assert block.missing_positions == (2, 3)
    assert block.stored_count.value == 2


def test_cedente_without_share_is_listed_and_counted(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass, total_b="10")
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1))
    informe.put_cedente(klass, "a", 2, cedente_cnpj(2), "25")
    informe.put_cedente(klass, "b", 1, cedente_cnpj(3))

    result = only(stored_cedentes(full_connection, SEP))
    block_a, block_b = result.block(BLOCK_A), result.block(BLOCK_B)

    assert (block_a.cedentes[0].share.state, block_a.cedentes[0].share.reason) == (NO_DATA, REASON_MISSING)
    assert block_a.cedentes[0].qualifier is None
    assert block_a.stored_count.value == 2
    assert block_a.largest_share.value == Decimal("25")
    assert (block_b.state, block_b.stored_count.value) == (PRESENT, 1)
    assert (block_b.largest_share.state, block_b.largest_share.reason) == (NO_DATA, REASON_MISSING)


def test_cedente_listed_with_block_total_zero(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass, total_a="0")
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "30")

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert (block.state, block.block_total.value) == (PRESENT, Decimal("0"))


def test_subject_with_cedente_and_without_block_totals(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "30")

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert block.state == PRESENT
    assert (block.block_total.state, block.block_total.reason) == (NO_DATA, REASON_MISSING)


def test_each_competence_on_its_own(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass, reference_date=AUG)
    with_totals(informe, klass, reference_date=SEP)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "30", reference_date=AUG)

    september = only(stored_cedentes(full_connection, SEP))
    august = only(stored_cedentes(full_connection, AUG))

    assert september.block(BLOCK_A).state == NO_CEDENTE_STORED
    assert august.block(BLOCK_A).stored_count.value == 1


def test_restated_share_uses_the_latest_collection_and_flags_the_conflict(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "20", collected_at=T0)
    informe.put_cedente(
        klass, "a", 1, cedente_cnpj(1), "30", collected_at=T1, raw=informe.new_raw("reapresentado", T1)
    )

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert len(block.cedentes) == 1
    assert (block.cedentes[0].share.value, block.cedentes[0].collected_at) == (Decimal("30"), T1)
    assert block.cedentes[0].open_conflict is True
    assert block.flags == ()


def test_two_cnpjs_in_the_same_position_are_both_listed_and_flagged(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "20", collected_at=T0)
    informe.put_cedente(
        klass, "a", 1, cedente_cnpj(2), "25", collected_at=T1, raw=informe.new_raw("reapresentado", T1)
    )

    block = only(stored_cedentes(full_connection, SEP)).block(BLOCK_A)

    assert sorted(c.cnpj for c in block.cedentes) == sorted([cedente_cnpj(1), cedente_cnpj(2)])
    assert block.flags == (SEVERAL_CNPJ_IN_POSITION,)
    assert block.stored_count.value == 2


def test_fund_subject_and_other_roles(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    with_totals(informe, klass)
    with_totals(informe, fund)
    informe.put_cedente(fund, "b", 1, cedente_cnpj(1), "40")
    informe.put_administrator(klass, make_test_cnpj(5))

    results = stored_cedentes(full_connection, SEP)

    assert [r.subject for r in results] == [klass, fund]
    assert results[0].block(BLOCK_A).state == NO_CEDENTE_STORED
    assert results[0].block(BLOCK_B).state == NO_CEDENTE_STORED
    assert results[1].block(BLOCK_B).stored_count.value == 1
    assert [r.subject for r in stored_cedentes(full_connection, SEP, [fund])] == [fund]
    assert stored_cedentes(full_connection, SEP, []) == ()


def test_database_without_the_cedente_migrations_is_refused(tmp_path):
    path = tmp_path / "fundos.db"
    db = create_schema(path, [MIGRATIONS_DIR / "001_initial_schema.sql", MIGRATIONS_DIR / "002_party_observations.sql"])
    connection = db.connect()

    try:
        with pytest.raises(IndicatorDatabaseError):
            stored_cedentes(connection, SEP)
    finally:
        connection.close()


def test_reading_through_open_read_only_leaves_the_file_unchanged(tmp_path):
    path = tmp_path / "fundos.db"
    writer = create_full_schema(path).connect()

    try:
        informe = SyntheticInforme(writer)
        _, klass = informe.fund_and_class(1)
        with_totals(informe, klass)
        informe.put_cedente(klass, "a", 1, cedente_cnpj(1), "50")
    finally:
        writer.close()

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = open_read_only(path)

    try:
        assert only(stored_cedentes(connection, SEP)).block(BLOCK_A).stored_count.value == 1
        assert connection.in_transaction is False
    finally:
        connection.close()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fundos.db"]


def test_competence_must_be_an_iso_date(informe, full_connection):
    with pytest.raises(ValueError):
        stored_cedentes(full_connection, "30/09/2026")
