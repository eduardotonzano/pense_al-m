"""Fila de download em lotes: enfileirar, executar e consultar.

  --status                       situação da fila (só leitura)
  --enqueue --dry-run|--commit   enfileira documentos pendentes do catálogo
  --run --dry-run|--commit       executa um lote (um download por vez)

Sem --dry-run nem --commit, enfileirar e executar recusam rodar. O padrão é o piloto:
concorrência 1, 2 s entre requisições, no máximo 20 por minuto, 3 tentativas
(1, 5 e 30 min), parada após 5 falhas seguidas ou taxa de falha >= 20% em 20+
tentativas, espaço livre mínimo = maior entre 10 GB e 10% do disco.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit_assets.database.connection import connect
from credit_assets.database.migrations import ensure_schema_current
from credit_assets.repositories.document_version_repository import (
    DocumentVersionRepository,
)
from credit_assets.services.document_download_service import DocumentDownloadService
from credit_assets.services.download_queue_service import (
    DEFAULT_CATEGORIES,
    GIGABYTE,
    DownloadQueueWorker,
    QueueConfig,
    candidate_documents,
    enqueue_documents,
    make_service_executor,
    queue_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", default=str(ROOT / "data" / "cri_cra.db"))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--status", action="store_true")
    action.add_argument("--enqueue", action="store_true")
    action.add_argument("--run", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--only", action="append", dest="only",
                        help="código CETIP (repetível ou separado por vírgula)")
    parser.add_argument("--category", action="append", dest="categories",
                        choices=DEFAULT_CATEGORIES)
    parser.add_argument("--include-failed", action="store_true")
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--max-duration-minutes", type=float)
    parser.add_argument("--max-total-megabytes", type=int)
    parser.add_argument("--max-megabytes", type=int, default=25, choices=range(1, 201),
                        metavar="1-200", help="limite por arquivo (padrão 25)")
    parser.add_argument("--min-interval-seconds", type=float, default=2.0)
    parser.add_argument("--max-per-minute", type=int, default=20)
    parser.add_argument("--abandon-minutes", type=float, default=30.0)
    parser.add_argument("--min-free-gb", type=float, default=10.0)
    return parser


def build_config(args: argparse.Namespace) -> QueueConfig:
    extra = {}
    if args.categories:
        extra["categories"] = tuple(args.categories)
    return QueueConfig(
        min_interval_seconds=args.min_interval_seconds,
        max_requests_per_minute=args.max_per_minute,
        max_items=args.max_items,
        max_duration_seconds=(
            args.max_duration_minutes * 60 if args.max_duration_minutes else None
        ),
        max_total_bytes=(
            args.max_total_megabytes * 1_000_000 if args.max_total_megabytes else None
        ),
        min_free_bytes_floor=int(args.min_free_gb * GIGABYTE),
        abandon_after_seconds=int(args.abandon_minutes * 60),
        **extra,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if (args.enqueue or args.run) and not (args.dry_run or args.commit):
        parser.error("informe --dry-run ou --commit")
    cetips = [part for value in args.only or [] for part in value.split(",") if part]
    config = build_config(args)

    connection = connect(args.database)
    try:
        ensure_schema_current(connection)
        if args.status:
            print(json.dumps(queue_status(connection), ensure_ascii=False, indent=2,
                             default=str))
            return 0
        if args.enqueue:
            report = enqueue_documents(
                connection, config, cetips, args.include_failed,
                dry_run=not args.commit,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if not args.commit:
            pending = queue_status(connection)["items"].get("pending", 0)
            print(json.dumps({
                "dry_run": True, "pending_in_queue": pending,
                "candidates_not_yet_enqueued": len(
                    candidate_documents(connection, config, cetips, args.include_failed)
                ),
                "config": {k: v for k, v in vars(args).items() if k != "database"},
            }, ensure_ascii=False, indent=2, default=str))
            return 0
        service = DocumentDownloadService(
            connection, DocumentVersionRepository(connection), ROOT,
            max_bytes=args.max_megabytes * 1_000_000,
        )
        worker = DownloadQueueWorker(
            connection, make_service_executor(service, connection), config,
            only_cetips=cetips,
        )
        report = worker.run()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "finished" else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
