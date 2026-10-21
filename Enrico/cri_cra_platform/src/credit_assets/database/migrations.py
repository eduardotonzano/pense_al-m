"""Migrations numeradas do banco do CRI/CRA.

O ``schema.sql`` e a linha de base. Cada arquivo ``migrations/NNN_nome.sql``
muda o schema a partir dela e e registrado em ``schema_migrations``. O
executor cria essa tabela e registra a versao; os arquivos so trazem DDL/DML.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
MIGRATION_FILE = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")
APPLY_COMMAND = (
    "python scripts/apply_migration.py --database <banco> --dry-run "
    "e depois --commit"
)
SCHEMA_MIGRATIONS_DDL = """CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


class MigrationError(Exception):
    """Erro ao aplicar ou verificar migrations."""


class PendingMigrationsError(MigrationError):
    """O banco tem migrations ainda nao aplicadas."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path


@dataclass(frozen=True)
class Snapshot:
    """Estrutura e contagens do banco, para comparar antes e depois."""

    tables: dict
    indexes: frozenset
    counts: dict


def discover_migrations(directory: str | Path | None = None) -> list[Migration]:
    """Lista as migrations numeradas da pasta, em ordem de versao."""

    folder = Path(directory) if directory is not None else MIGRATIONS_DIR

    if not folder.is_dir():
        raise MigrationError(f"Pasta de migrations nao encontrada: {folder}")

    migrations = []

    for path in folder.glob("*.sql"):
        match = MIGRATION_FILE.match(path.name)

        if match is not None:
            migrations.append(
                Migration(int(match.group(1)), match.group(2), path)
            )

    migrations.sort(key=lambda item: item.version)
    versions = [item.version for item in migrations]

    if len(versions) != len(set(versions)):
        raise MigrationError("Existem migrations com o mesmo numero.")

    return migrations


def split_statements(sql: str) -> list[str]:
    """Separa o script em instrucoes completas."""

    statements = []
    buffer = ""

    for line in sql.splitlines(keepends=True):
        buffer += line

        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""

            if statement:
                statements.append(statement)

    if buffer.strip():
        raise MigrationError(
            "A migration termina com uma instrucao incompleta."
        )

    return statements


def read_applied_versions(connection: sqlite3.Connection) -> dict[int, str]:
    """Retorna {versao: nome} das migrations registradas no banco."""

    exists = connection.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type = 'table' AND name = 'schema_migrations'"""
    ).fetchone()

    if exists is None:
        return {}

    return {
        int(row[0]): str(row[1])
        for row in connection.execute(
            "SELECT version, name FROM schema_migrations"
        )
    }


def pending_migrations(
    connection: sqlite3.Connection,
    directory: str | Path | None = None,
) -> list[Migration]:
    """Migrations da pasta que ainda nao estao registradas no banco."""

    applied = read_applied_versions(connection)

    return [
        migration
        for migration in discover_migrations(directory)
        if migration.version not in applied
    ]


def ensure_schema_current(
    connection: sqlite3.Connection,
    directory: str | Path | None = None,
) -> None:
    """Recusa seguir se o banco tem migrations pendentes."""

    pending = pending_migrations(connection, directory)

    if pending:
        versions = ", ".join(format(item.version, "03d") for item in pending)
        raise PendingMigrationsError(
            f"O banco tem migrations pendentes ({versions}). "
            f"Aplique com: {APPLY_COMMAND}."
        )


def schema_snapshot(connection: sqlite3.Connection) -> Snapshot:
    """Colunas de cada tabela, indices e contagem de linhas."""

    tables = {}
    counts = {}

    for row in connection.execute(
        """SELECT name FROM sqlite_master
           WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"""
    ).fetchall():
        name = row[0]
        quoted = '"' + name.replace('"', '""') + '"'
        tables[name] = {
            column[1]: (column[2], column[3], column[5])
            for column in connection.execute(f"PRAGMA table_info({quoted})")
        }
        counts[name] = connection.execute(
            f"SELECT COUNT(*) FROM {quoted}"
        ).fetchone()[0]

    indexes = frozenset(
        row[0]
        for row in connection.execute(
            """SELECT name FROM sqlite_master
               WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"""
        )
    )

    return Snapshot(tables, indexes, counts)


def schema_warnings(connection: sqlite3.Connection) -> list[str]:
    """Avisos sobre formatos legados que a migration nao corrige."""

    warnings = []
    columns = {
        column[1]: column
        for column in connection.execute("PRAGMA table_info(assets)")
    }

    if "codigo_cetip" in columns and columns["codigo_cetip"][3] == 1:
        warnings.append(
            "assets.codigo_cetip e NOT NULL (formato legado): um ativo sem "
            "CETIP nao poderia ser gravado. Corrigir exige reconstruir a "
            "tabela, o que esta fora desta migration."
        )

    return warnings


def verify_state(
    connection: sqlite3.Connection,
    before: Snapshot,
    expected: dict[int, str],
) -> list[str]:
    """Verifica o banco e retorna a lista de problemas encontrados."""

    problems = []
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

    if integrity != "ok":
        problems.append(f"integrity_check retornou: {integrity}")

    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if foreign_key_errors:
        problems.append(
            f"foreign_key_check encontrou {len(foreign_key_errors)} problema(s)."
        )

    applied = read_applied_versions(connection)

    for version, name in sorted(expected.items()):
        label = format(version, "03d")

        if version not in applied:
            problems.append(
                f"A migration {label} nao registrou a versao em "
                "schema_migrations."
            )
        elif applied[version] != name:
            problems.append(
                f"A migration {label} registrou outro nome: {applied[version]}."
            )

    after = schema_snapshot(connection)

    for table, columns in before.tables.items():
        if table not in after.tables:
            problems.append(f"Tabela removida: {table}.")
            continue

        for column, definition in columns.items():
            if column not in after.tables[table]:
                problems.append(f"Coluna removida: {table}.{column}.")
            elif after.tables[table][column] != definition:
                problems.append(f"Coluna alterada: {table}.{column}.")

    for index in sorted(before.indexes - after.indexes):
        problems.append(f"Indice removido: {index}.")

    for table, total in before.counts.items():
        if table == "schema_migrations" or table not in after.counts:
            continue

        if after.counts[table] != total:
            problems.append(
                f"Contagem alterada em {table}: {total} para "
                f"{after.counts[table]}."
            )

    return problems


def apply_pending(
    connection: sqlite3.Connection,
    pending: list[Migration],
    before: Snapshot | None = None,
) -> list[Migration]:
    """Aplica as migrations numa transacao e so confirma se a verificacao passar."""

    if not pending:
        return []

    if before is None:
        before = schema_snapshot(connection)

    expected = {item.version: item.name for item in pending}
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")

    try:
        connection.execute(SCHEMA_MIGRATIONS_DDL)

        for migration in pending:
            sql = migration.path.read_text(encoding="utf-8")

            for statement in split_statements(sql):
                connection.execute(statement)

            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, name) "
                "VALUES (?, ?)",
                (migration.version, migration.name),
            )

        problems = verify_state(connection, before, expected)

        if problems:
            raise MigrationError(
                "Verificacao antes do COMMIT falhou: " + " ".join(problems)
            )

        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")

        raise

    return list(pending)
