"""Aplica as migrations numeradas pendentes no banco de titulos bancarios.

Uso (a partir de Enrico/titulos_bancarios):

    python scripts/apply_migration.py --database <banco> --dry-run
    python scripts/apply_migration.py --database <banco> --commit

Banco novo: primeiro --create --dry-run (cria e verifica so numa pasta
temporaria), depois --create --commit.

--dry-run aplica e verifica numa copia do banco e nao grava no banco
informado. --commit faz o backup, aplica tudo numa unica transacao e so
confirma se a verificacao passar; caso contrario desfaz e mantem o banco
como estava. A verificacao recusa qualquer objeto ou coluna com 'cpf' no
nome: o banco nunca guarda CPF.

O banco e o backup ficam em disco local, de caminho curto: caminho de rede
(UNC ou unidade remota) ou longo e recusado antes de tudo, no --dry-run
tambem.

Nenhuma migration e aplicada sem --dry-run ou --commit, e o banco nunca e
escolhido por padrao.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sqlite3
import sys
import tempfile

from titulos_bancarios.backup import BackupError
from titulos_bancarios.backup import backup_path
from titulos_bancarios.backup import check_local_path
from titulos_bancarios.backup import check_local_paths
from titulos_bancarios.backup import check_path_length
from titulos_bancarios.backup import create_backup
from titulos_bancarios.database import Database


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = PROJECT_DIR / "migrations"
MIGRATION_FILE = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")


class MigrationError(Exception):
    """Erro ao aplicar ou verificar migrations."""


def discover_migrations(migrations_dir):
    """Lista as migrations numeradas como (versao, nome, caminho)."""

    directory = pathlib.Path(migrations_dir)

    if not directory.is_dir():
        raise MigrationError(
            "Pasta de migrations nao encontrada: " + str(directory)
        )

    migrations = []

    for path in directory.glob("*.sql"):
        match = MIGRATION_FILE.match(path.name)

        if match is not None:
            migrations.append((int(match.group(1)), match.group(2), path))

    migrations.sort()

    versions = [version for version, _, _ in migrations]

    if len(versions) != len(set(versions)):
        raise MigrationError("Existem migrations com o mesmo numero.")

    return migrations


def split_statements(sql):
    """Separa o script em instrucoes completas (triggers inclusive)."""

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
        raise MigrationError("A migration termina com uma instrucao incompleta.")

    return statements


def read_applied_versions(connection):
    """Retorna {versao: nome} das migrations registradas no banco."""

    exists = connection.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()

    if exists is None:
        return {}

    return {
        int(row[0]): str(row[1])
        for row in connection.execute(
            "SELECT version, name FROM schema_migrations"
        )
    }


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def rows_digest(connection, table, max_rowid=None):
    """(maior rowid, SHA-256 do conteudo) das linhas com rowid ate max_rowid.

    Com max_rowid, so as linhas que ja existiam entram: uma migration que
    acrescenta linhas nao muda o resumo, mas uma que altera valor existente
    muda (contagem e DDL iguais nao bastam para perceber um UPDATE).
    """

    sql = "SELECT rowid, * FROM " + quote(table)
    parameters = ()

    if max_rowid is not None:
        sql += " WHERE rowid <= ?"
        parameters = (max_rowid,)

    digest = hashlib.sha256()
    highest = 0

    for row in connection.execute(sql + " ORDER BY rowid", parameters):
        values = tuple(row)
        highest = max(highest, values[0])
        digest.update(repr(values).encode("utf-8"))

    return highest, digest.hexdigest()


def snapshot(connection):
    """Retorna o DDL dos objetos, a contagem e o resumo das linhas por tabela."""

    objects = {
        (row[0], row[1]): row[2]
        for row in connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'"
        )
    }
    counts = {}
    digests = {}

    for kind, name in objects:
        if kind == "table":
            counts[name] = connection.execute(
                "SELECT COUNT(*) FROM " + quote(name)
            ).fetchone()[0]
            digests[name] = rows_digest(connection, name)

    return objects, counts, digests


def find_cpf_columns(connection):
    """Objetos e colunas com 'cpf' no nome (o banco nunca guarda CPF)."""

    found = []

    for row in connection.execute(
        "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    ):
        if "cpf" in row[1].lower():
            found.append(row[0] + " " + row[1])

        if row[0] in ("table", "view"):
            quoted = '"' + row[1].replace('"', '""') + '"'

            for column in connection.execute("PRAGMA table_info(" + quoted + ")"):
                if "cpf" in column[1].lower():
                    found.append(row[1] + "." + column[1])

    return found


def check_state(connection, before, expected, allow_existing_changes):
    """Verifica o banco e retorna a lista de problemas encontrados."""

    problems = []

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

    if integrity != "ok":
        problems.append("integrity_check retornou: " + str(integrity))

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

    if foreign_key_errors:
        problems.append(
            "foreign_key_check encontrou "
            + str(len(foreign_key_errors))
            + " problema(s)."
        )

    for column in find_cpf_columns(connection):
        problems.append(
            "Objeto ou coluna com 'cpf' no nome: "
            + column
            + "; o banco nao guarda CPF."
        )

    applied = read_applied_versions(connection)

    for version, name in sorted(expected.items()):
        if version not in applied:
            problems.append(
                "A migration "
                + format(version, "03d")
                + " nao registrou a versao em schema_migrations."
            )
        elif applied[version] != name:
            problems.append(
                "A migration "
                + format(version, "03d")
                + " registrou outro nome: "
                + applied[version]
                + "."
            )

    if allow_existing_changes:
        return problems

    objects_before, counts_before, digests_before = before
    objects_after, counts_after, _ = snapshot(connection)

    for key, ddl in objects_before.items():
        if key not in objects_after:
            problems.append("Objeto removido: " + key[0] + " " + key[1] + ".")
        elif objects_after[key] != ddl:
            problems.append("DDL alterado: " + key[0] + " " + key[1] + ".")

    for table, total in counts_before.items():
        if table == "schema_migrations":
            continue

        if counts_after.get(table) != total:
            problems.append(
                "Contagem alterada em "
                + table
                + ": "
                + str(total)
                + " para "
                + str(counts_after.get(table))
                + "."
            )

    for table, (highest, digest) in digests_before.items():
        if table == "schema_migrations":
            continue

        if ("table", table) not in objects_after:
            continue  # ja apontada como "Objeto removido"

        if rows_digest(connection, table, highest)[1] != digest:
            problems.append("Conteudo alterado em " + table + ".")

    return problems


def open_connection(database_path, create=False):
    return Database(database_path).connect(create=create)


def apply_in_transaction(connection, before, pending, allow_existing_changes):
    """Aplica as migrations e so confirma se a verificacao passar."""

    expected = {version: name for version, name, _ in pending}

    connection.execute("BEGIN IMMEDIATE")

    try:
        for _, _, path in pending:
            for statement in split_statements(path.read_text(encoding="utf-8")):
                connection.execute(statement)

        problems = check_state(connection, before, expected, allow_existing_changes)

        if problems:
            raise MigrationError(
                "Verificacao antes do COMMIT falhou: " + " ".join(problems)
            )

        connection.execute("COMMIT")

    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")

        raise


def print_report(connection, before):
    """Mostra o estado do banco depois da aplicacao."""

    objects_before = before[0]
    objects_after, counts_after, _ = snapshot(connection)
    new_objects = sorted(set(objects_after) - set(objects_before))
    applied = read_applied_versions(connection)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

    print("Verificacao final:")
    print("  integrity_check: " + str(integrity))
    print("  foreign_key_check: " + str(len(foreign_key_errors)) + " problema(s)")
    print("  objetos com cpf no nome: " + str(len(find_cpf_columns(connection))))
    print(
        "  migrations registradas: "
        + ", ".join(
            format(version, "03d") + " " + name
            for version, name in sorted(applied.items())
        )
    )
    print(
        "  objetos novos: "
        + (", ".join(kind + " " + name for kind, name in new_objects) or "nenhum")
    )

    for table, total in sorted(counts_after.items()):
        print("  " + table + ": " + str(total) + " linha(s)")


def apply_and_verify(database_path, pending, allow_existing_changes, create=False):
    """Aplica numa transacao e reverifica numa conexao nova."""

    expected = {version: name for version, name, _ in pending}

    connection = open_connection(database_path, create=create)

    try:
        before = snapshot(connection)
        apply_in_transaction(connection, before, pending, allow_existing_changes)
    finally:
        connection.close()

    connection = open_connection(database_path)

    try:
        problems = check_state(connection, before, expected, allow_existing_changes)

        if problems:
            raise MigrationError("Verificacao final falhou: " + " ".join(problems))

        print_report(connection, before)
    finally:
        connection.close()


def remove_new_database(database_path):
    """Remove o arquivo criado por --create depois de uma falha."""

    for suffix in ("", "-wal", "-shm", "-journal"):
        pathlib.Path(str(database_path) + suffix).unlink(missing_ok=True)


def run(args):
    migrations = discover_migrations(args.migrations_dir)

    try:
        database_path = check_local_paths(args.database, args.backup_dir)
    except BackupError as error:
        raise MigrationError(str(error)) from error

    created_new = False

    if not database_path.exists():
        if not args.create:
            raise MigrationError(
                "Banco nao encontrado: "
                + str(database_path)
                + ". Para criar um novo, use --create, primeiro com "
                "--dry-run e depois com --commit."
            )

        created_new = True
        applied = {}
        print("Banco novo: " + str(database_path))
    else:
        print(
            "Banco: "
            + str(database_path)
            + " ("
            + str(database_path.stat().st_size)
            + " bytes)"
        )

        connection = open_connection(database_path)

        try:
            applied = read_applied_versions(connection)
        finally:
            connection.close()

    pending = [m for m in migrations if m[0] not in applied]

    print(
        "Migrations registradas no banco: "
        + (", ".join(format(v, "03d") for v in sorted(applied)) or "nenhuma")
    )

    if not pending:
        print("Nada a aplicar: nao ha migrations pendentes.")
        return 0

    print(
        "Migrations pendentes: "
        + ", ".join(format(v, "03d") + "_" + n for v, n, _ in pending)
    )

    if args.dry_run:
        try:
            check_local_path(tempfile.gettempdir(), "pasta temporaria")
        except BackupError as error:
            raise MigrationError(str(error)) from error

        with tempfile.TemporaryDirectory(
            prefix="tb_", ignore_cleanup_errors=True
        ) as temp_dir:
            if created_new:
                copy_path = pathlib.Path(temp_dir) / "titulos_bancarios.db"
                print("Banco de teste: " + str(copy_path))
                apply_and_verify(
                    copy_path, pending, args.allow_existing_changes, create=True
                )
            else:
                copy = create_backup(database_path, temp_dir, prefix="copia_teste")
                print("Copia de teste: " + str(copy.path))
                apply_and_verify(copy.path, pending, args.allow_existing_changes)

        if created_new:
            print("Dry-run concluido: nenhum banco foi criado.")
        else:
            print("Dry-run concluido: o banco informado nao foi alterado.")

        return 0

    backup = None

    if created_new:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        try:
            check_path_length(backup_path(database_path, args.backup_dir))
            backup = create_backup(database_path, args.backup_dir)
        except Exception as error:
            raise MigrationError(
                "Nao foi possivel criar o backup; o banco nao foi alterado: "
                + str(error)
            ) from error

        print("Backup: " + str(backup.path))
        print("  tamanho: " + str(backup.size_bytes) + " bytes")
        print("  sha256: " + backup.sha256)

    try:
        apply_and_verify(
            database_path,
            pending,
            args.allow_existing_changes,
            create=created_new,
        )
    except BaseException:
        if created_new:
            remove_new_database(database_path)
        elif backup is not None:
            print(
                "Falha: o banco foi mantido como estava. Backup: "
                + str(backup.path),
                file=sys.stderr,
            )

        raise

    print("Migrations aplicadas com sucesso.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Aplica as migrations numeradas pendentes do banco de titulos "
            "bancarios, com backup e verificacao."
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
    parser.add_argument(
        "--create",
        action="store_true",
        help=(
            "Cria o banco se ele nao existir. Com --dry-run, cria so numa "
            "pasta temporaria; com --commit, cria de verdade."
        ),
    )
    parser.add_argument(
        "--allow-existing-changes",
        action="store_true",
        help=(
            "Permite que a migration altere tabelas ou linhas ja existentes. "
            "Por padrao a verificacao exige que o que existia continue igual."
        ),
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except Exception as error:
        print("Erro ao aplicar migration: " + str(error), file=sys.stderr)
        return 1
