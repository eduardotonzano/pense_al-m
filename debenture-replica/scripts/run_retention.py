import argparse
import sys

from debenture_search.logging_config import (
    close_operational_logging,
    configure_operational_logging,
)
from debenture_search.services.execution_lock_service import (
    ExecutionLockError,
    ExecutionLockService,
)
from debenture_search.services.operation_log_service import OperationLogService
from debenture_search.services.retention_service import RetentionService


def format_bytes(value):
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.2f} {unit}"
        size /= 1024


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Executa a retenção segura dos arquivos operacionais."
    )
    parser.add_argument("config_path")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    return parser


def print_result(result, committed):
    print("RETENCAO OPERACIONAL")
    print("Modo:", "COMMIT" if committed else "DRY-RUN")
    print("Arquivos analisados:", result.scanned)
    print("Arquivos elegiveis:", result.eligible)
    print("Arquivos removidos:", result.removed)
    print("Falhas:", result.failed)
    print("Espaco elegivel:", format_bytes(result.bytes_eligible))
    print("Espaco liberado:", format_bytes(result.bytes_removed))

    for item in result.items:
        if item.eligible:
            action = "REMOVIDO" if item.removed else "REMOVERIA"
            if item.error:
                action = "FALHOU"
            print(action, "|", item.rule, "|", item.path, "|", item.reason)


def main(argv=None):
    arguments = build_argument_parser().parse_args(argv)
    logging_state = None

    try:
        config = RetentionService.load_config(arguments.config_path)
        logging_state = configure_operational_logging("logs")
        operation_log = OperationLogService(logging_state["logger"])

        with ExecutionLockService(
            "runtime/retention.lock",
            command=" ".join(sys.argv),
        ):
            result = RetentionService(
                project_root=".",
                operation_log=operation_log,
            ).run(config, commit=arguments.commit)

        operation_log.log(
            "INFO",
            "retention_finished",
            committed=arguments.commit,
            scanned=result.scanned,
            eligible=result.eligible,
            removed=result.removed,
            failed=result.failed,
            bytes_removed=result.bytes_removed,
        )

    except (ValueError, ExecutionLockError) as error:
        print("Falha:", error, file=sys.stderr)
        return 3 if isinstance(error, ExecutionLockError) else 1
    finally:
        if logging_state is not None:
            close_operational_logging(logging_state["logger"])

    print_result(result, arguments.commit)
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
