from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecord:
    """Fonte de dados cadastrada no banco."""

    id: int
    code: str
    name: str
    source_type: str
    priority: int
    active: bool
    created_at: str


class SourceRepository:
    """Le as fontes. Fontes e prioridades so mudam por migration."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def row_to_record(row):
        return SourceRecord(
            id=int(row["id"]),
            code=str(row["code"]),
            name=str(row["name"]),
            source_type=str(row["source_type"]),
            priority=int(row["priority"]),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
        )

    def get_by_id(self, source_id):
        """Busca uma fonte pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def get_by_code(self, code):
        """Busca uma fonte pelo codigo (sem diferenciar maiusculas)."""

        if not isinstance(code, str) or not code.strip():
            raise ValueError("O codigo da fonte e obrigatorio.")

        row = self.connection.execute(
            "SELECT * FROM sources WHERE code = ?",
            (code.strip().upper(),),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def list_all(self, active=None):
        """Lista as fontes da maior para a menor prioridade."""

        if active is None:
            rows = self.connection.execute(
                "SELECT * FROM sources ORDER BY priority DESC, code"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM sources WHERE active = ? "
                "ORDER BY priority DESC, code",
                (int(bool(active)),),
            ).fetchall()

        return [self.row_to_record(row) for row in rows]
