"""Classifica FIC-FIDC, confere o CDA com a tab_I e enfileira a revisao manual.

Uso (a partir da pasta do modulo de Fundos):

    python scripts/classify_fic_fidc.py --database <banco> --reference-date 2026-09-30 --dry-run
    python scripts/classify_fic_fidc.py --database <banco> --reference-date 2026-09-30 --commit

--reference-date e a competencia (o ultimo dia do mes). A classificacao
(decisao 6 de Fundos) e a conferencia do CDA com a tab_I sao calculadas na
leitura e nunca gravadas; o relatorio traz so contagens, nunca CNPJ, nome
nem valor de linha.

--dry-run abre o banco so para leitura (mode=ro e query_only; banco em WAL
e recusado) e mostra a regra, as competencias de cada lado, as faixas, os
estados da conferencia, o cruzamento dos dois e quantos assuntos em
revisao manual entrariam na fila. Nao escreve nada.

--commit so grava a fila de revisao manual no audit_log: uma linha por
assunto em revisao, competencia e evidencia, sem duplicar (a mesma
evidencia ja na fila nao e gravada de novo). Sem entrada nova, diz "Nada a
enfileirar" e nao faz backup. Com entrada nova, faz o backup antes, grava
numa unica transacao, confere o que gravou antes do COMMIT e depois roda
integrity_check e foreign_key_check.

O banco e o backup ficam em disco local, de caminho curto (decisao 9 de
Fundos): --database e o destino do backup (--backup-dir ou a pasta backups
ao lado do banco) em caminho de rede (UNC, relativo dentro de pasta de rede
ou unidade remota) ou longo sao recusados antes de abrir o banco, no
--dry-run tambem.
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
from fundos.backup import check_local_paths  # noqa: E402
from fundos.backup import check_path_length  # noqa: E402
from fundos.backup import create_backup  # noqa: E402
from fundos.cadastro.loader import missing_migrations  # noqa: E402
from fundos.database import Database  # noqa: E402
from fundos.fic_fidc.cda_check import cda_competences  # noqa: E402
from fundos.fic_fidc.cda_check import cda_vs_informe  # noqa: E402
from fundos.fic_fidc.classification import FIELDS  # noqa: E402
from fundos.fic_fidc.classification import classify  # noqa: E402
from fundos.fic_fidc.classification import month_end  # noqa: E402
from fundos.fic_fidc.report import format_check_report  # noqa: E402
from fundos.fic_fidc.report import format_classification_report  # noqa: E402
from fundos.fic_fidc.report import format_cross_report  # noqa: E402
from fundos.fic_fidc.report import format_queue_report  # noqa: E402
from fundos.fic_fidc.review_queue import enqueue  # noqa: E402
from fundos.fic_fidc.review_queue import queued  # noqa: E402
from fundos.fic_fidc.review_queue import scan_created  # noqa: E402
from fundos.fic_fidc.review_queue import to_enqueue  # noqa: E402
from fundos.indicators.reading import IndicatorDatabaseError  # noqa: E402
from fundos.indicators.reading import loaded_competences  # noqa: E402
from fundos.indicators.reading import open_read_only  # noqa: E402
from fundos.indicators.reading import read_snapshot  # noqa: E402
from fundos.informe_fidc.loader import REQUIRED_MIGRATIONS  # noqa: E402


class ClassifyError(Exception):
    """Erro com mensagem propria, sem caminho, CNPJ, nome nem valor."""


def say(line):
    print(line, flush=True)


def reference_argument(text):
    try:
        return month_end(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def describe(connection, reference):
    """Tudo o que o relatorio mostra, lido num unico retrato (so le)."""

    missing = missing_migrations(connection, REQUIRED_MIGRATIONS)

    if missing:
        raise ClassifyError("Banco sem as migrations: " + ", ".join(missing) + ".")

    with read_snapshot(connection):
        classifications = classify(connection, reference)
        new, already = to_enqueue(connection, classifications)

        return {
            "reference": reference,
            "informe_competences": loaded_competences(connection, FIELDS),
            "classifications": classifications,
            "checks": cda_vs_informe(connection, reference),
            "cda_competences": cda_competences(connection),
            "new": new,
            "already": already,
            "queued": queued(connection, reference, classifications),
        }


def report_lines(state, committed=None):
    return (
        format_classification_report(
            state["classifications"], state["reference"], state["informe_competences"]
        )
        + format_check_report(state["checks"], state["reference"], state["cda_competences"])
        + format_cross_report(state["classifications"], state["checks"])
        + format_queue_report(state["new"], state["already"], state["queued"], committed)
    )


def read_state(database_path, reference):
    if not database_path.is_file():
        raise ClassifyError("Banco nao encontrado; nada foi criado.")

    connection = open_read_only(database_path)

    try:
        return describe(connection, reference)
    finally:
        connection.close()


def dry_run(database_path, reference):
    for line in report_lines(read_state(database_path, reference)):
        say(line)

    say("Dry-run concluido: nenhum banco foi alterado.")
    return 0


def commit(args, database_path, reference):
    state = read_state(database_path, reference)

    if not state["classifications"]:
        for line in report_lines(state):
            say(line)

        say("Nada a enfileirar: o informe de FIDC nao tem esta competencia no banco.")
        return 0

    if not state["new"]:
        for line in report_lines(state):
            say(line)

        say("Nada a enfileirar: nenhum assunto novo em revisao manual nesta competencia.")
        return 0

    try:
        check_path_length(backup_path(database_path, args.backup_dir))
        backup = create_backup(database_path, args.backup_dir)
    except Exception as error:
        raise ClassifyError(
            "Nao foi possivel criar o backup; o banco nao foi alterado ("
            + type(error).__name__
            + ")."
        ) from error

    say("Backup: " + str(backup.path))
    say("  tamanho: " + str(backup.size_bytes) + " bytes")
    say("  sha256: " + backup.sha256)

    database = Database(database_path)

    try:
        with database.transaction() as connection:
            result = enqueue(connection, classify(connection, reference))
            problems = scan_created(connection, result.created)

            if problems:
                raise ClassifyError(
                    "Verificacao antes do COMMIT falhou: "
                    + str(problems)
                    + " linha(s) da fila fora do formato. Nada foi gravado."
                )
    except BaseException:
        print(
            "Falha: o banco foi mantido como estava. Backup: " + str(backup.path),
            file=sys.stderr,
        )
        raise

    integrity = database.integrity_check()
    foreign_key_errors = database.foreign_key_check()
    after = read_state(database_path, reference)

    for line in report_lines(after, committed=result):
        say(line)

    say("Verificacao final:")
    say("  integrity_check: " + integrity)
    say("  foreign_key_check: " + str(len(foreign_key_errors)) + " problema(s)")

    if integrity != "ok" or foreign_key_errors:
        raise ClassifyError(
            "Verificacao final falhou depois do COMMIT. Backup: " + str(backup.path)
        )

    say("Fila gravada.")
    return 0


def run(args):
    say("Pacote fundos: " + str(pathlib.Path(fundos.__file__).resolve().parent))

    # Banco e backup em disco local, de caminho curto, antes de abrir
    # qualquer banco (no dry-run tambem): caminho de rede ou longo e recusado.
    try:
        database_path = check_local_paths(args.database, args.backup_dir)
    except BackupError as error:
        raise ClassifyError(str(error)) from error

    if args.dry_run:
        return dry_run(database_path, args.reference_date)

    return commit(args, database_path, args.reference_date)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Classifica FIC-FIDC (decisao 6 de Fundos), confere o CDA com a tab_I "
            "e enfileira a revisao manual no audit_log."
        ),
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco, em disco local. Obrigatorio: nao ha banco padrao.",
    )
    parser.add_argument(
        "--reference-date",
        required=True,
        type=reference_argument,
        help="Competencia, o ultimo dia do mes (por exemplo 2026-09-30).",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Le o banco e imprime so contagens; nao escreve nada.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava so a fila de revisao manual no audit_log.",
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
    except (ClassifyError, IndicatorDatabaseError) as error:
        print("Erro na classificacao de FIC-FIDC: " + str(error), file=sys.stderr)
        return 1
    except Exception as error:
        # Erro inesperado: so o tipo, sem mensagem nem traceback, que poderiam
        # trazer valor de linha.
        print(
            "Erro inesperado na classificacao de FIC-FIDC: " + type(error).__name__,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
