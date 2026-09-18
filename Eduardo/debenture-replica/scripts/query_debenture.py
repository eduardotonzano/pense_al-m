import argparse
import sys

from debenture_search.database import database
from debenture_search.services.debenture_query_service import (
    DebentureQueryService,
)


def format_value(value):
    if value is True:
        return "Sim"
    if value is False:
        return "Nao"
    if value is None:
        return "Nao informado"
    return str(value)


def print_summary(item):
    print(
        item.asset_code,
        "|",
        item.isin or "sem ISIN",
        "|",
        item.issuer_name or "sem emissor",
        "|",
        item.status,
    )


def print_details(details):
    item = details.debenture
    print("DEBENTURE")
    print("Codigo:", item.asset_code)
    print("ISIN:", item.isin or "Nao informado")
    print("Emissor:", item.issuer_name or "Nao informado")
    print("CNPJ:", item.issuer_cnpj or "Nao informado")
    print("Emissao:", item.issue_number or "Nao informado")
    print("Serie:", item.series or "Nao informado")
    print("Status:", item.status)
    print("Conflitos abertos:", details.open_conflicts)
    print()
    print("VALORES ATUAIS")

    if not details.current_values:
        print("Nenhum valor atual encontrado.")
        return

    for field_name, observation in details.current_values.items():
        unit = "" if observation.unit is None else " " + observation.unit
        print(
            field_name + ":",
            format_value(observation.value) + unit,
            "| fonte:",
            observation.source_code,
            "| observado em:",
            observation.observed_at,
        )


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Consulta debentures armazenadas no banco local."
    )
    parser.add_argument("identifier", nargs="?")
    parser.add_argument(
        "--by",
        choices=["code", "isin", "issuer"],
        default="code",
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--history")
    return parser


def main(argv=None):
    arguments = build_argument_parser().parse_args(argv)
    service = DebentureQueryService(database)

    if arguments.list:
        items = service.list_all()
        for item in items:
            print_summary(item)
        print("Total:", len(items))
        return 0

    if not arguments.identifier:
        print("Falha: informe um identificador ou use --list.", file=sys.stderr)
        return 1

    if arguments.by == "issuer":
        items = service.search_by_issuer(arguments.identifier)
        for item in items:
            print_summary(item)
        print("Total:", len(items))
        return 0 if items else 2

    if arguments.history:
        history = service.history(arguments.identifier, arguments.history)
        if not history:
            print("Nenhum historico encontrado.")
            return 2
        for item in history:
            unit = "" if item.unit is None else " " + item.unit
            print(
                item.observed_at,
                "|",
                format_value(item.value) + unit,
                "| fonte:",
                item.source_code,
            )
        return 0

    details = service.get_details(arguments.identifier, by=arguments.by)
    if details is None:
        print("Debenture nao encontrada.")
        return 2

    print_details(details)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
