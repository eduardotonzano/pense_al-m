import hashlib
import itertools
import pathlib
import sqlite3

import pytest

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import (
    DebentureRepository,
)
from debenture_search.repositories.observation_repository import (
    ObservationRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
FIRST_MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)
EVENTS_MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "002_debenture_events.sql"
)

EVENT_TYPES = (
    "amortizacao",
    "atualizacao",
    "juros",
    "opcao_venda",
    "participacao",
    "premio",
    "premio_permanencia",
    "repactuacao",
    "resgate_total_antecipado",
    "vencimento",
)

checksum_numbers = itertools.count(1)


def new_checksum():
    return hashlib.sha256(
        str(next(checksum_numbers)).encode("utf-8")
    ).hexdigest()


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")

    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        FIRST_MIGRATION_PATH.read_text(encoding="utf-8")
    )
    connection.executescript(
        EVENTS_MIGRATION_PATH.read_text(encoding="utf-8")
    )
    connection.execute(
        "INSERT INTO debentures (asset_code) VALUES ('EVT12')"
    )
    connection.commit()

    yield connection

    connection.close()


def insert_event(connection, **overrides):
    values = {
        "debenture_id": 1,
        "event_type": "juros",
        "event_date": "2026-09-15",
        "value_numeric": None,
        "unit": None,
        "source_id": 1,
        "observed_at": "2026-09-11T12:00:00+00:00",
        "confidence": "reported",
        "checksum": new_checksum(),
    }
    values.update(overrides)

    connection.execute(
        """
        INSERT INTO debenture_events (
            debenture_id, event_type, event_date, value_numeric, unit,
            source_id, observed_at, confidence, checksum
        ) VALUES (
            :debenture_id, :event_type, :event_date, :value_numeric, :unit,
            :source_id, :observed_at, :confidence, :checksum
        )
        """,
        values,
    )


def snapshot(connection):
    """Objetos do schema (com o DDL) e contagem de linhas por tabela."""

    objects = {
        (row[0], row[1]): row[2]
        for row in connection.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            """
        )
    }
    counts = {
        name: connection.execute(
            'SELECT COUNT(*) FROM "' + name + '"'
        ).fetchone()[0]
        for (kind, name) in objects
        if kind == "table"
    }

    return objects, counts


def test_migration_was_registered(database):
    versions = database.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    ).fetchall()

    assert versions == [
        (1, "initial_schema"),
        (2, "debenture_events"),
    ]


def test_table_and_index_are_created_empty(database):
    objects = {
        (row[0], row[1])
        for row in database.execute(
            "SELECT type, name FROM sqlite_master"
        )
    }
    total = database.execute(
        "SELECT COUNT(*) FROM debenture_events"
    ).fetchone()[0]

    assert ("table", "debenture_events") in objects
    assert ("index", "idx_debenture_events_lookup") in objects
    assert total == 0


def test_migration_is_idempotent(database):
    database.executescript(
        EVENTS_MIGRATION_PATH.read_text(encoding="utf-8")
    )

    versions = database.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    indexes = database.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE name = 'idx_debenture_events_lookup'
        """
    ).fetchone()[0]

    assert versions == [(1,), (2,)]
    assert indexes == 1


def test_accepts_every_event_type(database):
    for event_type in EVENT_TYPES:
        insert_event(database, event_type=event_type)

    total = database.execute(
        "SELECT COUNT(*) FROM debenture_events"
    ).fetchone()[0]

    assert total == len(EVENT_TYPES)


def test_accepts_event_without_value_and_unit(database):
    insert_event(database)

    row = database.execute(
        "SELECT value_numeric, unit FROM debenture_events"
    ).fetchone()

    assert row == (None, None)


def test_accepts_event_with_value_and_unit(database):
    insert_event(
        database,
        event_type="amortizacao",
        value_numeric="16.6667",
        unit="percentual",
    )

    row = database.execute(
        "SELECT value_numeric, unit FROM debenture_events"
    ).fetchone()

    assert row == (16.6667, "percentual")


def test_accepts_leap_day(database):
    insert_event(database, event_date="2028-02-29")


def test_rejects_unknown_event_type(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, event_type="cupom")


def test_rejects_invalid_event_dates(database):
    # Datas que o SQLite normalizaria (30/02) ou que nao sao datas.
    invalid_dates = [
        "2026-02-30",
        "2027-02-29",
        "2026-9-1",
        "2026-09-01T10:00:00",
        "2026-13-01",
        "abc",
        "",
    ]

    for event_date in invalid_dates:
        with pytest.raises(sqlite3.IntegrityError):
            insert_event(database, event_date=event_date)


def test_rejects_unit_without_value(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, unit="percentual")


def test_rejects_blank_unit(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, value_numeric="1", unit="   ")


def test_rejects_invalid_confidence(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, confidence="guess")


def test_rejects_checksum_with_wrong_length(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, checksum="abc")


def test_rejects_duplicate_checksum(database):
    checksum = new_checksum()
    insert_event(database, checksum=checksum)

    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, checksum=checksum)


def test_rejects_unknown_debenture(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, debenture_id=999)


def test_rejects_unknown_source(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(database, source_id=999)


def test_restricts_deleting_debenture_with_events(database):
    insert_event(database)

    with pytest.raises(sqlite3.IntegrityError):
        database.execute("DELETE FROM debentures WHERE id = 1")


def test_raw_record_link_is_cleared_when_record_is_deleted(database):
    database.execute(
        """
        INSERT INTO raw_records (source_id, payload, payload_sha256)
        VALUES (1, x'41', ?)
        """,
        (new_checksum(),),
    )
    insert_event(database, raw_record_id=1)

    database.execute("DELETE FROM raw_records WHERE id = 1")

    row = database.execute(
        "SELECT raw_record_id FROM debenture_events"
    ).fetchone()

    assert row == (None,)


def test_applying_002_preserves_existing_data(tmp_path):
    db = Database(tmp_path / "migrate.db")

    with db.connection() as connection:
        connection.executescript(
            FIRST_MIGRATION_PATH.read_text(encoding="utf-8")
        )
        connection.commit()

    debenture = DebentureRepository(db).create(asset_code="KEEP12")
    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("SND",),
    )
    ObservationRepository(db).create(
        debenture_id=debenture.id,
        source_id=int(source["id"]),
        field_name="rating",
        value_type="text",
        value="AA",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    with db.connection() as connection:
        objects_before, counts_before = snapshot(connection)
        current_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM current_observations"
            )
        ]

    with db.connection() as connection:
        connection.executescript(
            EVENTS_MIGRATION_PATH.read_text(encoding="utf-8")
        )
        connection.commit()

    with db.connection() as connection:
        objects_after, counts_after = snapshot(connection)
        current_after = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM current_observations"
            )
        ]

    for key, ddl in objects_before.items():
        assert objects_after[key] == ddl

    assert set(objects_after) - set(objects_before) == {
        ("table", "debenture_events"),
        ("index", "idx_debenture_events_lookup"),
    }

    for table, total in counts_before.items():
        if table != "schema_migrations":
            assert counts_after[table] == total

    assert counts_before["schema_migrations"] == 1
    assert counts_after["schema_migrations"] == 2
    assert counts_after["debenture_events"] == 0
    assert current_after == current_before
    assert len(current_before) == 1
    assert db.integrity_check() == "ok"
    assert db.foreign_key_check() == []
