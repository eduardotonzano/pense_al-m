"""Carrega os FIDC e FIAGRO do cadastro de fundos da CVM no banco de Fundos.

Uso (a partir de Gui/fundos):

    python scripts/load_cadastro.py --database <banco> --zip <zip> --reference-date AAAA-MM-DD --dry-run
    python scripts/load_cadastro.py --database <banco> --zip <zip> --reference-date AAAA-MM-DD --commit

--reference-date e a competencia do retrato: a data do Last-Modified do
registro_fundo_classe.zip na CVM, nunca a data da coleta (ADR-010). E
recusada se for posterior a hoje (UTC) ou anterior ao maior Data_Registro do
arquivo.

--dry-run le o ZIP, escolhe os registros vigentes e imprime so agregados.
Nao escreve em banco nenhum; se o banco existir, so o le (query_only) para
dizer se o --commit seria aceito. --commit exige o banco com as migrations
001 e 002, faz o backup antes e grava tudo numa unica transacao, que so e
confirmada se a verificacao passar; caso contrario desfaz e mantem o banco
como estava. O mesmo ZIP ja carregado nao e carregado de novo.
"""

import argparse
import pathlib
import sys
from datetime import datetime
from datetime import timezone


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_DIR / "src"

# O codigo que altera o banco vem sempre deste checkout, nunca de uma copia
# instalada num ambiente virtual.
sys.path.insert(0, str(SOURCE_DIR))

import fundos  # noqa: E402
from fundos.backup import BackupError  # noqa: E402
from fundos.backup import backup_path  # noqa: E402
from fundos.backup import check_path_length  # noqa: E402
from fundos.backup import create_backup  # noqa: E402
from fundos.cadastro.loader import LoadError  # noqa: E402
from fundos.cadastro.loader import find_loaded_zip  # noqa: E402
from fundos.cadastro.loader import load_cadastro  # noqa: E402
from fundos.cadastro.loader import missing_migrations  # noqa: E402
from fundos.cadastro.reader import read_cadastro_zip  # noqa: E402
from fundos.cadastro.report import format_load_report  # noqa: E402
from fundos.cadastro.report import format_read_report  # noqa: E402
from fundos.cadastro.report import format_selection_report  # noqa: E402
from fundos.cadastro.selection import select_fidc_fiagro  # noqa: E402
from fundos.database import Database  # noqa: E402
from fundos.database import normalize_iso_date  # noqa: E402


NETWORK_WARNING = (
    "Aviso: o banco esta num caminho de rede. SQLite em compartilhamento de "
    "rede nao e seguro (trava e journal); use um banco em disco local."
)


def is_network_path(path):
    """Caminho UNC (comeca com duas barras invertidas ou normais)."""

    text = str(path)
    return text.startswith("\\\\") or text.startswith("//")


def parse_reference_date(text):
    """Valida --reference-date: AAAA-MM-DD e nao posterior a hoje (UTC)."""

    reference = normalize_iso_date(text, "A competencia (--reference-date)")
    today = datetime.now(timezone.utc).date().isoformat()

    if reference > today:
        raise LoadError(
            "A competencia (--reference-date) "
            + reference
            + " e posterior a hoje ("
            + today
            + ", UTC)."
        )

    return reference


def check_reference_against_file(reference, cadastro):
    """Recusa competencia anterior ao maior Data_Registro do arquivo."""

    latest = cadastro.max_registration_date

    if latest is not None and reference < latest:
        raise LoadError(
            "A competencia (--reference-date) "
            + reference
            + " e anterior ao maior Data_Registro do arquivo ("
            + latest
            + "): confira a data do Last-Modified do ZIP na CVM."
        )


def describe_database(connection, cadastro, reference):
    """(problema que faria o --commit recusar ou None, ja carregado)."""

    missing = missing_migrations(connection)

    if missing:
        return (
            "faltam as migrations "
            + ", ".join(missing)
            + "; aplique antes com scripts/apply_migration.py",
            None,
        )

    loaded = find_loaded_zip(connection, cadastro.zip)

    if (
        loaded is not None
        and loaded.reference_dates
        and reference not in loaded.reference_dates
    ):
        return (
            "este ZIP ja foi carregado com outra competencia ("
            + ", ".join(loaded.reference_dates)
            + ")",
            loaded,
        )

    return None, loaded


def dry_run(database_path, cadastro, reference):
    if not database_path.is_file():
        print(
            "Banco: nao encontrado; o --commit seria recusado (crie com "
            "scripts/apply_migration.py --create). Nenhum banco foi criado."
        )
    else:
        connection = Database(database_path).connect_read_only()

        try:
            problem, loaded = describe_database(connection, cadastro, reference)
        finally:
            connection.close()

        if problem is not None:
            print("Banco: o --commit seria recusado: " + problem + ".")
        elif loaded is not None:
            print("Banco: este ZIP ja foi carregado; o --commit nao faria nada.")
        else:
            print("Banco: migrations aplicadas; este ZIP ainda nao foi carregado.")

    print("Dry-run concluido: nenhum banco foi alterado.")
    return 0


def commit(args, database_path, cadastro, selection, reference):
    if not database_path.is_file():
        raise LoadError(
            "Banco nao encontrado: "
            + str(database_path)
            + ". Crie antes com scripts/apply_migration.py --create, "
            "primeiro com --dry-run."
        )

    connection = Database(database_path).connect_read_only()

    try:
        problem, loaded = describe_database(connection, cadastro, reference)
    finally:
        connection.close()

    if problem is not None:
        raise LoadError(
            "Banco recusado: " + problem + ". O banco nao foi alterado."
        )

    if loaded is not None:
        print("Nada a carregar: este ZIP ja foi carregado.")
        return 0

    try:
        check_path_length(backup_path(database_path, args.backup_dir))
        backup = create_backup(database_path, args.backup_dir)
    except Exception as error:
        raise LoadError(
            "Nao foi possivel criar o backup; o banco nao foi alterado: "
            + str(error)
        ) from error

    print("Backup: " + str(backup.path))
    print("  tamanho: " + str(backup.size_bytes) + " bytes")
    print("  sha256: " + backup.sha256)

    database = Database(database_path)

    try:
        with database.transaction() as connection:
            result = load_cadastro(connection, cadastro, selection, reference)
    except BaseException:
        print(
            "Falha: o banco foi mantido como estava. Backup: " + str(backup.path),
            file=sys.stderr,
        )
        raise

    integrity = database.integrity_check()
    foreign_key_errors = database.foreign_key_check()

    for line in format_load_report(result):
        print(line)

    print("Verificacao final:")
    print("  integrity_check: " + integrity)
    print("  foreign_key_check: " + str(len(foreign_key_errors)) + " problema(s)")

    if integrity != "ok" or foreign_key_errors:
        raise LoadError(
            "Verificacao final falhou depois do COMMIT. Backup: "
            + str(backup.path)
        )

    print("Carga concluida.")
    return 0


def run(args):
    database_path = pathlib.Path(args.database).resolve()

    print(
        "Pacote fundos: "
        + str(pathlib.Path(fundos.__file__).resolve().parent)
    )

    if is_network_path(args.database) or is_network_path(database_path):
        print(NETWORK_WARNING, file=sys.stderr)

    try:
        check_path_length(
            database_path,
            hint="use um banco numa pasta de caminho curto, em disco local.",
        )
    except BackupError as error:
        raise LoadError("Banco com " + str(error)) from error

    reference = parse_reference_date(args.reference_date)
    cadastro = read_cadastro_zip(args.zip)
    check_reference_against_file(reference, cadastro)
    selection = select_fidc_fiagro(cadastro)

    print("Competencia (--reference-date): " + reference)

    if cadastro.zip.member_dates != (reference,):
        print(
            "Aviso: a data dos membros do ZIP ("
            + (", ".join(cadastro.zip.member_dates) or "nenhuma")
            + ") e diferente da competencia informada; confira o "
            "Last-Modified na CVM.",
            file=sys.stderr,
        )

    for line in format_read_report(cadastro) + format_selection_report(selection):
        print(line)

    if args.dry_run:
        return dry_run(database_path, cadastro, reference)

    return commit(args, database_path, cadastro, selection, reference)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Carrega os FIDC e FIAGRO do cadastro de fundos da CVM "
            "(registro_fundo_classe.zip) no banco de Fundos."
        ),
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco, em disco local. Obrigatorio: nao ha banco padrao.",
    )
    parser.add_argument(
        "--zip",
        required=True,
        help="Caminho do registro_fundo_classe.zip baixado da CVM.",
    )
    parser.add_argument(
        "--reference-date",
        required=True,
        help=(
            "Competencia AAAA-MM-DD: a data do Last-Modified do ZIP na CVM, "
            "nunca a data da coleta."
        ),
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Le o ZIP e imprime so agregados; nao escreve em banco nenhum.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava no banco informado.",
    )

    parser.add_argument(
        "--backup-dir",
        default=None,
        help=(
            "Pasta do backup (padrao: backups ao lado do banco). Use uma "
            "pasta curta se o caminho passar de 260 caracteres."
        ),
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except Exception as error:
        print("Erro ao carregar o cadastro: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
