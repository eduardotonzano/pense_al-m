from dataclasses import dataclass


CONFLICT_STATUSES = {
    "open",
    "resolved",
    "ignored",
}


@dataclass(frozen=True)
class ConflictRecord:
    """Duas observacoes do mesmo assunto, campo e competencia que divergem."""

    id: int
    field_name: str
    reference_date: str
    observation_a_id: int
    observation_b_id: int
    status: str
    resolution_note: str | None
    resolved_at: str | None
    created_at: str


class ConflictRepository:
    """Consulta conflitos. Quem os abre e o ObservationRepository.

    Resolver ou ignorar conflito exige registro em audit_log e fica para
    uma etapa futura.
    """

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def row_to_record(row):
        return ConflictRecord(
            id=int(row["id"]),
            field_name=str(row["field_name"]),
            reference_date=str(row["reference_date"]),
            observation_a_id=int(row["observation_a_id"]),
            observation_b_id=int(row["observation_b_id"]),
            status=str(row["status"]),
            resolution_note=row["resolution_note"],
            resolved_at=row["resolved_at"],
            created_at=str(row["created_at"]),
        )

    def get_by_id(self, conflict_id):
        """Busca um conflito pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM data_conflicts WHERE id = ?",
            (conflict_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def list_open(self, *, field_name=None, observation_id=None):
        """Lista os conflitos abertos, com filtros opcionais."""

        clauses = ["status = 'open'"]
        parameters = []

        if field_name is not None:
            clauses.append("field_name = ?")
            parameters.append(field_name)

        if observation_id is not None:
            clauses.append("(observation_a_id = ? OR observation_b_id = ?)")
            parameters.extend([observation_id, observation_id])

        rows = self.connection.execute(
            "SELECT * FROM data_conflicts WHERE "
            + " AND ".join(clauses)
            + " ORDER BY id",
            tuple(parameters),
        ).fetchall()

        return [self.row_to_record(row) for row in rows]

    def count(self, status=None):
        """Conta conflitos, com filtro opcional de status."""

        if status is None:
            row = self.connection.execute(
                "SELECT COUNT(*) FROM data_conflicts"
            ).fetchone()
        else:
            normalized = str(status).strip().lower()

            if normalized not in CONFLICT_STATUSES:
                raise ValueError("Status de conflito invalido.")

            row = self.connection.execute(
                "SELECT COUNT(*) FROM data_conflicts WHERE status = ?",
                (normalized,),
            ).fetchone()

        return int(row[0])
