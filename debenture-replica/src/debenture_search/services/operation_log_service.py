import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from debenture_search.logging_config import sanitize_value


@dataclass
class OperationTimer:
    event: str
    asset_code: str | None
    started_at: float
    attempt: int | None = None


class OperationLogService:
    """Registra eventos operacionais textuais e estruturados."""

    def __init__(self, logger, clock=None, utcnow=None):
        self.logger = logger
        self.clock = clock or time.perf_counter
        self.utcnow = utcnow or (
            lambda: datetime.now(timezone.utc)
        )

    def log(self, level, event, **fields):
        normalized_level = str(level).strip().upper()
        numeric_level = getattr(logging, normalized_level, logging.INFO)
        safe_fields = sanitize_value(fields)

        parts = [event]
        for key in (
            "asset_code",
            "attempt",
            "http_status",
            "duration_seconds",
            "error_type",
            "error_message",
        ):
            value = safe_fields.get(key)
            if value is not None:
                parts.append(key + "=" + str(value))

        self.logger.log(
            numeric_level,
            " | ".join(parts),
            extra={
                "event": event,
                "event_timestamp": self.utcnow().isoformat(),
                **safe_fields,
            },
        )

    def automation_started(self, asset_count, committed):
        self.log(
            "INFO",
            "automation_started",
            asset_count=int(asset_count),
            committed=bool(committed),
        )

    def automation_finished(
        self,
        successes,
        failures,
        duration_seconds,
    ):
        self.log(
            "INFO" if failures == 0 else "WARNING",
            "automation_finished",
            successes=int(successes),
            failures=int(failures),
            duration_seconds=round(float(duration_seconds), 6),
        )

    def asset_started(self, asset_code, attempt=1):
        self.log(
            "INFO",
            "asset_started",
            asset_code=str(asset_code),
            attempt=int(attempt),
        )

    def asset_succeeded(
        self,
        asset_code,
        duration_seconds,
        attempt=1,
        http_status=None,
        **fields,
    ):
        self.log(
            "INFO",
            "asset_succeeded",
            asset_code=str(asset_code),
            attempt=int(attempt),
            duration_seconds=round(float(duration_seconds), 6),
            http_status=http_status,
            **fields,
        )

    def asset_failed(
        self,
        asset_code,
        error,
        duration_seconds,
        attempt=1,
        http_status=None,
    ):
        self.log(
            "ERROR",
            "asset_failed",
            asset_code=str(asset_code),
            attempt=int(attempt),
            duration_seconds=round(float(duration_seconds), 6),
            http_status=http_status,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    def retry_scheduled(
        self,
        asset_code,
        attempt,
        max_attempts,
        delay_seconds,
        category,
        error,
        http_status=None,
    ):
        """Registra uma nova tentativa permitida pela politica de retry."""

        self.log(
            "WARNING",
            "retry_scheduled",
            asset_code=str(asset_code),
            attempt=int(attempt),
            max_attempts=int(max_attempts),
            retry_delay_seconds=round(float(delay_seconds), 6),
            error_category=str(category),
            retryable=True,
            http_status=http_status,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    def backup_created(self, path, size_bytes=None, sha256=None):
        self.log(
            "INFO",
            "backup_created",
            backup_path=path,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    def export_created(self, path, file_format=None, rows=None):
        self.log(
            "INFO",
            "export_created",
            output_path=path,
            file_format=file_format,
            rows=rows,
        )

    def stale_run_closed(self, collection_run_id):
        self.log(
            "WARNING",
            "stale_run_closed",
            collection_run_id=int(collection_run_id),
        )

    def integrity_checked(self, integrity, foreign_keys):
        self.log(
            "INFO" if integrity == "ok" and not foreign_keys else "ERROR",
            "integrity_check_completed",
            integrity=integrity,
            foreign_key_violations=len(foreign_keys),
        )

    @contextmanager
    def asset_operation(self, asset_code, attempt=1):
        """Mede uma operacao e registra sucesso ou falha automaticamente."""

        started = self.clock()
        self.asset_started(asset_code, attempt=attempt)
        try:
            yield OperationTimer(
                event="asset_operation",
                asset_code=str(asset_code),
                started_at=started,
                attempt=attempt,
            )
        except Exception as error:
            elapsed = self.clock() - started
            self.asset_failed(
                asset_code,
                error,
                elapsed,
                attempt=attempt,
            )
            raise
        else:
            elapsed = self.clock() - started
            self.asset_succeeded(
                asset_code,
                elapsed,
                attempt=attempt,
            )
