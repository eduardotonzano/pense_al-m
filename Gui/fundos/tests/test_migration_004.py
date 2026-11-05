import importlib.util
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
from conftest import create_schema
from fundos.personal_data import find_cpf_columns


MIGRATION_002 = MIGRATIONS_DIR / "002_party_observations.sql"
MIGRATION_003 = MIGRATIONS_DIR / "003_party_observation_shares.sql"
MIGRATION_004 = MIGRATIONS_DIR / "004_holdings.sql"
SCRIPT_PATH = MIGRATIONS_DIR.parent / "scripts" / "apply_migration.py"

NEW_TABLES = (
    "confidential_holding_conflicts",
    "confidential_holdings",
    "holding_conflicts",
    "holdings",
)

NEW_TRIGGERS = (
    "trg_confidential_holdings_no_delete",
    "trg_confidential_holdings_no_update",
    "trg_holdings_no_delete",
    "trg_holdings_no_update",
)

HOLDING_COLUMNS = [
    "id",
    "fund_id",
    "fund_class_id",
    "investee_field_name",
    "investee_cnpj",
    "name_field_name",
    "investee_name",
    "quantity_field_name",
    "quantity",
    "value_field_name",
    "market_value",
    "source_id",
    "collection_run_id",
    "raw_record_id",
    "reference_date",
    "line_order",
    "collected_at",
    "checksum",
]

CONFIDENTIAL_COLUMNS = [
    "id",
    "fund_id",
    "fund_class_id",
    "value_field_name",
    "market_value",
    "confidential_until_field_name",
    "confidential_until",
    "source_id",
    "collection_run_id",
    "raw_record_id",
    "reference_date",
    "collected_at",
    "checksum",
]


def insert_row(connection, table, row):
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return connection.execute(
        "INSERT INTO " + table + " (" + columns + ") VALUES (" + marks + ")",
        tuple(row.values()),
    ).lastrowid


def insert_holding(connection, base, **changes):
    """Posicao identificada ficticia: classe detentora em cotas de outro CNPJ."""

    row = {
        "fund_class_id": base["fund_class"],
        "investee_field_name": "cda_fie.CPF_CNPJ_EMISSOR",
        "investee_cnpj": make_test_cnpj(5),
        "name_field_name": "cda_fie.EMISSOR",
        "investee_name": "FIDC Ficticio Investido",
        "quantity_field_name": "cda_fie.QT_POS_FINAL",
        "quantity": "1500.25",
        "value_field_name": "cda_fie.VL_MERC_POS_FINAL",
        "market_value": "1234567.89",
        "source_id": base["cvm"],
        "collection_run_id": base["cvm_run"],
        "raw_record_id": base["cvm_raw"],
        "reference_date": "2026-09-30",
        "line_order": 1,
        "collected_at": T0,
        "checksum": fake_sha256("holding" + repr(sorted(changes.items()))),
    }
    row.update(changes)
    return insert_row(connection, "holdings", row)


def insert_confidential(connection, base, **changes):
    """Consolidado confidencial ficticio de cotas de fundos."""

    row = {
        "fund_class_id": base["fund_class"],
        "value_field_name": "cda_fie_CONFID.VL_MERC_POS_FINAL",
        "market_value": "500000",
        "confidential_until_field_name": "cda_fie_CONFID.DT_CONFID_APLIC",
        "confidential_until": "2026-12-31",
        "source_id": base["cvm"],
        "collection_run_id": base["cvm_run"],
        "raw_record_id": base["cvm_raw"],
        "reference_date": "2026-09-30",
        "collected_at": T0,
        "checksum": fake_sha256("confid" + repr(sorted(changes.items()))),
    }
    row.update(changes)
    return insert_row(connection, "confidential_holdings", row)


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


def columns(connection, table):
    return [row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")]


def test_creates_tables_indexes_triggers_and_version(full_connection):
    found = objects(full_connection)

    assert {("table", name) for name in NEW_TABLES} <= found
    assert {("trigger", name) for name in NEW_TRIGGERS} <= found
    assert ("index", "idx_holdings_class") in found
    assert ("index", "idx_holdings_investee") in found
    assert columns(full_connection, "holdings") == HOLDING_COLUMNS
    assert columns(full_connection, "confidential_holdings") == CONFIDENTIAL_COLUMNS
    assert full_connection.execute(
        "SELECT name FROM schema_migrations WHERE version = 4"
    ).fetchone()[0] == "holdings"
    assert find_cpf_columns(full_connection) == []


def test_natural_key_has_the_line_order_and_is_not_unique(full_connection, base):
    # Decisao 2 da FU6.1: (detentor, investido, competencia, line_order). A
    # mesma chave com outro valor (reapresentacao) e linha nova, nao erro.
    for name in ("idx_holdings_fund", "idx_holdings_class"):
        unique = full_connection.execute(
            "SELECT \"unique\" FROM pragma_index_list('holdings') WHERE name = ?",
            (name,),
        ).fetchone()[0]
        columns_of_index = [
            row[0]
            for row in full_connection.execute("SELECT name FROM pragma_index_info(?) ORDER BY seqno", (name,))
        ]
        assert unique == 0
        assert columns_of_index[1:] == ["investee_cnpj", "reference_date", "line_order"]

    insert_holding(full_connection, base)
    insert_holding(full_connection, base, market_value="1")
    insert_holding(full_connection, base, line_order=2)

    assert count(full_connection, "holdings") == 3


def test_applying_twice_changes_nothing(tmp_path):
    db = create_full_schema(tmp_path / "fundos.db")
    connection = db.connect()

    try:
        before = objects(connection)
        connection.executescript(MIGRATION_004.read_text(encoding="utf-8"))
        after = objects(connection)
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    finally:
        connection.close()

    assert before == after
    assert [row[0] for row in versions] == [1, 2, 3, 4]


def test_accepts_valid_rows(full_connection, base):
    insert_holding(full_connection, base)
    insert_holding(
        full_connection,
        base,
        fund_class_id=None,
        fund_id=base["fund"],
        investee_cnpj=make_test_cnpj(6, alphanumeric=True),
        name_field_name=None,
        investee_name=None,
        quantity_field_name=None,
        quantity=None,
        market_value="-10.5",
    )
    insert_confidential(full_connection, base)
    insert_confidential(full_connection, base, fund_class_id=None, fund_id=base["fund"])

    assert count(full_connection, "holdings") == 2
    assert count(full_connection, "confidential_holdings") == 2


def test_investee_has_no_foreign_key(full_connection, base):
    # O investido pode estar fora do cadastro carregado (FIF, FII, FIP).
    insert_holding(full_connection, base, investee_cnpj=make_test_cnpj(9))

    assert full_connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("value", [FAKE_CPF, FAKE_CPF_MASKED, "123", ""])
def test_investee_cnpj_refuses_cpf_and_other_formats(full_connection, base, value):
    with pytest.raises(sqlite3.IntegrityError):
        insert_holding(full_connection, base, investee_cnpj=value)


@pytest.mark.parametrize(
    "changes",
    [
        {"fund_id": 1},
        {"fund_class_id": None},
        {"investee_field_name": "cda_fie.EMISSOR"},
        {"investee_field_name": "CPF_CNPJ_EMISSOR"},
        {"name_field_name": "cda_fie.CPF_CNPJ_EMISSOR"},
        {"name_field_name": "cda_fie.Diretor"},
        {"name_field_name": "cda_fie.CPF_EMISSOR"},
        {"name_field_name": None},
        {"investee_name": None},
        {"investee_name": "   "},
        {"quantity_field_name": None},
        {"quantity": None},
        {"quantity_field_name": "cda_fie.CPF_CNPJ_EMISSOR"},
        {"quantity": "1e3"},
        {"quantity": "1,5"},
        {"value_field_name": "cda_fie.CPF_CNPJ_EMISSOR"},
        {"value_field_name": "VL_MERC_POS_FINAL"},
        {"market_value": None},
        {"market_value": "1."},
        {"market_value": ".5"},
        {"market_value": "1-2"},
        {"market_value": " 1"},
        {"reference_date": "2026-09-31"},
        {"reference_date": "30/09/2026"},
        {"line_order": None},
        {"line_order": 0},
        {"line_order": -1},
        {"line_order": 1.5},
        {"line_order": "a"},
        {"collected_at": "ontem"},
        {"checksum": "abc"},
        {"source_id": 999},
        {"raw_record_id": 999},
    ],
)
def test_checks_refuse_invalid_holdings(full_connection, base, changes):
    with pytest.raises(sqlite3.IntegrityError):
        insert_holding(full_connection, base, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"fund_id": 1},
        {"fund_class_id": None},
        {"value_field_name": "cda_fie_CONFID.CPF_CNPJ_EMISSOR"},
        {"market_value": None},
        {"market_value": "1e3"},
        {"confidential_until_field_name": "DT_CONFID_APLIC"},
        {"confidential_until": None},
        {"confidential_until": "2026-13-01"},
        {"reference_date": "2026-09"},
        {"checksum": "Z" * 64},
    ],
)
def test_checks_refuse_invalid_confidential_holdings(full_connection, base, changes):
    with pytest.raises(sqlite3.IntegrityError):
        insert_confidential(full_connection, base, **changes)


def test_same_checksum_is_refused(full_connection, base):
    insert_holding(full_connection, base, checksum=fake_sha256("igual"))
    insert_confidential(full_connection, base, checksum=fake_sha256("igual"))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_holding(full_connection, base, checksum=fake_sha256("igual"))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_confidential(full_connection, base, checksum=fake_sha256("igual"))


@pytest.mark.parametrize(
    "table, insert",
    [("holdings", insert_holding), ("confidential_holdings", insert_confidential)],
)
def test_positions_are_immutable(full_connection, base, table, insert):
    row = insert(full_connection, base)

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        full_connection.execute("UPDATE " + table + " SET market_value = '1' WHERE id = ?", (row,))

    with pytest.raises(sqlite3.IntegrityError, match="imutavel"):
        full_connection.execute("DELETE FROM " + table + " WHERE id = ?", (row,))


@pytest.mark.parametrize(
    "table, columns_pair, insert",
    [
        ("holding_conflicts", ("holding_a_id", "holding_b_id"), insert_holding),
        (
            "confidential_holding_conflicts",
            ("confidential_holding_a_id", "confidential_holding_b_id"),
            insert_confidential,
        ),
    ],
)
def test_conflicts_check_the_pair_and_the_resolution(full_connection, base, table, columns_pair, insert):
    first = insert(full_connection, base)
    second = insert(full_connection, base, market_value="2")
    sql = (
        "INSERT INTO " + table + " (reference_date, " + ", ".join(columns_pair) + ", status)"
        " VALUES ('2026-09-30', ?, ?, ?)"
    )

    full_connection.execute(sql, (first, second, "open"))

    with pytest.raises(sqlite3.IntegrityError):
        full_connection.execute(sql, (second, first, "open"))

    with pytest.raises(sqlite3.IntegrityError):
        full_connection.execute(sql, (first, second, "open"))

    with pytest.raises(sqlite3.IntegrityError):
        full_connection.execute(sql, (first, 999, "open"))

    with pytest.raises(sqlite3.IntegrityError):
        full_connection.execute(
            "UPDATE " + table + " SET status = 'resolved' WHERE " + columns_pair[0] + " = ?",
            (first,),
        )

    full_connection.execute(
        "UPDATE " + table + " SET status = 'resolved', resolved_at = ?, resolution_note = ?"
        " WHERE " + columns_pair[0] + " = ?",
        (T0, "Nota ficticia", first),
    )
    assert count(full_connection, table) == 1


def test_database_checks_pass_with_rows(full_connection, base):
    first = insert_holding(full_connection, base)
    second = insert_holding(full_connection, base, market_value="2")
    insert_confidential(full_connection, base)
    full_connection.execute(
        "INSERT INTO holding_conflicts (reference_date, holding_a_id, holding_b_id)"
        " VALUES ('2026-09-30', ?, ?)",
        (first, second),
    )

    assert full_connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert full_connection.execute("PRAGMA foreign_key_check").fetchall() == []


def load_script():
    specification = importlib.util.spec_from_file_location("apply_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def dump(path):
    """Todas as linhas das tabelas que ja existiam, menos a da versao 4."""

    connection = sqlite3.connect(path)

    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " ORDER BY name"
            )
            if row[0] not in NEW_TABLES
        ]
        return {
            table: connection.execute(
                'SELECT * FROM "' + table + '"'
                + (" WHERE version <> 4" if table == "schema_migrations" else "")
                + " ORDER BY 1"
            ).fetchall()
            for table in tables
        }
    finally:
        connection.close()


def test_apply_migration_applies_004_over_001_to_003_with_data(tmp_path, capsys):
    path = tmp_path / "fundos.db"
    db = create_schema(path, (MIGRATION_001, MIGRATION_002, MIGRATION_003))

    with db.connection() as connection:
        seed_base(connection)

    before = dump(path)
    script = load_script()
    dry = script.main(["--database", str(path), "--dry-run"])
    dry_output = capsys.readouterr().out
    committed = script.main(["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "bk")])
    output = capsys.readouterr().out
    second = script.main(["--database", str(path), "--commit", "--backup-dir", str(tmp_path / "bk")])
    second_output = capsys.readouterr().out

    assert (dry, committed, second) == (0, 0, 0)
    assert "Migrations pendentes: 004_holdings" in dry_output
    assert "Dry-run concluido: o banco informado nao foi alterado." in dry_output
    assert "colunas com cpf: 0" in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output
    assert "Migrations aplicadas com sucesso." in output
    assert "Nada a aplicar" in second_output
    assert dump(path) == before
    assert before["funds"] and before["raw_records"]

    with db.connection() as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]

    assert versions == [1, 2, 3, 4]
