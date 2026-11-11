"""Nenhuma migration numerada cria uma tabela que o schema.sql já cria.

O schema.sql roda em todo initialize_database e é a linha de base; as migrations
rodam depois. Um CREATE TABLE IF NOT EXISTS numa migration para uma tabela que o
schema.sql já tem não faz nada, e ninguém percebe. Os nomes saem do próprio parser
do SQLite (set_authorizer), compilando cada instrução com EXPLAIN num banco vazio:
nada é executado, comentário e texto entre aspas simples não contam, e o nome chega
sem aspas e sem o prefixo main.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

import pytest

from credit_assets.database import connection as connection_module
from credit_assets.database.migrations import discover_migrations, split_statements

SCHEMA_PATH = Path(connection_module.__file__).with_name("schema.sql")
CREATE_ACTIONS = {
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_TABLE,
    sqlite3.SQLITE_CREATE_VTABLE,
}


def created_tables(sql: str) -> dict[str, str]:
    """Tabelas que o texto SQL cria: nome sem distinção de caixa -> nome como escrito.

    Conta CREATE TABLE, CREATE TEMP TABLE e CREATE VIRTUAL TABLE, com ou sem
    IF NOT EXISTS. Cada instrução é compilada com EXPLAIN num banco vazio, então
    nada roda; o authorizer vê o CREATE antes de qualquer erro de compilação
    (índice ou ALTER sobre tabela que o banco vazio não tem, CREATE TABLE ... AS
    SELECT de outra tabela), e esses erros são ignorados.
    """
    found: dict[str, str] = {}

    def authorizer(action, name, _argument, _database, _source):
        if action in CREATE_ACTIONS and name and not name.casefold().startswith("sqlite_"):
            found.setdefault(name.casefold(), name)
        return sqlite3.SQLITE_OK

    connection = sqlite3.connect(":memory:")
    connection.set_authorizer(authorizer)
    try:
        for statement in split_statements(sql):
            try:
                connection.execute("EXPLAIN " + statement).fetchall()
            except sqlite3.Error:
                pass
    finally:
        connection.close()
    return found


def tables_recreated(schema_sql: str, migrations: Iterable[tuple[str, str]]) -> list[str]:
    """Uma mensagem por tabela que uma migration cria e o schema.sql já cria."""
    schema = created_tables(schema_sql)
    problems = []
    for label, sql in migrations:
        for key, name in sorted(created_tables(sql).items()):
            if key in schema:
                problems.append(
                    f"{label} cria a tabela {name}, que já está no schema.sql ({schema[key]})"
                )
    return problems


def tables_recreated_in(schema_path: Path, migrations_dir: Path | None = None) -> list[str]:
    """O mesmo verificador sobre arquivos: o schema.sql e as migrations da pasta."""
    return tables_recreated(
        schema_path.read_text(encoding="utf-8"),
        [
            (migration.path.name, migration.path.read_text(encoding="utf-8"))
            for migration in discover_migrations(migrations_dir)
        ],
    )


# ------------------------------------------------------------------- o teste real

def test_no_migration_creates_a_table_that_schema_sql_already_creates():
    problems = tables_recreated_in(SCHEMA_PATH)
    assert problems == [], "\n".join(problems)


def test_the_check_sees_the_real_schema_and_the_tables_of_the_migrations():
    schema = created_tables(SCHEMA_PATH.read_text(encoding="utf-8"))
    from_migrations = set()
    for migration in discover_migrations():
        from_migrations |= set(created_tables(migration.path.read_text(encoding="utf-8")))

    assert {"assets", "documents", "document_versions", "extracted_values"} <= set(schema)
    # Migrations aplicadas nunca são editadas (migrations/README.md): estas ficam.
    assert {
        "document_category_changes", "asset_series", "download_batches",
        "download_queue", "asset_cnpj_observations",
    } <= from_migrations


# --------------------------------------- casos sintéticos: o verificador enxerga o erro

SCHEMA = "CREATE TABLE assets (asset_id INTEGER PRIMARY KEY);\nCREATE TABLE notas (texto TEXT);\n"


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE IF NOT EXISTS assets (x);",
        "CREATE TABLE assets (x);",
        "CREATE TABLE IF NOT EXISTS main.assets (x);",
        "CREATE TEMP TABLE assets (x);",
        # Módulo inexistente: o EXPLAIN não roda o módulo, então o teste não depende do fts5.
        "CREATE VIRTUAL TABLE assets USING modulo_que_nao_existe(a);",
        "CREATE TABLE IF NOT EXISTS outra (x);\nCREATE TABLE IF NOT EXISTS assets AS SELECT * FROM outra;",
    ],
    ids=["if-not-exists", "sem-if-not-exists", "prefixo-main", "temp", "virtual", "as-select"],
)
def test_a_migration_that_recreates_a_schema_table_is_caught(sql):
    assert tables_recreated(SCHEMA, [("005_teste.sql", sql)]) == [
        "005_teste.sql cria a tabela assets, que já está no schema.sql (assets)"
    ]


def test_migrations_without_overlap_pass_even_when_they_change_schema_tables():
    sql = (
        "CREATE TABLE IF NOT EXISTS outra (id INTEGER PRIMARY KEY, asset_id INTEGER REFERENCES assets(asset_id));\n"
        "CREATE INDEX IF NOT EXISTS ix_outra_asset ON outra(asset_id);\n"
        "ALTER TABLE assets ADD COLUMN apelido TEXT;\n"
        "CREATE VIEW IF NOT EXISTS v_assets AS SELECT * FROM assets;\n"
        "INSERT INTO notas (texto) VALUES ('x');\n"
    )
    assert tables_recreated(SCHEMA, [("005_teste.sql", sql)]) == []


def test_create_table_only_inside_a_comment_or_a_string_does_not_count():
    sql = (
        "-- CREATE TABLE assets (x);\n"
        "/* CREATE TABLE IF NOT EXISTS assets (y); */\n"
        "INSERT INTO notas (texto) VALUES ('CREATE TABLE assets (z)');\n"
    )
    assert created_tables(sql) == {}
    assert tables_recreated(SCHEMA, [("005_teste.sql", sql)]) == []


@pytest.mark.parametrize(
    ("schema_sql", "migration_sql", "written"),
    [
        (SCHEMA, 'CREATE TABLE IF NOT EXISTS "ASSETS" (x);', "ASSETS"),
        ('CREATE TABLE "Assets" (x);', "create table if not exists assets (x);", "assets"),
    ],
    ids=["aspas-na-migration", "aspas-no-schema"],
)
def test_quoted_and_uppercase_names_are_the_same_table(schema_sql, migration_sql, written):
    problems = tables_recreated(schema_sql, [("005_teste.sql", migration_sql)])
    assert len(problems) == 1
    assert problems[0].startswith(f"005_teste.sql cria a tabela {written}, que já está no schema.sql")


def test_the_file_check_names_the_migration_file_that_recreates_the_table(tmp_path):
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text(SCHEMA, encoding="utf-8")
    folder = tmp_path / "migrations"
    folder.mkdir()
    (folder / "001_outra.sql").write_text("CREATE TABLE IF NOT EXISTS outra (x);\n", encoding="utf-8")
    (folder / "002_recria_assets.sql").write_text(
        "CREATE TABLE IF NOT EXISTS assets (x);\n", encoding="utf-8"
    )

    assert tables_recreated_in(schema_path, folder) == [
        "002_recria_assets.sql cria a tabela assets, que já está no schema.sql (assets)"
    ]
