import sqlite3
from dataclasses import dataclass

from debenture_search.database import database


ALLOWED_SOURCE_TYPES = {
    "scraper",
    "api",
    "manual",
    "document",
    "internal",
}


@dataclass(frozen=True)
class SourceRecord:
    """Representa uma fonte de dados armazenada no banco."""

    id: int
    code: str
    name: str
    source_type: str
    priority: int
    active: bool
    created_at: str


class SourceRepository:
    """Gerencia as fontes utilizadas pelo sistema."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_code(code):
        """Normaliza e valida o codigo da fonte."""

        if code is None:
            raise ValueError("O codigo da fonte e obrigatorio.")

        normalized = "_".join(
            str(code).strip().upper().split()
        )

        if not normalized:
            raise ValueError("O codigo da fonte e obrigatorio.")

        return normalized

    @staticmethod
    def normalize_name(name):
        """Normaliza e valida o nome da fonte."""

        if name is None:
            raise ValueError("O nome da fonte e obrigatorio.")

        normalized = " ".join(str(name).split())

        if not normalized:
            raise ValueError("O nome da fonte e obrigatorio.")

        return normalized

    @staticmethod
    def normalize_source_type(source_type):
        """Normaliza e valida o tipo da fonte."""

        if source_type is None:
            raise ValueError("O tipo da fonte e obrigatorio.")

        normalized = str(source_type).strip().lower()

        if normalized not in ALLOWED_SOURCE_TYPES:
            raise ValueError("Tipo de fonte invalido.")

        return normalized

    @staticmethod
    def normalize_priority(priority):
        """Normaliza e valida a prioridade da fonte."""

        try:
            normalized = int(priority)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "A prioridade deve ser um numero inteiro."
            ) from error

        if normalized < 0:
            raise ValueError(
                "A prioridade nao pode ser negativa."
            )

        return normalized

    @staticmethod
    def normalize_active(active):
        """Normaliza um indicador de ativacao."""

        if isinstance(active, bool):
            return active

        if active in (0, 1):
            return bool(active)

        normalized = str(active).strip().lower()

        if normalized in {"true", "sim", "yes", "1"}:
            return True

        if normalized in {"false", "nao", "no", "0"}:
            return False

        raise ValueError("Indicador de ativacao invalido.")

    @staticmethod
    def row_to_record(row):
        """Converte uma linha SQLite em SourceRecord."""

        return SourceRecord(
            id=int(row["id"]),
            code=str(row["code"]),
            name=str(row["name"]),
            source_type=str(row["source_type"]),
            priority=int(row["priority"]),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
        )

    def create(
        self,
        code,
        name,
        source_type,
        priority=0,
        active=True,
    ):
        """Cria uma fonte sem permitir codigo duplicado."""

        normalized_code = self.normalize_code(code)
        normalized_name = self.normalize_name(name)
        normalized_type = self.normalize_source_type(
            source_type
        )
        normalized_priority = self.normalize_priority(
            priority
        )
        normalized_active = self.normalize_active(active)

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO sources (
                        code,
                        name,
                        source_type,
                        priority,
                        active
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_code,
                        normalized_name,
                        normalized_type,
                        normalized_priority,
                        int(normalized_active),
                    ),
                )
                source_id = cursor.lastrowid
        except sqlite3.IntegrityError as error:
            existing = self.get_by_code(normalized_code)

            if existing is not None:
                raise ValueError(
                    "Ja existe uma fonte com esse codigo."
                ) from error

            raise ValueError(
                "Nao foi possivel cadastrar a fonte."
            ) from error

        created = self.get_by_id(source_id)

        if created is None:
            raise RuntimeError(
                "A fonte foi gravada, mas nao foi localizada."
            )

        return created

    def get_or_create(
        self,
        code,
        name,
        source_type,
        priority=0,
        active=True,
    ):
        """Retorna uma fonte existente ou cria uma nova."""

        normalized_code = self.normalize_code(code)
        existing = self.get_by_code(normalized_code)

        if existing is not None:
            return existing, False

        created = self.create(
            code=normalized_code,
            name=name,
            source_type=source_type,
            priority=priority,
            active=active,
        )

        return created, True

    def get_by_id(self, source_id):
        """Busca uma fonte pelo ID."""

        row = self.db.fetch_one(
            """
            SELECT
                id, code, name, source_type,
                priority, active, created_at
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_code(self, code):
        """Busca uma fonte pelo codigo."""

        normalized_code = self.normalize_code(code)
        row = self.db.fetch_one(
            """
            SELECT
                id, code, name, source_type,
                priority, active, created_at
            FROM sources
            WHERE code = ?
            """,
            (normalized_code,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def list_all(
        self,
        active=None,
        limit=100,
        offset=0,
    ):
        """Lista fontes com filtro e paginacao."""

        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))

        if active is None:
            rows = self.db.fetch_all(
                """
                SELECT
                    id, code, name, source_type,
                    priority, active, created_at
                FROM sources
                ORDER BY priority DESC, code
                LIMIT ? OFFSET ?
                """,
                (safe_limit, safe_offset),
            )
        else:
            normalized_active = self.normalize_active(active)
            rows = self.db.fetch_all(
                """
                SELECT
                    id, code, name, source_type,
                    priority, active, created_at
                FROM sources
                WHERE active = ?
                ORDER BY priority DESC, code
                LIMIT ? OFFSET ?
                """,
                (
                    int(normalized_active),
                    safe_limit,
                    safe_offset,
                ),
            )

        return [self.row_to_record(row) for row in rows]

    def list_active(self):
        """Lista somente fontes ativas por prioridade."""

        return self.list_all(active=True, limit=500)

    def update(
        self,
        source_id,
        name=None,
        source_type=None,
        priority=None,
        active=None,
    ):
        """Atualiza os atributos permitidos de uma fonte."""

        current = self.get_by_id(source_id)

        if current is None:
            raise ValueError("Fonte nao encontrada.")

        final_name = (
            current.name
            if name is None
            else self.normalize_name(name)
        )
        final_type = (
            current.source_type
            if source_type is None
            else self.normalize_source_type(source_type)
        )
        final_priority = (
            current.priority
            if priority is None
            else self.normalize_priority(priority)
        )
        final_active = (
            current.active
            if active is None
            else self.normalize_active(active)
        )

        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE sources
                SET
                    name = ?,
                    source_type = ?,
                    priority = ?,
                    active = ?
                WHERE id = ?
                """,
                (
                    final_name,
                    final_type,
                    final_priority,
                    int(final_active),
                    source_id,
                ),
            )

        return self.get_by_id(source_id)

    def activate(self, source_id):
        """Ativa uma fonte."""

        return self.update(source_id, active=True)

    def deactivate(self, source_id):
        """Desativa uma fonte sem apagar seu historico."""

        return self.update(source_id, active=False)

    def update_priority(self, source_id, priority):
        """Altera a prioridade de uma fonte."""

        return self.update(source_id, priority=priority)

    def count(self, active=None):
        """Conta fontes com filtro opcional."""

        if active is None:
            row = self.db.fetch_one(
                "SELECT COUNT(*) AS total FROM sources"
            )
        else:
            normalized_active = self.normalize_active(active)
            row = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total
                FROM sources
                WHERE active = ?
                """,
                (int(normalized_active),),
            )

        return 0 if row is None else int(row["total"])


source_repository = SourceRepository()
