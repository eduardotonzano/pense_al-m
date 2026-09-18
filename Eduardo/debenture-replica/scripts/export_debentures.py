import argparse
import sys
from pathlib import Path

from debenture_search.database import database
from debenture_search.services.debenture_export_service import (
    DebentureExportService,
)


def default_output(file_format, history):
    filename = (
        "debenture_history." + file_format
        if history
        else "debentures." + file_format
    )
    return Path("exports") / filename


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Exporta debentures armazenadas no banco local."
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
    )
    parser.add_argument("--asset-code")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--output")
    return parser


def main(argv=None):
    arguments = build_argument_parser().parse_args(argv)
    output = (
        Path(arguments.output)
        if arguments.output
        else default_output(arguments.format, arguments.history)
    )

    try:
        result = DebentureExportService(database).export(
            file_format=arguments.format,
            output_path=output,
            asset_code=arguments.asset_code,
            history=arguments.history,
        )
    except ValueError as error:
        print("Falha:", error, file=sys.stderr)
        return 1

    print("EXPORTACAO CONCLUIDA")
    print("Arquivo:", result["path"])
    print("Formato:", result["format"])
    print("Historico:", "Sim" if result["history"] else "Nao")
    print("Linhas:", result["rows"])
    print("Banco alterado: Nao")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
