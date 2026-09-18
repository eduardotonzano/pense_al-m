import argparse
import sys
from pathlib import Path

from debenture_search.database import database
from debenture_search.providers.snd_provider import SndProvider
from debenture_search.services.snd_batch_import_service import (
    SndBatchImportService,
)


def read_codes(path):
    candidate = Path(path)

    if not candidate.exists():
        raise ValueError("Arquivo de ativos nao encontrado.")

    return [
        line.strip()
        for line in candidate.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Pre-visualiza ou importa uma lista de ativos do SND."
    )
    parser.add_argument("file_path")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--max-items", type=int, default=20)
    return parser


def print_result(result, committed):
    print("IMPORTACAO EM LOTE SND")
    print("Ativos solicitados:", result.requested)
    print("Ativos processados:", result.processed)
    print("Sucessos:", result.successes)
    print("Falhas:", result.failures)

    for item in result.items:
        suffix = "" if item.error is None else " - " + item.error
        print(item.asset_code + ": " + item.status + suffix)

    print("Observacoes criadas:", result.observations_created)
    print("Observacoes reutilizadas:", result.observations_reused)
    print("Conflitos criados:", result.conflicts_created)
    print("Backup:", result.backup_path)
    print(
        "Gravacao no banco:",
        "EXECUTADA" if committed else "NAO EXECUTADA",
    )

    if committed:
        print("Integridade SQLite:", database.integrity_check())
        print("Foreign keys:", database.foreign_key_check())


def main(argv=None):
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)

    try:
        codes = read_codes(arguments.file_path)
        service = SndBatchImportService(
            database,
            SndProvider(database),
            max_items=arguments.max_items,
        )
        result = service.run(codes, commit=arguments.commit)
    except (ValueError, RuntimeError) as error:
        print("Falha:", error, file=sys.stderr)
        return 1

    print_result(result, arguments.commit)
    return 0 if result.failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
