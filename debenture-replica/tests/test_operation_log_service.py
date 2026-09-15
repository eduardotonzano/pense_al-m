import json
import logging
from pathlib import Path

import pytest

from debenture_search.logging_config import (
    close_operational_logging,
    configure_operational_logging,
)
from debenture_search.services.operation_log_service import (
    OperationLogService,
)


def create_service(tmp_path, clock_values=None):
    configured = configure_operational_logging(tmp_path)
    values = iter(clock_values or [0.0])
    service = OperationLogService(
        configured["logger"],
        clock=lambda: next(values),
    )
    return service, configured


def read_events(configured):
    for handler in configured["logger"].handlers:
        handler.flush()
    return [
        json.loads(line)
        for line in configured["jsonl_path"].read_text(
            encoding="utf-8"
        ).splitlines()
    ]


def test_records_automation_lifecycle(tmp_path):
    service, configured = create_service(tmp_path)
    try:
        service.automation_started(3, True)
        service.automation_finished(3, 0, 4.5)
        events = read_events(configured)
        assert [event["event"] for event in events] == [
            "automation_started",
            "automation_finished",
        ]
        assert events[0]["asset_count"] == 3
        assert events[1]["duration_seconds"] == 4.5
    finally:
        close_operational_logging(configured["logger"])


def test_records_asset_success_with_duration(tmp_path):
    service, configured = create_service(tmp_path)
    try:
        service.asset_succeeded("PETR27", 1.2345678, http_status=200)
        event = read_events(configured)[0]
        assert event["event"] == "asset_succeeded"
        assert event["asset_code"] == "PETR27"
        assert event["duration_seconds"] == 1.234568
        assert event["http_status"] == 200
    finally:
        close_operational_logging(configured["logger"])


def test_records_asset_failure_without_traceback(tmp_path):
    service, configured = create_service(tmp_path)
    try:
        service.asset_failed("CEPEA1", TimeoutError("tempo esgotado"), 2.0)
        event = read_events(configured)[0]
        assert event["event"] == "asset_failed"
        assert event["error_type"] == "TimeoutError"
        assert event["error_message"] == "tempo esgotado"
        assert "traceback" not in event
    finally:
        close_operational_logging(configured["logger"])


def test_context_manager_records_success(tmp_path):
    service, configured = create_service(tmp_path, [10.0, 12.5])
    try:
        with service.asset_operation("SBSPC9"):
            pass
        events = read_events(configured)
        assert [event["event"] for event in events] == [
            "asset_started",
            "asset_succeeded",
        ]
        assert events[1]["duration_seconds"] == 2.5
    finally:
        close_operational_logging(configured["logger"])


def test_context_manager_records_and_reraises_failure(tmp_path):
    service, configured = create_service(tmp_path, [3.0, 4.25])
    try:
        with pytest.raises(ValueError, match="falha simulada"):
            with service.asset_operation("PETR27", attempt=2):
                raise ValueError("falha simulada")
        events = read_events(configured)
        assert events[-1]["event"] == "asset_failed"
        assert events[-1]["attempt"] == 2
        assert events[-1]["duration_seconds"] == 1.25
    finally:
        close_operational_logging(configured["logger"])


def test_records_backup_export_and_integrity(tmp_path):
    service, configured = create_service(tmp_path)
    try:
        service.backup_created(Path("data/backup.db"), 100, "abc")
        service.export_created(Path("exports/debentures.csv"), "csv", 3)
        service.integrity_checked("ok", [])
        events = read_events(configured)
        assert [event["event"] for event in events] == [
            "backup_created",
            "export_created",
            "integrity_check_completed",
        ]
        assert events[0]["backup_path"] == str(Path("data/backup.db"))
        assert events[1]["rows"] == 3
        assert events[2]["foreign_key_violations"] == 0
    finally:
        close_operational_logging(configured["logger"])
