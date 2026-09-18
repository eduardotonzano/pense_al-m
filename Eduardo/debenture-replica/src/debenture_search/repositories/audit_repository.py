import json
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from debenture_search.database import database


@dataclass(frozen=True)
class AuditRecord:
    """Representa um registro de auditoria."""

    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: int
    before_data: str | None
    after_data: str | None
    reason: str | None
    occurred_at: str

    @property
    def before(self):
        """Retorna o estado anterior como objeto Python."""

        if self.before_data is None:
            return None

        return json.loads(self.before_data)

    @property
    def after(self):
        """Retorna o estado posterior como objeto Python."""

        if self.after_data is None:
            return None

        return json.loads(self.after_data)


class AuditRepository:
    """Registra e consulta alteracoes auditaveis."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_required_text(value, field_name):
        """Normaliza um texto obrigatorio."""

        if value is None:
            raise ValueError(field_name + " e obrigatorio.")

        normalized = " ".join(str(value).split())

        if not normalized:
            raise ValueError(field_name + " e obrigatorio.")

        return normalized

    @staticmethod
    def normalize_optional_text(value):
        """Normaliza um texto opcional."""

        if value is None:
            return None

        normalized = " ".join(str(value).split())
        return normalized or None

    @staticmethod
    def normalize_entity_id(entity_id):
        """Valida o identificador da entidade."""

        try:
            normalized = int(entity_id)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "O ID da entidade deve ser um numero inteiro."
            ) from error

        if normalized <= 0:
            raise ValueError(
                "O ID da entidade deve ser maior que zero."
            )

        return normalized

    @staticmethod
    def serialize_data(data, field_name):
        """Serializa dados de auditoria como JSON deterministico."""

        if data is None:
            return None

        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError as error:
                raise ValueError(
                    field_name + " deve conter JSON valido."
                ) from error
        else:
            parsed = data

        try:
            return json.dumps(
                parsed,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except TypeError as error:
            raise ValueError(
                field_name + " nao pode ser serializado."
            ) from error

    @staticmethod
    def utc_now():
        """Retorna o horario atual em UTC."""

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em AuditRecord."""

        return AuditRecord(
            id=int(row["id"]),
            actor=str(row["actor"]),
            action=str(row["action"]),
            entity_type=str(row["entity_type"]),
            entity_id=int(row["entity_id"]),
            before_data=row["before_data"],
            after_data=row["after_data"],
            reason=row["reason"],
            occurred_at=str(row["occurred_at"]),
        )

    def create(
        self,
        actor,
        action,
        entity_type,
        entity_id,
        before=None,
        after=None,
        reason=None,
    ):
        """Cria um registro imutavel de auditoria."""

        normalized_actor = self.normalize_required_text(
            actor,
            "O responsavel",
        )
        normalized_action = self.normalize_required_text(
            action,
            "A acao",
        )
        normalized_entity_type = self.normalize_required_text(
            entity_type,
            "O tipo da entidade",
        ).lower()
        normalized_entity_id = self.normalize_entity_id(
            entity_id
        )
        normalized_before = self.serialize_data(
            before,
            "O estado anterior",
        )
        normalized_after = self.serialize_data(
            after,
            "O estado posterior",
        )
        normalized_reason = self.normalize_optional_text(
            reason
        )

        if normalized_before is None and normalized_after is None:
            raise ValueError(
                "A auditoria precisa do estado anterior ou posterior."
            )

        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_log (
                    actor,
                    action,
                    entity_type,
                    entity_id,
                    before_data,
                    after_data,
                    reason,
                    occurred_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_actor,
                    normalized_action,
                    normalized_entity_type,
                    normalized_entity_id,
                    normalized_before,
                    normalized_after,
                    normalized_reason,
                    self.utc_now(),
                ),
            )
            audit_id = cursor.lastrowid

        created = self.get_by_id(audit_id)

        if created is None:
            raise RuntimeError(
                "A auditoria foi gravada, mas nao foi localizada."
            )

        return created

    def get_by_id(self, audit_id):
        """Busca um registro de auditoria pelo ID."""

        row = self.db.fetch_one(
            """
            SELECT
                id,
                actor,
                action,
                entity_type,
                entity_id,
                before_data,
                after_data,
                reason,
                occurred_at
            FROM audit_log
            WHERE id = ?
            """,
            (audit_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def list_by_entity(
        self,
        entity_type,
        entity_id,
        limit=100,
        offset=0,
    ):
        """Lista a auditoria de uma entidade."""

        normalized_entity_type = self.normalize_required_text(
            entity_type,
            "O tipo da entidade",
        ).lower()
        normalized_entity_id = self.normalize_entity_id(
            entity_id
        )
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))

        rows = self.db.fetch_all(
            """
            SELECT
                id,
                actor,
                action,
                entity_type,
                entity_id,
                before_data,
                after_data,
                reason,
                occurred_at
            FROM audit_log
            WHERE entity_type = ?
              AND entity_id = ?
            ORDER BY occurred_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (
                normalized_entity_type,
                normalized_entity_id,
                safe_limit,
                safe_offset,
            ),
        )

        return [self.row_to_record(row) for row in rows]

    def list_by_actor(
        self,
        actor,
        limit=100,
        offset=0,
    ):
        """Lista registros de um responsavel."""

        normalized_actor = self.normalize_required_text(
            actor,
            "O responsavel",
        )
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))

        rows = self.db.fetch_all(
            """
            SELECT
                id,
                actor,
                action,
                entity_type,
                entity_id,
                before_data,
                after_data,
                reason,
                occurred_at
            FROM audit_log
            WHERE actor = ?
            ORDER BY occurred_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (normalized_actor, safe_limit, safe_offset),
        )

        return [self.row_to_record(row) for row in rows]

    def count(self, entity_type=None, entity_id=None, actor=None):
        """Conta registros de auditoria com filtros opcionais."""

        clauses = []
        parameters = []

        if entity_type is not None:
            clauses.append("entity_type = ?")
            parameters.append(
                self.normalize_required_text(
                    entity_type,
                    "O tipo da entidade",
                ).lower()
            )

        if entity_id is not None:
            clauses.append("entity_id = ?")
            parameters.append(
                self.normalize_entity_id(entity_id)
            )

        if actor is not None:
            clauses.append("actor = ?")
            parameters.append(
                self.normalize_required_text(
                    actor,
                    "O responsavel",
                )
            )

        sql = "SELECT COUNT(*) AS total FROM audit_log"

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        row = self.db.fetch_one(sql, tuple(parameters))
        return 0 if row is None else int(row["total"])


audit_repository = AuditRepository()
