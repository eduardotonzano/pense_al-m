"""Relatorio de revisao do mapa das series de FIDC (quota_class_map), so leitura.

Uso (a partir da pasta do modulo de Fundos):

    python scripts/report_quota_class_map.py --database <banco>
    python scripts/report_quota_class_map.py --database <banco> --reference-date 2026-09-30

Mostra as regras (situacao da revisao, papel do revisor, data e vigencia) e,
por competencia com tab_X_2 (ou so a informada), quantas series e rotulos
cada regra classifica, os rotulos sem regra, os assuntos com 2 ou mais
series nao seniores e nenhum mezanino, as series com subtipo ausente, os
rotulos novos desde a ultima revisao e as series de FIAGRO sem mapa. So
contagens e rotulos normalizados de serie: nunca CNPJ, nome, valor de linha
nem o rotulo original.

Abre o banco so para leitura (mode=ro e query_only; banco em WAL e
recusado) e nao escreve nada. O banco fica em disco local, de caminho curto
(decisao 9 de Fundos): --database em caminho de rede (UNC, relativo dentro
de pasta de rede ou unidade remota) ou longo e recusado antes de abrir o
banco.
"""

import argparse
import pathlib
import sys


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_DIR / "src"

# O codigo que le o banco vem sempre deste checkout, nunca de uma copia
# instalada num ambiente virtual.
sys.path.insert(0, str(SOURCE_DIR))

import fundos  # noqa: E402
from fundos.backup import BackupError  # noqa: E402
from fundos.backup import check_local_paths  # noqa: E402
from fundos.cadastro.loader import missing_migrations  # noqa: E402
from fundos.database import normalize_iso_date  # noqa: E402
from fundos.indicators.reading import IndicatorDatabaseError  # noqa: E402
from fundos.indicators.reading import open_read_only  # noqa: E402
from fundos.indicators.reading import read_snapshot  # noqa: E402
from fundos.quota_classes.report import format_review_report  # noqa: E402
from fundos.quota_classes.review import ReviewError  # noqa: E402
from fundos.quota_classes.review import review_report  # noqa: E402


REQUIRED_MIGRATIONS = {1: "initial_schema", 6: "quota_class_map"}


class ReportError(Exception):
    """Erro com mensagem propria, sem caminho, CNPJ, nome nem valor."""


def say(line):
    print(line, flush=True)


def date_argument(text):
    try:
        return normalize_iso_date(text, "Competencia")
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def run(args):
    say("Pacote fundos: " + str(pathlib.Path(fundos.__file__).resolve().parent))

    # Banco em disco local, de caminho curto, antes de abrir qualquer banco.
    try:
        database_path = check_local_paths(args.database)
    except BackupError as error:
        raise ReportError(str(error)) from error

    if not database_path.is_file():
        raise ReportError("Banco nao encontrado; nada foi criado.")

    connection = open_read_only(database_path)

    try:
        missing = missing_migrations(connection, REQUIRED_MIGRATIONS)

        if missing:
            raise ReportError("Banco sem as migrations: " + ", ".join(missing) + ".")

        with read_snapshot(connection):
            report = review_report(
                connection,
                None if args.reference_date is None else (args.reference_date,),
            )
    finally:
        connection.close()

    for line in format_review_report(report):
        say(line)

    say("Relatorio concluido: nenhum banco foi alterado.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Relatorio de revisao do quota_class_map (so leitura, so contagens).",
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco, em disco local. Obrigatorio: nao ha banco padrao.",
    )
    parser.add_argument(
        "--reference-date",
        type=date_argument,
        default=None,
        help="So esta competencia (AAAA-MM-DD). Sem ela: todas as com tab_X_2.",
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except (ReportError, ReviewError, IndicatorDatabaseError) as error:
        print("Erro no relatorio do quota_class_map: " + str(error), file=sys.stderr)
        return 1
    except Exception as error:
        # Erro inesperado: so o tipo, sem mensagem nem traceback.
        print(
            "Erro inesperado no relatorio do quota_class_map: " + type(error).__name__,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
