import sqlite3
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from debenture_search.database import database


ALLOWED_CONFLICT_STATUSES = {
    "open",
    "resolved",
    "ignored",
}


@dataclass(frozen=True)
class ConflictRecord:
    """Representa um conflito entre duas observacoes."""

    id: int
    debenture_id: int
    field_name: str
    observation_a_id: int
    observation_b_id: int
    status: str
    resolution_note: str | None
    resolved_at: str | None
    created_at: str


class ConflictRepository:
    """Registra e consulta conflitos entre fontes."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_field_name(field_name):
        """Normaliza o nome do campo."""

        if field_name is None:
            raise ValueError("O nome do campo e obrigatorio.")

        normalized = "_".join(
            str(field_name).strip().lower().split()
        )

        if not normalized:
            raise ValueError("O nome do campo e obrigatorio.")

        return normalized

    @staticmethod
    def normalize_status(status):
        """Valida o status do conflito."""

        normalized = str(status).strip().lower()

        if normalized not in ALLOWED_CONFLICT_STATUSES:
            raise ValueError("Status de conflito invalido.")

        return normalized

    @staticmethod
    def normalize_optional_text(value):
        """Normaliza um texto opcional."""

        if value is None:
            return None

        normalized = " ".join(str(value).split())
        return normalized or None

    @staticmethod
    def utc_now():
        """Retorna o horario atual em UTC."""

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em ConflictRecord."""

        return ConflictRecord(
            id=int(row["id"]),
            debenture_id=int(row["debenture_id"]),
            field_name=str(row["field_name"]),
            observation_a_id=int(row["observation_a_id"]),
            observation_b_id=int(row["observation_b_id"]),
            status=str(row["status"]),
            resolution_note=row["resolution_note"],
            resolved_at=row["resolved_at"],
            created_at=str(row["created_at"]),
        )

    def debenture_exists(self, debenture_id):
        """Verifica se a debenture existe."""

        row = self.db.fetch_one(
            "SELECT id FROM debentures WHERE id = ?",
            (debenture_id,),
        )
        return row is not None

    def get_observation(self, observation_id):
        """Busca os dados essenciais de uma observacao."""

        return self.db.fetch_one(
            """
            SELECT id, debenture_id, field_name, source_id
            FROM observations
            WHERE id = ?
            """,
            (observation_id,),
        )

    @staticmethod
    def canonical_pair(observation_a_id, observation_b_id):
        """Ordena os IDs para impedir conflito duplicado invertido."""

        first = int(observation_a_id)
        second = int(observation_b_id)

        if first == second:
            raise ValueError(
                "Uma observacao nao pode conflitar com ela mesma."
            )

        return min(first, second), max(first, second)

    def get_by_id(self, conflict_id):
        """Busca um conflito pelo ID."""

        row = self.db.fetch_one(
            """
            SELECT
                id, debenture_id, field_name,
                observation_a_id, observation_b_id,
                status, resolution_note, resolved_at, created_at
            FROM data_conflicts
            WHERE id = ?
            """,
            (conflict_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def find_existing(
        self,
        debenture_id,
        field_name,
        observation_a_id,
        observation_b_id,
    ):
        """Procura um conflito ja registrado."""

        first, second = self.canonical_pair(
            observation_a_id,
            observation_b_id,
        )

        row = self.db.fetch_one(
            """
            SELECT
                id, debenture_id, field_name,
                observation_a_id, observation_b_id,
                status, resolution_note, resolved_at, created_at
            FROM data_conflicts
            WHERE debenture_id = ?
              AND field_name = ?
              AND observation_a_id = ?
              AND observation_b_id = ?
            """,
            (
                debenture_id,
                field_name,
                first,
                second,
            ),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def create(
        self,
        debenture_id,
        field_name,
        observation_a_id,
        observation_b_id,
    ):
        """Cria um conflito de forma idempotente."""

        if not self.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        normalized_field = self.normalize_field_name(
            field_name
        )
        first, second = self.canonical_pair(
            observation_a_id,
            observation_b_id,
        )

        observation_a = self.get_observation(first)
        observation_b = self.get_observation(second)

        if observation_a is None or observation_b is None:
            raise ValueError(
                "Uma das observacoes informadas nao existe."
            )

        for observation in (observation_a, observation_b):
            if int(observation["debenture_id"]) != int(debenture_id):
                raise ValueError(
                    "As observacoes devem pertencer a debenture informada."
                )

            if str(observation["field_name"]) != normalized_field:
                raise ValueError(
                    "As observacoes devem pertencer ao mesmo campo."
                )

        if int(observation_a["source_id"]) == int(
            observation_b["source_id"]
        ):
            raise ValueError(
                "Um conflito exige observacoes de fontes diferentes."
            )

        existing = self.find_existing(
            debenture_id,
            normalized_field,
            first,
            second,
        )

        if existing is not None:
            return existing, False

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO data_conflicts (
                        debenture_id,
                        field_name,
                        observation_a_id,
                        observation_b_id,
                        status
                    )
                    VALUES (?, ?, ?, ?, 'open')
                    """,
                    (
                        debenture_id,
                        normalized_field,
                        first,
                        second,
                    ),
                )
                conflict_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            existing = self.find_existing(
                debenture_id,
                normalized_field,
                first,
                second,
            )

            if existing is not None:
                return existing, False

            raise

        created = self.get_by_id(conflict_id)

        if created is None:
            raise RuntimeError(
                "O conflito foi gravado, mas nao foi localizado."
            )

        return created, True

    def resolve(self, conflict_id, note):
        """Marca um conflito como resolvido."""

        normalized_note = self.normalize_optional_text(note)

        if normalized_note is None:
            raise ValueError(
                "A resolucao precisa de uma justificativa."
            )

        current = self.get_by_id(conflict_id)

        if current is None:
            raise ValueError("Conflito nao encontrado.")

        if current.status != "open":
            raise ValueError("O conflito ja foi encerrado.")

        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE data_conflicts
                SET
                    status = 'resolved',
                    resolution_note = ?,
                    resolved_at = ?
                WHERE id = ?
                """,
                (
                    normalized_note,
                    self.utc_now(),
                    conflict_id,
                ),
            )

        return self.get_by_id(conflict_id)

    def ignore(self, conflict_id, note=None):
        """Marca um conflito como ignorado."""

        current = self.get_by_id(conflict_id)

        if current is None:
            raise ValueError("Conflito nao encontrado.")

        if current.status != "open":
            raise ValueError("O conflito ja foi encerrado.")

        normalized_note = self.normalize_optional_text(note)

        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE data_conflicts
                SET
                    status = 'ignored',
                    resolution_note = ?,
                    resolved_at = NULL
                WHERE id = ?
                """,
                (
                    normalized_note,
                    conflict_id,
                ),
            )

        return self.get_by_id(conflict_id)

    def list_by_debenture(
        self,
        debenture_id,
        status=None,
        limit=100,
        offset=0,
    ):
        """Lista conflitos de uma debenture."""

        if not self.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))
        parameters = [debenture_id]
        status_clause = ""

        if status is not None:
            status_clause = " AND status = ?"
            parameters.append(self.normalize_status(status))

        parameters.extend([safe_limit, safe_offset])

        rows = self.db.fetch_all(
            """
            SELECT
                id, debenture_id, field_name,
                observation_a_id, observation_b_id,
                status, resolution_note, resolved_at, created_at
            FROM data_conflicts
            WHERE debenture_id = ?
            """ + status_clause + """
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(parameters),
        )

        return [self.row_to_record(row) for row in rows]

    def count(self, debenture_id=None, status=None):
        """Conta conflitos com filtros opcionais."""

        clauses = []
        parameters = []

        if debenture_id is not None:
            clauses.append("debenture_id = ?")
            parameters.append(debenture_id)

        if status is not None:
            clauses.append("status = ?")
            parameters.append(self.normalize_status(status))

        sql = "SELECT COUNT(*) AS total FROM data_conflicts"

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        row = self.db.fetch_one(sql, tuple(parameters))
        return 0 if row is None else int(row["total"])


conflict_repository = ConflictRepository()
