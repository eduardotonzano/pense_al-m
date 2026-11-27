import sqlite3

import pytest

from apoio import COLLECTED
from apoio import MIGRATION_001
from apoio import T0
from apoio import add_catalog_field
from apoio import add_raw_record
from apoio import add_run
from apoio import add_subject
from apoio import apply_migration
from apoio import fake_sha256
from apoio import insert_observation
from apoio import names
from apoio import snapshot
from apoio import source_id
from apoio import unique_checksum


EXPECTED_TABLES = {
    "schema_migrations",
    "sources",
    "collection_runs",
    "raw_records",
    "subjects",
    "field_catalog",
    "observations",
    "unmatched_issuers",
    "data_conflicts",
    "audit_log",
}

EXPECTED_TRIGGERS = {
    "trg_observations_no_update",
    "trg_observations_no_delete",
    "trg_observations_reference_not_future",
}

CNPJ_A = "11222333000181"
CNPJ_B = "44555666000122"


@pytest.fixture
def base(connection):
    """Coleta, arquivo bruto, campo do catalogo e um banco (sujeito)."""

    run_id = add_run(connection)
    raw_id = add_raw_record(connection, run_id)
    add_catalog_field(connection, run_id)
    subject_id = add_subject(connection, run_id, CNPJ_A)
    return connection, run_id, raw_id, subject_id


# --- estrutura -------------------------------------------------------------


def test_creates_expected_tables_view_and_triggers(connection):
    assert names(connection, "table") == EXPECTED_TABLES
    assert names(connection, "view") == {"current_observations"}
    assert names(connection, "trigger") == EXPECTED_TRIGGERS


def test_registers_version_one(connection):
    rows = connection.execute(
        "SELECT version, name FROM schema_migrations"
    ).fetchall()

    assert [tuple(row) for row in rows] == [(1, "initial_schema")]


def test_integrity_and_foreign_keys_are_clean(connection):
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_no_object_mentions_cpf(connection):
    for kind in ("table", "view", "index", "trigger"):
        assert not [n for n in names(connection, kind) if "cpf" in n.lower()]

    for table in names(connection, "table"):
        columns = [
            row[1]
            for row in connection.execute(
                'PRAGMA table_info("' + table + '")'
            )
        ]
        assert not [c for c in columns if "cpf" in c.lower()], table


def test_second_application_changes_nothing(connection):
    before = snapshot(connection)

    apply_migration(connection)

    assert snapshot(connection) == before


# --- fontes ----------------------------------------------------------------


def test_seeded_sources_by_code(connection):
    rows = connection.execute(
        "SELECT code, source_type, layer, priority, active "
        "FROM sources ORDER BY priority DESC"
    ).fetchall()

    assert [tuple(row) for row in rows] == [
        ("BACEN_IFDATA", "api", "bacen", 550, 1),
        ("BACEN_SGS", "api", "bacen", 540, 1),
        ("CVM_OFERTAS", "open_data", "cvm", 450, 1),
        ("CVM_CDA", "open_data", "cvm", 440, 1),
    ]


def test_scale_follows_the_source_hierarchy(connection):
    order = ["bacen", "cvm", "anbima", "specialized", "institutional"]
    rank = {layer: position for position, layer in enumerate(order)}
    rows = connection.execute(
        "SELECT layer, priority FROM sources"
    ).fetchall()

    for first in rows:
        for second in rows:
            if rank[first["layer"]] < rank[second["layer"]]:
                assert first["priority"] > second["priority"]


def test_priorities_are_unique(connection):
    rows = connection.execute("SELECT priority FROM sources").fetchall()

    assert len({row[0] for row in rows}) == len(rows)


@pytest.mark.parametrize(
    "layer, priority",
    [
        ("cvm", 550),
        ("bacen", 450),
        ("anbima", 450),
        ("anbima", 400),
        ("specialized", 150),
        ("institutional", 250),
        ("bacen", 99),
        ("bacen", 600),
        ("manual", 999),
        ("manual", 550),
    ],
)
def test_priority_outside_the_layer_band_is_refused(
    connection, layer, priority
):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO sources(code, name, source_type, layer, priority) "
            "VALUES('NOVA', 'Nova', 'api', ?, ?)",
            (layer, priority),
        )


@pytest.mark.parametrize(
    "layer, priority",
    [
        ("anbima", 350),
        ("specialized", 250),
        ("institutional", 150),
        ("manual", 1000),
    ],
)
def test_priority_inside_the_layer_band_is_accepted(
    connection, layer, priority
):
    connection.execute(
        "INSERT INTO sources(code, name, source_type, layer, priority) "
        "VALUES('NOVA', 'Nova', 'api', ?, ?)",
        (layer, priority),
    )


def test_internal_source_type_is_refused(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO sources(code, name, source_type, layer, priority) "
            "VALUES('CASA', 'Dado da casa', 'internal', 'bacen', 560)"
        )


def test_anbima_b3_and_fgc_are_not_seeded(connection):
    codes = {
        row[0] for row in connection.execute("SELECT code FROM sources")
    }

    assert not [c for c in codes if c.startswith(("ANBIMA", "B3", "FGC"))]


# --- coletas e arquivo bruto ----------------------------------------------


def test_running_run_has_no_finish_time_and_finished_has(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO collection_runs(source_id, started_at, status) "
            "VALUES(?, ?, 'success')",
            (source_id(connection, "BACEN_IFDATA"), T0),
        )


def test_same_manifest_twice_is_refused(base):
    connection, run_id, _raw_id, _subject_id = base
    sha = fake_sha256("mesmo-arquivo")
    sql = (
        "INSERT INTO raw_records(source_id, collection_run_id, file_name, "
        "size_bytes, sha256, collected_at) VALUES(?, ?, 'cda.csv', 5, ?, ?)"
    )
    args = (source_id(connection, "CVM_CDA"), run_id, sha, COLLECTED)
    connection.execute(sql, args)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql, args)


def test_republished_file_with_new_hash_is_a_new_manifest(base):
    connection, run_id, _raw_id, _subject_id = base
    sql = (
        "INSERT INTO raw_records(source_id, collection_run_id, file_name, "
        "size_bytes, sha256, collected_at) VALUES(?, ?, 'cda.csv', 5, ?, ?)"
    )
    cda = source_id(connection, "CVM_CDA")
    connection.execute(sql, (cda, run_id, fake_sha256("v1"), COLLECTED))
    connection.execute(sql, (cda, run_id, fake_sha256("v2"), COLLECTED))


@pytest.mark.parametrize(
    "sha",
    ["abc", "G" * 64, fake_sha256("x").upper()],
)
def test_raw_record_refuses_a_bad_hash(base, sha):
    connection, run_id, _raw_id, _subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO raw_records(source_id, collection_run_id, "
            "file_name, size_bytes, sha256, collected_at) "
            "VALUES(?, ?, 'x.csv', 5, ?, ?)",
            (source_id(connection, "CVM_CDA"), run_id, sha, COLLECTED),
        )


def test_failed_raw_record_needs_an_error(base):
    connection, run_id, _raw_id, _subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO raw_records(source_id, collection_run_id, "
            "file_name, size_bytes, sha256, collected_at, "
            "processing_status) VALUES(?, ?, 'x.csv', 5, ?, ?, 'failed')",
            (
                source_id(connection, "CVM_CDA"),
                run_id,
                fake_sha256("f"),
                COLLECTED,
            ),
        )


# --- sujeitos --------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        CNPJ_A,
        "12ABC345000195",
        "AB12CD34EF5601",
    ],
)
def test_institution_accepts_a_14_character_cnpj(connection, key):
    run_id = add_run(connection)

    add_subject(connection, run_id, key)


@pytest.mark.parametrize(
    "key",
    [
        "11222333",
        "11.222.333/0001-81",
        "11222333000181 ",
        "1122233300018",
        "112223330001811",
        "11222333000AB1",
        "c0080312",
        "C0080312",
        "11222333000181".lower().replace("1", "a"),
    ],
)
def test_institution_refuses_other_formats(connection, key):
    run_id = add_run(connection)

    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, run_id, key)


def test_a_root_of_8_digits_does_not_create_a_subject(connection):
    run_id = add_run(connection)

    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, run_id, "11222333", kind="institution")


def test_conglomerate_accepts_only_the_bacen_code(connection):
    run_id = add_run(connection)

    add_subject(connection, run_id, "C0080312", kind="conglomerate")

    for key in ("0080312", "C008031", "C00803123", "c0080312", CNPJ_A):
        with pytest.raises(sqlite3.IntegrityError):
            add_subject(
                connection,
                run_id,
                key,
                kind="conglomerate",
                entity_id="entity-" + key,
            )


def test_kind_and_key_must_match(connection):
    run_id = add_run(connection)

    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, run_id, "C0080312", kind="institution")


def test_same_kind_and_key_twice_is_refused(connection):
    run_id = add_run(connection)
    add_subject(connection, run_id, CNPJ_A, entity_id="entity-1")

    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, run_id, CNPJ_A, entity_id="entity-2")


def test_one_entity_has_one_subject(connection):
    run_id = add_run(connection)
    add_subject(connection, run_id, CNPJ_A, entity_id="entity-1")

    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, run_id, CNPJ_B, entity_id="entity-1")


def test_two_institutions_with_the_same_root_are_refused(connection):
    run_id = add_run(connection)
    add_subject(connection, run_id, "11222333000181", entity_id="matriz")

    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, run_id, "11222333000262", entity_id="filial")


def test_a_conglomerate_does_not_collide_with_an_institution_root(connection):
    run_id = add_run(connection)
    add_subject(connection, run_id, "C0080312", kind="conglomerate")
    add_subject(connection, run_id, "00803123000100", entity_id="instituicao")


def test_subject_needs_an_existing_run(connection):
    with pytest.raises(sqlite3.IntegrityError):
        add_subject(connection, 999, CNPJ_A)


# --- catalogo de campos ----------------------------------------------------


def test_unit_starts_unconfirmed_and_null(base):
    connection, _run_id, _raw_id, _subject_id = base

    row = connection.execute(
        "SELECT unit, unit_confirmed FROM field_catalog"
    ).fetchone()

    assert (row["unit"], row["unit_confirmed"]) == (None, 0)


def test_confirmed_unit_needs_a_unit(base):
    connection, run_id, _raw_id, _subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO field_catalog(source_id, field_name, label, "
            "unit_confirmed, first_seen_run_id) "
            "VALUES(?, 'r5.c79665', 'RWA', 1, ?)",
            (source_id(connection, "BACEN_IFDATA"), run_id),
        )


@pytest.mark.parametrize(
    "field_name",
    ["r5", "r5.", ".c1", "r5.c1.x", "r5 .c1", "r5.c-1"],
)
def test_catalog_refuses_a_malformed_field_name(base, field_name):
    connection, run_id, _raw_id, _subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO field_catalog(source_id, field_name, label, "
            "first_seen_run_id) VALUES(?, ?, 'x', ?)",
            (source_id(connection, "BACEN_IFDATA"), field_name, run_id),
        )


# --- observacoes -----------------------------------------------------------


def test_observation_is_stored_with_the_exact_decimal(base):
    connection, run_id, raw_id, subject_id = base

    insert_observation(connection, subject_id, run_id, raw_id)

    row = connection.execute(
        "SELECT value_numeric, reference_date, confidence FROM observations"
    ).fetchone()

    assert row["value_numeric"] == "0.161796402088591"
    assert row["reference_date"] == "2026-06-30"
    assert row["confidence"] == "reported"


def test_observation_needs_the_field_in_the_catalog(base):
    connection, run_id, raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection, subject_id, run_id, raw_id, field_name="r5.c99999"
        )


def test_the_catalog_is_per_source(base):
    connection, run_id, raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection, subject_id, run_id, raw_id, code="CVM_CDA"
        )


def test_observation_needs_a_subject(base):
    connection, run_id, raw_id, _subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(connection, 999, run_id, raw_id)


def test_observation_needs_a_raw_record(base):
    connection, run_id, _raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(connection, subject_id, run_id, 999)


def test_same_checksum_twice_is_refused(base):
    connection, run_id, raw_id, subject_id = base
    checksum = fake_sha256("igual")
    insert_observation(
        connection, subject_id, run_id, raw_id, checksum=checksum
    )

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection, subject_id, run_id, raw_id, checksum=checksum
        )


def test_observation_cannot_be_updated(base):
    connection, run_id, raw_id, subject_id = base
    observation_id = insert_observation(
        connection, subject_id, run_id, raw_id
    )

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        connection.execute(
            "UPDATE observations SET value_numeric = '0.5' WHERE id = ?",
            (observation_id,),
        )


def test_observation_cannot_be_deleted(base):
    connection, run_id, raw_id, subject_id = base
    observation_id = insert_observation(
        connection, subject_id, run_id, raw_id
    )

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        connection.execute(
            "DELETE FROM observations WHERE id = ?", (observation_id,)
        )


def test_reference_date_after_the_collection_is_refused(base):
    connection, run_id, raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError, match="posterior"):
        insert_observation(
            connection,
            subject_id,
            run_id,
            raw_id,
            reference_date="2026-12-31",
            collected_at="2026-11-27T10:00:00",
        )


def test_reference_date_on_the_collection_day_is_accepted(base):
    connection, run_id, raw_id, subject_id = base

    insert_observation(
        connection,
        subject_id,
        run_id,
        raw_id,
        reference_date="2026-11-27",
        collected_at="2026-11-27T10:00:00",
    )


@pytest.mark.parametrize(
    "value",
    ["abc", "1.2.3", "--1", "1e5", "", ".5", "5.", "0,16", "1 2"],
)
def test_numeric_value_must_be_a_plain_decimal(base, value):
    connection, run_id, raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection, subject_id, run_id, raw_id, value=value
        )


@pytest.mark.parametrize("value", ["0", "17.29", "-48849708.57", "72255299877.74"])
def test_numeric_value_accepts_plain_decimals(base, value):
    connection, run_id, raw_id, subject_id = base

    insert_observation(connection, subject_id, run_id, raw_id, value=value)


def test_exactly_one_value_column_matches_the_type(base):
    connection, run_id, raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection,
            subject_id,
            run_id,
            raw_id,
            value_text="sobra",
        )

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection,
            subject_id,
            run_id,
            raw_id,
            value_type="text",
        )


def test_confidence_values_are_limited(base):
    connection, run_id, raw_id, subject_id = base

    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(
            connection,
            subject_id,
            run_id,
            raw_id,
            confidence="provavel",
        )


# --- valor atual (ADR-010 b) ----------------------------------------------


def seed_two_sources(connection):
    """Mesmo campo e sujeito gravado por duas fontes ativas."""

    run_a = add_run(connection, "BACEN_IFDATA")
    run_b = add_run(connection, "CVM_CDA")
    raw_a = add_raw_record(connection, run_a, "BACEN_IFDATA", "a.json")
    raw_b = add_raw_record(connection, run_b, "CVM_CDA", "b.csv")
    add_catalog_field(connection, run_a, "r5.c79664", "BACEN_IFDATA")
    add_catalog_field(connection, run_b, "r5.c79664", "CVM_CDA")
    subject_id = add_subject(connection, run_a, CNPJ_A)
    return subject_id, run_a, raw_a, run_b, raw_b


def current(connection):
    return connection.execute(
        "SELECT value_numeric, source_code, reference_date "
        "FROM current_observations"
    ).fetchall()


def test_view_shows_the_most_recent_reference_over_a_higher_priority(
    connection,
):
    subject_id, run_a, raw_a, run_b, raw_b = seed_two_sources(connection)
    insert_observation(
        connection, subject_id, run_a, raw_a, "BACEN_IFDATA",
        value="0.10", reference_date="2026-03-31",
    )
    insert_observation(
        connection, subject_id, run_b, raw_b, "CVM_CDA",
        value="0.20", reference_date="2026-06-30",
    )

    rows = current(connection)

    assert [tuple(row) for row in rows] == [("0.20", "CVM_CDA", "2026-06-30")]


def test_view_prefers_the_higher_priority_in_the_same_reference(connection):
    subject_id, run_a, raw_a, run_b, raw_b = seed_two_sources(connection)
    insert_observation(
        connection, subject_id, run_b, raw_b, "CVM_CDA",
        value="0.20", reference_date="2026-06-30",
    )
    insert_observation(
        connection, subject_id, run_a, raw_a, "BACEN_IFDATA",
        value="0.10", reference_date="2026-06-30",
    )

    rows = current(connection)

    assert [tuple(row) for row in rows] == [
        ("0.10", "BACEN_IFDATA", "2026-06-30")
    ]


def test_view_keeps_the_most_recent_collection_in_the_same_source(
    connection,
):
    subject_id, run_a, raw_a, _run_b, _raw_b = seed_two_sources(connection)
    insert_observation(
        connection, subject_id, run_a, raw_a, "BACEN_IFDATA",
        value="0.10", reference_date="2026-06-30",
        collected_at="2026-11-26T10:00:00",
    )
    insert_observation(
        connection, subject_id, run_a, raw_a, "BACEN_IFDATA",
        value="0.11", reference_date="2026-06-30",
        collected_at="2026-11-27T10:00:00",
    )

    assert [tuple(r) for r in current(connection)] == [
        ("0.11", "BACEN_IFDATA", "2026-06-30")
    ]
    assert connection.execute(
        "SELECT COUNT(*) FROM observations"
    ).fetchone()[0] == 2


def test_view_ignores_inactive_sources(connection):
    subject_id, run_a, raw_a, run_b, raw_b = seed_two_sources(connection)
    insert_observation(
        connection, subject_id, run_a, raw_a, "BACEN_IFDATA",
        value="0.10", reference_date="2026-06-30",
    )
    insert_observation(
        connection, subject_id, run_b, raw_b, "CVM_CDA",
        value="0.20", reference_date="2026-06-30",
    )
    connection.execute(
        "UPDATE sources SET active = 0 WHERE code = 'BACEN_IFDATA'"
    )

    assert [tuple(r) for r in current(connection)] == [
        ("0.20", "CVM_CDA", "2026-06-30")
    ]


def test_view_exposes_source_layer_and_priority(base):
    connection, run_id, raw_id, subject_id = base
    insert_observation(connection, subject_id, run_id, raw_id)

    row = connection.execute(
        "SELECT source_code, source_layer, source_priority "
        "FROM current_observations"
    ).fetchone()

    assert tuple(row) == ("BACEN_IFDATA", "bacen", 550)


# --- fila de revisao -------------------------------------------------------


def add_unmatched(connection, run_id, kind, value, reason="no_entity"):
    return connection.execute(
        "INSERT INTO unmatched_issuers(source_id, key_kind, key_value, "
        "name_seen, reason, first_run_id, last_run_id) "
        "VALUES(?, ?, ?, 'BANCO FICTICIO S.A.', ?, ?, ?)",
        (
            source_id(connection, "BACEN_IFDATA"),
            kind,
            value,
            reason,
            run_id,
            run_id,
        ),
    ).lastrowid


@pytest.mark.parametrize(
    "kind, value",
    [
        ("cnpj", CNPJ_A),
        ("cnpj_root", "11222333"),
        ("conglomerate_code", "C0080312"),
    ],
)
def test_unmatched_accepts_the_three_key_kinds(connection, kind, value):
    run_id = add_run(connection)

    add_unmatched(connection, run_id, kind, value)


@pytest.mark.parametrize(
    "kind, value",
    [
        ("cnpj", "11222333"),
        ("cnpj", "11.222.333/0001-81"),
        ("cnpj_root", CNPJ_A),
        ("cnpj_root", "1122233"),
        ("conglomerate_code", "0080312"),
        ("conglomerate_code", "c0080312"),
        ("cpf", "12345678901"),
    ],
)
def test_unmatched_refuses_malformed_keys(connection, kind, value):
    run_id = add_run(connection)

    with pytest.raises(sqlite3.IntegrityError):
        add_unmatched(connection, run_id, kind, value)


def test_unmatched_key_is_unique_per_source(connection):
    run_id = add_run(connection)
    add_unmatched(connection, run_id, "cnpj_root", "11222333")

    with pytest.raises(sqlite3.IntegrityError):
        add_unmatched(
            connection, run_id, "cnpj_root", "11222333", "ambiguous_root"
        )


def test_unmatched_reason_is_limited(connection):
    run_id = add_run(connection)

    with pytest.raises(sqlite3.IntegrityError):
        add_unmatched(connection, run_id, "cnpj", CNPJ_A, "palpite_por_nome")


def test_unmatched_resolution_needs_a_date(connection):
    run_id = add_run(connection)
    queue_id = add_unmatched(connection, run_id, "cnpj", CNPJ_A)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE unmatched_issuers SET status = 'resolved' WHERE id = ?",
            (queue_id,),
        )

    connection.execute(
        "UPDATE unmatched_issuers SET status = 'resolved', "
        "resolved_at = ? WHERE id = ?",
        (COLLECTED, queue_id),
    )


def test_unmatched_never_creates_a_subject(connection):
    run_id = add_run(connection)
    add_unmatched(connection, run_id, "cnpj", CNPJ_A)

    assert connection.execute(
        "SELECT COUNT(*) FROM subjects"
    ).fetchone()[0] == 0


# --- conflitos e auditoria -------------------------------------------------


def test_conflict_needs_two_different_observations(base):
    connection, run_id, raw_id, subject_id = base
    first = insert_observation(connection, subject_id, run_id, raw_id)
    second = insert_observation(
        connection, subject_id, run_id, raw_id, value="0.17"
    )
    sql = (
        "INSERT INTO data_conflicts(subject_id, field_name, reference_date, "
        "observation_a_id, observation_b_id) "
        "VALUES(?, 'r5.c79664', '2026-06-30', ?, ?)"
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql, (subject_id, first, first))

    connection.execute(sql, (subject_id, first, second))

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql, (subject_id, first, second))


def test_conflict_resolution_needs_a_date(base):
    connection, run_id, raw_id, subject_id = base
    first = insert_observation(connection, subject_id, run_id, raw_id)
    second = insert_observation(
        connection, subject_id, run_id, raw_id, value="0.17"
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO data_conflicts(subject_id, field_name, "
            "reference_date, observation_a_id, observation_b_id, status) "
            "VALUES(?, 'r5.c79664', '2026-06-30', ?, ?, 'resolved')",
            (subject_id, first, second),
        )


def test_audit_log_needs_an_actor(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO audit_log(actor, action, entity_type, entity_id) "
            "VALUES('  ', 'resolver', 'unmatched_issuers', 1)"
        )

    connection.execute(
        "INSERT INTO audit_log(actor, action, entity_type, entity_id, reason) "
        "VALUES('Enrico', 'resolver', 'unmatched_issuers', 1, 'conferido')"
    )


# --- varias execucoes ------------------------------------------------------


def test_foreign_key_check_stays_clean_after_use(base):
    connection, run_id, raw_id, subject_id = base
    insert_observation(connection, subject_id, run_id, raw_id)
    insert_observation(
        connection, subject_id, run_id, raw_id, value="0.17",
        reference_date="2026-03-31", checksum=unique_checksum(),
    )

    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_the_migration_file_is_the_one_under_test():
    assert MIGRATION_001.name == "001_initial_schema.sql"
    assert MIGRATION_001.is_file()
