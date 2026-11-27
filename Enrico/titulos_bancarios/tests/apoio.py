"""Apoio dos testes do modulo de Titulos bancarios.

Todo banco e sintetico, criado em tmp_path. Nenhum teste abre banco real nem
acessa a rede. Os CNPJs, nomes e valores abaixo sao ficticios: o banco confere
so o formato do CNPJ (o digito verificador e conferido no Python, depois).
"""

import hashlib
import itertools
import sqlite3
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = MODULE_DIR / "migrations"
MIGRATION_001 = MIGRATIONS_DIR / "001_initial_schema.sql"

T0 = "2026-11-27 10:00:00"
COLLECTED = "2026-11-27T10:00:00"

_counter = itertools.count(1)


def open_connection(path):
    """Abre o banco como o codigo de producao deve abrir: foreign_keys=ON."""

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def apply_migration(connection, migration=MIGRATION_001):
    connection.executescript(migration.read_text(encoding="utf-8"))


def fake_sha256(seed):
    return hashlib.sha256(str(seed).encode("utf-8")).hexdigest()


def unique_checksum():
    return fake_sha256("obs-" + str(next(_counter)))


def source_id(connection, code):
    return connection.execute(
        "SELECT id FROM sources WHERE code = ?", (code,)
    ).fetchone()[0]


def add_run(connection, code="BACEN_IFDATA"):
    cursor = connection.execute(
        "INSERT INTO collection_runs(source_id, started_at, finished_at, status) "
        "VALUES(?, ?, ?, 'success')",
        (source_id(connection, code), T0, T0),
    )
    return cursor.lastrowid


def add_raw_record(connection, run_id, code="BACEN_IFDATA", name="r5.json"):
    cursor = connection.execute(
        "INSERT INTO raw_records(source_id, collection_run_id, file_name, "
        "size_bytes, sha256, collected_at) VALUES(?, ?, ?, 10, ?, ?)",
        (
            source_id(connection, code),
            run_id,
            name,
            fake_sha256("raw-" + str(next(_counter))),
            COLLECTED,
        ),
    )
    return cursor.lastrowid


def add_catalog_field(
    connection, run_id, field_name="r5.c79664", code="BACEN_IFDATA"
):
    connection.execute(
        "INSERT OR IGNORE INTO field_catalog(source_id, field_name, label, "
        "first_seen_run_id) VALUES(?, ?, 'Indice de Basileia', ?)",
        (source_id(connection, code), field_name, run_id),
    )


def add_subject(
    connection,
    run_id,
    key="11222333000181",
    kind="institution",
    entity_id=None,
):
    cursor = connection.execute(
        "INSERT INTO subjects(entity_id, subject_kind, subject_key, "
        "first_seen_run_id) VALUES(?, ?, ?, ?)",
        (entity_id or "entity-" + key, kind, key, run_id),
    )
    return cursor.lastrowid


def insert_observation(
    connection,
    subject_id,
    run_id,
    raw_id,
    code="BACEN_IFDATA",
    field_name="r5.c79664",
    value="0.161796402088591",
    reference_date="2026-06-30",
    collected_at=COLLECTED,
    checksum=None,
    **overrides,
):
    values = {
        "subject_id": subject_id,
        "source_id": source_id(connection, code),
        "collection_run_id": run_id,
        "raw_record_id": raw_id,
        "field_name": field_name,
        "value_type": "numeric",
        "value_numeric": value,
        "reference_date": reference_date,
        "collected_at": collected_at,
        "checksum": checksum or unique_checksum(),
    }
    values.update(overrides)
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cursor = connection.execute(
        "INSERT INTO observations(" + columns + ") VALUES(" + marks + ")",
        tuple(values.values()),
    )
    return cursor.lastrowid


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
