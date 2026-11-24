import hashlib
import sqlite3
from decimal import Decimal

import pytest

from apoio import T0
from apoio import T1
from apoio import T2
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme
from conftest import create_full_schema

from fundos.cnpj import InvalidCnpjError
from fundos.indicators.reading import IndicatorDatabaseError
from fundos.indicators.reading import check_field_names
from fundos.indicators.reading import loaded_competences
from fundos.indicators.reading import open_read_only
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.reading import subjects_by_cnpj
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE


OVERDUE = "tab_V.TAB_V_B_VL_DIRCRED_INAD"
PORTFOLIO = "tab_I.TAB_I2_VL_CARTEIRA"
FIELDS = (OVERDUE, PORTFOLIO)
SEP = "2026-09-30"
AUG = "2026-08-31"


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_open_read_only_turns_on_query_only_and_refuses_writes(tmp_path):
    path = tmp_path / "fundos.db"
    create_full_schema(path)
    before = sha256(path)

    connection = open_read_only(path)

    try:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert loaded_competences(connection, FIELDS) == ()

        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO funds (cnpj) VALUES (?)", (make_test_cnpj(1),))
    finally:
        connection.close()

    assert sha256(path) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fundos.db"]


def test_reading_through_open_read_only_leaves_the_file_unchanged(tmp_path):
    path = tmp_path / "fundos.db"
    writer = create_full_schema(path).connect()

    try:
        informe = SyntheticInforme(writer)
        _, klass = informe.fund_and_class(1)
        informe.put(klass, {OVERDUE: "10", PORTFOLIO: "100"})
    finally:
        writer.close()

    before = sha256(path)
    connection = open_read_only(path)

    try:
        values = read_competence(connection, SEP, FIELDS)
        assert values[klass][OVERDUE].value == Decimal("10")
        assert connection.in_transaction is False
    finally:
        connection.close()

    assert sha256(path) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fundos.db"]


def test_open_read_only_accepts_space_accent_and_hash_in_the_path(tmp_path):
    folder = tmp_path / "pasta com espaço #1"
    folder.mkdir()
    path = folder / "fundos ação.db"
    create_full_schema(path)

    connection = open_read_only(path)

    try:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 2
    finally:
        connection.close()

    assert sorted(p.name for p in folder.iterdir()) == ["fundos ação.db"]


def test_open_read_only_refuses_wal_database(tmp_path):
    path = tmp_path / "wal.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("CREATE TABLE t (x)")
    connection.close()

    with pytest.raises(IndicatorDatabaseError) as error:
        open_read_only(path)

    assert "WAL" in str(error.value)
    assert str(tmp_path) not in str(error.value)


@pytest.mark.parametrize("kind", ("missing", "not_sqlite", "network", "empty"))
def test_open_read_only_refuses_bad_paths_without_repeating_them(tmp_path, kind):
    if kind == "missing":
        path = str(tmp_path / "nao_existe.db")
    elif kind == "not_sqlite":
        path = tmp_path / "texto.db"
        path.write_text("nao e banco", encoding="utf-8")
        path = str(path)
    elif kind == "network":
        path = "\\\\servidor_ficticio\\pasta\\fundos.db"
    else:
        path = "  "

    with pytest.raises(IndicatorDatabaseError) as error:
        open_read_only(path)

    assert "servidor_ficticio" not in str(error.value)
    assert str(tmp_path) not in str(error.value)


@pytest.mark.parametrize(
    "fields",
    (
        (),
        ("tab_I",),
        ("tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1",),
        ("tab_I.TAB_I2A12_PR_CEDENTE_1",),
        ("tab_I.CNPJ_ADMIN",),
        (OVERDUE, OVERDUE),
    ),
)
def test_field_list_is_closed_and_never_identification(fields):
    with pytest.raises(ValueError):
        check_field_names(fields)


@pytest.mark.parametrize(
    ("current", "previous"),
    (("2026-09-30", "2026-08-31"), ("2026-03-31", "2026-02-28"), ("2026-01-31", "2025-12-31"), ("2028-03-31", "2028-02-29")),
)
def test_previous_month_end(current, previous):
    assert previous_month_end(current) == previous


@pytest.mark.parametrize("value", ("2026-09-15", "2026-09", "30/09/2026"))
def test_previous_month_end_needs_a_month_end(value):
    with pytest.raises(ValueError):
        previous_month_end(value)


def test_missing_field_is_no_data_and_a_real_zero_is_present(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {OVERDUE: "0"})

    values = read_competence(full_connection, SEP, FIELDS)[klass]

    assert (values[OVERDUE].state, values[OVERDUE].value) == (PRESENT, Decimal("0"))
    assert (values[PORTFOLIO].state, values[PORTFOLIO].value, values[PORTFOLIO].reason) == (
        NO_DATA,
        None,
        REASON_MISSING,
    )


def test_values_keep_the_provenance(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    ids = informe.put(klass, {OVERDUE: "123.45"})

    value = read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE]

    assert value.observation_id == ids[OVERDUE]
    assert value.source_code == "CVM_DADOS_ABERTOS"
    assert value.collected_at == T0
    assert value.reference_date == SEP
    assert value.field_name == OVERDUE
    assert value.open_conflict is False


def test_each_competence_is_read_on_its_own(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {OVERDUE: "8", PORTFOLIO: "80"}, reference_date=AUG)
    informe.put(klass, {OVERDUE: "9", PORTFOLIO: "90"}, reference_date=SEP)

    august = read_competence(full_connection, AUG, FIELDS)[klass]
    september = read_competence(full_connection, SEP, FIELDS)[klass]

    assert (august[OVERDUE].value, august[PORTFOLIO].value) == (Decimal("8"), Decimal("80"))
    assert (september[OVERDUE].value, september[PORTFOLIO].value) == (Decimal("9"), Decimal("90"))
    assert loaded_competences(full_connection, FIELDS) == (AUG, SEP)


def test_a_field_from_an_older_competence_never_fills_the_newer_one(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {OVERDUE: "8", PORTFOLIO: "80"}, reference_date=AUG)
    informe.put(klass, {PORTFOLIO: "90"}, reference_date=SEP)

    september = read_competence(full_connection, SEP, FIELDS)[klass]
    view = full_connection.execute(
        "SELECT value_numeric, reference_date FROM current_observations"
        " WHERE fund_class_id = ? AND field_name = ?",
        (klass.id, OVERDUE),
    ).fetchone()

    assert (september[OVERDUE].state, september[OVERDUE].reason) == (NO_DATA, REASON_MISSING)
    assert tuple(view) == ("8", AUG)


def test_latest_collection_wins_inside_the_competence(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    later = informe.new_raw("reapresentado", T1)
    informe.put(klass, {OVERDUE: "10"}, collected_at=T0)
    ids = informe.put(klass, {OVERDUE: "11"}, collected_at=T1, raw=later)

    value = read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE]

    assert (value.value, value.observation_id, value.collected_at) == (Decimal("11"), ids[OVERDUE], T1)


def test_source_priority_wins_over_a_later_collection(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    manual = informe.put(klass, {OVERDUE: "5"}, source="manual", collected_at=T0)
    informe.put(klass, {OVERDUE: "6"}, source="cvm", collected_at=T2)

    value = read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE]

    assert (value.value, value.observation_id, value.source_code) == (Decimal("5"), manual[OVERDUE], "MANUAL")


def test_inactive_source_is_ignored(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {OVERDUE: "5"}, source="manual")
    cvm = informe.put(klass, {OVERDUE: "6"}, source="cvm")
    full_connection.execute("UPDATE sources SET active = 0 WHERE code = 'MANUAL'")

    value = read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE]

    assert value.observation_id == cvm[OVERDUE]


def test_latest_competence_matches_the_current_observations_view(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    _, other = informe.fund_and_class(2)
    later = informe.new_raw("reapresentado", T1)
    informe.put(klass, {OVERDUE: "1", PORTFOLIO: "10"}, reference_date=AUG)
    informe.put(klass, {OVERDUE: "2", PORTFOLIO: "20"}, reference_date=SEP)
    informe.put(klass, {OVERDUE: "3"}, reference_date=SEP, collected_at=T1, raw=later)
    informe.put(klass, {PORTFOLIO: "25"}, reference_date=SEP, source="manual")
    informe.put(fund, {OVERDUE: "4", PORTFOLIO: "40"}, reference_date=SEP)
    informe.put(other, {OVERDUE: "0", PORTFOLIO: "0"}, reference_date=SEP)

    values = read_competence(full_connection, SEP, FIELDS)
    view = {
        (row[0], row[1], row[2]): row[3]
        for row in full_connection.execute(
            "SELECT fund_id, fund_class_id, field_name, id FROM current_observations"
        )
    }
    ours = {
        (
            subject.id if subject.kind == FUND_SUBJECT else None,
            subject.id if subject.kind == CLASS_SUBJECT else None,
            name,
        ): value.observation_id
        for subject, fields in values.items()
        for name, value in fields.items()
    }

    assert ours == view
    assert values[klass][PORTFOLIO].value == Decimal("25")
    assert values[klass][OVERDUE].value == Decimal("3")


def test_manual_value_of_an_older_competence_does_not_cross_into_the_newer_one(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {OVERDUE: "5"}, reference_date=AUG, source="manual")
    cvm = informe.put(klass, {OVERDUE: "6"}, reference_date=SEP)

    september = read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE]
    august = read_competence(full_connection, AUG, FIELDS)[klass][OVERDUE]
    view = full_connection.execute(
        "SELECT value_numeric, reference_date FROM current_observations"
        " WHERE fund_class_id = ? AND field_name = ?",
        (klass.id, OVERDUE),
    ).fetchone()

    assert (september.value, september.observation_id) == (Decimal("6"), cvm[OVERDUE])
    assert (august.value, august.source_code) == (Decimal("5"), "MANUAL")
    assert tuple(view) == ("5", AUG)


def test_fund_and_class_with_the_same_cnpj_stay_separate(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    informe.put(fund, {OVERDUE: "1"})
    informe.put(klass, {OVERDUE: "2"})

    values = read_competence(full_connection, SEP, FIELDS)

    assert list(values) == [klass, fund]
    assert values[fund][OVERDUE].value == Decimal("1")
    assert values[klass][OVERDUE].value == Decimal("2")
    assert fund.cnpj == klass.cnpj == make_test_cnpj(1)
    assert [s.kind for s in values] == [CLASS_SUBJECT, FUND_SUBJECT]


def test_subject_filter_and_empty_filter(informe, full_connection):
    _, first = informe.fund_and_class(1)
    _, second = informe.fund_and_class(2)
    informe.put(first, {OVERDUE: "1"})
    informe.put(second, {OVERDUE: "2"})

    assert list(read_competence(full_connection, SEP, FIELDS, [second])) == [second]
    assert read_competence(full_connection, SEP, FIELDS, []) == {}

    with pytest.raises(ValueError):
        read_competence(full_connection, SEP, FIELDS, [("classe", second.id)])


def test_subject_without_any_field_in_the_competence_is_not_returned(informe, full_connection):
    _, first = informe.fund_and_class(1)
    _, second = informe.fund_and_class(2)
    informe.put(first, {OVERDUE: "1"})
    informe.put(second, {OVERDUE: "2"}, reference_date=AUG)

    assert list(read_competence(full_connection, SEP, FIELDS)) == [first]


def test_series_observations_are_left_out(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    series = full_connection.execute(
        "INSERT INTO quota_series (fund_class_id, series_label_key) VALUES (?, ?)",
        (klass.id, "serie ficticia"),
    ).lastrowid
    informe.connection.execute(
        "INSERT INTO observations (quota_series_id, source_id, collection_run_id, raw_record_id,"
        " field_name, value_type, value_numeric, reference_date, collected_at, checksum)"
        " VALUES (?, ?, ?, ?, ?, 'numeric', '7', ?, ?, ?)",
        (series, informe.source["cvm"], informe.run["cvm"], informe.raw["cvm"], OVERDUE, SEP, T0, "a" * 64),
    )

    assert read_competence(full_connection, SEP, FIELDS) == {}


def test_value_that_is_not_a_number_is_no_data_without_the_value(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, {OVERDUE: "valor ficticio"}, value_type="text")

    value = read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE]

    assert (value.state, value.value, value.reason) == (NO_DATA, None, REASON_UNEXPECTED_TYPE)
    assert "ficticio" not in repr(value)


def test_open_conflict_is_flagged_on_the_field(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    later = informe.new_raw("reapresentado", T1)
    first = informe.put(klass, {OVERDUE: "10", PORTFOLIO: "100"})
    second = informe.put(klass, {OVERDUE: "11"}, collected_at=T1, raw=later)
    informe.open_conflict(OVERDUE, SEP, first[OVERDUE], second[OVERDUE])

    values = read_competence(full_connection, SEP, FIELDS)[klass]

    assert values[OVERDUE].open_conflict is True
    assert values[PORTFOLIO].open_conflict is False

    full_connection.execute("UPDATE data_conflicts SET status = 'ignored'")

    assert read_competence(full_connection, SEP, FIELDS)[klass][OVERDUE].open_conflict is False


def test_read_snapshot_rolls_back_and_reuses_an_open_transaction(full_connection):
    with read_snapshot(full_connection):
        assert full_connection.in_transaction is True

    assert full_connection.in_transaction is False

    full_connection.execute("BEGIN")

    with read_snapshot(full_connection):
        pass

    assert full_connection.in_transaction is True
    full_connection.execute("ROLLBACK")


def test_competence_must_be_an_iso_date(informe, full_connection):
    with pytest.raises(ValueError):
        read_competence(full_connection, "30/09/2026", FIELDS)


def test_subjects_by_cnpj_returns_fund_and_class_and_never_matches_by_name(informe, full_connection):
    fund, klass = informe.fund_and_class(1)

    assert subjects_by_cnpj(full_connection, make_test_cnpj(1)) == (klass, fund)
    assert subjects_by_cnpj(full_connection, make_test_cnpj(2)) == ()

    with pytest.raises(InvalidCnpjError):
        subjects_by_cnpj(full_connection, "nome de fundo")
