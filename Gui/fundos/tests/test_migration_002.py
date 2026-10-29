import importlib.util
import pathlib
import sqlite3

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio import T0
from apoio import fake_sha256
from apoio import make_test_cnpj
from apoio import seed_base
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_full_schema
from fundos.database import Database
from fundos.personal_data import find_cpf_columns


MIGRATION_002 = MIGRATIONS_DIR / "002_party_observations.sql"
SCRIPT_PATH = MIGRATIONS_DIR.parent / "scripts" / "apply_migration.py"


def insert_party(connection, base, **changes):
    row = {
        "fund_id": base["fund"],
        "role": "gestor",
        "field_name": "registro_fundo.CPF_CNPJ_Gestor",
        "party_cnpj": make_test_cnpj(2),
        "name_field_name": "registro_fundo.Gestor",
        "party_name": "Gestora Ficticia Ltda",
        "source_id": base["cvm"],
        "collection_run_id": base["cvm_run"],
        "raw_record_id": base["cvm_raw"],
        "reference_date": "2026-10-27",
        "collected_at": T0,
        "checksum": fake_sha256(repr(sorted(changes.items()))),
    }
    row.update(changes)
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return connection.execute(
        "INSERT INTO party_observations (" + columns + ") VALUES (" + marks + ")",
        tuple(row.values()),
    ).lastrowid


@pytest.fixture
def base(full_connection):
    return seed_base(full_connection)


def objects(connection):
    return {
        (row[0], row[1])
        for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    }


def test_creates_tables_indexes_triggers_and_version(full_connection):
    found = objects(full_connection)

    assert ("table", "party_observations") in found
    assert ("table", "party_conflicts") in found
    assert ("trigger", "trg_party_observations_no_update") in found
    assert ("trigger", "trg_party_observations_no_delete") in found
    assert ("index", "idx_party_observations_fund") in found
    assert full_connection.execute(
        "SELECT name FROM schema_migrations WHERE version = 2"
    ).fetchone()[0] == "party_observations"
    assert find_cpf_columns(full_connection) == []


def test_applying_twice_changes_nothing(tmp_path):
    db = create_full_schema(tmp_path / "fundos.db")
    connection = db.connect()

    try:
        before = objects(connection)
        connection.executescript(MIGRATION_002.read_text(encoding="utf-8"))
        after = objects(connection)
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    finally:
        connection.close()

    assert before == after
    assert [row[0] for row in versions] == [1, 2]


def test_accepts_a_valid_party(full_connection, base):
    insert_party(full_connection, base)
    insert_party(
        full_connection,
        base,
        fund_id=None,
        fund_class_id=base["fund_class"],
        role="cedente",
        field_name="tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1",
        name_field_name=None,
        party_name=None,
    )

    assert full_connection.execute("SELECT COUNT(*) FROM party_observations").fetchone()[0] == 2


@pytest.mark.parametrize("value", [FAKE_CPF, FAKE_CPF_MASKED, "123"])
def test_party_cnpj_refuses_cpf_and_other_formats(full_connection, base, value):
    with pytest.raises(sqlite3.IntegrityError):
        insert_party(full_connection, base, party_cnpj=value)


@pytest.mark.parametrize(
    "changes",
    [
        {"name_field_name": "registro_fundo.Diretor"},
        {"name_field_name": "registro_fundo.CPF_CNPJ_Gestor"},
        {"name_field_name": None},
        {"party_name": "   "},
        {"field_name": "registro_fundo.Gestor"},
        {"role": "diretor"},
        {"fund_class_id": 1},
    ],
)
def test_checks_refuse_invalid_rows(full_connection, base, changes):
    with pytest.raises(sqlite3.IntegrityError):
        insert_party(full_connection, base, **changes)


def test_party_observations_is_immutable(full_connection, base):
    party = insert_party(full_connection, base)

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        full_connection.execute(
            "UPDATE party_observations SET party_name = 'Outro' WHERE id = ?",
            (party,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        full_connection.execute("DELETE FROM party_observations WHERE id = ?", (party,))


def test_party_conflicts_checks_the_pair_order(full_connection, base):
    first = insert_party(full_connection, base)
    second = insert_party(full_connection, base, party_name="Outro Nome Ficticio")

    full_connection.execute(
        "INSERT INTO party_conflicts (field_name, reference_date,"
        " party_observation_a_id, party_observation_b_id) VALUES (?, ?, ?, ?)",
        ("registro_fundo.CPF_CNPJ_Gestor", "2026-10-27", first, second),
    )

    with pytest.raises(sqlite3.IntegrityError):
        full_connection.execute(
            "INSERT INTO party_conflicts (field_name, reference_date,"
            " party_observation_a_id, party_observation_b_id) VALUES (?, ?, ?, ?)",
            ("registro_fundo.CPF_CNPJ_Gestor", "2026-10-27", second, first),
        )


def load_script():
    specification = importlib.util.spec_from_file_location("apply_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_apply_migration_applies_002_over_version_1(tmp_path, capsys):
    path = tmp_path / "fundos.db"
    connection = Database(path).connect(create=True)

    try:
        connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
        connection.execute("INSERT INTO funds (cnpj) VALUES (?)", (make_test_cnpj(1),))
    finally:
        connection.close()

    script = load_script()
    backup_dir = tmp_path / "bk"

    dry = script.main(["--database", str(path), "--dry-run"])
    dry_output = capsys.readouterr().out
    committed = script.main(
        ["--database", str(path), "--commit", "--backup-dir", str(backup_dir)]
    )
    output = capsys.readouterr().out
    connection = sqlite3.connect(path)

    try:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
        funds = connection.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
    finally:
        connection.close()

    assert (dry, committed) == (0, 0)
    assert "002_party_observations" in dry_output
    assert "Dry-run concluido: o banco informado nao foi alterado." in dry_output
    assert versions == [1, 2]
    assert funds == 1
    assert len(list(pathlib.Path(backup_dir).glob("fundos_*.sqlite3"))) == 1
    assert "colunas com cpf: 0" in output
    assert "Migrations aplicadas com sucesso." in output
