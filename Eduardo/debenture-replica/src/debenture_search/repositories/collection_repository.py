import json
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from debenture_search.database import database


ALLOWED_COLLECTION_STATUSES = {
    "running",
    "success",
    "partial",
    "failed",
    "cancelled",
}


@dataclass(frozen=True)
class CollectionRunRecord:
    """Representa uma execucao de coleta."""

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
        """Retorna o resumo de erros como objeto Python."""

        if self.error_summary is None:
            return None

        return json.loads(self.error_summary)


class CollectionRepository:
    """Gerencia execucoes de coleta de dados."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_status(status):
        """Valida o status da coleta."""

        if status is None:
            return "running"

        normalized = str(status).strip().lower()

        if normalized not in ALLOWED_COLLECTION_STATUSES:
            raise ValueError("Status de coleta invalido.")

        return normalized

    @staticmethod
    def normalize_count(value, field_name):
        """Valida um contador da coleta."""

        try:
            normalized = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                field_name + " deve ser um numero inteiro."
            ) from error

        if normalized < 0:
            raise ValueError(
                field_name + " nao pode ser negativo."
            )

        return normalized

    @staticmethod
    def normalize_errors(errors):
        """Serializa o resumo de erros como JSON."""

        if errors is None:
            return None

        try:
            return json.dumps(
                errors,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except TypeError as error:
            raise ValueError(
                "O resumo de erros nao pode ser serializado."
            ) from error

    @staticmethod
    def utc_now():
        """Retorna o horario atual em UTC."""

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em CollectionRunRecord."""

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

    def source_exists(self, source_id):
        """Verifica se a fonte existe."""

        row = self.db.fetch_one(
            "SELECT id FROM sources WHERE id = ?",
            (source_id,),
        )
        return row is not None

    def get_by_id(self, collection_run_id):
        """Busca uma coleta pelo ID."""

        row = self.db.fetch_one(
            """
            SELECT
                id, source_id, started_at, finished_at,
                status, requested_items, successful_items,
                failed_items, error_summary
            FROM collection_runs
            WHERE id = ?
            """,
            (collection_run_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def start(self, source_id, requested_items=0):
        """Inicia uma nova execucao de coleta."""

        if not self.source_exists(source_id):
            raise ValueError("A fonte informada nao existe.")

        requested = self.normalize_count(
            requested_items,
            "requested_items",
        )

        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO collection_runs (
                    source_id,
                    started_at,
                    status,
                    requested_items,
                    successful_items,
                    failed_items
                )
                VALUES (?, ?, 'running', ?, 0, 0)
                """,
                (
                    source_id,
                    self.utc_now(),
                    requested,
                ),
            )
            collection_run_id = cursor.lastrowid

        created = self.get_by_id(collection_run_id)

        if created is None:
            raise RuntimeError(
                "A coleta foi criada, mas nao foi localizada."
            )

        return created

    def finish(
        self,
        collection_run_id,
        status,
        successful_items=0,
        failed_items=0,
        errors=None,
    ):
        """Finaliza uma coleta e grava os resultados."""

        current = self.get_by_id(collection_run_id)

        if current is None:
            raise ValueError("Execucao de coleta nao encontrada.")

        if current.status != "running":
            raise ValueError("A execucao de coleta ja foi finalizada.")

        normalized_status = self.normalize_status(status)

        if normalized_status == "running":
            raise ValueError(
                "Uma coleta finalizada nao pode permanecer running."
            )

        successful = self.normalize_count(
            successful_items,
            "successful_items",
        )
        failed = self.normalize_count(
            failed_items,
            "failed_items",
        )
        error_summary = self.normalize_errors(errors)

        if normalized_status == "success" and failed != 0:
            raise ValueError(
                "Uma coleta success nao pode ter falhas."
            )

        if normalized_status == "failed" and failed == 0:
            raise ValueError(
                "Uma coleta failed deve registrar ao menos uma falha."
            )

        processed = successful + failed

        if (
            current.requested_items > 0
            and processed > current.requested_items
        ):
            raise ValueError(
                "O total processado excede o total solicitado."
            )

        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE collection_runs
                SET
                    finished_at = ?,
                    status = ?,
                    successful_items = ?,
                    failed_items = ?,
                    error_summary = ?
                WHERE id = ?
                """,
                (
                    self.utc_now(),
                    normalized_status,
                    successful,
                    failed,
                    error_summary,
                    collection_run_id,
                ),
            )

        return self.get_by_id(collection_run_id)

    def cancel(self, collection_run_id, reason=None):
        """Cancela uma coleta em andamento."""

        errors = None

        if reason is not None:
            errors = {"reason": str(reason)}

        return self.finish(
            collection_run_id=collection_run_id,
            status="cancelled",
            successful_items=0,
            failed_items=0,
            errors=errors,
        )

    def list_by_source(
        self,
        source_id,
        status=None,
        limit=100,
        offset=0,
    ):
        """Lista coletas de uma fonte."""

        if not self.source_exists(source_id):
            raise ValueError("A fonte informada nao existe.")

        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))

        parameters = [source_id]
        status_clause = ""

        if status is not None:
            status_clause = " AND status = ?"
            parameters.append(self.normalize_status(status))

        parameters.extend([safe_limit, safe_offset])

        rows = self.db.fetch_all(
            """
            SELECT
                id, source_id, started_at, finished_at,
                status, requested_items, successful_items,
                failed_items, error_summary
            FROM collection_runs
            WHERE source_id = ?
            """ + status_clause + """
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(parameters),
        )

        return [self.row_to_record(row) for row in rows]

    def count(self, source_id=None, status=None):
        """Conta coletas com filtros opcionais."""

        clauses = []
        parameters = []

        if source_id is not None:
            clauses.append("source_id = ?")
            parameters.append(source_id)

        if status is not None:
            clauses.append("status = ?")
            parameters.append(self.normalize_status(status))

        sql = "SELECT COUNT(*) AS total FROM collection_runs"

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        row = self.db.fetch_one(sql, tuple(parameters))
        return 0 if row is None else int(row["total"])


collection_repository = CollectionRepository()
