from dataclasses import dataclass

from fundos.cnpj import normalize_cnpj
from fundos.repositories import IdentityConflictError


@dataclass(frozen=True)
class FundClassRecord:
    """Classe de cotas identificada pelo CNPJ da classe."""

    id: int
    fund_id: int
    cnpj: str
    created_at: str


class FundClassRepository:
    """Classes por CNPJ. O vinculo com o fundo nunca e trocado."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def row_to_record(row):
        return FundClassRecord(
            id=int(row["id"]),
            fund_id=int(row["fund_id"]),
            cnpj=str(row["cnpj"]),
            created_at=str(row["created_at"]),
        )

    def get_by_id(self, fund_class_id):
        """Busca uma classe pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM fund_classes WHERE id = ?",
            (fund_class_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def get_by_cnpj(self, cnpj):
        """Busca uma classe pelo CNPJ (com ou sem mascara)."""

        row = self.connection.execute(
            "SELECT * FROM fund_classes WHERE cnpj = ?",
            (normalize_cnpj(cnpj),),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def list_by_fund(self, fund_id):
        """Lista as classes de um fundo."""

        rows = self.connection.execute(
            "SELECT * FROM fund_classes WHERE fund_id = ? ORDER BY cnpj",
            (fund_id,),
        ).fetchall()

        return [self.row_to_record(row) for row in rows]

    def get_or_create(self, cnpj, fund_id):
        """Devolve (classe, criada).

        O mesmo CNPJ de classe ligado a outro fundo e conflito de
        identificador: bloqueia e nao grava nada.
        """

        normalized = normalize_cnpj(cnpj)
        fund = self.connection.execute(
            "SELECT id FROM funds WHERE id = ?",
            (fund_id,),
        ).fetchone()

        if fund is None:
            raise ValueError("O fundo informado nao existe.")

        existing = self.get_by_cnpj(normalized)

        if existing is not None:
            if existing.fund_id != int(fund_id):
                raise IdentityConflictError(
                    "O CNPJ de classe ja esta ligado a outro fundo; "
                    "o vinculo nao e trocado e o caso vai para revisao."
                )

            return existing, False

        cursor = self.connection.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (?, ?)",
            (fund_id, normalized),
        )

        return self.get_by_id(cursor.lastrowid), True
