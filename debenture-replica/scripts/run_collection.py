from ast import arguments
from unittest import result

from debenture_search.services.health_monitor_service import (
    HealthMonitorService,
)

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from debenture_search.config import load_collection_config
from debenture_search.database import database
from debenture_search.logging_config import (
    close_operational_logging,
    configure_operational_logging,
)
from debenture_search.services.collection_automation_service import (
    CollectionAutomationService,
)
from debenture_search.services.data_quality_service import (
    DataQualityService,
)
from debenture_search.services.execution_lock_service import (
    ExecutionLockError,
    ExecutionLockService,
)
from debenture_search.services.operation_log_service import (
    OperationLogService,
)
from debenture_search.services.quality_report_service import (
    QualityReportService,
)


def build_argument_parser():
    """Configura os argumentos da linha de comando."""

    parser = argparse.ArgumentParser(
        description="Executa a coleta configurada de debentures."
    )

    parser.add_argument(
        "config_path",
        help="Caminho do arquivo JSON de configuracao.",
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta os ativos sem gravar no banco.",
    )

    mode.add_argument(
        "--commit",
        action="store_true",
        help="Autoriza backup, gravacao e exportacao.",
    )

    parser.add_argument(
        "--report",
        default="logs/collection_last.json",
        help="Caminho do relatorio JSON da execucao.",
    )

    return parser


def result_to_dict(
    result,
    committed,
    quality_report=None,
    quality_paths=None,
):
    """Converte o resultado completo para um dicionario."""

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "committed": bool(committed),
        "requested": result.requested,
        "processed": result.processed,
        "successes": result.successes,
        "failures": result.failures,
        "observations_created": (
            result.observations_created
        ),
        "observations_reused": (
            result.observations_reused
        ),
        "conflicts_created": (
            result.conflicts_created
        ),
        "stale_runs_closed": (
            result.stale_runs_closed
        ),
        "stale_raw_records_closed": (
            result.stale_raw_records_closed
        ),
        "backup_path": (
            None
            if result.backup_path is None
            else str(result.backup_path)
        ),
        "exports": [
            str(path)
            for path in result.exports
        ],
        "items": list(result.items),
        "quality": (
            None
            if quality_report is None
            else QualityReportService.to_dict(
                quality_report
            )
        ),
        "quality_files": {
            key: (
                None
                if value is None
                else str(value)
            )
            for key, value in (
                quality_paths or {}
            ).items()
        },
    }


def write_report(path, data):
    """Grava o relatorio operacional em JSON."""

    destination = Path(path)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return destination


def print_result(
    result,
    report_path,
    committed,
    quality_report=None,
):
    """Exibe o resumo completo da execucao."""

    print("EXECUCAO AUTOMATIZADA")
    print(
        "Modo:",
        "COMMIT" if committed else "DRY-RUN",
    )
    print(
        "Ativos solicitados:",
        result.requested,
    )
    print(
        "Ativos processados:",
        result.processed,
    )
    print(
        "Sucessos:",
        result.successes,
    )
    print(
        "Falhas:",
        result.failures,
    )

    for item in result.items:
        error = item.get("error")

        suffix = (
            ""
            if error is None
            else " - " + str(error)
        )

        print(
            str(item["asset_code"])
            + ": "
            + str(item["status"])
            + suffix
        )

    print(
        "Coletas abandonadas encerradas:",
        result.stale_runs_closed,
    )
    print(
        "Registros pendentes encerrados:",
        result.stale_raw_records_closed,
    )
    print(
        "Observacoes criadas:",
        result.observations_created,
    )
    print(
        "Observacoes reutilizadas:",
        result.observations_reused,
    )
    print(
        "Conflitos criados:",
        result.conflicts_created,
    )
    print(
        "Backup:",
        result.backup_path,
    )
    print(
        "Exportacoes:",
        [
            str(path)
            for path in result.exports
        ],
    )
    print(
        "Relatorio:",
        report_path,
    )
    print(
        "Integridade SQLite:",
        database.integrity_check(),
    )
    print(
        "Foreign keys:",
        database.foreign_key_check(),
    )

    if quality_report is not None:
        print(
            "Qualidade:",
            quality_report.status,
        )
        print(
            "Problemas de qualidade:",
            quality_report.issue_count,
        )
        print(
            "Criticos:",
            quality_report.critical_count,
        )
        print(
            "Alertas:",
            quality_report.warning_count,
        )


def main(argv=None):
    """Executa a automacao com lock, logs e qualidade."""

    arguments = build_argument_parser().parse_args(
        argv
    )

    logging_state = None
    operation_log = None
    result = None
    report_path = None
    quality_report = None
    health_report = None
    quality_paths = {}

    try:
        config = load_collection_config(
            arguments.config_path
        )

        logging_state = configure_operational_logging(
            "logs"
        )

        operation_log = OperationLogService(
            logging_state["logger"]
        )

        lock = ExecutionLockService(
            lock_path="runtime/collection.lock",
            stale_minutes=config.stale_run_minutes,
            command=" ".join(sys.argv),
        )

        with lock:
            operation_log.log(
                "INFO",
                "execution_lock_acquired",
                lock_path=lock.lock_path,
                pid=lock.pid,
                hostname=lock.hostname,
                username=lock.username,
            )

            result = CollectionAutomationService(
                database,
                operation_log_service=operation_log,
            ).run(
                config,
                commit=arguments.commit,
            )

            quality_service = QualityReportService(
                database,
                DataQualityService(database),
                output_dir="logs",
                operation_log=operation_log,
            )

            quality_report, quality_paths = (
                quality_service.run(
                    write=True
                )
            )

            health_service = HealthMonitorService(
                logs_directory="logs",
                runtime_directory="runtime",
            )

            health_report = (
                health_service.save_report()
            )

            report_data = result_to_dict(
            result,
            arguments.commit,
            quality_report=quality_report,
            quality_paths=quality_paths,
            )

            report_data["health"] = {
                "health": health_report.health,
                "critical_count": health_report.critical_count,
                "warning_count": health_report.warning_count,
                "open_alerts": health_report.open_alerts,
            }

            report_path = write_report(
                arguments.report,
                report_data,
            )

        operation_log.log(
            "INFO",
            "execution_lock_released",
            lock_path=lock.lock_path,
            pid=lock.pid,
            hostname=lock.hostname,
        )

    except ExecutionLockError as error:
        if operation_log is not None:
            operation_log.log(
                "ERROR",
                "execution_lock_rejected",
                error_type=type(error).__name__,
                error_message=str(error),
            )

        print(
            "Falha:",
            error,
            file=sys.stderr,
        )

        return 3

    except (ValueError, RuntimeError) as error:
        if operation_log is not None:
            operation_log.log(
                "ERROR",
                "automation_failed",
                error_type=type(error).__name__,
                error_message=str(error),
            )

        print(
            "Falha:",
            error,
            file=sys.stderr,
        )

        return 1

    except KeyboardInterrupt:
        if operation_log is not None:
            operation_log.log(
                "WARNING",
                "automation_interrupted",
                error_type="KeyboardInterrupt",
                error_message=(
                    "Execucao interrompida pelo usuario."
                ),
            )

        print(
            "Falha: execucao interrompida pelo usuario.",
            file=sys.stderr,
        )

        return 130

    except Exception as error:
        if operation_log is not None:
            operation_log.log(
                "ERROR",
                "automation_unexpected_error",
                error_type=type(error).__name__,
                error_message=str(error),
            )

        print(
            "Falha inesperada:",
            type(error).__name__,
            "-",
            error,
            file=sys.stderr,
        )

        return 1

    finally:
        if logging_state is not None:
            close_operational_logging(
                logging_state["logger"]
            )

    if result is None:
        print(
            "Falha: a automacao nao produziu um resultado.",
            file=sys.stderr,
        )

        return 1

    print_result(
        result,
        report_path,
        arguments.commit,
        quality_report=quality_report,
    )

    if quality_report is not None:
        if quality_report.status == "failed":
            return 4

    if result.failures > 0:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())