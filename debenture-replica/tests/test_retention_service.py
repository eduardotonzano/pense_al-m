import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from debenture_search.services.retention_service import RetentionService


NOW = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)


def config():
    return {
        "backup_days": 30,
        "log_days": 90,
        "report_days": 90,
        "export_days": 90,
        "temporary_days": 7,
        "code_backup_days": 30,
        "keep_latest_backup": True,
        "keep_latest_report": True,
        "protected_files": (
            "exports/debentures.csv",
            "exports/debentures.json",
            "exports/debenture_history.csv",
            "logs/collection_last.json",
            "logs/debenture_collection.log",
            "logs/debenture_collection.jsonl",
        ),
    }


def create_file(root, relative, age_days, content="x"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    timestamp = (NOW - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path.resolve()


def service(tmp_path):
    return RetentionService(tmp_path, now_function=lambda: NOW)


def test_old_backup_is_eligible(tmp_path):
    old = create_file(tmp_path, "data/backups/old.db", 40)
    create_file(tmp_path, "data/backups/new.db", 1)
    items = service(tmp_path).plan(config())
    target = next(item for item in items if item.path == old)
    assert target.eligible is True


def test_new_file_is_preserved(tmp_path):
    recent = create_file(tmp_path, "data/backups/recent.db", 1)
    item = next(item for item in service(tmp_path).plan(config()) if item.path == recent)
    assert item.eligible is False


def test_latest_backup_is_preserved_even_if_old(tmp_path):
    latest = create_file(tmp_path, "data/backups/latest.db", 31)
    create_file(tmp_path, "data/backups/older.db", 40)
    item = next(item for item in service(tmp_path).plan(config()) if item.path == latest)
    assert item.protected is True
    assert item.eligible is False


def test_protected_export_is_never_removed(tmp_path):
    protected = create_file(tmp_path, "exports/debentures.csv", 200)
    item = next(item for item in service(tmp_path).plan(config()) if item.path == protected)
    assert item.protected is True
    assert item.eligible is False


def test_dry_run_does_not_delete(tmp_path):
    old = create_file(tmp_path, "runtime/old.tmp", 10)
    result = service(tmp_path).run(config(), commit=False)
    assert result.eligible == 1
    assert result.removed == 0
    assert old.exists()


def test_commit_deletes_only_eligible_file(tmp_path):
    old = create_file(tmp_path, "runtime/old.tmp", 10)
    recent = create_file(tmp_path, "runtime/new.tmp", 1)
    result = service(tmp_path).run(config(), commit=True)
    assert result.removed == 1
    assert not old.exists()
    assert recent.exists()


def test_calculates_removed_bytes(tmp_path):
    create_file(tmp_path, "runtime/old.tmp", 10, content="12345")
    result = service(tmp_path).run(config(), commit=True)
    assert result.bytes_removed == 5


def test_missing_directories_are_safe(tmp_path):
    result = service(tmp_path).run(config(), commit=False)
    assert result.scanned == 0
    assert result.failed == 0


def test_symbolic_link_is_ignored(
    tmp_path,
    monkeypatch,
):
    candidate = create_file(
        tmp_path,
        "runtime/linked.tmp",
        30,
    )

    original_is_symlink = Path.is_symlink

    def simulated_is_symlink(path):
        if path.resolve() == candidate:
            return True

        return original_is_symlink(path)

    monkeypatch.setattr(
        Path,
        "is_symlink",
        simulated_is_symlink,
    )

    result = service(tmp_path).run(
        config(),
        commit=True,
    )

    assert result.scanned == 0
    assert result.removed == 0
    assert candidate.exists()


def test_rejects_path_outside_project(tmp_path):
    with pytest.raises(ValueError, match="fora do projeto"):
        service(tmp_path)._safe_path(tmp_path.parent / "outside.txt")


def test_loads_valid_configuration(tmp_path):
    path = tmp_path / "retention.json"
    data = dict(config())
    data["protected_files"] = list(data["protected_files"])
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = RetentionService.load_config(path)
    assert loaded["backup_days"] == 30
    assert loaded["keep_latest_backup"] is True


def test_rejects_invalid_configuration(tmp_path):
    path = tmp_path / "retention.json"
    path.write_text('{"backup_days": 0}', encoding="utf-8")
    with pytest.raises(ValueError):
        RetentionService.load_config(path)


def test_results_are_sorted(tmp_path):
    create_file(tmp_path, "runtime/z.tmp", 10)
    create_file(tmp_path, "runtime/a.tmp", 10)
    items = service(tmp_path).plan(config())
    paths = [str(item.path) for item in items]
    assert paths == sorted(paths, key=str.casefold)
