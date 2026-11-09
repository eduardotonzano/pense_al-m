from dataclasses import dataclass

from fundos.cnpj import normalize_cnpj


@dataclass(frozen=True)
class FundRecord:
    """Fundo identificado so pelo CNPJ."""

    id: int
    cnpj: str
    created_at: str


class FundRepository:
    """Fundos por CNPJ. Uma linha por CNPJ, mesmo com varios registros na CVM."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def row_to_record(row):
        return FundRecord(
            id=int(row["id"]),
            cnpj=str(row["cnpj"]),
            created_at=str(row["created_at"]),
        )

    def get_by_id(self, fund_id):
        """Busca um fundo pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM funds WHERE id = ?",
            (fund_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def get_by_cnpj(self, cnpj):
        """Busca um fundo pelo CNPJ (com ou sem mascara)."""

        row = self.connection.execute(
            "SELECT * FROM funds WHERE cnpj = ?",
            (normalize_cnpj(cnpj),),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def get_or_create(self, cnpj):
        """Devolve (fundo, criado). O CNPJ precisa ter DV valido."""

        normalized = normalize_cnpj(cnpj)
        existing = self.get_by_cnpj(normalized)

        if existing is not None:
            return existing, False

        cursor = self.connection.execute(
            "INSERT INTO funds (cnpj) VALUES (?)",
            (normalized,),
        )

        return self.get_by_id(cursor.lastrowid), True
