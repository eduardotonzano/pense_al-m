"""Fila de download em lotes (migration 003).

Um worker por vez, um download por vez. A fila nunca cria versão de documento:
quem baixa e valida é o executor (``DocumentDownloadService``), que já recusa
ISIN divergente, arquivo acima do limite e documento inválido.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import time
import unicodedata
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol


TEMPORARY = "temporary"
PERMANENT = "permanent"
VALIDATION = "validation"
BLOCKED = "blocked"

DEFAULT_CATEGORIES = (
    "Informe Mensal",
    "Termo de Securitização",
    "Aditamento",
    "Relatório Agente Fiduciário",
    "Ata/Edital",
    "Fato Relevante",
    "Anúncio de Encerramento",
    "Outro",
)
CATEGORY_PRIORITY = {
    "Informe Mensal": 10,
    "Termo de Securitização": 20,
    "Aditamento": 30,
    "Relatório Agente Fiduciário": 40,
    "Ata/Edital": 50,
    "Fato Relevante": 60,
    "Outro": 70,
    "Anúncio de Encerramento": 80,
}
DEFAULT_EXCLUDED_NAME_TERMS = ("prospecto", "suplemento")
GIGABYTE = 1_000_000_000

# Erros do serviço de download que nunca melhoram com nova tentativa.
VALIDATION_ERRORS = (
    "size_limit_exceeded",
    "empty_file",
    "html_instead_of_file",
    "invalid_format",
    "não corresponde ao isin",
    "isin",
)
PERMANENT_MARKERS = (
    "link oficial download do documento ausente",
    "documento não apareceu na grade",
    "não catalogado",
    "categoria fora da amostra",
    "sem url válida",
)
TEMPORARY_MARKERS = ("timeout", "timed out", "connection", "net::err", "temporar")


@dataclass(frozen=True)
class QueueConfig:
    min_interval_seconds: float = 2.0
    max_requests_per_minute: int = 20
    max_attempts: int = 3
    retry_delays_seconds: tuple[int, ...] = (60, 300, 1800)
    max_consecutive_failures: int = 5
    failure_rate_threshold: float = 0.20
    failure_rate_min_attempts: int = 20
    max_items: int | None = None
    max_duration_seconds: float | None = None
    max_total_bytes: int | None = None
    min_free_bytes_floor: int = 10 * GIGABYTE
    min_free_fraction: float = 0.10
    abandon_after_seconds: int = 1800
    chunk_size: int = 1  # documentos do mesmo ativo por sessão de navegador
    categories: tuple[str, ...] = DEFAULT_CATEGORIES
    excluded_name_terms: tuple[str, ...] = DEFAULT_EXCLUDED_NAME_TERMS

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0 or self.max_requests_per_minute < 1:
            raise ValueError("limites de taxa inválidos")
        if not 1 <= self.chunk_size <= 20:
            raise ValueError("chunk_size deve estar entre 1 e 20")
        if self.max_attempts < 1 or len(self.retry_delays_seconds) < 1:
            raise ValueError("tentativas inválidas")
        if not 0 < self.failure_rate_threshold <= 1:
            raise ValueError("taxa de falha deve estar entre 0 e 1")


@dataclass(frozen=True)
class DownloadOutcome:
    """Resultado de um download tentado pelo executor."""

    ok: bool
    http_status: int | None = None
    error: str | None = None
    bytes_downloaded: int = 0
    retry_after_seconds: float | None = None
    already_current: bool = False


class Executor(Protocol):
    def __call__(self, document: dict[str, Any]) -> DownloadOutcome: ...


class Clock(Protocol):
    def now(self) -> datetime: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def classify_error(http_status: int | None, error: str | None) -> tuple[str, str]:
    """Devolve (classe, tipo). Erro desconhecido é temporário: o limite de
    tentativas o transforma em falha definitiva."""

    text = _fold(error or "")
    if http_status == 403:
        return BLOCKED, "http_403"
    if http_status == 429:
        return TEMPORARY, "http_429"
    if http_status is not None and 500 <= http_status <= 599:
        return TEMPORARY, f"http_{http_status}"
    if http_status == 404:
        return PERMANENT, "http_404"
    if http_status is not None and 400 <= http_status <= 499:
        return PERMANENT, f"http_{http_status}"
    if "isin" in text and ("corresponde" in text or "divergente" in text):
        return VALIDATION, "isin_divergente"
    for marker in VALIDATION_ERRORS[:4]:
        if marker in text:
            return VALIDATION, marker
    for marker in PERMANENT_MARKERS:
        if _fold(marker) in text:
            return PERMANENT, "documento_indisponivel"
    if any(marker in text for marker in TEMPORARY_MARKERS):
        return TEMPORARY, "timeout_ou_rede"
    return TEMPORARY, "desconhecido"


class RateLimiter:
    """Intervalo mínimo entre requisições e teto por minuto (janela móvel)."""

    def __init__(self, clock: Clock, min_interval: float, per_minute: int):
        self.clock = clock
        self.min_interval = min_interval
        self.per_minute = per_minute
        self._stamps: deque[datetime] = deque()

    def wait(self) -> float:
        waited = 0.0
        while True:
            now = self.clock.now()
            while self._stamps and (now - self._stamps[0]).total_seconds() >= 60:
                self._stamps.popleft()
            delay = 0.0
            if self._stamps:
                delay = max(
                    delay,
                    self.min_interval - (now - self._stamps[-1]).total_seconds(),
                )
            if len(self._stamps) >= self.per_minute:
                delay = max(
                    delay, 60 - (now - self._stamps[0]).total_seconds() + 0.001
                )
            if delay <= 0:
                self._stamps.append(now)
                return waited
            self.clock.sleep(delay)
            waited += delay


# ---------------------------------------------------------------- enfileirar

def candidate_documents(
    connection: sqlite3.Connection,
    config: QueueConfig,
    cetips: Iterable[str] | None = None,
    include_failed: bool = False,
) -> list[sqlite3.Row]:
    statuses = ("pending", "failed") if include_failed else ("pending",)
    params: list[Any] = [*statuses]
    sql = f"""
        SELECT d.document_pk, d.source_document_id, d.category, d.document_name,
               d.source_url, a.codigo_cetip, a.isin, a.asset_id
        FROM documents d
        JOIN assets a ON a.asset_id = d.asset_id
        WHERE d.source = 'Fundos.NET'
          AND d.download_status IN ({','.join('?' * len(statuses))})
          AND NOT EXISTS (
              SELECT 1 FROM document_versions v
              WHERE v.document_id = d.document_pk AND v.is_current = 1
                AND v.validation_status = 'valid')
          AND NOT EXISTS (
              SELECT 1 FROM download_queue q
              WHERE q.document_id = d.document_pk
                AND q.status IN ('pending', 'running'))
    """
    cetip_list = [c.strip() for c in cetips or [] if c.strip()]
    if cetip_list:
        sql += f" AND a.codigo_cetip IN ({','.join('?' * len(cetip_list))})"
        params.extend(cetip_list)
    sql += " ORDER BY a.codigo_cetip, d.document_pk"
    rows = connection.execute(sql, params).fetchall()
    terms = [_fold(t) for t in config.excluded_name_terms]
    return [
        row for row in rows
        if row["category"] in config.categories
        and not any(term in _fold(row["document_name"]) for term in terms)
    ]


def enqueue_documents(
    connection: sqlite3.Connection,
    config: QueueConfig,
    cetips: Iterable[str] | None = None,
    include_failed: bool = False,
    dry_run: bool = True,
    clock: Clock | None = None,
) -> dict[str, Any]:
    clock = clock or SystemClock()
    rows = candidate_documents(connection, config, cetips, include_failed)
    by_asset: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for row in rows:
        by_asset[row["codigo_cetip"]] = by_asset.get(row["codigo_cetip"], 0) + 1
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
    report = {
        "dry_run": dry_run,
        "to_enqueue": len(rows),
        "by_asset": by_asset,
        "by_category": by_category,
        "enqueued": 0,
    }
    if dry_run or not rows:
        return report
    now = _iso(clock.now())
    try:
        connection.execute("BEGIN IMMEDIATE")
        for row in rows:
            connection.execute(
                """INSERT INTO download_queue
                   (document_id, priority, max_attempts, enqueued_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    row["document_pk"],
                    CATEGORY_PRIORITY.get(row["category"], 100),
                    config.max_attempts,
                    now,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    report["enqueued"] = len(rows)
    return report


def queue_status(connection: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        row["status"]: row["total"]
        for row in connection.execute(
            "SELECT status, COUNT(*) AS total FROM download_queue GROUP BY status"
        )
    }
    batch = connection.execute(
        "SELECT * FROM download_batches ORDER BY batch_id DESC LIMIT 1"
    ).fetchone()
    return {"items": counts, "last_batch": dict(batch) if batch else None}


# -------------------------------------------------------------------- worker

class DownloadQueueWorker:
    def __init__(
        self,
        connection: sqlite3.Connection,
        executor: Executor,
        config: QueueConfig | None = None,
        worker_id: str | None = None,
        clock: Clock | None = None,
        disk_usage: Callable[[], tuple[int, int]] | None = None,
        only_cetips: Iterable[str] | None = None,
    ):
        self.connection = connection
        self.executor = executor
        self.config = config or QueueConfig()
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.clock = clock or SystemClock()
        self.disk_usage = disk_usage or self._default_disk_usage
        self.only_cetips = [c for c in (only_cetips or []) if c]
        self.limiter = RateLimiter(
            self.clock, self.config.min_interval_seconds,
            self.config.max_requests_per_minute,
        )
        self.batch_id: int | None = None

    @staticmethod
    def _default_disk_usage() -> tuple[int, int]:
        usage = shutil.disk_usage(Path.cwd())
        return usage.free, usage.total

    # -- lote ---------------------------------------------------------------

    def _recover_abandoned(self) -> list[int]:
        """Só reabre um lote 'running' cujo batimento passou do prazo. Se o
        batimento é recente, o outro worker é considerado vivo e este não inicia."""

        now = self.clock.now()
        recovered = []
        for batch in self.connection.execute(
            "SELECT batch_id, heartbeat_at FROM download_batches WHERE status = 'running'"
        ).fetchall():
            idle = (now - _parse(batch["heartbeat_at"])).total_seconds()
            if idle <= self.config.abandon_after_seconds:
                raise RuntimeError(
                    f"já existe o lote {batch['batch_id']} em andamento "
                    f"(último batimento há {int(idle)} s)"
                )
            self.connection.execute(
                """UPDATE download_batches SET status = 'abandoned', finished_at = ?,
                       stop_reason = 'abandonado: sem batimento no prazo'
                   WHERE batch_id = ?""",
                (_iso(now), batch["batch_id"]),
            )
            self.connection.execute(
                """UPDATE download_queue SET status = 'pending', worker_id = NULL,
                       next_attempt_at = NULL
                   WHERE batch_id = ? AND status = 'running'""",
                (batch["batch_id"],),
            )
            recovered.append(batch["batch_id"])
        return recovered

    def _start_batch(self) -> list[int]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            recovered = self._recover_abandoned()
            now = _iso(self.clock.now())
            params = asdict(self.config)
            params["only_cetips"] = self.only_cetips
            cursor = self.connection.execute(
                """INSERT INTO download_batches
                   (worker_id, params_json, started_at, heartbeat_at)
                   VALUES (?, ?, ?, ?)""",
                (self.worker_id, json.dumps(params, default=list), now, now),
            )
            self.batch_id = cursor.lastrowid
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return recovered

    def _heartbeat(self) -> None:
        now = _iso(self.clock.now())
        self.connection.execute(
            "UPDATE download_batches SET heartbeat_at = ? WHERE batch_id = ?",
            (now, self.batch_id),
        )
        self.connection.commit()

    def _finish_batch(self, status: str, reason: str, stats: dict[str, int]) -> None:
        self.connection.execute(
            """UPDATE download_batches SET status = ?, finished_at = ?, stop_reason = ?,
                   items_processed = ?, items_failed = ?, bytes_downloaded = ?,
                   heartbeat_at = ?
               WHERE batch_id = ?""",
            (
                status, _iso(self.clock.now()), reason, stats["processed"],
                stats["failed"], stats["bytes"], _iso(self.clock.now()), self.batch_id,
            ),
        )
        self.connection.commit()

    # -- item ---------------------------------------------------------------

    def _claim(self) -> sqlite3.Row | None:
        now = _iso(self.clock.now())
        scope = ""
        params: list[Any] = [now]
        if self.only_cetips:
            scope = (
                " AND a.codigo_cetip IN (" + ",".join("?" * len(self.only_cetips)) + ")"
            )
            params.extend(self.only_cetips)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                f"""SELECT q.queue_id, q.attempts, q.max_attempts, d.document_pk,
                           d.source_document_id, d.category, d.document_name,
                           a.codigo_cetip, a.isin, a.asset_id
                    FROM download_queue q
                    JOIN documents d ON d.document_pk = q.document_id
                    JOIN assets a ON a.asset_id = d.asset_id
                    WHERE q.status = 'pending'
                      AND (q.next_attempt_at IS NULL OR q.next_attempt_at <= ?){scope}
                    ORDER BY q.priority, q.queue_id LIMIT 1""",
                params,
            ).fetchone()
            if row is None:
                self.connection.rollback()
                return None
            updated = self.connection.execute(
                """UPDATE download_queue SET status = 'running', worker_id = ?,
                       batch_id = ?, started_at = ?, heartbeat_at = ?
                   WHERE queue_id = ? AND status = 'pending'""",
                (self.worker_id, self.batch_id, now, now, row["queue_id"]),
            )
            if updated.rowcount != 1:
                self.connection.rollback()
                return None
            self.connection.commit()
            return row
        except Exception:
            self.connection.rollback()
            raise

    def _claim_more(self, first: sqlite3.Row, limit: int) -> list[sqlite3.Row]:
        """Até ``limit`` itens pendentes do mesmo ativo do primeiro, para baixar na mesma sessão."""

        if limit <= 0:
            return []
        now = _iso(self.clock.now())
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            rows = self.connection.execute(
                """SELECT q.queue_id, q.attempts, q.max_attempts, d.document_pk,
                          d.source_document_id, d.category, d.document_name,
                          a.codigo_cetip, a.isin, a.asset_id
                   FROM download_queue q
                   JOIN documents d ON d.document_pk = q.document_id
                   JOIN assets a ON a.asset_id = d.asset_id
                   WHERE q.status = 'pending' AND a.asset_id = ?
                     AND (q.next_attempt_at IS NULL OR q.next_attempt_at <= ?)
                   ORDER BY q.priority, q.queue_id LIMIT ?""",
                (first["asset_id"], now, limit),
            ).fetchall()
            claimed = []
            for row in rows:
                updated = self.connection.execute(
                    """UPDATE download_queue SET status = 'running', worker_id = ?,
                           batch_id = ?, started_at = ?, heartbeat_at = ?
                       WHERE queue_id = ? AND status = 'pending'""",
                    (self.worker_id, self.batch_id, now, now, row["queue_id"]),
                )
                if updated.rowcount == 1:
                    claimed.append(row)
            self.connection.commit()
            return claimed
        except Exception:
            self.connection.rollback()
            raise

    def _next_wake(self) -> datetime | None:
        scope = ""
        params: list[Any] = []
        if self.only_cetips:
            scope = (
                " AND a.codigo_cetip IN (" + ",".join("?" * len(self.only_cetips)) + ")"
            )
            params.extend(self.only_cetips)
        value = self.connection.execute(
            f"""SELECT MIN(q.next_attempt_at) FROM download_queue q
                JOIN documents d ON d.document_pk = q.document_id
                JOIN assets a ON a.asset_id = d.asset_id
                WHERE q.status = 'pending' AND q.next_attempt_at IS NOT NULL{scope}""",
            params,
        ).fetchone()[0]
        return _parse(value) if value else None

    def _record(
        self, row: sqlite3.Row, outcome: DownloadOutcome
    ) -> tuple[str, str | None]:
        """Grava o resultado do item. Devolve (status final, classe do erro)."""

        now = self.clock.now()
        attempts = row["attempts"] + 1
        if outcome.ok:
            status = "skipped" if outcome.already_current else "done"
            self.connection.execute(
                """UPDATE download_queue SET status = ?, attempts = ?, finished_at = ?,
                       bytes_downloaded = ?, last_http_status = ?, last_error = NULL,
                       last_error_type = NULL, error_class = NULL, next_attempt_at = NULL
                   WHERE queue_id = ?""",
                (status, attempts, _iso(now), outcome.bytes_downloaded,
                 outcome.http_status, row["queue_id"]),
            )
            self.connection.commit()
            return status, None
        error_class, error_type = classify_error(outcome.http_status, outcome.error)
        retry = error_class == TEMPORARY and attempts < row["max_attempts"]
        if retry:
            delays = self.config.retry_delays_seconds
            delay = float(delays[min(attempts - 1, len(delays) - 1)])
            if outcome.retry_after_seconds:
                delay = max(delay, float(outcome.retry_after_seconds))
            self.connection.execute(
                """UPDATE download_queue SET status = 'pending', attempts = ?,
                       next_attempt_at = ?, last_error = ?, last_error_type = ?,
                       error_class = ?, last_http_status = ?, worker_id = NULL
                   WHERE queue_id = ?""",
                (attempts, _iso(now + timedelta(seconds=delay)),
                 (outcome.error or "")[:2000], error_type, error_class,
                 outcome.http_status, row["queue_id"]),
            )
            status = "pending"
        else:
            self.connection.execute(
                """UPDATE download_queue SET status = 'failed', attempts = ?,
                       finished_at = ?, last_error = ?, last_error_type = ?,
                       error_class = ?, last_http_status = ?, next_attempt_at = NULL
                   WHERE queue_id = ?""",
                (attempts, _iso(now), (outcome.error or "")[:2000], error_type,
                 error_class, outcome.http_status, row["queue_id"]),
            )
            status = "failed"
        self.connection.commit()
        return status, error_class

    # -- laço ---------------------------------------------------------------

    def _disk_ok(self) -> tuple[bool, int]:
        free, total = self.disk_usage()
        required = max(self.config.min_free_bytes_floor,
                       int(total * self.config.min_free_fraction))
        return free >= required, required

    def run(self) -> dict[str, Any]:
        recovered = self._start_batch()
        started = self.clock.now()
        stats = {"processed": 0, "failed": 0, "bytes": 0}
        attempts_total = 0
        failures_total = 0
        consecutive = 0
        results: list[dict[str, Any]] = []
        stop_reason = "fila vazia"
        status = "finished"
        try:
            while True:
                reason = self._limit_reason(started, stats)
                if reason:
                    stop_reason, status = reason, "stopped"
                    break
                disk_ok, required = self._disk_ok()
                if not disk_ok:
                    stop_reason = (
                        f"espaço livre abaixo do mínimo ({required} bytes)"
                    )
                    status = "stopped"
                    break
                row = self._claim()
                if row is None:
                    wake = self._next_wake()
                    if wake is None:
                        stop_reason = "fila vazia"
                        break
                    wait = (wake - self.clock.now()).total_seconds()
                    elapsed = (self.clock.now() - started).total_seconds()
                    limit = self.config.max_duration_seconds
                    if limit is not None and elapsed + wait > limit:
                        stop_reason = "itens restantes aguardam nova tentativa além da duração do lote"
                        status = "stopped"
                        break
                    self._heartbeat()
                    self.clock.sleep(max(wait, 0))
                    continue
                rows = [row] + self._claim_more(row, self.config.chunk_size - 1)
                for _ in rows:
                    self.limiter.wait()
                documents = [{k: r[k] for k in r.keys()} for r in rows]
                try:
                    if len(rows) > 1 and hasattr(self.executor, "chunk"):
                        outcomes = list(self.executor.chunk(documents))
                        if len(outcomes) != len(rows):
                            raise RuntimeError("o executor devolveu número de resultados diferente do de documentos")
                    else:
                        outcomes = [self.executor(document) for document in documents]
                except Exception as error:  # falha inesperada do executor
                    outcomes = [
                        DownloadOutcome(ok=False, error=f"{type(error).__name__}: {error}")
                        for _ in rows
                    ]
                stop: tuple[str, str] | None = None
                # a sessão inteira falhou com o mesmo erro (ex.: grade fora do ar): conta como uma falha seguida, não N
                session_failure = (len(rows) > 1 and all(not o.ok for o in outcomes)
                                   and len({o.error for o in outcomes}) == 1)
                for position, (item, outcome) in enumerate(zip(rows, outcomes)):
                    final, error_class = self._record(item, outcome)
                    attempts_total += 1
                    stats["processed"] += 1
                    stats["bytes"] += outcome.bytes_downloaded if outcome.ok else 0
                    if outcome.ok:
                        consecutive = 0
                    else:
                        failures_total += 1
                        if not session_failure or position == 0:
                            consecutive += 1
                        stats["failed"] += 1
                    results.append({
                        "source_document_id": item["source_document_id"],
                        "status": final, "error_class": error_class,
                        "http_status": outcome.http_status,
                    })
                    if stop is None:
                        if error_class == BLOCKED:
                            stop = ("bloqueio detectado (HTTP 403)", "stopped")
                        elif consecutive >= self.config.max_consecutive_failures:
                            stop = (f"{consecutive} falhas consecutivas", "stopped")
                        elif (
                            attempts_total >= self.config.failure_rate_min_attempts
                            and failures_total / attempts_total >= self.config.failure_rate_threshold
                        ):
                            stop = (
                                f"taxa de falha {failures_total}/{attempts_total} "
                                f">= {self.config.failure_rate_threshold:.0%}",
                                "stopped",
                            )
                self.connection.execute(
                    """UPDATE download_batches SET items_processed = ?, items_failed = ?,
                           bytes_downloaded = ? WHERE batch_id = ?""",
                    (stats["processed"], stats["failed"], stats["bytes"], self.batch_id),
                )
                self._heartbeat()
                if stop is not None:
                    stop_reason, status = stop
                    break
        except BaseException as error:
            self._requeue_running()
            self._finish_batch("stopped", f"interrompido: {type(error).__name__}", stats)
            raise
        self._requeue_running()
        self._finish_batch(status, stop_reason, stats)
        return {
            "batch_id": self.batch_id, "worker_id": self.worker_id,
            "status": status, "stop_reason": stop_reason,
            "recovered_batches": recovered, **stats,
            "attempts": attempts_total, "results": results,
        }

    def _requeue_running(self) -> None:
        self.connection.execute(
            """UPDATE download_queue SET status = 'pending', worker_id = NULL
               WHERE batch_id = ? AND status = 'running'""",
            (self.batch_id,),
        )
        self.connection.commit()

    def _limit_reason(self, started: datetime, stats: dict[str, int]) -> str | None:
        cfg = self.config
        if cfg.max_items is not None and stats["processed"] >= cfg.max_items:
            return f"limite de {cfg.max_items} itens"
        if cfg.max_total_bytes is not None and stats["bytes"] >= cfg.max_total_bytes:
            return f"limite de {cfg.max_total_bytes} bytes baixados"
        if cfg.max_duration_seconds is not None:
            elapsed = (self.clock.now() - started).total_seconds()
            if elapsed >= cfg.max_duration_seconds:
                return f"limite de {cfg.max_duration_seconds:g} s de duração"
        return None


# ------------------------------------------------------ executor de produção

def make_service_executor(service: Any, connection: sqlite3.Connection) -> Executor:
    """Executor real: um documento por chamada ao ``DocumentDownloadService``.
    O código HTTP e o erro vêm da tentativa gravada em ``collection_attempts``."""

    def execute(document: dict[str, Any]) -> DownloadOutcome:
        report = service.run(
            document["codigo_cetip"], document["isin"],
            max_documents=1,
            source_document_ids=[document["source_document_id"]],
            allow_other=document["category"] == "Outro",
        )
        attempt = connection.execute(
            """SELECT http_status, error_message, status FROM collection_attempts
               WHERE document_id = ? ORDER BY attempt_id DESC LIMIT 1""",
            (document["document_pk"],),
        ).fetchone()
        http_status = attempt["http_status"] if attempt else None
        if report["failed"]:
            error = next(
                (e["error"] for e in reversed(report["errors"])
                 if e.get("document_id") == document["document_pk"]),
                attempt["error_message"] if attempt else "download falhou",
            )
            return DownloadOutcome(ok=False, http_status=http_status, error=error)
        files = report["files_downloaded"]
        result = files[-1].get("result") if files else None
        size = int(files[-1].get("size_bytes") or 0) if files else 0
        return DownloadOutcome(
            ok=True, http_status=http_status, bytes_downloaded=size,
            already_current=result in {"unchanged", "duplicate_content"},
        )

    def execute_chunk(documents: list[dict[str, Any]]) -> list[DownloadOutcome]:
        """Um ativo, vários documentos, uma sessão de navegador."""

        first = documents[0]
        if any(d["isin"] != first["isin"] for d in documents):
            raise ValueError("o grupo mistura ativos")
        report = service.run(
            first["codigo_cetip"], first["isin"],
            max_documents=len(documents),
            source_document_ids=[d["source_document_id"] for d in documents],
            allow_other=any(d["category"] == "Outro" for d in documents),
        )
        outcomes = []
        for document in documents:
            sid = document["source_document_id"]
            attempt = connection.execute(
                """SELECT http_status, error_message FROM collection_attempts
                   WHERE document_id = ? ORDER BY attempt_id DESC LIMIT 1""",
                (document["document_pk"],),
            ).fetchone()
            http_status = attempt["http_status"] if attempt else None
            error = next((e["error"] for e in report["errors"] if str(e.get("source_document_id")) == str(sid)), None)
            if error is not None:
                outcomes.append(DownloadOutcome(ok=False, http_status=http_status, error=error))
                continue
            entry = next((f for f in report["files_downloaded"] if str(f.get("source_document_id")) == str(sid)), None)
            if entry is None:
                outcomes.append(DownloadOutcome(ok=False, http_status=http_status, error="download sem resultado"))
                continue
            outcomes.append(DownloadOutcome(
                ok=True, http_status=http_status, bytes_downloaded=int(entry.get("size_bytes") or 0),
                already_current=entry.get("result") in {"unchanged", "duplicate_content"},
            ))
        return outcomes

    execute.chunk = execute_chunk  # type: ignore[attr-defined]
    return execute
