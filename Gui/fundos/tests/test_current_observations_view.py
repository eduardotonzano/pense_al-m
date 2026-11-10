from apoio import T0
from apoio import T1
from apoio import insert_observation
from apoio import insert_raw
from apoio import seed_base


FIELD = "tab_IV.TAB_IV_A_VL_PL"


def current(connection, column, subject_id, field_name=FIELD):
    return connection.execute(
        "SELECT * FROM current_observations WHERE "
        + column
        + " = ? AND field_name = ?",
        (subject_id, field_name),
    ).fetchall()


def add(connection, base, source, value, reference_date, collected_at=T0, raw=None, subject=None):
    prefix = "cvm" if source == "cvm" else "manual"
    return insert_observation(
        connection,
        subject=subject or ("class", base["fund_class"]),
        source=base[prefix],
        run=base[prefix + "_run"],
        raw=raw or base[prefix + "_raw"],
        value=value,
        reference_date=reference_date,
        collected_at=collected_at,
    )


def test_higher_priority_source_wins_over_newer_reference_date(connection):
    base = seed_base(connection)
    manual = add(connection, base, "manual", "10", "2026-06-30")
    add(connection, base, "cvm", "20", "2026-09-30")

    rows = current(connection, "fund_class_id", base["fund_class"])

    assert [row["id"] for row in rows] == [manual]
    assert rows[0]["source_code"] == "MANUAL"


def test_same_source_most_recent_reference_date_wins(connection):
    base = seed_base(connection)
    add(connection, base, "cvm", "10", "2026-08-31")
    latest = add(connection, base, "cvm", "20", "2026-09-30")

    rows = current(connection, "fund_class_id", base["fund_class"])

    assert [row["id"] for row in rows] == [latest]


def test_same_reference_date_most_recent_collection_wins_and_both_rows_stay(connection):
    base = seed_base(connection)
    later_raw = insert_raw(connection, base["cvm"], base["cvm_run"], "cvm_reapresentado", T1)
    add(connection, base, "cvm", "10", "2026-09-30", collected_at=T0)
    resubmitted = add(
        connection,
        base,
        "cvm",
        "11",
        "2026-09-30",
        collected_at=T1,
        raw=later_raw,
    )

    rows = current(connection, "fund_class_id", base["fund_class"])
    history = connection.execute(
        "SELECT value_numeric FROM observations ORDER BY id"
    ).fetchall()

    assert [row["id"] for row in rows] == [resubmitted]
    assert [row[0] for row in history] == ["10", "11"]


def test_inactive_source_is_ignored(connection):
    base = seed_base(connection)
    add(connection, base, "manual", "10", "2026-09-30")
    cvm = add(connection, base, "cvm", "20", "2026-09-30")
    connection.execute("UPDATE sources SET active = 0 WHERE code = 'MANUAL'")

    rows = current(connection, "fund_class_id", base["fund_class"])

    assert [row["id"] for row in rows] == [cvm]


def test_fund_class_and_series_subjects_do_not_mix(connection):
    base = seed_base(connection)
    series = connection.execute(
        "INSERT INTO quota_series (fund_class_id, series_label_key) VALUES (?, ?)",
        (base["fund_class"], "subclasse senior serie 1"),
    ).lastrowid
    on_fund = add(connection, base, "cvm", "1", "2026-09-30", subject=("fund", base["fund"]))
    on_class = add(connection, base, "cvm", "2", "2026-09-30")
    on_series = add(connection, base, "cvm", "3", "2026-09-30", subject=("series", series))

    assert [r["id"] for r in current(connection, "fund_id", base["fund"])] == [on_fund]
    assert [r["id"] for r in current(connection, "fund_class_id", base["fund_class"])] == [on_class]
    assert [r["id"] for r in current(connection, "quota_series_id", series)] == [on_series]


def test_view_exposes_provenance(connection):
    base = seed_base(connection)
    add(connection, base, "cvm", "10", "2026-09-30")

    row = current(connection, "fund_class_id", base["fund_class"])[0]

    assert row["raw_record_id"] == base["cvm_raw"]
    assert row["collection_run_id"] == base["cvm_run"]
    assert row["source_id"] == base["cvm"]
    assert row["source_code"] == "CVM_DADOS_ABERTOS"
    assert row["source_priority"] == 200
    assert row["reference_date"] == "2026-09-30"
    assert row["collected_at"] == T0
