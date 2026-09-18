import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from debenture_search.database import database


ALLOWED_PROCESSING_STATUSES = {
    "pending",
    "processed",
    "failed",
    "ignored",
}


@dataclass(frozen=True)
class RawRecord:
    """Representa uma resposta bruta armazenada no banco."""

    id: int
    source_id: int
    collection_run_id: int | None
    request_url: str | None
    request_parameters: str | None
    content_type: str | None
    payload: bytes
    payload_sha256: str
    http_status: int | None
    collected_at: str
    parser_version: str | None
    processing_status: str
    processing_error: str | None

    @property
    def parameters(self):
        """Retorna os parametros como objeto Python."""

        if self.request_parameters is None:
            return None

        return json.loads(self.request_parameters)

    @property
    def text(self):
        """Decodifica o payload como UTF-8."""

        return self.payload.decode("utf-8")


class RawRecordRepository:
    """Armazena respostas brutas de fontes externas."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_payload(payload):
        """Converte o payload para bytes e rejeita conteudo vazio."""

        if isinstance(payload, str):
            normalized = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            normalized = payload
        elif isinstance(payload, bytearray):
            normalized = bytes(payload)
        else:
            raise ValueError(
                "O payload deve ser texto ou bytes."
            )

        if not normalized:
            raise ValueError(
                "O payload nao pode ficar vazio."
            )

        return normalized

    @staticmethod
    def normalize_optional_text(value):
        """Normaliza um texto opcional."""

        if value is None:
            return None

        normalized = " ".join(str(value).split())
        return normalized or None

    @staticmethod
    def normalize_parameters(parameters):
        """Serializa os parametros de maneira deterministica."""

        if parameters is None:
            return None

        if isinstance(parameters, str):
            try:
                parsed = json.loads(parameters)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Os parametros devem conter JSON valido."
                ) from error
        else:
            parsed = parameters

        try:
            return json.dumps(
                parsed,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except TypeError as error:
            raise ValueError(
                "Os parametros nao podem ser serializados."
            ) from error

    @staticmethod
    def normalize_http_status(http_status):
        """Valida o status HTTP."""

        if http_status is None:
            return None

        normalized = int(http_status)

        if normalized < 100 or normalized > 599:
            raise ValueError(
                "Status HTTP invalido."
            )

        return normalized

    @staticmethod
    def normalize_processing_status(status):
        """Valida o status de processamento."""

        if status is None:
            return "pending"

        normalized = str(status).strip().lower()

        if normalized not in ALLOWED_PROCESSING_STATUSES:
            raise ValueError(
                "Status de processamento invalido."
            )

        return normalized

    @staticmethod
    def sha256(payload):
        """Calcula o SHA-256 do payload."""

        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em RawRecord."""

        return RawRecord(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            collection_run_id=row["collection_run_id"],
            request_url=row["request_url"],
            request_parameters=row["request_parameters"],
            content_type=row["content_type"],
            payload=bytes(row["payload"]),
            payload_sha256=str(row["payload_sha256"]),
            http_status=row["http_status"],
            collected_at=str(row["collected_at"]),
            parser_version=row["parser_version"],
            processing_status=str(row["processing_status"]),
            processing_error=row["processing_error"],
        )

    def source_exists(self, source_id):
        """Verifica se a fonte existe."""

        row = self.db.fetch_one(
            "SELECT id FROM sources WHERE id = ?",
            (source_id,),
        )
        return row is not None

    def collection_run_exists(self, collection_run_id):
        """Verifica se a execucao de coleta existe."""

        if collection_run_id is None:
            return True

        row = self.db.fetch_one(
            "SELECT id FROM collection_runs WHERE id = ?",
            (collection_run_id,),
        )
        return row is not None

    def get_by_id(self, raw_record_id):
        """Busca um registro bruto pelo ID."""

        row = self.db.fetch_one(
            """
            SELECT
                id, source_id, collection_run_id,
                request_url, request_parameters,
                content_type, payload, payload_sha256,
                http_status, collected_at, parser_version,
                processing_status, processing_error
            FROM raw_records
            WHERE id = ?
            """,
            (raw_record_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_hash(self, source_id, payload_sha256):
        """Busca por fonte e hash do payload."""

        row = self.db.fetch_one(
            """
            SELECT
                id, source_id, collection_run_id,
                request_url, request_parameters,
                content_type, payload, payload_sha256,
                http_status, collected_at, parser_version,
                processing_status, processing_error
            FROM raw_records
            WHERE source_id = ?
              AND payload_sha256 = ?
            """,
            (source_id, payload_sha256),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def create(
        self,
        source_id,
        payload,
        collection_run_id=None,
        request_url=None,
        request_parameters=None,
        content_type=None,
        http_status=None,
        parser_version=None,
        processing_status="pending",
        processing_error=None,
    ):
        """Cria um registro bruto de forma idempotente."""

        if not self.source_exists(source_id):
            raise ValueError(
                "A fonte informada nao existe."
            )

        if not self.collection_run_exists(collection_run_id):
            raise ValueError(
                "A execucao de coleta informada nao existe."
            )

        normalized_payload = self.normalize_payload(payload)
        payload_hash = self.sha256(normalized_payload)
        normalized_parameters = self.normalize_parameters(
            request_parameters
        )
        normalized_url = self.normalize_optional_text(
            request_url
        )
        normalized_content_type = self.normalize_optional_text(
            content_type
        )
        normalized_http_status = self.normalize_http_status(
            http_status
        )
        normalized_parser_version = self.normalize_optional_text(
            parser_version
        )
        normalized_status = self.normalize_processing_status(
            processing_status
        )
        normalized_error = self.normalize_optional_text(
            processing_error
        )

        existing = self.get_by_hash(source_id, payload_hash)

        if existing is not None:
            return existing, False

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO raw_records (
                        source_id,
                        collection_run_id,
                        request_url,
                        request_parameters,
                        content_type,
                        payload,
                        payload_sha256,
                        http_status,
                        collected_at,
                        parser_version,
                        processing_status,
                        processing_error
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        source_id,
                        collection_run_id,
                        normalized_url,
                        normalized_parameters,
                        normalized_content_type,
                        normalized_payload,
                        payload_hash,
                        normalized_http_status,
                        datetime.now(timezone.utc).isoformat(),
                        normalized_parser_version,
                        normalized_status,
                        normalized_error,
                    ),
                )
                raw_record_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            existing = self.get_by_hash(source_id, payload_hash)

            if existing is not None:
                return existing, False

            raise

        created = self.get_by_id(raw_record_id)

        if created is None:
            raise RuntimeError(
                "O registro bruto foi gravado, "
                "mas nao foi localizado."
            )

        return created, True

    def update_processing(
        self,
        raw_record_id,
        status,
        parser_version=None,
        processing_error=None,
    ):
        """Atualiza o resultado do processamento do payload."""

        normalized_status = self.normalize_processing_status(
            status
        )
        normalized_parser_version = self.normalize_optional_text(
            parser_version
        )
        normalized_error = self.normalize_optional_text(
            processing_error
        )

        if normalized_status == "failed" and normalized_error is None:
            raise ValueError(
                "Um processamento com falha precisa informar o erro."
            )

        if normalized_status == "processed":
            normalized_error = None

        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE raw_records
                SET
                    processing_status = ?,
                    parser_version = COALESCE(?, parser_version),
                    processing_error = ?
                WHERE id = ?
                """,
                (
                    normalized_status,
                    normalized_parser_version,
                    normalized_error,
                    raw_record_id,
                ),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Registro bruto nao encontrado."
                )

        return self.get_by_id(raw_record_id)

    def list_by_source(
        self,
        source_id,
        status=None,
        limit=100,
        offset=0,
    ):
        """Lista registros brutos de uma fonte."""

        if not self.source_exists(source_id):
            raise ValueError(
                "A fonte informada nao existe."
            )

        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))

        if status is None:
            rows = self.db.fetch_all(
                """
                SELECT
                    id, source_id, collection_run_id,
                    request_url, request_parameters,
                    content_type, payload, payload_sha256,
                    http_status, collected_at, parser_version,
                    processing_status, processing_error
                FROM raw_records
                WHERE source_id = ?
                ORDER BY collected_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (source_id, safe_limit, safe_offset),
            )
        else:
            normalized_status = self.normalize_processing_status(
                status
            )
            rows = self.db.fetch_all(
                """
                SELECT
                    id, source_id, collection_run_id,
                    request_url, request_parameters,
                    content_type, payload, payload_sha256,
                    http_status, collected_at, parser_version,
                    processing_status, processing_error
                FROM raw_records
                WHERE source_id = ?
                  AND processing_status = ?
                ORDER BY collected_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (
                    source_id,
                    normalized_status,
                    safe_limit,
                    safe_offset,
                ),
            )

        return [self.row_to_record(row) for row in rows]

    def count(self, source_id=None, status=None):
        """Conta registros brutos com filtros opcionais."""

        clauses = []
        parameters = []

        if source_id is not None:
            clauses.append("source_id = ?")
            parameters.append(source_id)

        if status is not None:
            clauses.append("processing_status = ?")
            parameters.append(
                self.normalize_processing_status(status)
            )

        sql = "SELECT COUNT(*) AS total FROM raw_records"

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        row = self.db.fetch_one(sql, tuple(parameters))

        if row is None:
            return 0

        return int(row["total"])


raw_record_repository = RawRecordRepository()
