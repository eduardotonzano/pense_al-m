from dataclasses import dataclass
import sqlite3

from debenture_search.database import Database
from debenture_search.database import database


@dataclass(frozen=True)
class IssuerRecord:
    """Representa um emissor armazenado no banco."""

    id: int
    cnpj: str | None
    legal_name: str
    trade_name: str | None
    created_at: str
    updated_at: str


class IssuerRepository:
    """Gerencia o cadastro e a consulta de emissores."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_cnpj(cnpj):
        """Remove a pontuacao e valida o tamanho do CNPJ."""

        if cnpj is None:
            return None

        normalized = "".join(
            character
            for character in str(cnpj)
            if character.isdigit()
        )

        if len(normalized) != 14:
            raise ValueError(
                "O CNPJ deve conter exatamente 14 digitos."
            )

        return normalized

    @staticmethod
    def normalize_name(name):
        """Remove espacos duplicados e valida o nome."""

        if name is None:
            raise ValueError(
                "A razao social nao pode ficar vazia."
            )

        normalized = " ".join(str(name).split())

        if not normalized:
            raise ValueError(
                "A razao social nao pode ficar vazia."
            )

        return normalized

    @staticmethod
    def normalize_optional_name(name):
        """Normaliza um nome opcional."""

        if name is None:
            return None

        normalized = " ".join(str(name).split())

        if not normalized:
            return None

        return normalized

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em IssuerRecord."""

        return IssuerRecord(
            id=int(row["id"]),
            cnpj=row["cnpj"],
            legal_name=str(row["legal_name"]),
            trade_name=row["trade_name"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def create(
        self,
        legal_name,
        cnpj=None,
        trade_name=None,
    ):
        """Cria um emissor e rejeita CNPJ duplicado."""

        normalized_name = self.normalize_name(
            legal_name
        )

        normalized_cnpj = self.normalize_cnpj(
            cnpj
        )

        normalized_trade_name = (
            self.normalize_optional_name(trade_name)
        )

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO issuers (
                        cnpj,
                        legal_name,
                        trade_name
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        normalized_cnpj,
                        normalized_name,
                        normalized_trade_name,
                    ),
                )

                issuer_id = cursor.lastrowid

                row = connection.execute(
                    """
                    SELECT
                        id,
                        cnpj,
                        legal_name,
                        trade_name,
                        created_at,
                        updated_at
                    FROM issuers
                    WHERE id = ?
                    """,
                    (issuer_id,),
                ).fetchone()

        except sqlite3.IntegrityError as error:
            if normalized_cnpj is not None:
                existing = self.get_by_cnpj(
                    normalized_cnpj
                )

                if existing is not None:
                    raise ValueError(
                        "Ja existe um emissor com esse CNPJ."
                    ) from error

            raise ValueError(
                "Nao foi possivel cadastrar o emissor."
            ) from error

        if row is None:
            raise RuntimeError(
                "O emissor foi gravado, "
                "mas nao foi localizado."
            )

        return self.row_to_record(row)

    def get_or_create(
        self,
        legal_name,
        cnpj=None,
        trade_name=None,
    ):
        """
        Retorna um emissor existente ou cria um novo.

        O segundo valor retornado informa se o emissor
        foi criado nesta operacao.
        """

        normalized_cnpj = self.normalize_cnpj(
            cnpj
        )

        if normalized_cnpj is not None:
            existing = self.get_by_cnpj(
                normalized_cnpj
            )

            if existing is not None:
                return existing, False

        created = self.create(
            legal_name=legal_name,
            cnpj=normalized_cnpj,
            trade_name=trade_name,
        )

        return created, True

    def get_by_id(self, issuer_id):
        """Busca um emissor pelo identificador interno."""

        row = self.db.fetch_one(
            """
            SELECT
                id,
                cnpj,
                legal_name,
                trade_name,
                created_at,
                updated_at
            FROM issuers
            WHERE id = ?
            """,
            (issuer_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_cnpj(self, cnpj):
        """Busca um emissor pelo CNPJ."""

        normalized_cnpj = self.normalize_cnpj(
            cnpj
        )

        row = self.db.fetch_one(
            """
            SELECT
                id,
                cnpj,
                legal_name,
                trade_name,
                created_at,
                updated_at
            FROM issuers
            WHERE cnpj = ?
            """,
            (normalized_cnpj,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def search_by_name(
        self,
        query,
        limit=50,
    ):
        """Pesquisa por razao social ou nome fantasia."""

        if query is None:
            return []

        normalized_query = " ".join(
            str(query).split()
        )

        if not normalized_query:
            return []

        safe_limit = int(limit)

        if safe_limit < 1:
            safe_limit = 1

        if safe_limit > 200:
            safe_limit = 200

        pattern = "%" + normalized_query + "%"

        rows = self.db.fetch_all(
            """
            SELECT
                id,
                cnpj,
                legal_name,
                trade_name,
                created_at,
                updated_at
            FROM issuers
            WHERE legal_name LIKE ? COLLATE NOCASE
               OR trade_name LIKE ? COLLATE NOCASE
            ORDER BY legal_name, id
            LIMIT ?
            """,
            (
                pattern,
                pattern,
                safe_limit,
            ),
        )

        return [
            self.row_to_record(row)
            for row in rows
        ]

    def list_all(
        self,
        limit=100,
        offset=0,
    ):
        """Lista emissores de forma paginada."""

        safe_limit = int(limit)
        safe_offset = int(offset)

        if safe_limit < 1:
            safe_limit = 1

        if safe_limit > 500:
            safe_limit = 500

        if safe_offset < 0:
            safe_offset = 0

        rows = self.db.fetch_all(
            """
            SELECT
                id,
                cnpj,
                legal_name,
                trade_name,
                created_at,
                updated_at
            FROM issuers
            ORDER BY legal_name, id
            LIMIT ?
            OFFSET ?
            """,
            (
                safe_limit,
                safe_offset,
            ),
        )

        return [
            self.row_to_record(row)
            for row in rows
        ]

    def count(self):
        """Retorna a quantidade total de emissores."""

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM issuers
            """
        )

        if row is None:
            return 0

        return int(row["total"])

    def update(
        self,
        issuer_id,
        legal_name,
        trade_name=None,
    ):
        """Atualiza os nomes de um emissor existente."""

        normalized_name = self.normalize_name(
            legal_name
        )

        normalized_trade_name = (
            self.normalize_optional_name(trade_name)
        )

        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE issuers
                SET
                    legal_name = ?,
                    trade_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    normalized_name,
                    normalized_trade_name,
                    issuer_id,
                ),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Emissor nao encontrado."
                )

            row = connection.execute(
                """
                SELECT
                    id,
                    cnpj,
                    legal_name,
                    trade_name,
                    created_at,
                    updated_at
                FROM issuers
                WHERE id = ?
                """,
                (issuer_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "O emissor foi atualizado, "
                "mas nao foi localizado."
            )

        return self.row_to_record(row)


issuer_repository = IssuerRepository()