import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from debenture_search.logging_config import (
    close_operational_logging,
    configure_operational_logging,
    sanitize_value,
)


def test_creates_log_directory_and_files(tmp_path):
    result = configure_operational_logging(tmp_path / "logs")
    try:
        result["logger"].info("teste")
        for handler in result["logger"].handlers:
            handler.flush()
        assert result["text_path"].exists()
        assert result["jsonl_path"].exists()
    finally:
        close_operational_logging(result["logger"])


def test_jsonl_contains_valid_json_and_accents(tmp_path):
    result = configure_operational_logging(tmp_path)
    try:
        result["logger"].info(
            "operação concluída",
            extra={"event": "test_event", "asset_code": "PETR27"},
        )
        for handler in result["logger"].handlers:
            handler.flush()
        line = result["jsonl_path"].read_text(encoding="utf-8").splitlines()[0]
        data = json.loads(line)
        assert data["message"] == "operação concluída"
        assert data["event"] == "test_event"
        assert data["asset_code"] == "PETR27"
    finally:
        close_operational_logging(result["logger"])


def test_reconfiguration_does_not_duplicate_handlers(tmp_path):
    first = configure_operational_logging(tmp_path)
    second = configure_operational_logging(tmp_path)
    try:
        assert first["logger"] is second["logger"]
        assert len(second["logger"].handlers) == 2
    finally:
        close_operational_logging(second["logger"])


def test_sanitizes_sensitive_information():
    value = sanitize_value(
        {
            "token": "abc",
            "Authorization": "Bearer secret",
            "nested": {"password": "123", "safe": "ok"},
        }
    )
    assert value["token"] == "[REDACTED]"
    assert value["Authorization"] == "[REDACTED]"
    assert value["nested"]["password"] == "[REDACTED]"
    assert value["nested"]["safe"] == "ok"


def test_serializes_supported_types():
    value = sanitize_value(
        {
            "path": Path("logs/test.log"),
            "decimal": Decimal("1.2300"),
            "date": datetime(2026, 9, 14, tzinfo=timezone.utc),
        }
    )
    assert value["path"] == str(Path("logs/test.log"))
    assert value["decimal"] == "1.2300"
    assert value["date"] == "2026-09-14T00:00:00+00:00"


def test_text_log_is_utf8(tmp_path):
    result = configure_operational_logging(tmp_path)
    try:
        result["logger"].warning("atenção")
        for handler in result["logger"].handlers:
            handler.flush()
        assert "atenção" in result["text_path"].read_text(encoding="utf-8")
    finally:
        close_operational_logging(result["logger"])
