from dataclasses import dataclass
import sqlite3

from debenture_search.database import Database
from debenture_search.database import database


ALLOWED_STATUSES = {
    "unknown",
    "active",
    "inactive",
    "matured",
    "cancelled",
}


@dataclass(frozen=True)
class DebentureRecord:
    """Representa uma debenture armazenada no banco."""

    id: int
    issuer_id: int | None
    asset_code: str | None
    isin: str | None
    issue_number: str | None
    series: str | None
    status: str
    created_at: str
    updated_at: str
    inactive_at: str | None


class DebentureRepository:
    """Gerencia o cadastro e a consulta de debentures."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_asset_code(asset_code):
        """Normaliza o codigo do ativo."""

        if asset_code is None:
            return None

        normalized = "".join(
            str(asset_code).upper().split()
        )

        if not normalized:
            return None

        return normalized

    @staticmethod
    def normalize_isin(isin):
        """Normaliza e valida o ISIN."""

        if isin is None:
            return None

        normalized = "".join(
            str(isin).upper().split()
        )

        if not normalized:
            return None

        if len(normalized) != 12:
            raise ValueError(
                "O ISIN deve conter exatamente 12 caracteres."
            )

        if not normalized.isalnum():
            raise ValueError(
                "O ISIN deve conter somente letras e numeros."
            )

        return normalized

    @staticmethod
    def normalize_optional_text(value):
        """Normaliza um texto opcional."""

        if value is None:
            return None

        normalized = " ".join(str(value).split())

        if not normalized:
            return None

        return normalized

    @staticmethod
    def normalize_status(status):
        """Normaliza e valida o status."""

        if status is None:
            return "unknown"

        normalized = str(status).strip().lower()

        if normalized not in ALLOWED_STATUSES:
            raise ValueError(
                "Status de debenture invalido."
            )

        return normalized

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em DebentureRecord."""

        return DebentureRecord(
            id=int(row["id"]),
            issuer_id=row["issuer_id"],
            asset_code=row["asset_code"],
            isin=row["isin"],
            issue_number=row["issue_number"],
            series=row["series"],
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            inactive_at=row["inactive_at"],
        )

    def issuer_exists(self, issuer_id):
        """Verifica se o emissor existe."""

        if issuer_id is None:
            return True

        row = self.db.fetch_one(
            """
            SELECT id
            FROM issuers
            WHERE id = ?
            """,
            (issuer_id,),
        )

        return row is not None

    def create(
        self,
        asset_code=None,
        isin=None,
        issuer_id=None,
        issue_number=None,
        series=None,
        status="unknown",
    ):
        """Cria uma debenture sem permitir duplicidades."""

        normalized_asset_code = (
            self.normalize_asset_code(asset_code)
        )

        normalized_isin = self.normalize_isin(isin)

        normalized_issue_number = (
            self.normalize_optional_text(issue_number)
        )

        normalized_series = self.normalize_optional_text(
            series
        )

        normalized_status = self.normalize_status(status)

        if (
            normalized_asset_code is None
            and normalized_isin is None
        ):
            raise ValueError(
                "Informe o codigo do ativo ou o ISIN."
            )

        if not self.issuer_exists(issuer_id):
            raise ValueError(
                "O emissor informado nao existe."
            )

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO debentures (
                        issuer_id,
                        asset_code,
                        isin,
                        issue_number,
                        series,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        issuer_id,
                        normalized_asset_code,
                        normalized_isin,
                        normalized_issue_number,
                        normalized_series,
                        normalized_status,
                    ),
                )

                debenture_id = cursor.lastrowid

                row = connection.execute(
                    """
                    SELECT
                        id,
                        issuer_id,
                        asset_code,
                        isin,
                        issue_number,
                        series,
                        status,
                        created_at,
                        updated_at,
                        inactive_at
                    FROM debentures
                    WHERE id = ?
                    """,
                    (debenture_id,),
                ).fetchone()

        except sqlite3.IntegrityError as error:
            if normalized_asset_code is not None:
                existing = self.get_by_asset_code(
                    normalized_asset_code
                )

                if existing is not None:
                    raise ValueError(
                        "Ja existe uma debenture "
                        "com esse codigo de ativo."
                    ) from error

            if normalized_isin is not None:
                existing = self.get_by_isin(
                    normalized_isin
                )

                if existing is not None:
                    raise ValueError(
                        "Ja existe uma debenture "
                        "com esse ISIN."
                    ) from error

            raise ValueError(
                "Nao foi possivel cadastrar a debenture."
            ) from error

        if row is None:
            raise RuntimeError(
                "A debenture foi gravada, "
                "mas nao foi localizada."
            )

        return self.row_to_record(row)

    def get_or_create(
        self,
        asset_code=None,
        isin=None,
        issuer_id=None,
        issue_number=None,
        series=None,
        status="unknown",
    ):
        """
        Localiza uma debenture existente ou cria uma nova.

        O segundo valor retornado informa se o registro foi criado.
        """

        normalized_asset_code = (
            self.normalize_asset_code(asset_code)
        )

        normalized_isin = self.normalize_isin(isin)

        if normalized_asset_code is not None:
            existing = self.get_by_asset_code(
                normalized_asset_code
            )

            if existing is not None:
                return existing, False

        if normalized_isin is not None:
            existing = self.get_by_isin(
                normalized_isin
            )

            if existing is not None:
                return existing, False

        created = self.create(
            asset_code=normalized_asset_code,
            isin=normalized_isin,
            issuer_id=issuer_id,
            issue_number=issue_number,
            series=series,
            status=status,
        )

        return created, True

    def get_by_id(self, debenture_id):
        """Busca uma debenture pelo identificador interno."""

        row = self.db.fetch_one(
            """
            SELECT
                id,
                issuer_id,
                asset_code,
                isin,
                issue_number,
                series,
                status,
                created_at,
                updated_at,
                inactive_at
            FROM debentures
            WHERE id = ?
            """,
            (debenture_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_asset_code(self, asset_code):
        """Busca uma debenture pelo codigo do ativo."""

        normalized_asset_code = (
            self.normalize_asset_code(asset_code)
        )

        if normalized_asset_code is None:
            return None

        row = self.db.fetch_one(
            """
            SELECT
                id,
                issuer_id,
                asset_code,
                isin,
                issue_number,
                series,
                status,
                created_at,
                updated_at,
                inactive_at
            FROM debentures
            WHERE asset_code = ?
            """,
            (normalized_asset_code,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_isin(self, isin):
        """Busca uma debenture pelo ISIN."""

        normalized_isin = self.normalize_isin(isin)

        if normalized_isin is None:
            return None

        row = self.db.fetch_one(
            """
            SELECT
                id,
                issuer_id,
                asset_code,
                isin,
                issue_number,
                series,
                status,
                created_at,
                updated_at,
                inactive_at
            FROM debentures
            WHERE isin = ?
            """,
            (normalized_isin,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def list_by_issuer(
        self,
        issuer_id,
        limit=100,
        offset=0,
    ):
        """Lista as debentures de um emissor."""

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
                issuer_id,
                asset_code,
                isin,
                issue_number,
                series,
                status,
                created_at,
                updated_at,
                inactive_at
            FROM debentures
            WHERE issuer_id = ?
            ORDER BY asset_code, isin, id
            LIMIT ?
            OFFSET ?
            """,
            (
                issuer_id,
                safe_limit,
                safe_offset,
            ),
        )

        return [
            self.row_to_record(row)
            for row in rows
        ]

    def search(
        self,
        query,
        limit=50,
    ):
        """Pesquisa por codigo, ISIN, emissor ou serie."""

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
            SELECT DISTINCT
                d.id,
                d.issuer_id,
                d.asset_code,
                d.isin,
                d.issue_number,
                d.series,
                d.status,
                d.created_at,
                d.updated_at,
                d.inactive_at
            FROM debentures AS d
            LEFT JOIN issuers AS i
                ON i.id = d.issuer_id
            WHERE d.asset_code LIKE ? COLLATE NOCASE
               OR d.isin LIKE ? COLLATE NOCASE
               OR d.issue_number LIKE ? COLLATE NOCASE
               OR d.series LIKE ? COLLATE NOCASE
               OR i.legal_name LIKE ? COLLATE NOCASE
               OR i.trade_name LIKE ? COLLATE NOCASE
            ORDER BY d.asset_code, d.isin, d.id
            LIMIT ?
            """,
            (
                pattern,
                pattern,
                pattern,
                pattern,
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
        status=None,
    ):
        """Lista debentures com paginacao."""

        safe_limit = int(limit)
        safe_offset = int(offset)

        if safe_limit < 1:
            safe_limit = 1

        if safe_limit > 500:
            safe_limit = 500

        if safe_offset < 0:
            safe_offset = 0

        if status is None:
            rows = self.db.fetch_all(
                """
                SELECT
                    id,
                    issuer_id,
                    asset_code,
                    isin,
                    issue_number,
                    series,
                    status,
                    created_at,
                    updated_at,
                    inactive_at
                FROM debentures
                ORDER BY asset_code, isin, id
                LIMIT ?
                OFFSET ?
                """,
                (
                    safe_limit,
                    safe_offset,
                ),
            )

        else:
            normalized_status = self.normalize_status(
                status
            )

            rows = self.db.fetch_all(
                """
                SELECT
                    id,
                    issuer_id,
                    asset_code,
                    isin,
                    issue_number,
                    series,
                    status,
                    created_at,
                    updated_at,
                    inactive_at
                FROM debentures
                WHERE status = ?
                ORDER BY asset_code, isin, id
                LIMIT ?
                OFFSET ?
                """,
                (
                    normalized_status,
                    safe_limit,
                    safe_offset,
                ),
            )

        return [
            self.row_to_record(row)
            for row in rows
        ]

    def count(self, status=None):
        """Conta as debentures cadastradas."""

        if status is None:
            row = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total
                FROM debentures
                """
            )

        else:
            normalized_status = self.normalize_status(
                status
            )

            row = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total
                FROM debentures
                WHERE status = ?
                """,
                (normalized_status,),
            )

        if row is None:
            return 0

        return int(row["total"])

    def update_identification(
        self,
        debenture_id,
        asset_code=None,
        isin=None,
        issuer_id=None,
        issue_number=None,
        series=None,
    ):
        """Atualiza a identificacao de uma debenture."""

        current = self.get_by_id(debenture_id)

        if current is None:
            raise ValueError(
                "Debenture nao encontrada."
            )

        normalized_asset_code = (
            self.normalize_asset_code(asset_code)
            if asset_code is not None
            else current.asset_code
        )

        normalized_isin = (
            self.normalize_isin(isin)
            if isin is not None
            else current.isin
        )

        final_issuer_id = (
            issuer_id
            if issuer_id is not None
            else current.issuer_id
        )

        normalized_issue_number = (
            self.normalize_optional_text(issue_number)
            if issue_number is not None
            else current.issue_number
        )

        normalized_series = (
            self.normalize_optional_text(series)
            if series is not None
            else current.series
        )

        if (
            normalized_asset_code is None
            and normalized_isin is None
        ):
            raise ValueError(
                "A debenture precisa de codigo ou ISIN."
            )

        if not self.issuer_exists(final_issuer_id):
            raise ValueError(
                "O emissor informado nao existe."
            )

        try:
            with self.db.transaction() as connection:
                connection.execute(
                    """
                    UPDATE debentures
                    SET
                        issuer_id = ?,
                        asset_code = ?,
                        isin = ?,
                        issue_number = ?,
                        series = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        final_issuer_id,
                        normalized_asset_code,
                        normalized_isin,
                        normalized_issue_number,
                        normalized_series,
                        debenture_id,
                    ),
                )

        except sqlite3.IntegrityError as error:
            raise ValueError(
                "Codigo de ativo ou ISIN ja cadastrado."
            ) from error

        updated = self.get_by_id(debenture_id)

        if updated is None:
            raise RuntimeError(
                "A debenture foi atualizada, "
                "mas nao foi localizada."
            )

        return updated

    def update_status(
        self,
        debenture_id,
        status,
    ):
        """Atualiza o status sem apagar a debenture."""

        normalized_status = self.normalize_status(
            status
        )

        inactive_statuses = {
            "inactive",
            "matured",
            "cancelled",
        }

        with self.db.transaction() as connection:
            if normalized_status in inactive_statuses:
                cursor = connection.execute(
                    """
                    UPDATE debentures
                    SET
                        status = ?,
                        inactive_at = COALESCE(
                            inactive_at,
                            CURRENT_TIMESTAMP
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        normalized_status,
                        debenture_id,
                    ),
                )

            else:
                cursor = connection.execute(
                    """
                    UPDATE debentures
                    SET
                        status = ?,
                        inactive_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        normalized_status,
                        debenture_id,
                    ),
                )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Debenture nao encontrada."
                )

        updated = self.get_by_id(debenture_id)

        if updated is None:
            raise RuntimeError(
                "A debenture foi atualizada, "
                "mas nao foi localizada."
            )

        return updated


debenture_repository = DebentureRepository()