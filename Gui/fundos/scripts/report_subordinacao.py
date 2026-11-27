"""Relatorio da subordinacao das classes de FIDC, calculada na leitura (so leitura).

Uso (a partir da pasta do modulo de Fundos):

    python scripts/report_subordinacao.py --database <banco> --reference-date 2026-09-30

Mostra a formula, a competencia, a situacao das regras do quota_class_map
usadas e contagens por estado (calculado ou sem_dado), motivo e marca, a
conferencia da soma das series com o PL (1% puro), as faixas da
subordinacao e a divisao do valor das series em senior, mezanino,
subordinada e subtipo ausente. So contagens: nunca CNPJ, nome nem valor de
linha.

Abre o banco so para leitura (mode=ro e query_only; banco em WAL e
recusado) e nao escreve nada. Exige as migrations 001 e 006. O banco fica
em disco local, de caminho curto (decisao 9 de Fundos): --database em
caminho de rede (UNC, relativo dentro de pasta de rede ou unidade remota)
ou longo e recusado antes de abrir o banco.
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
from fundos.indicators.reading import previous_month_end  # noqa: E402
from fundos.indicators.subordinacao import subordinacao  # noqa: E402
from fundos.indicators.subordinacao_report import format_subordinacao_report  # noqa: E402


REQUIRED_MIGRATIONS = {1: "initial_schema", 6: "quota_class_map"}


class ReportError(Exception):
    """Erro com mensagem propria, sem caminho, CNPJ, nome nem valor."""


def say(line):
    print(line, flush=True)


def month_end_argument(text):
    try:
        reference = normalize_iso_date(text, "Competencia")
        previous_month_end(reference)
        return reference
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

        results = subordinacao(connection, args.reference_date)
    finally:
        connection.close()

    for line in format_subordinacao_report(results, args.reference_date):
        say(line)

    say("Relatorio concluido: nenhum banco foi alterado.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Relatorio da subordinacao das classes de FIDC (so leitura, so contagens).",
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Caminho do banco, em disco local. Obrigatorio: nao ha banco padrao.",
    )
    parser.add_argument(
        "--reference-date",
        required=True,
        type=month_end_argument,
        help="Competencia, o ultimo dia do mes (por exemplo 2026-09-30).",
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        return run(args)
    except (ReportError, IndicatorDatabaseError) as error:
        print("Erro no relatorio da subordinacao: " + str(error), file=sys.stderr)
        return 1
    except Exception as error:
        # Erro inesperado: so o tipo, sem mensagem nem traceback.
        print(
            "Erro inesperado no relatorio da subordinacao: " + type(error).__name__,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
