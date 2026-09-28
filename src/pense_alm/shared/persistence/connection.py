"""Conexao SQLite da camada compartilhada."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection, Row, connect

from pense_alm.shared.entities import RepositoryValidationError


class SQLiteConnectionManager:
    """Gerencia conexoes e transacoes SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        if not isinstance(database_path, (str, Path)):
            raise RepositoryValidationError(
                "database_path deve ser texto ou Path."
            )

        if isinstance(database_path, str) and not database_path.strip():
            raise RepositoryValidationError(
                "database_path nao pode ser vazio."
            )

        self._database_path = Path(database_path)

    @property
    def database_path(self) -> Path:
        """Retorna o caminho configurado para o banco."""

        return self._database_path

    def connect(self) -> Connection:
        """Abre uma conexao SQLite configurada."""

        if self._database_path != Path(":memory:"):
            self._database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        connection = connect(
            str(self._database_path),
            timeout=30,
        )

        connection.row_factory = Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")

        return connection

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Abre uma transacao com commit ou rollback."""

        connection = self.connect()

        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read_connection(self) -> Iterator[Connection]:
        """Abre uma conexao destinada a consultas."""

        connection = self.connect()

        try:
            yield connection
        finally:
            connection.close()
