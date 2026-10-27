"""Manifesto dos arquivos coletados: nome, tamanho, SHA-256 e linhas.

Nunca o conteudo: nao existe parametro nem coluna para os bytes do arquivo.
Proposta ainda nao aprovada pelo Gui: se a regra do CPF vale tambem para o
arquivo original da CVM (docs/decisoes-em-aberto.md, decisao 3).
"""

import re
from dataclasses import dataclass

from fundos.database import normalize_timestamp
from fundos.database import utc_now


PROCESSING_STATUSES = {
    "pending",
    "processed",
    "failed",
    "ignored",
}

SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RawRecord:
    """Manifesto de um arquivo (ZIP) ou de um membro dele (CSV)."""

    id: int
    source_id: int
    collection_run_id: int
    parent_raw_record_id: int | None
    file_name: str
    size_bytes: int
    sha256: str
    line_count: int | None
    request_url: str | None
    content_type: str | None
    http_status: int | None
    last_modified: str | None
    collected_at: str
    parser_version: str | None
    processing_status: str
    processing_error: str | None


class RawRecordRepository:
    """Registra manifestos de arquivo de forma idempotente."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def row_to_record(row):
        return RawRecord(**{key: row[key] for key in row.keys()})

    @staticmethod
    def normalize_file_name(file_name):
        """So o nome do arquivo: nenhum caminho local entra no banco."""

        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("O nome do arquivo e obrigatorio.")

        if file_name != file_name.strip():
            raise ValueError(
                "O nome do arquivo nao pode ter espacos nas pontas."
            )

        if any(char in file_name for char in "/\\:"):
            raise ValueError(
                "O nome do arquivo nao pode ter pasta nem unidade; "
                "guarde so o nome."
            )

        return file_name

    @staticmethod
    def normalize_optional_text(value):
        if value is None:
            return None

        normalized = str(value).strip()
        return normalized or None

    def get_by_id(self, raw_record_id):
        """Busca um manifesto pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM raw_records WHERE id = ?",
            (raw_record_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def find(self, source_id, parent_raw_record_id, file_name, sha256):
        """Busca pela chave do manifesto: fonte, pai, nome e hash."""

        row = self.connection.execute(
            """
            SELECT *
            FROM raw_records
            WHERE source_id = ?
              AND COALESCE(parent_raw_record_id, 0) = COALESCE(?, 0)
              AND file_name = ?
              AND sha256 = ?
            """,
            (source_id, parent_raw_record_id, file_name, sha256),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def register_file(
        self,
        *,
        source_id,
        collection_run_id,
        file_name,
        size_bytes,
        sha256,
        line_count=None,
        parent_raw_record_id=None,
        request_url=None,
        content_type=None,
        http_status=None,
        last_modified=None,
        collected_at=None,
    ):
        """Registra o manifesto; devolve (manifesto, criado)."""

        run = self.connection.execute(
            "SELECT source_id FROM collection_runs WHERE id = ?",
            (collection_run_id,),
        ).fetchone()

        if run is None:
            raise ValueError("A coleta informada nao existe.")

        if int(run["source_id"]) != int(source_id):
            raise ValueError("A coleta informada e de outra fonte.")

        name = self.normalize_file_name(file_name)

        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
            raise ValueError("O tamanho do arquivo deve ser inteiro.")

        if size_bytes <= 0:
            raise ValueError("O tamanho do arquivo deve ser maior que zero.")

        digest = str(sha256).strip().lower() if sha256 is not None else ""

        if SHA256.fullmatch(digest) is None:
            raise ValueError("O SHA-256 deve ter 64 caracteres hexadecimais.")

        if line_count is not None and (
            isinstance(line_count, bool)
            or not isinstance(line_count, int)
            or line_count < 0
        ):
            raise ValueError(
                "O numero de linhas deve ser inteiro e nao negativo."
            )

        if parent_raw_record_id is not None:
            parent = self.get_by_id(parent_raw_record_id)

            if parent is None:
                raise ValueError("O arquivo pai informado nao existe.")

            if parent.source_id != int(source_id):
                raise ValueError("O arquivo pai e de outra fonte.")

            if parent.parent_raw_record_id is not None:
                raise ValueError(
                    "O arquivo pai deve ser de primeiro nivel (o ZIP)."
                )

        url = self.normalize_optional_text(request_url)

        if url is not None and not url.startswith("https://"):
            raise ValueError("A URL de origem deve comecar com https://.")

        if http_status is not None and (
            isinstance(http_status, bool)
            or not isinstance(http_status, int)
            or not 100 <= http_status <= 599
        ):
            raise ValueError("Status HTTP invalido.")

        existing = self.find(source_id, parent_raw_record_id, name, digest)

        if existing is not None:
            if existing.size_bytes != size_bytes:
                raise ValueError(
                    "O mesmo arquivo (nome e SHA-256) ja foi registrado "
                    "com outro tamanho."
                )

            return existing, False

        cursor = self.connection.execute(
            """
            INSERT INTO raw_records (
                source_id, collection_run_id, parent_raw_record_id,
                file_name, size_bytes, sha256, line_count, request_url,
                content_type, http_status, last_modified, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                collection_run_id,
                parent_raw_record_id,
                name,
                size_bytes,
                digest,
                line_count,
                url,
                self.normalize_optional_text(content_type),
                http_status,
                self.normalize_optional_text(last_modified),
                (
                    utc_now()
                    if collected_at is None
                    else normalize_timestamp(collected_at, "A data de coleta")
                ),
            ),
        )

        return self.get_by_id(cursor.lastrowid), True

    def list_members(self, parent_raw_record_id):
        """Lista os membros (CSV) de um arquivo (ZIP)."""

        rows = self.connection.execute(
            """
            SELECT *
            FROM raw_records
            WHERE parent_raw_record_id = ?
            ORDER BY file_name, id
            """,
            (parent_raw_record_id,),
        ).fetchall()

        return [self.row_to_record(row) for row in rows]

    def update_processing(
        self,
        raw_record_id,
        status,
        *,
        parser_version=None,
        processing_error=None,
    ):
        """Registra o resultado do processamento do arquivo."""

        normalized_status = str(status).strip().lower()

        if normalized_status not in PROCESSING_STATUSES:
            raise ValueError("Status de processamento invalido.")

        error = self.normalize_optional_text(processing_error)

        if normalized_status == "failed" and error is None:
            raise ValueError(
                "Um processamento com falha precisa informar o erro."
            )

        if normalized_status == "processed":
            error = None

        cursor = self.connection.execute(
            """
            UPDATE raw_records
            SET processing_status = ?,
                parser_version = COALESCE(?, parser_version),
                processing_error = ?
            WHERE id = ?
            """,
            (
                normalized_status,
                self.normalize_optional_text(parser_version),
                error,
                raw_record_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError("Manifesto nao encontrado.")

        return self.get_by_id(raw_record_id)
