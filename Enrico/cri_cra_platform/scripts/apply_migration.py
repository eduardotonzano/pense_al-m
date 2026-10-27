"""Aplica as migrations numeradas pendentes ao banco do CRI/CRA.

Uso (a partir de Enrico/cri_cra_platform):

    python scripts/apply_migration.py --database <banco> --dry-run
    python scripts/apply_migration.py --database <banco> --commit

--dry-run aplica e verifica numa copia e nao grava no banco informado.
--commit faz o backup, aplica tudo numa unica transacao e so confirma se a
verificacao passar; caso contrario desfaz e mantem o banco como estava.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.backup import create_backup
from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    MIGRATIONS_DIR,
    MigrationError,
    apply_pending,
    discover_migrations,
    pending_migrations,
    read_applied_versions,
    schema_snapshot,
    schema_warnings,
    verify_state,
)


def print_report(connection, before):
    """Mostra o estado do banco depois da aplicacao."""

    after = schema_snapshot(connection)
    new_tables = sorted(set(after.tables) - set(before.tables))
    new_columns = sorted(
        f"{table}.{column}"
        for table, columns in after.tables.items()
        if table in before.tables
        for column in columns
        if column not in before.tables[table]
    )
    new_indexes = sorted(after.indexes - before.indexes)
    applied = read_applied_versions(connection)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    print("Verificacao final:")
    print("  integrity_check: " + str(integrity))
    print(
        "  foreign_key_check: "
        + str(len(foreign_key_errors))
        + " problema(s)"
    )
    print(
        "  migrations registradas: "
        + (
            ", ".join(
                format(version, "03d") + " " + name
                for version, name in sorted(applied.items())
            )
            or "nenhuma"
        )
    )
    print("  tabelas novas: " + (", ".join(new_tables) or "nenhuma"))
    print("  colunas novas: " + (", ".join(new_columns) or "nenhuma"))
    print("  indices novos: " + (", ".join(new_indexes) or "nenhum"))

    for table, total in sorted(after.counts.items()):
        print("  " + table + ": " + str(total) + " linha(s)")


def apply_and_verify(database_path, migrations_dir):
    """Aplica as pendentes numa transacao e reverifica numa conexao nova."""

    connection = connect(database_path)

    try:
        initialize_database(connection, migrations_dir)
        pending = pending_migrations(connection, migrations_dir)
        before = schema_snapshot(connection)

        for warning in schema_warnings(connection):
            print("Aviso: " + warning)

        applied_now = apply_pending(connection, pending, before)
    finally:
        connection.close()

    expected = {item.version: item.name for item in applied_now}
    connection = connect(database_path)

    try:
        problems = verify_state(connection, before, expected)

        if problems:
            raise MigrationError(
                "Verificacao final falhou: " + " ".join(problems)
            )

        print_report(connection, before)
    finally:
        connection.close()


def run(args):
    database_path = Path(args.database).resolve()
    migrations_dir = Path(args.migrations_dir)
    migrations = discover_migrations(migrations_dir)

    if not database_path.is_file():
        raise MigrationError(f"Banco nao encontrado: {database_path}")

    print(f"Banco: {database_path} ({database_path.stat().st_size} bytes)")

    connection = sqlite3.connect(database_path)

    try:
        applied = read_applied_versions(connection)
    finally:
        connection.close()

    pending = [item for item in migrations if item.version not in applied]
    print(
        "Migrations registradas no banco: "
        + (", ".join(format(v, "03d") for v in sorted(applied)) or "nenhuma")
    )

    if not pending:
        print("Nada a aplicar: nao ha migrations pendentes.")
        return 0

    print(
        "Migrations pendentes: "
        + ", ".join(
            format(item.version, "03d") + "_" + item.name
            for item in pending
        )
    )

    if args.dry_run:
        with tempfile.TemporaryDirectory(
            prefix="apply_migration_",
            ignore_cleanup_errors=True,
        ) as temp_dir:
            copy = create_backup(database_path, temp_dir, prefix="copia_teste")
            print(f"Copia de teste: {copy.path}")
            apply_and_verify(copy.path, migrations_dir)

        print("Dry-run concluido: o banco informado nao foi alterado.")
        return 0

    try:
        backup = create_backup(database_path, args.backup_dir)
    except Exception as error:
        raise MigrationError(
            f"Nao foi possivel criar o backup; o banco nao foi alterado: {error}"
        ) from error

    print(f"Backup: {backup.path}")
    print(f"  tamanho: {backup.size_bytes} bytes")
    print(f"  sha256: {backup.sha256}")

    try:
        apply_and_verify(database_path, migrations_dir)
    except BaseException:
        print(
            f"Falha: o banco foi mantido como estava. Backup: {backup.path}",
            file=sys.stderr,
        )
        raise

    print("Migrations aplicadas com sucesso.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Aplica as migrations numeradas pendentes de um banco SQLite "
            "do CRI/CRA, com backup e verificacao."
        ),
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco. Obrigatorio: nao ha banco padrao.",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Aplica e verifica numa copia; nao grava no banco.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e aplica no banco informado.",
    )

    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Pasta do backup (padrao: backups ao lado do banco).",
    )
    parser.add_argument(
        "--migrations-dir",
        default=str(MIGRATIONS_DIR),
        help="Pasta com os arquivos NNN_nome.sql.",
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except Exception as error:
        print("Erro ao aplicar migration: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
