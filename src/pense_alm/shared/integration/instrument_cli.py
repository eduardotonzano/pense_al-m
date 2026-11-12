"""Entrada operacional da integracao de debentures (instrumento).

Por padrao a execucao e uma simulacao: o banco de destino e copiado
para uma pasta temporaria e nada e gravado nele. Gravar exige --commit
e --backup-dir; o backup e feito antes de qualquer gravacao.
"""

import argparse
import tempfile
from pathlib import Path

from pense_alm.shared.entities import IdentifierType
from pense_alm.shared.persistence import (
    SQLiteConnectionManager,
    SQLiteEntityRepository,
    SQLiteRelationshipRepository,
    create_sqlite_backup,
)

from .debenture_instrument_batch_import_service import (
    DebentureInstrumentBatchImportService,
    InstrumentBatchOutcome,
)
from .legacy_instrument_reader import (
    LegacyDebentureInstrumentReader,
)


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da entrada operacional."""

    parser = argparse.ArgumentParser(
        description=(
            "Importa debentures (instrumento) do banco legado "
            "para a Shared Entity Layer. Sem --commit apenas "
            "simula, em uma copia descartavel do destino."
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

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Simula sobre uma copia descartavel do destino "
            "(comportamento padrao)."
        ),
    )

    mode.add_argument(
        "--commit",
        action="store_true",
        help="Faz o backup e grava no banco de destino.",
    )

    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Pasta do backup. Obrigatoria com --commit.",
    )

    parser.add_argument(
        "--create",
        action="store_true",
        help=(
            "Cria o banco de destino se ele nao existir "
            "(so com --commit)."
        ),
    )

    return parser


def _identifier_text(entity, identifier_type) -> str:
    identifier = entity.get_identifier(identifier_type)

    return "-" if identifier is None else identifier.value


def _exit_code(outcome: InstrumentBatchOutcome) -> int:
    report = outcome.report

    if report.errors > 0:
        return 2

    if report.blocked > 0:
        return 3

    if report.review > 0:
        return 4

    return 0


def _import_into(
    reader: LegacyDebentureInstrumentReader,
    database_path: Path,
    batch_size: int,
    dry_run: bool,
) -> int:
    manager = SQLiteConnectionManager(database_path)

    outcome = DebentureInstrumentBatchImportService(
        reader,
        SQLiteEntityRepository(manager),
        SQLiteRelationshipRepository(manager),
    ).run(
        batch_size=batch_size,
        dry_run=dry_run,
    )

    report = outcome.report

    print(f"Total lido: {report.total_read}")
    print(f"Criados: {report.created}")
    print(f"Correspondentes: {report.matched}")
    print(f"Revisao: {report.review}")
    print(f"Bloqueados: {report.blocked}")
    print(f"Erros: {report.errors}")
    print(f"Dry run: {report.dry_run}")

    for result in outcome.pending:
        code = _identifier_text(
            result.incoming_entity,
            IdentifierType.ASSET_CODE,
        )
        isin = _identifier_text(
            result.incoming_entity,
            IdentifierType.ISIN,
        )

        print(
            "Pendente:",
            f"legacy_id={result.legacy_id};",
            f"codigo={code};",
            f"isin={isin};",
            f"acao={result.action.value};",
            f"motivo={result.reason.value}",
        )

    for detail in report.error_details:
        print(
            "Erro:",
            f"legacy_id={detail.legacy_id};",
            f"tipo={detail.error_type};",
            f"mensagem={detail.message}",
        )

    return _exit_code(outcome)


def run_instrument_import(
    legacy_db: Path,
    target_db: Path,
    batch_size: int,
    commit: bool = False,
    backup_dir: Path | None = None,
    create: bool = False,
) -> int:
    """Executa a importacao com caminhos explicitos."""

    if commit and backup_dir is None:
        raise ValueError("--commit exige --backup-dir.")

    if not commit and (create or backup_dir is not None):
        raise ValueError(
            "--create e --backup-dir so valem com --commit."
        )

    reader = LegacyDebentureInstrumentReader(legacy_db)
    target_exists = Path(target_db).is_file()

    if not commit:
        print(
            "Modo: dry-run (simulacao em copia descartavel; "
            "o destino nao e alterado)"
        )

        with tempfile.TemporaryDirectory(
            prefix="instrument_import_",
            ignore_cleanup_errors=True,
        ) as temp_dir:
            if target_exists:
                working = create_sqlite_backup(
                    target_db,
                    temp_dir,
                ).path
            else:
                print(
                    "Aviso: banco de destino inexistente; "
                    "simulacao sobre um banco vazio."
                )
                working = Path(temp_dir) / "empty.sqlite3"

            return _import_into(
                reader,
                working,
                batch_size,
                dry_run=True,
            )

    print("Modo: commit")

    if target_exists:
        try:
            backup = create_sqlite_backup(
                target_db,
                backup_dir,
            )
        except Exception as error:
            print(
                "Erro: nao foi possivel criar o backup; "
                f"nada foi gravado: {error}"
            )
            return 2

        print(f"Backup: {backup.path}")
        print(f"  tamanho: {backup.size_bytes} bytes")
        print(f"  sha256: {backup.sha256}")
    elif create:
        print(
            "Banco de destino novo: nao ha o que copiar "
            "no backup."
        )
    else:
        print(
            "Erro: banco de destino inexistente; "
            "use --create para criar um novo."
        )
        return 2

    return _import_into(
        reader,
        Path(target_db),
        batch_size,
        dry_run=False,
    )


def main(argv: list[str] | None = None) -> int:
    """Processa argumentos e executa a importacao."""

    parser = build_parser()
    arguments = parser.parse_args(argv)

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

    if arguments.commit and arguments.backup_dir is None:
        parser.error("--commit exige --backup-dir.")

    if not arguments.commit and arguments.backup_dir is not None:
        parser.error(
            "--backup-dir so pode ser usado com --commit."
        )

    if not arguments.commit and arguments.create:
        parser.error("--create so pode ser usado com --commit.")

    if (
        arguments.commit
        and not arguments.create
        and not arguments.target_db.is_file()
    ):
        parser.error(
            "--target-db nao existe; "
            "use --create para criar um novo."
        )

    return run_instrument_import(
        legacy_db=arguments.legacy_db,
        target_db=arguments.target_db,
        batch_size=arguments.batch_size,
        commit=arguments.commit,
        backup_dir=arguments.backup_dir,
        create=arguments.create,
    )


if __name__ == "__main__":
    raise SystemExit(main())
