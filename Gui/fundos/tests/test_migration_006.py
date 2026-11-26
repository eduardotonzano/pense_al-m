import importlib.util
import shutil
import sqlite3

import pytest

from apoio import seed_base
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_full_schema
from conftest import create_schema
from fundos.personal_data import find_cpf_columns


MIGRATION_002 = MIGRATIONS_DIR / "002_party_observations.sql"
MIGRATION_003 = MIGRATIONS_DIR / "003_party_observation_shares.sql"
MIGRATION_004 = MIGRATIONS_DIR / "004_holdings.sql"
MIGRATION_006 = MIGRATIONS_DIR / "006_quota_class_map.sql"
SCRIPT_PATH = MIGRATIONS_DIR.parent / "scripts" / "apply_migration.py"

NEW_TRIGGERS = (
    "trg_quota_class_map_no_delete",
    "trg_quota_class_map_review",
    "trg_quota_class_map_rule_fixed",
    "trg_quota_class_map_valid_to",
)

COLUMNS = [
    "id",
    "pattern",
    "match_type",
    "level",
    "subtype",
    "origin_note",
    "review_status",
    "reviewer",
    "reviewed_at",
    "review_note",
    "valid_from",
    "valid_to",
    "created_at",
]

SEEDS = [
    ("subclasse senior", "inicio", "senior", "nao_se_aplica"),
    ("subclasse subordinada mezanino", "inicio", "nao_senior", "mezanino"),
    ("subclasse subordinada subordinada", "inicio", "nao_senior", "subordinada"),
    ("subclasse subordinada", "igual", "nao_senior", "ausente"),
]

REVIEWED_AT = "2026-11-26T15:00:00.000000+00:00"


def objects(connection):
    return {
        (row[0], row[1])
        for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    }


def insert_rule(connection, **changes):
    row = {
        "pattern": "subclasse ficticia",
        "match_type": "inicio",
        "level": "nao_senior",
        "subtype": "subordinada",
    }
    row.update(changes)
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)

    return connection.execute(
        "INSERT INTO quota_class_map (" + columns + ") VALUES (" + marks + ")",
        tuple(row.values()),
    ).lastrowid


def review(connection, rule_id, status="revisado", reviewer="papel:revisor_fundos"):
    connection.execute(
        "UPDATE quota_class_map SET review_status = ?, reviewer = ?, reviewed_at = ?,"
        " review_note = ? WHERE id = ?",
        (status, reviewer, REVIEWED_AT, "nota ficticia", rule_id),
    )


def test_creates_the_table_triggers_index_and_version(full_connection):
    found = objects(full_connection)

    assert ("table", "quota_class_map") in found
    assert {("trigger", name) for name in NEW_TRIGGERS} <= found
    assert ("index", "ux_quota_class_map_rule") in found
    assert [
        row[1] for row in full_connection.execute("PRAGMA table_info(quota_class_map)")
    ] == COLUMNS
    assert full_connection.execute(
        "SELECT name FROM schema_migrations WHERE version = 6"
    ).fetchone()[0] == "quota_class_map"
    assert find_cpf_columns(full_connection) == []


def test_seeds_the_four_rules_as_proposed_with_open_validity(full_connection):
    rows = full_connection.execute(
        "SELECT pattern, match_type, level, subtype, review_status, reviewer, reviewed_at,"
        " review_note, valid_from, valid_to, origin_note FROM quota_class_map ORDER BY id"
    ).fetchall()

    assert [tuple(row[:4]) for row in rows] == SEEDS
    assert {tuple(row[4:10]) for row in rows} == {("proposto", None, None, None, None, None)}
    assert all("secao 10.6" in row[10] for row in rows)


def test_applying_twice_changes_nothing(tmp_path):
    db = create_full_schema(tmp_path / "fundos.db")
    connection = db.connect()

    try:
        before = objects(connection)
        connection.executescript(MIGRATION_006.read_text(encoding="utf-8"))
        after = objects(connection)
        rules = connection.execute("SELECT COUNT(*) FROM quota_class_map").fetchone()[0]
        versions = [
            row[0]
            for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]
    finally:
        connection.close()

    assert before == after
    assert rules == 4
    assert versions == [1, 2, 3, 4, 6]


def test_seed_is_not_inserted_again_after_a_rejection(full_connection):
    rule_id = full_connection.execute(
        "SELECT id FROM quota_class_map WHERE pattern = 'subclasse senior'"
    ).fetchone()[0]
    review(full_connection, rule_id, status="rejeitado")

    full_connection.executescript(MIGRATION_006.read_text(encoding="utf-8"))

    assert full_connection.execute(
        "SELECT COUNT(*) FROM quota_class_map WHERE pattern = 'subclasse senior'"
    ).fetchone()[0] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"level": "senior", "subtype": "mezanino"},
        {"level": "nao_senior", "subtype": "nao_se_aplica"},
        {"level": "junior"},
        {"subtype": "terciaria"},
        {"match_type": "contem"},
        {"pattern": "Subclasse Ficticia"},
        {"pattern": "subclasse  ficticia"},
        {"pattern": "subclasse ficticia |"},
        {"pattern": " subclasse ficticia"},
        {"review_status": "revisado"},
        {"review_status": "revisado", "reviewer": "papel:revisor_fundos"},
        {"review_status": "proposto", "reviewer": "papel:revisor_fundos"},
        {"review_status": "aprovado"},
        {"valid_from": "2026-10-31", "valid_to": "2026-09-30"},
        {"valid_from": "30/09/2026"},
    ],
)
def test_checks_refuse_incoherent_rules(full_connection, changes):
    with pytest.raises(sqlite3.IntegrityError):
        insert_rule(full_connection, **changes)


@pytest.mark.parametrize(
    "reviewer",
    ["Pessoa Ficticia", "papel:Revisor", "papel:revisor fundos", "revisor_fundos", "papel:"],
)
def test_reviewer_must_be_a_role_identifier(full_connection, reviewer):
    rule_id = insert_rule(full_connection)

    with pytest.raises(sqlite3.IntegrityError):
        review(full_connection, rule_id, reviewer=reviewer)


def test_review_transitions(full_connection):
    rule_id = insert_rule(full_connection)
    review(full_connection, rule_id)

    with pytest.raises(sqlite3.IntegrityError, match="a revisao so vai"):
        full_connection.execute(
            "UPDATE quota_class_map SET review_status = 'proposto', reviewer = NULL,"
            " reviewed_at = NULL WHERE id = ?",
            (rule_id,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="a revisao so vai"):
        review(full_connection, rule_id)

    review(full_connection, rule_id, status="rejeitado", reviewer="papel:dono_da_frente_fundos")

    assert tuple(
        full_connection.execute(
            "SELECT review_status, reviewer FROM quota_class_map WHERE id = ?", (rule_id,)
        ).fetchone()
    ) == ("rejeitado", "papel:dono_da_frente_fundos")

    with pytest.raises(sqlite3.IntegrityError, match="a revisao so vai"):
        review(full_connection, rule_id)


@pytest.mark.parametrize(
    "column, value",
    [
        ("pattern", "subclasse outra"),
        ("match_type", "igual"),
        ("level", "senior"),
        ("subtype", "mezanino"),
        ("origin_note", "outra origem"),
        ("valid_from", "2026-01-31"),
    ],
)
def test_rule_columns_are_immutable(full_connection, column, value):
    rule_id = insert_rule(full_connection)

    with pytest.raises(sqlite3.IntegrityError, match="imutaveis"):
        full_connection.execute(
            "UPDATE quota_class_map SET " + column + " = ? WHERE id = ?", (value, rule_id)
        )


def test_no_rule_is_deleted(full_connection):
    with pytest.raises(sqlite3.IntegrityError, match="nao apaga regra"):
        full_connection.execute("DELETE FROM quota_class_map")


def test_end_of_validity_is_filled_only_once(full_connection):
    rule_id = insert_rule(full_connection)
    full_connection.execute(
        "UPDATE quota_class_map SET valid_to = '2026-12-31' WHERE id = ?", (rule_id,)
    )

    for value in ("2027-01-31", None):
        with pytest.raises(sqlite3.IntegrityError, match="so e preenchido uma vez"):
            full_connection.execute(
                "UPDATE quota_class_map SET valid_to = ? WHERE id = ?", (value, rule_id)
            )


def test_one_active_rule_per_pattern_and_match_type(full_connection):
    insert_rule(full_connection)

    with pytest.raises(sqlite3.IntegrityError):
        insert_rule(full_connection, level="nao_senior", subtype="mezanino")

    insert_rule(full_connection, match_type="igual")
    insert_rule(full_connection, valid_from="2026-10-31")


def load_script():
    specification = importlib.util.spec_from_file_location("apply_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def selected_migrations(tmp_path, migrations):
    folder = tmp_path / "migrations"
    folder.mkdir()

    for migration in migrations:
        shutil.copy(migration, folder)

    return folder


@pytest.mark.parametrize(
    "existing, pending, expected",
    [
        ((MIGRATION_001, MIGRATION_002, MIGRATION_003, MIGRATION_004), "006_quota_class_map", [1, 2, 3, 4, 6]),
        ((MIGRATION_001, MIGRATION_002, MIGRATION_003), "004_holdings, 006_quota_class_map", [1, 2, 3, 4, 6]),
    ],
)
def test_apply_migration_applies_006_without_005(tmp_path, capsys, existing, pending, expected):
    path = tmp_path / "fundos.db"
    db = create_schema(path, existing)

    with db.connection() as connection:
        seed_base(connection)

    folder = selected_migrations(
        tmp_path, (MIGRATION_001, MIGRATION_002, MIGRATION_003, MIGRATION_004, MIGRATION_006)
    )
    script = load_script()
    selected = ["--database", str(path), "--migrations-dir", str(folder)]
    dry = script.main([*selected, "--dry-run"])
    dry_output = capsys.readouterr().out
    committed = script.main([*selected, "--commit", "--backup-dir", str(tmp_path / "bk")])
    output = capsys.readouterr().out
    second = script.main([*selected, "--commit", "--backup-dir", str(tmp_path / "bk")])
    second_output = capsys.readouterr().out

    assert (dry, committed, second) == (0, 0, 0)
    assert "Migrations pendentes: " + pending in dry_output
    assert "colunas com cpf: 0" in output
    assert "Migrations aplicadas com sucesso." in output
    assert "Nada a aplicar" in second_output

    with db.connection() as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
        rules = connection.execute("SELECT COUNT(*) FROM quota_class_map").fetchone()[0]

    assert versions == expected
    assert rules == 4
