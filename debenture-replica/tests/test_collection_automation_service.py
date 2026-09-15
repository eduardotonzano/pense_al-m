from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from debenture_search.config import CollectionConfig
from debenture_search.services.collection_automation_service import (
    CollectionAutomationService,
)


class Database:
    def __init__(self):
        self.executed = []

    def fetch_all(self, sql, parameters=()):
        if "FROM collection_runs" in sql:
            return [{"id": 8}]
        if "FROM raw_records" in sql:
            return [{"id": 8}]
        return []

    def execute(self, sql, parameters=()):
        self.executed.append((sql, parameters))

    def integrity_check(self):
        return "ok"

    def foreign_key_check(self):
        return []


class Provider:
    def __init__(self, failing=None):
        self.failing = set(failing or [])
        self.fetch_calls = []
        self.collect_calls = []

    def fetch_html(self, code):
        self.fetch_calls.append(code)
        if code in self.failing:
            raise RuntimeError("falha simulada")
        return SimpleNamespace(text="ok")

    def collect(self, code):
        self.collect_calls.append(code)
        if code in self.failing:
            raise RuntimeError("falha simulada")
        return SimpleNamespace(
            observations_created=1,
            observations_reused=2,
            conflicts_created=0,
        )


class Backup:
    def __init__(self):
        self.calls = 0

    def create_backup(self):
        self.calls += 1
        return SimpleNamespace(path=Path("backup.sqlite3"))


class Export:
    def __init__(self):
        self.calls = []

    def export(self, file_format, output_path, **kwargs):
        self.calls.append((file_format, Path(output_path), kwargs))
        return {"path": Path(output_path)}


def config(**overrides):
    data = {
        "asset_codes": ["PETR27", "CEPEA1"],
        "request_interval_seconds": 0,
        "max_attempts": 1,
        "export_dir": "exports",
    }
    data.update(overrides)
    return CollectionConfig.from_dict(data)


def build_service(provider=None):
    db = Database()
    backup = Backup()
    export = Export()
    sleeps = []
    service = CollectionAutomationService(
        db,
        provider_factory=lambda cfg: provider or Provider(),
        backup_service=backup,
        export_service=export,
        sleep_function=lambda seconds: sleeps.append(seconds),
        now_function=lambda: datetime(2026, 9, 14, 12, tzinfo=timezone.utc),
    )
    return service, db, backup, export, sleeps


def test_dry_run_does_not_backup_export_or_mutate():
    provider = Provider()
    service, db, backup, export, _ = build_service(provider)
    result = service.run(config(), commit=False)
    assert result.successes == 2
    assert provider.fetch_calls == ["PETR27", "CEPEA1"]
    assert provider.collect_calls == []
    assert backup.calls == 0
    assert export.calls == []
    assert db.executed == []


def test_commit_closes_stale_records_and_creates_backup():
    service, db, backup, _, _ = build_service()
    result = service.run(config(), commit=True)
    assert result.stale_runs_closed == 1
    assert result.stale_raw_records_closed == 1
    assert backup.calls == 1
    assert len(db.executed) == 2


def test_commit_exports_requested_files():
    service, _, _, export, _ = build_service()
    result = service.run(config(), commit=True)
    assert len(result.exports) == 3
    assert [call[0] for call in export.calls] == ["csv", "json", "csv"]
    assert export.calls[2][2]["history"] is True


def test_failure_does_not_stop_other_assets():
    provider = Provider(failing={"CEPEA1"})
    service, _, _, _, _ = build_service(provider)
    result = service.run(config(), commit=True)
    assert result.processed == 2
    assert result.successes == 1
    assert result.failures == 1


def test_interval_is_applied_between_assets():
    service, _, _, _, sleeps = build_service()
    service.run(config(request_interval_seconds=1.5), commit=False)
    assert sleeps == [1.5]


def test_backup_can_be_disabled():
    service, _, backup, _, _ = build_service()
    result = service.run(config(create_backup=False), commit=True)
    assert backup.calls == 0
    assert result.backup_path is None
