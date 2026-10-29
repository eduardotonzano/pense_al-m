from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import (
    MIGRATIONS_DIR,
    apply_pending,
    pending_migrations,
    read_applied_versions,
)
from credit_assets.services.download_queue_service import (
    BLOCKED,
    PERMANENT,
    TEMPORARY,
    VALIDATION,
    DownloadOutcome,
    DownloadQueueWorker,
    QueueConfig,
    RateLimiter,
    classify_error,
    enqueue_documents,
    make_service_executor,
    queue_status,
)


class FakeClock:
    def __init__(self):
        self.current = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        self.slept: list[float] = []

    def now(self):
        return self.current

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.current += timedelta(seconds=seconds)


def _config(**overrides) -> QueueConfig:
    base = dict(min_interval_seconds=0, max_requests_per_minute=1000,
                min_free_bytes_floor=0, min_free_fraction=0.0)
    base.update(overrides)
    return QueueConfig(**base)


def _free_disk():
    return 100 * 10**9, 200 * 10**9


@pytest.fixture
def connection(tmp_path):
    conn = connect(tmp_path / "cri_cra.db")
    initialize_database(conn)
    conn.execute("INSERT INTO executions (run_id, started_at, status) VALUES ('r1', 'now', 'success')")
    conn.commit()
    return conn


def _seed(conn, count=3, category="Informe Mensal", names=None, cetip="CRA1", isin="BRX1"):
    cur = conn.execute(
        """INSERT INTO assets (codigo_cetip, isin, tipo_ativo, securitizadora, cnpj_securitizadora,
               emissao, serie, created_at, updated_at)
           VALUES (?, ?, 'CRA', 'Eco', '1', '1', '1', 'now', 'now')""",
        (cetip, isin),
    )
    asset_id = cur.lastrowid
    ids = []
    for i in range(count):
        name = (names or [])[i] if names else f"Documento {i}"
        ids.append(conn.execute(
            """INSERT INTO documents (source_document_id, asset_id, category, document_name,
                   source, source_url, run_id)
               VALUES (?, ?, ?, ?, 'Fundos.NET', 'https://x/y', 'r1')""",
            (f"{cetip}-{i}", asset_id, category, name),
        ).lastrowid)
    conn.commit()
    return ids


def _run(conn, outcomes, config=None, clock=None, **kwargs):
    clock = clock or FakeClock()
    calls = []

    def executor(document):
        calls.append(document["source_document_id"])
        outcome = outcomes[len(calls) - 1] if len(calls) <= len(outcomes) else outcomes[-1]
        return outcome

    worker = DownloadQueueWorker(
        conn, executor, config or _config(), clock=clock, disk_usage=_free_disk,
        worker_id="w1", **kwargs,
    )
    return worker.run(), calls, clock


OK = DownloadOutcome(ok=True, bytes_downloaded=100)


def test_classify_error_separates_temporary_from_permanent():
    assert classify_error(403, None)[0] == BLOCKED
    assert classify_error(429, None) == (TEMPORARY, "http_429")
    assert classify_error(503, None)[0] == TEMPORARY
    assert classify_error(404, None) == (PERMANENT, "http_404")
    assert classify_error(None, "TimeoutError: esgotou")[0] == TEMPORARY
    assert classify_error(None, "a descrição da linha não corresponde ao ISIN solicitado")[0] == VALIDATION
    assert classify_error(None, "size_limit_exceeded")[0] == VALIDATION
    assert classify_error(None, "empty_file")[0] == VALIDATION
    assert classify_error(None, "link oficial Download do Documento ausente na linha")[0] == PERMANENT
    assert classify_error(None, "algo nunca visto")[0] == TEMPORARY


def test_enqueue_dry_run_does_not_write_and_excludes_prospectus(connection):
    _seed(connection, 3, names=["Informe jan", "Prospecto Definitivo", "Suplemento ao prospecto"])
    report = enqueue_documents(connection, _config(), dry_run=True)
    assert report["to_enqueue"] == 1 and report["enqueued"] == 0
    assert connection.execute("SELECT COUNT(*) FROM download_queue").fetchone()[0] == 0


def test_enqueue_is_idempotent_and_can_requeue_after_completion(connection):
    ids = _seed(connection, 2)
    assert enqueue_documents(connection, _config(), dry_run=False)["enqueued"] == 2
    assert enqueue_documents(connection, _config(), dry_run=False)["enqueued"] == 0
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO download_queue (document_id, enqueued_at) VALUES (?, 'now')", (ids[0],)
        )
    connection.execute("UPDATE download_queue SET status = 'done' WHERE document_id = ?", (ids[0],))
    connection.execute(
        "INSERT INTO download_queue (document_id, enqueued_at) VALUES (?, 'now')", (ids[0],)
    )
    connection.commit()


def test_run_processes_in_priority_order_and_records_batch(connection):
    _seed(connection, 2, category="Outro")
    _seed(connection, 2, cetip="CRA2", isin="BRX2")
    enqueue_documents(connection, _config(), dry_run=False)
    connection.execute("UPDATE download_queue SET priority = 5 WHERE document_id IN (3, 4)")
    connection.commit()
    report, calls, _ = _run(connection, [OK])
    assert calls[:2] == ["CRA2-0", "CRA2-1"]
    assert report["status"] == "finished" and report["processed"] == 4 and report["bytes"] == 400
    assert queue_status(connection)["items"] == {"done": 4}
    batch = connection.execute("SELECT * FROM download_batches").fetchone()
    assert batch["status"] == "finished" and batch["items_processed"] == 4


def test_second_run_does_not_download_again(connection):
    _seed(connection, 2)
    enqueue_documents(connection, _config(), dry_run=False)
    _run(connection, [OK])
    report, calls, _ = _run(connection, [OK])
    assert calls == [] and report["processed"] == 0


def test_temporary_error_retries_with_backoff_then_fails(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(), dry_run=False)
    timeout = DownloadOutcome(ok=False, error="TimeoutError: x")
    report, calls, clock = _run(connection, [timeout])
    assert len(calls) == 3
    assert clock.slept == [60, 300]
    row = connection.execute("SELECT * FROM download_queue").fetchone()
    assert row["status"] == "failed" and row["attempts"] == 3
    assert row["error_class"] == TEMPORARY


def test_permanent_error_does_not_retry(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(), dry_run=False)
    report, calls, _ = _run(connection, [DownloadOutcome(ok=False, http_status=404, error="nao existe")])
    assert len(calls) == 1
    row = connection.execute("SELECT * FROM download_queue").fetchone()
    assert (row["status"], row["error_class"], row["last_http_status"]) == ("failed", PERMANENT, 404)


def test_http_429_honors_retry_after(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(), dry_run=False)
    outcomes = [DownloadOutcome(ok=False, http_status=429, retry_after_seconds=900), OK]
    _, calls, clock = _run(connection, outcomes)
    assert len(calls) == 2 and clock.slept == [900]


def test_http_403_stops_batch_immediately(connection):
    _seed(connection, 5)
    enqueue_documents(connection, _config(), dry_run=False)
    report, calls, _ = _run(connection, [DownloadOutcome(ok=False, http_status=403)])
    assert len(calls) == 1 and report["status"] == "stopped"
    assert "403" in report["stop_reason"]
    assert queue_status(connection)["items"]["pending"] == 4


def test_stops_after_five_consecutive_failures(connection):
    _seed(connection, 10)
    enqueue_documents(connection, _config(), dry_run=False)
    bad = DownloadOutcome(ok=False, http_status=404, error="x")
    report, calls, _ = _run(connection, [bad])
    assert len(calls) == 5 and "5 falhas consecutivas" in report["stop_reason"]


def test_failure_rate_needs_twenty_attempts(connection):
    _seed(connection, 30)
    enqueue_documents(connection, _config(), dry_run=False)
    bad = DownloadOutcome(ok=False, http_status=404, error="x")
    # 1 falha a cada 4 downloads: nunca 5 seguidas, taxa 25% >= 20%
    pattern = ([OK, OK, OK, bad] * 10)
    report, calls, _ = _run(connection, pattern)
    assert len(calls) == 20 and "taxa de falha 5/20" in report["stop_reason"]


def test_failure_rate_below_threshold_keeps_going(connection):
    _seed(connection, 25)
    enqueue_documents(connection, _config(), dry_run=False)
    bad = DownloadOutcome(ok=False, http_status=404, error="x")
    pattern = ([OK] * 9 + [bad]) * 3
    report, calls, _ = _run(connection, pattern)
    assert len(calls) == 25 and report["status"] == "finished"


def test_item_limit_duration_and_bytes(connection):
    _seed(connection, 10)
    enqueue_documents(connection, _config(), dry_run=False)
    report, calls, _ = _run(connection, [OK], config=_config(max_items=3))
    assert len(calls) == 3 and "3 itens" in report["stop_reason"]
    report, calls, _ = _run(connection, [OK], config=_config(max_total_bytes=250))
    assert len(calls) == 3 and "bytes" in report["stop_reason"]
    clock = FakeClock()
    config = _config(max_duration_seconds=10, min_interval_seconds=6)
    report, calls, _ = _run(connection, [OK], config=config, clock=clock)
    assert report["status"] == "stopped" and "duração" in report["stop_reason"]


def test_stops_when_disk_is_low(connection):
    _seed(connection, 2)
    enqueue_documents(connection, _config(), dry_run=False)
    worker = DownloadQueueWorker(
        connection, lambda d: OK, QueueConfig(), clock=FakeClock(),
        disk_usage=lambda: (5 * 10**9, 100 * 10**9),
    )
    report = worker.run()
    assert report["status"] == "stopped" and "espaço livre" in report["stop_reason"]
    assert report["processed"] == 0


def test_required_free_space_is_max_of_floor_and_ten_percent(connection):
    worker = DownloadQueueWorker(connection, lambda d: OK, QueueConfig(),
                                 disk_usage=lambda: (50 * 10**9, 1000 * 10**9))
    ok, required = worker._disk_ok()
    assert required == 100 * 10**9 and not ok
    worker = DownloadQueueWorker(connection, lambda d: OK, QueueConfig(),
                                 disk_usage=lambda: (50 * 10**9, 100 * 10**9))
    ok, required = worker._disk_ok()
    assert required == 10 * 10**9 and ok


def test_rate_limiter_interval_and_per_minute():
    clock = FakeClock()
    limiter = RateLimiter(clock, min_interval=2, per_minute=3)
    for _ in range(3):
        limiter.wait()
    assert clock.slept == [2, 2]
    limiter.wait()  # a 4ª precisa esperar a janela de 60 s
    assert clock.current - datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc) >= timedelta(seconds=60)


def test_second_worker_refused_while_first_is_alive(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(), dry_run=False)
    clock = FakeClock()
    connection.execute(
        """INSERT INTO download_batches (worker_id, params_json, started_at, heartbeat_at)
           VALUES ('outro', '{}', ?, ?)""",
        (clock.now().isoformat(), (clock.now() - timedelta(minutes=5)).isoformat()),
    )
    connection.commit()
    worker = DownloadQueueWorker(connection, lambda d: OK, _config(), clock=clock,
                                 disk_usage=_free_disk)
    with pytest.raises(RuntimeError, match="em andamento"):
        worker.run()


def test_database_blocks_two_running_batches(connection):
    insert = """INSERT INTO download_batches (worker_id, params_json, started_at, heartbeat_at)
                VALUES (?, '{}', 'a', 'a')"""
    connection.execute(insert, ("w1",))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("w2",))


def test_abandoned_batch_is_recovered_only_after_deadline(connection):
    ids = _seed(connection, 2)
    enqueue_documents(connection, _config(), dry_run=False)
    clock = FakeClock()
    old = (clock.now() - timedelta(hours=2)).isoformat()
    connection.execute(
        """INSERT INTO download_batches (worker_id, params_json, started_at, heartbeat_at)
           VALUES ('morto', '{}', ?, ?)""", (old, old),
    )
    connection.execute(
        "UPDATE download_queue SET status = 'running', batch_id = 1, worker_id = 'morto' "
        "WHERE document_id = ?", (ids[0],),
    )
    connection.commit()
    worker = DownloadQueueWorker(connection, lambda d: OK, _config(), clock=clock,
                                 disk_usage=_free_disk, worker_id="novo")
    report = worker.run()
    assert report["recovered_batches"] == [1] and report["processed"] == 2
    assert connection.execute("SELECT status FROM download_batches WHERE batch_id = 1").fetchone()[0] == "abandoned"
    assert queue_status(connection)["items"] == {"done": 2}


def test_claim_is_exclusive(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(), dry_run=False)
    first = DownloadQueueWorker(connection, lambda d: OK, _config(), disk_usage=_free_disk)
    first._start_batch()
    assert first._claim() is not None
    assert first._claim() is None


def test_executor_exception_becomes_temporary_failure(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(max_attempts=1), dry_run=False)

    def boom(document):
        raise RuntimeError("caiu")

    worker = DownloadQueueWorker(connection, boom, _config(max_attempts=1), clock=FakeClock(),
                                 disk_usage=_free_disk)
    report = worker.run()
    assert report["failed"] == 1
    assert connection.execute("SELECT status FROM download_queue").fetchone()[0] == "failed"


def test_interrupted_run_returns_running_items_to_pending(connection):
    _seed(connection, 2)
    enqueue_documents(connection, _config(), dry_run=False)

    def interrupt(document):
        raise KeyboardInterrupt

    worker = DownloadQueueWorker(connection, interrupt, _config(), clock=FakeClock(),
                                 disk_usage=_free_disk)
    with pytest.raises(KeyboardInterrupt):
        worker.run()
    assert queue_status(connection)["items"] == {"pending": 2}
    assert connection.execute("SELECT status FROM download_batches").fetchone()[0] == "stopped"


def test_failure_never_creates_document_version(connection):
    _seed(connection, 1)
    enqueue_documents(connection, _config(), dry_run=False)
    _run(connection, [DownloadOutcome(ok=False, http_status=404)])
    assert connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0


def test_only_filter_limits_assets(connection):
    _seed(connection, 2)
    _seed(connection, 2, cetip="CRA2", isin="BRX2")
    enqueue_documents(connection, _config(), dry_run=False)
    _, calls, _ = _run(connection, [OK], only_cetips=["CRA2"])
    assert calls == ["CRA2-0", "CRA2-1"]


def test_migration_003_on_existing_database_is_idempotent(tmp_path):
    only_old = tmp_path / "m"
    only_old.mkdir()
    for name in ("001_document_catalog.sql", "002_asset_series.sql"):
        (only_old / name).write_text((MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    conn = connect(tmp_path / "old.db")
    initialize_database(conn, migrations_dir=only_old)
    assert [m.version for m in pending_migrations(conn, MIGRATIONS_DIR)] == [3]
    apply_pending(conn, pending_migrations(conn, MIGRATIONS_DIR))
    assert read_applied_versions(conn)[3] == "download_queue"
    assert apply_pending(conn, pending_migrations(conn, MIGRATIONS_DIR)) == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


class FakeService:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def run(self, cetip, isin, **kwargs):
        self.calls.append((cetip, isin, kwargs))
        return self.report


def _document(connection):
    _seed(connection, 1, category="Outro")
    return {"codigo_cetip": "CRA1", "isin": "BRX1", "category": "Outro",
            "source_document_id": "CRA1-0", "document_pk": 1}


def test_service_executor_success_and_unchanged(connection):
    document = _document(connection)
    service = FakeService({"failed": 0, "errors": [],
                           "files_downloaded": [{"result": "unchanged", "size_bytes": 10}]})
    outcome = make_service_executor(service, connection)(document)
    assert outcome.ok and outcome.already_current and outcome.bytes_downloaded == 10
    cetip, isin, kwargs = service.calls[0]
    assert kwargs["source_document_ids"] == ["CRA1-0"] and kwargs["allow_other"] is True
    assert kwargs["max_documents"] == 1


def test_service_executor_failure_uses_attempt_http_status(connection):
    document = _document(connection)
    connection.execute(
        """INSERT INTO collection_attempts (run_id, asset_id, document_id, source, started_at,
               status, http_status, error_message) VALUES ('r1', 1, 1, 'Fundos.NET', 'now', 'failed', 429, 'x')"""
    )
    connection.commit()
    service = FakeService({"failed": 1, "files_downloaded": [],
                           "errors": [{"document_id": 1, "error": "size_limit_exceeded"}]})
    outcome = make_service_executor(service, connection)(document)
    assert not outcome.ok and outcome.http_status == 429 and outcome.error == "size_limit_exceeded"
