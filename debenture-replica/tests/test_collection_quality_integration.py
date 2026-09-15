from pathlib import Path
from types import SimpleNamespace

from debenture_search.services.quality_report_service import QualityReportService


class Database:
    def integrity_check(self):
        return "ok"
    def foreign_key_check(self):
        return []


class DataQuality:
    def __init__(self, issues):
        self._issues = issues
    def check(self):
        return SimpleNamespace(issues=self._issues)


def automation_payload(base, quality_report, quality_paths):
    result = dict(base)
    result["quality"] = QualityReportService.to_dict(quality_report)
    result["quality_files"] = {
        key: None if value is None else str(value)
        for key, value in quality_paths.items()
    }
    result["status"] = quality_report.status
    return result


def test_automation_payload_contains_quality(tmp_path):
    quality = QualityReportService(Database(), DataQuality([]), tmp_path)
    report, paths = quality.run(write=True)
    payload = automation_payload({"successes": 3, "failures": 0}, report, paths)
    assert payload["status"] == "success"
    assert payload["quality"]["integrity"] == "ok"
    assert Path(payload["quality_files"]["latest_path"]).exists()


def test_warning_changes_automation_status(tmp_path):
    issue = {"severity": "warning", "message": "CNPJ ausente", "code": "cnpj_missing"}
    quality = QualityReportService(Database(), DataQuality([issue]), tmp_path)
    report, paths = quality.run(write=False)
    payload = automation_payload({"successes": 3, "failures": 0}, report, paths)
    assert payload["status"] == "success_with_warnings"
    assert payload["quality"]["warning_count"] == 1


def test_critical_changes_automation_status(tmp_path):
    issue = {"severity": "critical", "message": "Valor inválido", "code": "invalid_value"}
    quality = QualityReportService(Database(), DataQuality([issue]), tmp_path)
    report, paths = quality.run(write=False)
    payload = automation_payload({"successes": 3, "failures": 0}, report, paths)
    assert payload["status"] == "failed"
    assert payload["quality"]["critical_count"] == 1


def test_quality_check_is_read_only(tmp_path):
    class ReadOnlyDatabase(Database):
        def execute(self, *args, **kwargs):
            raise AssertionError("Quality report must not write to the database")
    report, _ = QualityReportService(
        ReadOnlyDatabase(), DataQuality([]), tmp_path
    ).run(write=False)
    assert report.status == "success"
