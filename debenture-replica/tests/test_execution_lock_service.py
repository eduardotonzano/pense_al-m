import json
from datetime import datetime, timedelta, timezone

import pytest

from debenture_search.services.execution_lock_service import (
    ExecutionLockError,
    ExecutionLockService,
)


NOW = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)


def service(tmp_path, **kwargs):
    defaults = {
        "lock_path": tmp_path / "runtime" / "collection.lock",
        "pid": 1234,
        "hostname": "TEST-PC",
        "username": "tester",
        "command": "run_collection.py --commit",
        "now_function": lambda: NOW,
        "process_checker": lambda pid: True,
    }
    defaults.update(kwargs)
    return ExecutionLockService(**defaults)


def write_lock(path, **overrides):
    data = {
        "pid": 9999,
        "hostname": "TEST-PC",
        "username": "other",
        "started_at": NOW.isoformat(),
        "command": "other command",
    }
    data.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def test_acquires_lock_and_creates_parent(tmp_path):
    lock = service(tmp_path)
    data = lock.acquire()
    assert lock.lock_path.exists()
    assert data["pid"] == 1234
    assert data["hostname"] == "TEST-PC"
    lock.release()


def test_file_contains_required_metadata(tmp_path):
    lock = service(tmp_path)
    lock.acquire()
    data = json.loads(lock.lock_path.read_text(encoding="utf-8"))
    assert data == {
        "pid": 1234,
        "hostname": "TEST-PC",
        "username": "tester",
        "started_at": NOW.isoformat(),
        "command": "run_collection.py --commit",
    }
    lock.release()


def test_rejects_second_active_lock(tmp_path):
    first = service(tmp_path)
    first.acquire()
    second = service(tmp_path, pid=4321)
    with pytest.raises(ExecutionLockError, match="Ja existe uma coleta"):
        second.acquire()
    first.release()


def test_context_manager_releases_lock(tmp_path):
    lock = service(tmp_path)
    with lock:
        assert lock.lock_path.exists()
    assert not lock.lock_path.exists()


def test_context_manager_releases_after_exception(tmp_path):
    lock = service(tmp_path)
    with pytest.raises(ValueError, match="falha"):
        with lock:
            raise ValueError("falha")
    assert not lock.lock_path.exists()


def test_detects_dead_process_as_stale(tmp_path):
    lock = service(tmp_path, process_checker=lambda pid: False)
    write_lock(lock.lock_path)
    assert lock.is_stale() is True


def test_detects_expired_lock_as_stale(tmp_path):
    lock = service(tmp_path, stale_minutes=60)
    write_lock(
        lock.lock_path,
        hostname="OTHER-PC",
        started_at=(NOW - timedelta(hours=2)).isoformat(),
    )
    assert lock.is_stale() is True


def test_recovers_stale_lock(tmp_path):
    lock = service(tmp_path, process_checker=lambda pid: False)
    write_lock(lock.lock_path)
    data = lock.acquire(recover_stale=True)
    assert data["pid"] == 1234
    lock.release()


def test_refuses_to_break_active_lock(tmp_path):
    lock = service(tmp_path, process_checker=lambda pid: True)
    write_lock(lock.lock_path)
    with pytest.raises(ExecutionLockError, match="ainda pode estar ativa"):
        lock.break_stale_lock()


def test_rejects_invalid_json(tmp_path):
    lock = service(tmp_path)
    lock.lock_path.parent.mkdir(parents=True)
    lock.lock_path.write_text("{", encoding="utf-8")
    with pytest.raises(ExecutionLockError, match="conteudo invalido"):
        lock.acquire()


def test_rejects_incomplete_lock(tmp_path):
    lock = service(tmp_path)
    lock.lock_path.parent.mkdir(parents=True)
    lock.lock_path.write_text('{"pid": 1}', encoding="utf-8")
    with pytest.raises(ExecutionLockError, match="incompleto"):
        lock.read_lock()


def test_does_not_release_foreign_lock(tmp_path):
    lock = service(tmp_path)
    write_lock(lock.lock_path, pid=9999)
    with pytest.raises(ExecutionLockError, match="outro processo"):
        lock.release()
    assert lock.lock_path.exists()


def test_release_missing_lock_is_safe(tmp_path):
    lock = service(tmp_path)
    assert lock.release() is False
