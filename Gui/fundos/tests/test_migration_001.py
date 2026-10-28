import sqlite3
from pathlib import Path

import pytest

from apoio import T0
from apoio import fake_sha256
from apoio import insert_observation
from apoio import make_test_cnpj
from apoio import seed_base


MIGRATION_001 = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "001_initial_schema.sql"
)

EXPECTED_TABLES = {
    "schema_migrations",
    "sources",
    "collection_runs",
    "raw_records",
    "funds",
    "fund_classes",
    "quota_series",
    "observations",
    "data_conflicts",
    "audit_log",
}

EXPECTED_TRIGGERS = {
    "trg_observations_no_update",
    "trg_observations_no_delete",
    "trg_observations_personal_data",
}


def names(connection, kind):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = ? AND name NOT LIKE 'sqlite_%'",
            (kind,),
        )
    }


def snapshot(connection):
    ddl = {
        (row[0], row[1]): row[2]
        for row in connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'"
        )
    }
    counts = {
        name: connection.execute(
            'SELECT COUNT(*) FROM "' + name + '"'
        ).fetchone()[0]
        for name in names(connection, "table")
    }
    return ddl, counts


def test_creates_expected_tables_view_and_triggers(connection):
    assert names(connection, "table") == EXPECTED_TABLES
    assert names(connection, "view") == {"current_observations"}
    assert names(connection, "trigger") == EXPECTED_TRIGGERS


def test_registers_version_one(connection):
    rows = connection.execute(
        "SELECT version, name FROM schema_migrations"
    ).fetchall()

    assert [tuple(row) for row in rows] == [(1, "initial_schema")]


def test_seeds_only_cvm_open_data_and_manual(connection):
    rows = connection.execute(
        "SELECT code, source_type, priority, active FROM sources ORDER BY code"
    ).fetchall()

    assert [tuple(row) for row in rows] == [
        ("CVM_DADOS_ABERTOS", "open_data", 200, 1),
        ("MANUAL", "manual", 1000, 1),
    ]


def test_running_the_migration_twice_changes_nothing(connection):
    before = snapshot(connection)

    connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))

    assert snapshot(connection) == before


def test_new_database_is_consistent(connection):
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def insert_fund_with_class(connection, table, cnpj):
    if table == "funds":
        connection.execute("INSERT INTO funds (cnpj) VALUES (?)", (cnpj,))
        return

    fund = connection.execute(
        "INSERT INTO funds (cnpj) VALUES (?)",
        (make_test_cnpj(9),),
    ).lastrowid
    connection.execute(
        "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
        (fund, cnpj),
    )


@pytest.mark.parametrize("table", ["funds", "fund_classes"])
@pytest.mark.parametrize(
    "cnpj",
    [make_test_cnpj(1), make_test_cnpj(1, alphanumeric=True)],
    ids=["numerico", "alfanumerico"],
)
def test_cnpj_check_accepts_numeric_and_uppercase_alphanumeric(
    connection,
    table,
    cnpj,
):
    insert_fund_with_class(connection, table, cnpj)

    stored = connection.execute(
        "SELECT cnpj FROM " + table + " WHERE cnpj = ?",
        (cnpj,),
    ).fetchone()

    assert stored is not None


@pytest.mark.parametrize("table", ["funds", "fund_classes"])
@pytest.mark.parametrize(
    "cnpj",
    [
        make_test_cnpj(1, alphanumeric=True).lower(),
        make_test_cnpj(1, alphanumeric=True)[:12] + "0A",
        "99.999.991/9999-" + make_test_cnpj(1)[12:],
        make_test_cnpj(1)[:13],
        make_test_cnpj(1)[:11] + "*" + make_test_cnpj(1)[12:],
    ],
    ids=["minuscula", "letra-no-dv", "mascara", "13-caracteres", "simbolo"],
)
def test_cnpj_check_refuses_other_formats(connection, table, cnpj):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_fund_with_class(connection, table, cnpj)


def test_fund_cnpj_is_unique(connection):
    connection.execute("INSERT INTO funds (cnpj) VALUES (?)", (make_test_cnpj(2),))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute(
            "INSERT INTO funds (cnpj) VALUES (?)",
            (make_test_cnpj(2),),
        )


def test_class_cnpj_is_unique_and_needs_an_existing_fund(connection):
    fund = connection.execute(
        "INSERT INTO funds (cnpj) VALUES (?)",
        (make_test_cnpj(2),),
    ).lastrowid
    connection.execute(
        "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
        (fund, make_test_cnpj(3)),
    )

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
            (fund, make_test_cnpj(3)),
        )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
            (999, make_test_cnpj(4)),
        )


def test_quota_series_keys(connection):
    base = seed_base(connection)
    insert = (
        "INSERT INTO quota_series "
        "(fund_class_id, fund_id, series_label_key, cvm_subclass_id) "
        "VALUES (?, ?, ?, ?)"
    )
    connection.execute(insert, (base["fund_class"], None, "subclasse senior", "SUB1"))

    # Mesmo rotulo na mesma classe, mesmo ID de subclasse em outra serie.
    for values in (
        (base["fund_class"], None, "subclasse senior", None),
        (base["fund_class"], None, "outra", "SUB1"),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            connection.execute(insert, values)

    # O mesmo rotulo sob o fundo e outra serie.
    connection.execute(insert, (None, base["fund"], "subclasse senior", None))

    # Sem pai, com dois pais, sem chave, rotulo fora da forma normalizada.
    for values in (
        (None, None, "x", None),
        (base["fund_class"], base["fund"], "y", None),
        (base["fund_class"], None, None, None),
        (base["fund_class"], None, "Subclasse Senior", None),
        (base["fund_class"], None, "senior |", None),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            connection.execute(insert, values)


@pytest.mark.parametrize(
    "subjects",
    [(), ("fund", "class")],
    ids=["nenhum-assunto", "dois-assuntos"],
)
def test_observation_needs_exactly_one_subject(connection, subjects):
    base = seed_base(connection)
    columns = {"fund": "fund_id", "class": "fund_class_id"}
    values = {"fund": base["fund"], "class": base["fund_class"]}
    subject_columns = "".join(columns[s] + ", " for s in subjects)
    placeholders = "".join("?, " for _ in subjects)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(
            "INSERT INTO observations ("
            + subject_columns
            + "source_id, collection_run_id, raw_record_id, field_name, "
            "value_type, value_numeric, reference_date, collected_at, checksum"
            ") VALUES ("
            + placeholders
            + "?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(values[s] for s in subjects)
            + (
                base["cvm"],
                base["cvm_run"],
                base["cvm_raw"],
                "tab_IV.TAB_IV_A_VL_PL",
                "numeric",
                "1",
                "2026-09-30",
                T0,
                fake_sha256("x"),
            ),
        )


def test_observation_needs_exactly_one_value_of_its_type(connection):
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(
            """
            INSERT INTO observations (
                fund_class_id, source_id, collection_run_id, raw_record_id,
                field_name, value_type, value_text, value_numeric,
                reference_date, collected_at, checksum
            ) VALUES (?, ?, ?, ?, 'tab_IV.TAB_IV_A_VL_PL', 'numeric',
                      'texto', '1', '2026-09-30', ?, ?)
            """,
            (
                base["fund_class"],
                base["cvm"],
                base["cvm_run"],
                base["cvm_raw"],
                T0,
                fake_sha256("y"),
            ),
        )


@pytest.mark.parametrize(
    "field_name",
    ["TAB_IV_A_VL_PL", "tab_IV.", ".TAB_IV", "a.b.c", "tab IV.X", "tab_IV.VL_Ç"],
)
def test_field_name_must_be_table_dot_column(connection, field_name):
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_observation(
            connection,
            subject=("class", base["fund_class"]),
            source=base["cvm"],
            run=base["cvm_run"],
            raw=base["cvm_raw"],
            field_name=field_name,
        )


def test_numeric_value_is_kept_exactly_as_text(connection):
    base = seed_base(connection)
    exact = "12345678901234567.123456"
    observation = insert_observation(
        connection,
        subject=("class", base["fund_class"]),
        source=base["cvm"],
        run=base["cvm_run"],
        raw=base["cvm_raw"],
        value=exact,
    )

    stored = connection.execute(
        "SELECT value_numeric, typeof(value_numeric) FROM observations WHERE id = ?",
        (observation,),
    ).fetchone()

    assert tuple(stored) == (exact, "text")


@pytest.mark.parametrize("value", ["1,5", "1e5", "--1", "1.", ".5", "1.2.3"])
def test_numeric_text_must_be_a_plain_decimal(connection, value):
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_observation(
            connection,
            subject=("class", base["fund_class"]),
            source=base["cvm"],
            run=base["cvm_run"],
            raw=base["cvm_raw"],
            value=value,
        )


def test_observations_cannot_be_updated_or_deleted(connection):
    base = seed_base(connection)
    observation = insert_observation(
        connection,
        subject=("class", base["fund_class"]),
        source=base["cvm"],
        run=base["cvm_run"],
        raw=base["cvm_raw"],
    )

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        connection.execute(
            "UPDATE observations SET value_numeric = '2' WHERE id = ?",
            (observation,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        connection.execute(
            "DELETE FROM observations WHERE id = ?",
            (observation,),
        )

    assert connection.execute(
        "SELECT value_numeric FROM observations WHERE id = ?",
        (observation,),
    ).fetchone()[0] == "100"


def test_conflict_pair_is_ordered_and_unique(connection):
    base = seed_base(connection)
    first = insert_observation(
        connection,
        subject=("class", base["fund_class"]),
        source=base["cvm"],
        run=base["cvm_run"],
        raw=base["cvm_raw"],
        value="1",
    )
    second = insert_observation(
        connection,
        subject=("class", base["fund_class"]),
        source=base["cvm"],
        run=base["cvm_run"],
        raw=base["cvm_raw"],
        value="2",
    )
    insert = (
        "INSERT INTO data_conflicts "
        "(field_name, reference_date, observation_a_id, observation_b_id) "
        "VALUES ('tab_IV.TAB_IV_A_VL_PL', '2026-09-30', ?, ?)"
    )
    connection.execute(insert, (first, second))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute(insert, (first, second))

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(insert, (second, first))


@pytest.mark.parametrize(
    "column, value",
    [
        ("sha256", "ABC"),
        ("sha256", "A" * 64),
        ("size_bytes", 0),
        ("file_name", "pasta/arquivo.zip"),
        ("file_name", "C:arquivo.zip"),
        ("file_name", "pasta\\arquivo.zip"),
        ("request_url", "http://exemplo.invalid/arquivo.zip"),
    ],
)
def test_raw_record_manifest_checks(connection, column, value):
    base = seed_base(connection)
    row = {
        "source_id": base["cvm"],
        "collection_run_id": base["cvm_run"],
        "file_name": "outro_ficticio.zip",
        "size_bytes": 10,
        "sha256": fake_sha256("outro"),
        "collected_at": T0,
    }
    row[column] = value

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(
            "INSERT INTO raw_records ("
            + ", ".join(row)
            + ") VALUES ("
            + ", ".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )


def test_raw_record_manifest_is_unique_per_source_parent_name_and_hash(connection):
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute(
            """
            INSERT INTO raw_records (
                source_id, collection_run_id, file_name, size_bytes,
                sha256, collected_at
            ) VALUES (?, ?, 'cvm_ficticio.zip', 100, ?, ?)
            """,
            (base["cvm"], base["cvm_run"], fake_sha256("cvm"), T0),
        )


def test_source_in_use_cannot_be_deleted(connection):
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute("DELETE FROM sources WHERE id = ?", (base["cvm"],))
