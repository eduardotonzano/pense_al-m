import json
from dataclasses import dataclass

from fundos.database import normalize_timestamp
from fundos.database import utc_now


FINAL_STATUSES = {
    "success",
    "partial",
    "failed",
    "cancelled",
}


@dataclass(frozen=True)
class CollectionRunRecord:
    """Execucao de coleta de uma fonte."""

    id: int
    source_id: int
    started_at: str
    finished_at: str | None
    status: str
    requested_items: int
    successful_items: int
    failed_items: int
    error_summary: str | None

    @property
    def errors(self):
        """Resumo de erros como objeto Python."""

        if self.error_summary is None:
            return None

        return json.loads(self.error_summary)


class CollectionRunRepository:
    """Abre e encerra execucoes de coleta."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def normalize_count(value, label):
        """Valida um contador inteiro e nao negativo."""

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(label + " deve ser um numero inteiro.")

        if value < 0:
            raise ValueError(label + " nao pode ser negativo.")

        return value

    @staticmethod
    def row_to_record(row):
        return CollectionRunRecord(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            started_at=str(row["started_at"]),
            finished_at=row["finished_at"],
            status=str(row["status"]),
            requested_items=int(row["requested_items"]),
            successful_items=int(row["successful_items"]),
            failed_items=int(row["failed_items"]),
            error_summary=row["error_summary"],
        )

    def get_by_id(self, run_id):
        """Busca uma coleta pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM collection_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def start(self, source_id, *, started_at=None, requested_items=0):
        """Abre uma coleta com status running."""

        source = self.connection.execute(
            "SELECT id FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()

        if source is None:
            raise ValueError("A fonte informada nao existe.")

        normalized_start = (
            utc_now()
            if started_at is None
            else normalize_timestamp(started_at, "A data de inicio da coleta")
        )
        requested = self.normalize_count(
            requested_items,
            "A quantidade pedida",
        )

        cursor = self.connection.execute(
            """
            INSERT INTO collection_runs (source_id, started_at, requested_items)
            VALUES (?, ?, ?)
            """,
            (source_id, normalized_start, requested),
        )

        return self.get_by_id(cursor.lastrowid)

    def finish(
        self,
        run_id,
        status,
        *,
        successful_items,
        failed_items,
        error_summary=None,
        finished_at=None,
    ):
        """Encerra uma coleta aberta; uma coleta encerrada nao muda mais."""

        current = self.get_by_id(run_id)

        if current is None:
            raise ValueError("Coleta nao encontrada.")

        if current.status != "running":
            raise ValueError("A coleta ja foi encerrada.")

        normalized_status = str(status).strip().lower()

        if normalized_status not in FINAL_STATUSES:
            raise ValueError("Status final de coleta invalido.")

        successful = self.normalize_count(
            successful_items,
            "A quantidade com sucesso",
        )
        failed = self.normalize_count(failed_items, "A quantidade com falha")
        normalized_end = (
            utc_now()
            if finished_at is None
            else normalize_timestamp(finished_at, "A data de fim da coleta")
        )

        if normalized_end < current.started_at:
            raise ValueError(
                "A data de fim nao pode ser anterior a data de inicio."
            )

        summary = None

        if error_summary is not None:
            try:
                summary = json.dumps(
                    error_summary,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except TypeError as error:
                raise ValueError(
                    "O resumo de erros nao pode ser serializado."
                ) from error

        self.connection.execute(
            """
            UPDATE collection_runs
            SET status = ?, finished_at = ?, successful_items = ?,
                failed_items = ?, error_summary = ?
            WHERE id = ? AND status = 'running'
            """,
            (normalized_status, normalized_end, successful, failed, summary, run_id),
        )

        return self.get_by_id(run_id)
