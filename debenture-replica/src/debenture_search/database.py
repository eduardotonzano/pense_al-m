from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_DIR / "data" / "debenture.db"


class Database:
    """Gerencia conexoes e transacoes SQLite."""

    def __init__(
        self,
        database_path: str | Path = DEFAULT_DATABASE_PATH,
    ) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        """Abre uma conexao segura com o banco."""

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")

        foreign_keys_enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        if foreign_keys_enabled != 1:
            connection.close()
            raise RuntimeError(
                "Nao foi possivel ativar as chaves estrangeiras."
            )

        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Fornece uma conexao e garante o fechamento."""

        connection = self.connect()

        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Executa uma transacao atomica."""

        connection = self.connect()

        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def integrity_check(self) -> str:
        """Verifica a integridade estrutural do banco."""

        with self.connection() as connection:
            result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

        return str(result)

    def foreign_key_check(self) -> list[sqlite3.Row]:
        """Retorna eventuais erros de chaves estrangeiras."""

        with self.connection() as connection:
            errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

        return errors

    def table_exists(self, table_name: str) -> bool:
        """Verifica se uma tabela existe."""

        with self.connection() as connection:
            result = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = ?
                LIMIT 1
                """,
                (table_name,),
            ).fetchone()

        return result is not None

    def execute(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> int:
        """Executa uma escrita dentro de uma transacao."""

        with self.transaction() as connection:
            cursor = connection.execute(
                sql,
                parameters,
            )

            return int(cursor.lastrowid or 0)

    def fetch_one(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> sqlite3.Row | None:
        """Retorna uma linha de uma consulta."""

        with self.connection() as connection:
            result = connection.execute(
                sql,
                parameters,
            ).fetchone()

        return result

    def fetch_all(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> list[sqlite3.Row]:
        """Retorna todas as linhas de uma consulta."""

        with self.connection() as connection:
            results = connection.execute(
                sql,
                parameters,
            ).fetchall()

        return results


database = Database()