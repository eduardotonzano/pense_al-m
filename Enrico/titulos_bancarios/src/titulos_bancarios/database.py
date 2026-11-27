"""Conexoes SQLite do banco de titulos bancarios.

Nao existe banco padrao: o caminho e sempre informado. connect() recusa um
arquivo inexistente; so connect(create=True) cria, para que um caminho
digitado errado nunca vire um banco vazio. As conexoes saem em modo
autocommit (isolation_level None): quem escreve abre a transacao
explicitamente.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    """Abre conexoes com chaves estrangeiras ativas."""

    def __init__(self, database_path: str | Path) -> None:
        if database_path is None or not str(database_path).strip():
            raise ValueError("O caminho do banco e obrigatorio.")

        self.database_path = Path(database_path)

    def connect(self, create: bool = False) -> sqlite3.Connection:
        if not create and not self.database_path.is_file():
            raise FileNotFoundError(
                "Banco nao encontrado: " + str(self.database_path)
            )

        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")

        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            connection.close()
            raise RuntimeError(
                "Nao foi possivel ativar as chaves estrangeiras."
            )

        return connection

    def connect_read_only(self) -> sqlite3.Connection:
        """Abre um banco existente so para leitura (PRAGMA query_only)."""

        connection = self.connect()
        connection.execute("PRAGMA query_only = ON")
        return connection
