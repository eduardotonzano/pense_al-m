import json
from datetime import datetime, timezone
from types import SimpleNamespace

from debenture_search.services.quality_report_service import QualityReportService


NOW = datetime(2026, 9, 14, 18, tzinfo=timezone.utc)


class Database:
    def __init__(self, integrity="ok", foreign_keys=None):
        self.integrity = integrity
        self.foreign_keys = foreign_keys or []

    def integrity_check(self):
        return self.integrity

    def foreign_key_check(self):
        return self.foreign_keys


class Quality:
    def __init__(self, issues=None):
        self.issues = issues or []

    def check(self):
        return SimpleNamespace(issues=self.issues)


def service(tmp_path, issues=None, integrity="ok", foreign_keys=None, logger=None):
    return QualityReportService(
        Database(integrity, foreign_keys),
        Quality(issues),
        output_dir=tmp_path / "logs",
        now_function=lambda: NOW,
        operation_log=logger,
    )


def test_success_without_issues(tmp_path):
    report = service(tmp_path).build()
    assert report.status == "success"
    assert report.issue_count == 0


def test_warning_classification(tmp_path):
    report = service(
        tmp_path,
        [{"code": "missing_field", "severity": "warning", "message": "Campo ausente"}],
    ).build()
    assert report.status == "success_with_warnings"
    assert report.warning_count == 1


def test_critical_classification(tmp_path):
    report = service(
        tmp_path,
        [{"code": "invalid_value", "severity": "critical", "message": "Valor inválido"}],
    ).build()
    assert report.status == "failed"
    assert report.critical_count == 1


def test_integrity_failure_is_critical(tmp_path):
    report = service(tmp_path, integrity="corrupt").build()
    assert report.status == "failed"
    assert any(item["code"] == "sqlite_integrity" for item in report.issues)


def test_foreign_key_failure_is_critical(tmp_path):
    report = service(tmp_path, foreign_keys=[{"table": "observations"}]).build()
    assert report.foreign_key_violations == 1
    assert report.status == "failed"


def test_writes_latest_and_history(tmp_path):
    report, paths = service(tmp_path).run(write=True)
    assert paths["latest_path"].exists()
    assert paths["history_path"].exists()
    latest = json.loads(paths["latest_path"].read_text(encoding="utf-8"))
    history = json.loads(paths["history_path"].read_text(encoding="utf-8").splitlines()[0])
    assert latest["status"] == "success"
    assert history["generated_at"] == NOW.isoformat()


def test_history_appends(tmp_path):
    configured = service(tmp_path)
    configured.run(write=True)
    configured.run(write=True)
    lines = (tmp_path / "logs" / "quality_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_write_false_does_not_create_files(tmp_path):
    _, paths = service(tmp_path).run(write=False)
    assert paths["latest_path"] is None
    assert not (tmp_path / "logs").exists()


def test_logs_completion(tmp_path):
    class Logger:
        def __init__(self):
            self.calls = []
        def log(self, level, event, **fields):
            self.calls.append((level, event, fields))

    logger = Logger()
    service(tmp_path, logger=logger).build()
    assert logger.calls[0][1] == "quality_check_completed"
    assert logger.calls[0][2]["status"] == "success"
