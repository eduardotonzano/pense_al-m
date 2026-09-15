import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from debenture_search.providers.snd_provider import SndProvider
from debenture_search.services.backup_service import BackupService
from debenture_search.services.debenture_export_service import DebentureExportService
from debenture_search.services.retry_policy import RetryPolicy


@dataclass(frozen=True)
class AutomationResult:
    requested: int
    processed: int
    successes: int
    failures: int
    observations_created: int
    observations_reused: int
    conflicts_created: int
    stale_runs_closed: int
    stale_raw_records_closed: int
    backup_path: object | None
    exports: tuple
    items: tuple


class CollectionAutomationService:
    """Executa uma coleta configurada com saneamento, backup e exportacao."""

    def __init__(
        self,
        db,
        provider_factory=None,
        backup_service=None,
        export_service=None,
        sleep_function=None,
        now_function=None,
        operation_log_service=None,
    ):
        self.db = db
        self.provider_factory = provider_factory or self._default_provider
        self.backup_service = backup_service or BackupService(db)
        self.export_service = export_service or DebentureExportService(db)
        self.sleep = sleep_function or time.sleep
        self.now = now_function or (lambda: datetime.now(timezone.utc))
        self.operation_log = operation_log_service

    def _default_provider(self, config):
        return SndProvider(
            self.db,
            timeout_seconds=config.request_timeout_seconds,
        )

    def close_stale_records(self, stale_run_minutes):
        cutoff = (self.now() - timedelta(minutes=stale_run_minutes)).isoformat()
        runs = self.db.fetch_all(
            """
            SELECT id
            FROM collection_runs
            WHERE status = 'running'
              AND started_at < ?
            """,
            (cutoff,),
        )
        raw_records = self.db.fetch_all(
            """
            SELECT rr.id
            FROM raw_records rr
            JOIN collection_runs cr ON cr.id = rr.collection_run_id
            WHERE rr.processing_status = 'pending'
              AND cr.started_at < ?
            """,
            (cutoff,),
        )

        finished_at = self.now().isoformat()
        for row in runs:
            self.db.execute(
                """
                UPDATE collection_runs
                SET status = 'failed',
                    finished_at = ?,
                    failed_items = requested_items - successful_items
                WHERE id = ? AND status = 'running'
                """,
                (finished_at, row["id"]),
            )

        for row in raw_records:
            self.db.execute(
                """
                UPDATE raw_records
                SET processing_status = 'failed'
                WHERE id = ? AND processing_status = 'pending'
                """,
                (row["id"],),
            )

        return len(runs), len(raw_records)

    def _collect_with_attempts(self, provider, code, max_attempts):
        policy = RetryPolicy(max_attempts=max_attempts)

        for attempt in range(1, policy.max_attempts + 1):
            try:
                return provider.collect(code)
            except Exception as error:
                decision = policy.classify(error)

                if not policy.should_retry(error, attempt):
                    raise

                delay = policy.delay_for_attempt(attempt)

                if self.operation_log is not None:
                    self.operation_log.retry_scheduled(
                        asset_code=code,
                        attempt=attempt,
                        max_attempts=policy.max_attempts,
                        delay_seconds=delay,
                        category=decision.category,
                        http_status=decision.http_status,
                        error=error,
                    )

                self.sleep(delay)

        raise RuntimeError("Fluxo de retry terminou sem resultado.")

    def _export(self, config):
        export_dir = Path(config.export_dir)
        exports = []

        if config.export_csv:
            result = self.export_service.export(
                "csv",
                export_dir / "debentures.csv",
            )
            exports.append(result["path"])

        if config.export_json:
            result = self.export_service.export(
                "json",
                export_dir / "debentures.json",
            )
            exports.append(result["path"])

        if config.export_history:
            result = self.export_service.export(
                "csv",
                export_dir / "debenture_history.csv",
                history=True,
            )
            exports.append(result["path"])

        return tuple(exports)

    def run(self, config, commit=False):
        automation_started_at = time.perf_counter()
        if self.operation_log is not None:
            self.operation_log.automation_started(
                len(config.asset_codes),
                commit,
            )
        stale_runs, stale_raws = (0, 0)
        if commit:
            stale_runs, stale_raws = self.close_stale_records(
                config.stale_run_minutes
            )

        backup_path = None
        if commit and config.create_backup:
            backup_record = self.backup_service.create_backup()
            backup_path = backup_record.path
            if self.operation_log is not None:
                self.operation_log.backup_created(
                    backup_record.path,
                    getattr(backup_record, "size_bytes", None),
                    getattr(backup_record, "sha256", None),
                )

        provider = self.provider_factory(config)
        items = []

        for index, code in enumerate(config.asset_codes):
            asset_started_at = time.perf_counter()
            if self.operation_log is not None:
                self.operation_log.asset_started(code, attempt=1)
            try:
                if commit:
                    result = self._collect_with_attempts(
                        provider,
                        code,
                        config.max_attempts,
                    )
                    items.append(
                        {
                            "asset_code": code,
                            "status": "success",
                            "observations_created": result.observations_created,
                            "observations_reused": result.observations_reused,
                            "conflicts_created": result.conflicts_created,
                            "error": None,
                        }
                    )
                else:
                    provider.fetch_html(code)
                    items.append(
                        {
                            "asset_code": code,
                            "status": "preview",
                            "observations_created": 0,
                            "observations_reused": 0,
                            "conflicts_created": 0,
                            "error": None,
                        }
                    )
                if self.operation_log is not None:
                    self.operation_log.asset_succeeded(
                        code,
                        time.perf_counter() - asset_started_at,
                        attempt=1,
                    )
            except Exception as error:
                if self.operation_log is not None:
                    self.operation_log.asset_failed(
                        code,
                        error,
                        time.perf_counter() - asset_started_at,
                        attempt=1,
                    )
                items.append(
                    {
                        "asset_code": code,
                        "status": "failed",
                        "observations_created": 0,
                        "observations_reused": 0,
                        "conflicts_created": 0,
                        "error": type(error).__name__ + ": " + str(error),
                    }
                )

            if index < len(config.asset_codes) - 1:
                self.sleep(config.request_interval_seconds)

        exports = self._export(config) if commit else ()

        if commit:
            if self.db.integrity_check() != "ok":
                raise RuntimeError("A integridade do banco falhou.")
            if self.db.foreign_key_check():
                raise RuntimeError("Foram encontradas violacoes de foreign keys.")

        failures = sum(item["status"] == "failed" for item in items)
        if self.operation_log is not None:
            self.operation_log.integrity_checked(
                self.db.integrity_check(),
                self.db.foreign_key_check(),
            )
            self.operation_log.automation_finished(
                len(items) - failures,
                failures,
                time.perf_counter() - automation_started_at,
            )
        return AutomationResult(
            requested=len(config.asset_codes),
            processed=len(items),
            successes=len(items) - failures,
            failures=failures,
            observations_created=sum(
                item["observations_created"] for item in items
            ),
            observations_reused=sum(
                item["observations_reused"] for item in items
            ),
            conflicts_created=sum(
                item["conflicts_created"] for item in items
            ),
            stale_runs_closed=stale_runs,
            stale_raw_records_closed=stale_raws,
            backup_path=backup_path,
            exports=exports,
            items=tuple(items),
        )
