"""Carrega as posicoes em cotas de fundos do CDA da CVM no banco de Fundos.

Uso (a partir de Gui/fundos):

    python scripts/load_cda.py --database <banco> --zip <cda_fi_AAAAMM.zip> --dry-run
    python scripts/load_cda.py --database <banco> --zip <cda_fi_AAAAMM.zip> --commit

A competencia e o DT_COMPTC das linhas de cotas. A identidade do detentor
vem do cadastro ja carregado (scripts/load_cadastro.py): nenhum fundo nem
classe e criado aqui. --last-modified e o Last-Modified do ZIP na CVM, com
fuso; e gravado no manifesto do ZIP.

--dry-run le e confere o ZIP e imprime so agregados. Nao escreve em banco
nenhum; se o banco existir, so o le (query_only) para mostrar o casamento
do detentor, o tipo do investido no cadastro, a comparacao com o que ja
esta no banco e dizer se o --commit seria aceito. --commit exige o banco
com as migrations 001 a 004 e o cadastro carregado, recusa arquivo com mais
de uma linha confidencial de cotas do mesmo detentor (as identificadas
repetidas na chave sao posicoes proprias, com a ordem na chave), faz o
backup antes e grava tudo numa unica transacao, que
so e confirmada se a verificacao passar. O mesmo ZIP nao e carregado de
novo. Outro ZIP de uma competencia ja carregada (reapresentacao) exige
--last-modified posterior ao do ZIP mais novo ja carregado.
"""

import argparse
import pathlib
import sys


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
from fundos.cda.loader import ALREADY_LOADED  # noqa: E402
from fundos.cda.loader import SAME_COMPETENCE  # noqa: E402
from fundos.cda.loader import SubjectResolver  # noqa: E402
from fundos.cda.loader import compare_counts  # noqa: E402
from fundos.cda.loader import database_problem  # noqa: E402
from fundos.cda.loader import find_loaded_cda  # noqa: E402
from fundos.cda.loader import investee_type_counts  # noqa: E402
from fundos.cda.loader import load_cda  # noqa: E402
from fundos.cda.loader import normalize_last_modified  # noqa: E402
from fundos.cda.loader import reapresentation_problem  # noqa: E402
from fundos.cda.loader import repeated_key_problem  # noqa: E402
from fundos.cda.reader import read_cda_zip  # noqa: E402
from fundos.cda.report import format_comparison_report  # noqa: E402
from fundos.cda.report import format_investee_type_report  # noqa: E402
from fundos.cda.report import format_load_report  # noqa: E402
from fundos.cda.report import format_match_report  # noqa: E402
from fundos.cda.report import format_read_report  # noqa: E402
from fundos.database import Database  # noqa: E402


NETWORK_WARNING = (
    "Aviso: o banco esta num caminho de rede. SQLite em compartilhamento de "
    "rede nao e seguro (trava e journal); use um banco em disco local."
)


def is_network_path(path):
    """Caminho UNC (comeca com duas barras invertidas ou normais)."""

    text = str(path)
    return text.startswith("\\\\") or text.startswith("//")


def say(line):
    print(line, flush=True)


def describe_database(connection, cda, last_modified=None):
    """(problema que faria o --commit recusar ou None, ja carregado).

    Com migration ou cadastro faltando, ja carregado e None e nada mais e
    lido do banco.
    """

    problem = database_problem(connection)

    if problem is not None:
        return problem.rstrip("."), None

    loaded = find_loaded_cda(connection, cda)
    problem = repeated_key_problem(cda)

    if problem is None and loaded == SAME_COMPETENCE:
        problem = reapresentation_problem(connection, cda, last_modified)

    return (None if problem is None else problem.rstrip(".")), loaded


def dry_run(database_path, cda, last_modified):
    if not database_path.is_file():
        say(
            "Banco: nao encontrado; o --commit seria recusado (crie com "
            "scripts/apply_migration.py --create e carregue o cadastro). "
            "Casamento do detentor nao calculado. Nenhum banco foi criado."
        )
        problem = repeated_key_problem(cda)

        if problem is not None:
            say("Arquivo: o --commit seria recusado: " + problem.rstrip(".") + ".")
    else:
        connection = Database(database_path).connect_read_only()
        counts = None

        try:
            problem, loaded = describe_database(connection, cda, last_modified)

            if database_problem(connection) is None:
                counts = compare_counts(connection, cda, SubjectResolver(connection))
                counts.update(investee_type_counts(connection, cda))
        finally:
            connection.close()

        if counts is not None:
            lines = format_match_report(counts) + format_investee_type_report(counts)

            for line in lines + format_comparison_report(counts):
                say(line)

        if problem is not None:
            say("Banco: o --commit seria recusado: " + problem + ".")
        elif loaded == ALREADY_LOADED:
            say("Banco: este ZIP ja foi carregado; o --commit nao faria nada.")
        elif loaded == SAME_COMPETENCE:
            say(
                "Banco: migrations aplicadas e cadastro carregado; esta competencia ja tem "
                "ZIP carregado: o --commit carregaria este como reapresentacao."
            )
        else:
            say("Banco: migrations aplicadas e cadastro carregado; o --commit seria aceito.")

    say("Dry-run concluido: nenhum banco foi alterado.")
    return 0


def commit(args, database_path, cda, last_modified):
    problem = repeated_key_problem(cda)

    if problem is not None:
        raise LoadError("Arquivo recusado: " + problem)

    if not database_path.is_file():
        raise LoadError(
            "Banco nao encontrado: "
            + str(database_path)
            + ". Crie antes com scripts/apply_migration.py --create e "
            "carregue o cadastro com scripts/load_cadastro.py."
        )

    connection = Database(database_path).connect_read_only()

    try:
        problem, loaded = describe_database(connection, cda, last_modified)
    finally:
        connection.close()

    if problem is not None:
        raise LoadError("Banco recusado: " + problem + ". O banco nao foi alterado.")

    if loaded == ALREADY_LOADED:
        say("Nada a carregar: este ZIP ja foi carregado.")
        return 0

    try:
        check_path_length(backup_path(database_path, args.backup_dir))
        backup = create_backup(database_path, args.backup_dir)
    except Exception as error:
        raise LoadError(
            "Nao foi possivel criar o backup; o banco nao foi alterado: "
            + str(error)
        ) from error

    say("Backup: " + str(backup.path))
    say("  tamanho: " + str(backup.size_bytes) + " bytes")
    say("  sha256: " + backup.sha256)

    database = Database(database_path)

    try:
        with database.transaction() as connection:
            result = load_cda(connection, cda, last_modified=last_modified)
    except BaseException:
        print(
            "Falha: o banco foi mantido como estava. Backup: " + str(backup.path),
            file=sys.stderr,
        )
        raise

    integrity = database.integrity_check()
    foreign_key_errors = database.foreign_key_check()

    for line in format_match_report(result.counts) + format_load_report(result):
        say(line)

    say("Verificacao final:")
    say("  integrity_check: " + integrity)
    say("  foreign_key_check: " + str(len(foreign_key_errors)) + " problema(s)")

    if integrity != "ok" or foreign_key_errors:
        raise LoadError(
            "Verificacao final falhou depois do COMMIT. Backup: " + str(backup.path)
        )

    say("Carga concluida.")
    return 0


def run(args):
    database_path = pathlib.Path(args.database).resolve()

    say("Pacote fundos: " + str(pathlib.Path(fundos.__file__).resolve().parent))

    if is_network_path(args.database) or is_network_path(database_path):
        print(NETWORK_WARNING, file=sys.stderr)

    try:
        check_path_length(
            database_path,
            hint="use um banco numa pasta de caminho curto, em disco local.",
        )
    except BackupError as error:
        raise LoadError("Banco com " + str(error)) from error

    last_modified = None

    if args.last_modified is not None:
        try:
            last_modified = normalize_last_modified(args.last_modified)
        except ValueError as error:
            raise LoadError(str(error)) from error

    say("Lendo o ZIP:")
    cda = read_cda_zip(args.zip)

    for line in format_read_report(cda):
        say(line)

    say("Last-Modified do ZIP a gravar (UTC): " + (last_modified or "nao informado"))

    if args.dry_run:
        return dry_run(database_path, cda, last_modified)

    return commit(args, database_path, cda, last_modified)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Carrega as posicoes em cotas de fundos do CDA da CVM "
            "(cda_fi_AAAAMM.zip) no banco de Fundos."
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
        help="Caminho do cda_fi_AAAAMM.zip baixado da CVM.",
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
    parser.add_argument(
        "--last-modified",
        default=None,
        help=(
            "Last-Modified do ZIP na CVM, com fuso (2026-10-29T03:58:52Z ou "
            "'Thu, 29 Oct 2026 03:58:52 GMT'). Obrigatorio quando a competencia "
            "ja tem outro ZIP carregado (reapresentacao)."
        ),
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except Exception as error:
        print("Erro ao carregar o CDA: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
