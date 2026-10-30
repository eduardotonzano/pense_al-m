"""Carrega o informe mensal de FIDC da CVM no banco de Fundos.

Uso (a partir de Gui/fundos):

    python scripts/load_informe_fidc.py --database <banco> --zip <inf_mensal_fidc_AAAAMM.zip> --last-modified <data> --dry-run
    python scripts/load_informe_fidc.py --database <banco> --zip <inf_mensal_fidc_AAAAMM.zip> --last-modified <data> --commit

A competencia e o DT_COMPTC do arquivo (nao ha --reference-date). A
identidade vem do cadastro ja carregado (scripts/load_cadastro.py): nenhum
fundo nem classe e criado aqui. --last-modified e o Last-Modified do ZIP na
CVM, com fuso; e gravado no manifesto do ZIP.

--dry-run le e confere o ZIP e imprime so agregados. Nao escreve em banco
nenhum; se o banco existir, so o le (query_only) para mostrar o casamento
com o cadastro (ou, se a competencia ja tiver outro ZIP, a comparacao com o
que esta no banco) e dizer se o --commit seria aceito. --commit exige o
banco com as migrations 001 a 003 e o cadastro carregado, faz o backup
antes e grava tudo numa unica transacao, que so e confirmada se a
verificacao passar. O mesmo ZIP nao e carregado de novo. Outro ZIP de
uma competencia ja carregada (reapresentacao) exige --last-modified
posterior ao do ZIP mais novo ja carregado.
"""

import argparse
import pathlib
import sys
from datetime import date
from datetime import timedelta


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
from fundos.cadastro.loader import missing_migrations  # noqa: E402
from fundos.database import Database  # noqa: E402
from fundos.informe_fidc.loader import ALREADY_LOADED  # noqa: E402
from fundos.informe_fidc.loader import OLDER_VERSION  # noqa: E402
from fundos.informe_fidc.loader import REQUIRED_MIGRATIONS  # noqa: E402
from fundos.informe_fidc.loader import SAME_COMPETENCE  # noqa: E402
from fundos.informe_fidc.loader import SubjectResolver  # noqa: E402
from fundos.informe_fidc.loader import cadastro_loaded  # noqa: E402
from fundos.informe_fidc.loader import find_loaded_informe  # noqa: E402
from fundos.informe_fidc.loader import load_informe  # noqa: E402
from fundos.informe_fidc.loader import loaded_zips  # noqa: E402
from fundos.informe_fidc.loader import match_counts  # noqa: E402
from fundos.informe_fidc.loader import normalize_last_modified  # noqa: E402
from fundos.informe_fidc.loader import older_version_message  # noqa: E402
from fundos.informe_fidc.loader import reapresentation_counts  # noqa: E402
from fundos.informe_fidc.loader import reapresentation_problem  # noqa: E402
from fundos.informe_fidc.reader import read_informe_zip  # noqa: E402
from fundos.informe_fidc.report import format_candidates_report  # noqa: E402
from fundos.informe_fidc.report import format_load_report  # noqa: E402
from fundos.informe_fidc.report import format_match_report  # noqa: E402
from fundos.informe_fidc.report import format_read_report  # noqa: E402
from fundos.informe_fidc.report import format_reapresentation_report  # noqa: E402


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


def member_date_warning(informe, last_modified):
    """Aviso se a data dos membros passar da do --last-modified (folga de 1 dia, pelo fuso)."""

    if last_modified is None or not informe.zip.member_dates:
        return None

    latest = max(informe.zip.member_dates)

    if date.fromisoformat(latest) <= date.fromisoformat(last_modified[:10]) + timedelta(days=1):
        return None

    return (
        "Aviso: a data dos membros do ZIP ("
        + latest
        + ") e posterior a do --last-modified ("
        + last_modified[:10]
        + "); confira o Last-Modified do ZIP na CVM."
    )


def loaded_dates_line(connection, informe):
    """Datas dos ZIPs ja carregados da competencia (para o operador conferir a ordem)."""

    zips = loaded_zips(connection, informe)
    dated = [z.last_modified for z in zips if z.last_modified is not None]
    undated = [z.collected_at for z in zips if z.last_modified is None]
    parts = ["maior Last-Modified " + (max(dated) if dated else "nenhum")]

    if undated:
        parts.append(
            "sem Last-Modified "
            + str(len(undated))
            + " (inicio da carga mais recente "
            + max(undated)
            + ")"
        )

    return "ZIPs ja carregados desta competencia: " + str(len(zips)) + "; " + "; ".join(parts)


def describe_database(connection, informe, last_modified=None):
    """(problema que faria o --commit recusar ou None, ja carregado)."""

    missing = missing_migrations(connection, REQUIRED_MIGRATIONS)

    if missing:
        return (
            "faltam as migrations "
            + ", ".join(missing)
            + "; aplique antes com scripts/apply_migration.py",
            None,
        )

    if not cadastro_loaded(connection):
        return (
            "o cadastro nao foi carregado; carregue antes o "
            "registro_fundo_classe.zip com scripts/load_cadastro.py",
            None,
        )

    loaded = find_loaded_informe(connection, informe)

    if loaded == OLDER_VERSION:
        return older_version_message(connection, informe).rstrip("."), loaded

    if loaded == SAME_COMPETENCE:
        problem = reapresentation_problem(connection, informe, last_modified)
        return (None if problem is None else problem.rstrip(".")), loaded

    return None, loaded


def dry_run(database_path, informe, last_modified):
    if not database_path.is_file():
        say(
            "Banco: nao encontrado; o --commit seria recusado (crie com "
            "scripts/apply_migration.py --create e carregue o cadastro). "
            "Casamento com o cadastro nao calculado. Nenhum banco foi criado."
        )
    else:
        connection = Database(database_path).connect_read_only()

        try:
            problem, loaded = describe_database(connection, informe, last_modified)

            if loaded == SAME_COMPETENCE:
                counts = reapresentation_counts(connection, informe, SubjectResolver(connection))
                dates = loaded_dates_line(connection, informe)
            elif problem is None and loaded is None:
                counts = match_counts(informe, SubjectResolver(connection))
            else:
                counts = None
        finally:
            connection.close()

        if loaded == SAME_COMPETENCE:
            for line in format_match_report(counts) + format_reapresentation_report(counts):
                say(line)

            say(dates)

        if problem is not None:
            say("Banco: o --commit seria recusado: " + problem + ".")
        elif loaded == SAME_COMPETENCE:
            say(
                "Banco: migrations aplicadas e cadastro carregado; esta competencia ja tem "
                "ZIP carregado: o --commit carregaria este como reapresentacao."
            )
        elif loaded is not None:
            say("Banco: este ZIP ja foi carregado; o --commit nao faria nada.")
        else:
            for line in format_match_report(counts) + format_candidates_report(counts):
                say(line)

            say("Banco: migrations aplicadas e cadastro carregado; esta competencia ainda nao foi carregada.")

    say("Dry-run concluido: nenhum banco foi alterado.")
    return 0


def commit(args, database_path, informe, last_modified):
    if not database_path.is_file():
        raise LoadError(
            "Banco nao encontrado: "
            + str(database_path)
            + ". Crie antes com scripts/apply_migration.py --create e "
            "carregue o cadastro com scripts/load_cadastro.py."
        )

    connection = Database(database_path).connect_read_only()

    try:
        problem, loaded = describe_database(connection, informe, last_modified)
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
    say("Gravando (andamento por tabela):")

    def progress(table, observations, seconds):
        say(
            "  gravado "
            + table
            + ": "
            + str(observations)
            + " observacao(oes), "
            + str(round(seconds, 1))
            + " s"
        )

    database = Database(database_path)

    try:
        with database.transaction() as connection:
            result = load_informe(connection, informe, progress=progress, last_modified=last_modified)
    except BaseException:
        print(
            "Falha: o banco foi mantido como estava. Backup: " + str(backup.path),
            file=sys.stderr,
        )
        raise

    integrity = database.integrity_check()
    foreign_key_errors = database.foreign_key_check()
    lines = format_match_report(result.counts)

    if result.counts[("reapresentacao", "zips")]:
        lines += format_reapresentation_report(result.counts)

    for line in lines + format_load_report(result):
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

    say("Lendo o ZIP (andamento por tabela):")
    informe = read_informe_zip(
        args.zip,
        progress=lambda table, lines: say("  lido " + table + ": " + str(lines) + " linha(s)"),
    )

    for line in format_read_report(informe):
        say(line)

    say("Last-Modified do ZIP a gravar (UTC): " + (last_modified or "nao informado"))
    warning = member_date_warning(informe, last_modified)

    if warning is not None:
        print(warning, file=sys.stderr)

    if args.dry_run:
        return dry_run(database_path, informe, last_modified)

    return commit(args, database_path, informe, last_modified)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Carrega o informe mensal de FIDC da CVM "
            "(inf_mensal_fidc_AAAAMM.zip) no banco de Fundos."
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
        help="Caminho do inf_mensal_fidc_AAAAMM.zip baixado da CVM.",
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
            "Last-Modified do ZIP na CVM, com fuso (2026-10-24T11:46:15Z ou "
            "'Sat, 24 Oct 2026 11:46:15 GMT'). Obrigatorio quando a competencia "
            "ja tem outro ZIP carregado (reapresentacao)."
        ),
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except Exception as error:
        print("Erro ao carregar o informe de FIDC: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
