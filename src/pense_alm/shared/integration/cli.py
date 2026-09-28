"""Entrada operacional da integracao de emissores."""

import argparse
from pathlib import Path

from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
)

from .debenture_issuer_batch_import_service import (
    DebentureIssuerBatchImportService,
)
from .legacy_issuer_reader import (
    LegacyDebentureIssuerReader,
)


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da entrada operacional."""

    parser = argparse.ArgumentParser(
        description=(
            "Importa emissores do banco legado "
            "para a Shared Entity Layer."
        )
    )

    parser.add_argument(
        "--legacy-db",
        required=True,
        type=Path,
        help="Caminho do banco SQLite legado.",
    )

    parser.add_argument(
        "--target-db",
        required=True,
        type=Path,
        help="Caminho do banco SQLite de destino.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Quantidade de registros por lote.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a importacao sem persistir entidades.",
    )

    return parser


def run_import(
    legacy_db: Path,
    target_db: Path,
    batch_size: int,
    dry_run: bool,
) -> int:
    """Executa a importacao com caminhos explicitos."""

    reader = LegacyDebentureIssuerReader(
        legacy_db
    )

    repository = SQLiteEntityRepository(
        SQLiteConnectionManager(
            target_db
        )
    )

    service = DebentureIssuerBatchImportService(
        reader,
        repository,
    )

    report = service.run(
        batch_size=batch_size,
        dry_run=dry_run,
    )

    print(f"Total lido: {report.total_read}")
    print(f"Criados: {report.created}")
    print(f"Correspondentes: {report.matched}")
    print(f"Revisao: {report.review}")
    print(f"Bloqueados: {report.blocked}")
    print(f"Erros: {report.errors}")
    print(f"Dry run: {report.dry_run}")

    for detail in report.error_details:
        print(
            "Erro:",
            f"legacy_id={detail.legacy_id};",
            f"tipo={detail.error_type};",
            f"mensagem={detail.message}",
        )

    if report.errors > 0:
        return 2

    if report.blocked > 0:
        return 3

    if report.review > 0:
        return 4

    return 0


def main() -> int:
    """Processa argumentos e executa a importacao."""

    parser = build_parser()
    arguments = parser.parse_args()

    if arguments.batch_size <= 0:
        parser.error(
            "--batch-size deve ser maior que zero."
        )

    if not arguments.legacy_db.is_file():
        parser.error(
            "--legacy-db deve apontar para "
            "um arquivo existente."
        )

    if (
        arguments.legacy_db.resolve()
        == arguments.target_db.resolve()
    ):
        parser.error(
            "--legacy-db e --target-db "
            "devem ser diferentes."
        )

    return run_import(
        legacy_db=arguments.legacy_db,
        target_db=arguments.target_db,
        batch_size=arguments.batch_size,
        dry_run=arguments.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
