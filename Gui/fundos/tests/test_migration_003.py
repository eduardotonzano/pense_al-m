import importlib.util
import sqlite3

import pytest

from apoio import T0
from apoio import fake_sha256
from apoio import insert_observation
from apoio import make_test_cnpj
from apoio import seed_base
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_full_schema
from conftest import create_schema
from fundos.personal_data import find_cpf_columns


MIGRATION_002 = MIGRATIONS_DIR / "002_party_observations.sql"
MIGRATION_003 = MIGRATIONS_DIR / "003_party_observation_shares.sql"
SCRIPT_PATH = MIGRATIONS_DIR.parent / "scripts" / "apply_migration.py"

CEDENTE_FIELD = "tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1"
SHARE_FIELD = "tab_I.TAB_I2A12_PR_CEDENTE_1"

NEW_OBJECTS = (
    ("table", "party_observation_shares"),
    ("trigger", "trg_party_observation_shares_no_delete"),
    ("trigger", "trg_party_observation_shares_no_update"),
    ("trigger", "trg_party_observation_shares_only_cedente"),
    ("trigger", "trg_party_observation_shares_with_parent"),
    ("trigger", "trg_party_observations_cedente_without_name"),
)


def insert_party(connection, base, **changes):
    row = {
        "fund_class_id": base["fund_class"],
        "role": "cedente",
        "field_name": CEDENTE_FIELD,
        "party_cnpj": make_test_cnpj(2),
        "name_field_name": None,
        "party_name": None,
        "source_id": base["cvm"],
        "collection_run_id": base["cvm_run"],
        "raw_record_id": base["cvm_raw"],
        "reference_date": "2026-09-30",
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


def insert_share(connection, party_id, **changes):
    row = {
        "party_observation_id": party_id,
        "share_field_name": SHARE_FIELD,
        "share_value": "37.125",
    }
    row.update(changes)
    return connection.execute(
        "INSERT INTO party_observation_shares (party_observation_id, share_field_name, share_value)"
        " VALUES (?, ?, ?)",
        tuple(row.values()),
    )


def count(connection, table):
    return connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


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


def test_creates_the_table_the_triggers_and_the_version(full_connection):
    found = objects(full_connection)
    columns = [row[1] for row in full_connection.execute("PRAGMA table_info(party_observation_shares)")]

    assert set(NEW_OBJECTS) <= found
    assert columns == ["party_observation_id", "share_field_name", "share_value"]
    assert full_connection.execute(
        "SELECT name FROM schema_migrations WHERE version = 3"
    ).fetchone()[0] == "party_observation_shares"
    assert find_cpf_columns(full_connection) == []


def test_applying_twice_changes_nothing(tmp_path):
    db = create_full_schema(tmp_path / "fundos.db")
    connection = db.connect()

    try:
        before = objects(connection)
        connection.executescript(MIGRATION_003.read_text(encoding="utf-8"))
        after = objects(connection)
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    finally:
        connection.close()

    assert before == after
    assert [row[0] for row in versions] == [1, 2, 3]


def test_share_right_after_its_cedente_is_accepted(full_connection, base):
    party = insert_party(full_connection, base)
    insert_share(full_connection, party)

    assert tuple(full_connection.execute(
        "SELECT share_field_name, share_value FROM party_observation_shares"
        " WHERE party_observation_id = ?",
        (party,),
    ).fetchone()) == (SHARE_FIELD, "37.125")


def test_share_for_a_cedente_recorded_before_is_refused(full_db):
    with full_db.connection() as connection:
        base = seed_base(connection)
        party = insert_party(connection, base)

    # Outra conexao: o cedente ja estava gravado sem percentual.
    with full_db.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="junto com a linha do cedente"):
            insert_share(connection, party)

        assert count(connection, "party_observation_shares") == 0


def test_share_after_another_insert_is_refused(full_connection, base):
    insert_party(full_connection, base)
    party = insert_party(full_connection, base, party_cnpj=make_test_cnpj(3))
    insert_observation(
        full_connection,
        subject=("class", base["fund_class"]),
        source=base["cvm"],
        run=base["cvm_run"],
        raw=base["cvm_raw"],
    )

    with pytest.raises(sqlite3.IntegrityError, match="junto com a linha do cedente"):
        insert_share(full_connection, party)


def test_share_for_an_earlier_parent_is_refused(full_connection, base):
    first = insert_party(full_connection, base)
    second = insert_party(full_connection, base, party_cnpj=make_test_cnpj(3))

    with pytest.raises(sqlite3.IntegrityError, match="junto com a linha do cedente"):
        insert_share(full_connection, first)

    insert_share(full_connection, second)
    assert count(full_connection, "party_observation_shares") == 1


def test_share_only_for_the_cedente_role(full_connection, base):
    party = insert_party(
        full_connection,
        base,
        role="administrador",
        field_name="tab_I.CNPJ_ADMIN",
        name_field_name="tab_I.ADMIN",
        party_name="Administradora Ficticia SA",
    )

    with pytest.raises(sqlite3.IntegrityError, match="so aceita percentual de cedente"):
        insert_share(full_connection, party)


def test_share_needs_an_existing_parent(full_connection, base):
    with pytest.raises(sqlite3.IntegrityError):
        insert_share(full_connection, 999)


def test_cedente_with_a_name_is_refused(full_connection, base):
    with pytest.raises(sqlite3.IntegrityError, match="cedente nao tem nome"):
        insert_party(
            full_connection,
            base,
            name_field_name="tab_I.ADMIN",
            party_name="Nome Ficticio",
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"share_field_name": CEDENTE_FIELD},
        {"share_field_name": "tab_I.CPF_CEDENTE"},
        {"share_field_name": "registro_fundo.Diretor"},
        {"share_field_name": "TAB_I2A12_PR_CEDENTE_1"},
        {"share_field_name": "tab_I.PR-1"},
        {"share_value": "1e3"},
        {"share_value": "1."},
        {"share_value": ".5"},
        {"share_value": "1.2.3"},
        {"share_value": "1-2"},
        {"share_value": " 1"},
        {"share_value": ""},
    ],
)
def test_checks_refuse_invalid_shares(full_connection, base, changes):
    party = insert_party(full_connection, base)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        insert_share(full_connection, party, **changes)


def test_shares_are_immutable(full_connection, base):
    party = insert_party(full_connection, base)
    insert_share(full_connection, party)

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        full_connection.execute(
            "UPDATE party_observation_shares SET share_value = '1' WHERE party_observation_id = ?",
            (party,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        full_connection.execute(
            "DELETE FROM party_observation_shares WHERE party_observation_id = ?",
            (party,),
        )


def load_script():
    specification = importlib.util.spec_from_file_location("apply_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def dump(path):
    """Todas as linhas de todas as tabelas, menos a da versao 3."""

    connection = sqlite3.connect(path)

    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " AND name <> 'party_observation_shares' ORDER BY name"
            )
        ]
        return {
            table: connection.execute(
                'SELECT * FROM "' + table + '"'
                + (" WHERE version <> 3" if table == "schema_migrations" else "")
                + " ORDER BY 1"
            ).fetchall()
            for table in tables
        }
    finally:
        connection.close()


def test_apply_migration_applies_003_over_001_and_002_with_data(tmp_path, capsys):
    path = tmp_path / "fundos.db"
    db = create_schema(path, (MIGRATION_001, MIGRATION_002))

    with db.connection() as connection:
        base = seed_base(connection)
        insert_observation(
            connection,
            subject=("class", base["fund_class"]),
            source=base["cvm"],
            run=base["cvm_run"],
            raw=base["cvm_raw"],
        )
        insert_party(connection, base)
        admin = {
            "role": "administrador",
            "field_name": "tab_I.CNPJ_ADMIN",
            "name_field_name": "tab_I.ADMIN",
        }
        first = insert_party(connection, base, party_name="Administradora Ficticia SA", **admin)
        second = insert_party(connection, base, party_name="Administradora Ficticia Renomeada", **admin)
        connection.execute(
            "INSERT INTO party_conflicts (field_name, reference_date,"
            " party_observation_a_id, party_observation_b_id) VALUES (?, ?, ?, ?)",
            ("tab_I.CNPJ_ADMIN", "2026-09-30", first, second),
        )

    before = dump(path)
    script = load_script()
    dry = script.main(["--database", str(path), "--dry-run"])
    dry_output = capsys.readouterr().out
    committed = script.main(["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "bk")])
    output = capsys.readouterr().out
    expected_new = ", ".join(kind + " " + name for kind, name in NEW_OBJECTS)

    assert (dry, committed) == (0, 0)
    assert "Migrations pendentes: 003_party_observation_shares" in dry_output
    assert "objetos novos: " + expected_new in dry_output
    assert "objetos novos: " + expected_new in output
    assert "colunas com cpf: 0" in output
    assert "Migrations aplicadas com sucesso." in output
    assert dump(path) == before
    assert before["party_observations"] and before["party_conflicts"] and before["observations"]

    with db.connection() as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]

    assert versions == [1, 2, 3]
