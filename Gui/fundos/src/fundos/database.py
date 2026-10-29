"""Conexoes SQLite e formatos de data gravados no banco de Fundos.

Nao existe banco padrao: o caminho e sempre informado. connect() recusa um
arquivo inexistente; so connect(create=True) cria, para que um caminho
digitado errado nunca vire um banco vazio.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Iterator


ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class Database:
    """Abre conexoes com chaves estrangeiras ativas e transacoes explicitas."""

    def __init__(self, database_path: str | Path) -> None:
        if database_path is None or not str(database_path).strip():
            raise ValueError("O caminho do banco e obrigatorio.")

        self.database_path = Path(database_path)

    def connect(self, create: bool = False) -> sqlite3.Connection:
        """Abre uma conexao em modo autocommit (transacoes explicitas)."""

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
        """Executa uma transacao atomica; desfaz tudo em caso de erro."""

        connection = self.connect()

        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")

            raise
        finally:
            connection.close()

    def integrity_check(self) -> str:
        """Retorna o resultado de PRAGMA integrity_check."""

        with self.connection() as connection:
            return str(
                connection.execute("PRAGMA integrity_check").fetchone()[0]
            )

    def foreign_key_check(self) -> list[sqlite3.Row]:
        """Retorna os erros de chave estrangeira (lista vazia se nao houver)."""

        with self.connection() as connection:
            return connection.execute("PRAGMA foreign_key_check").fetchall()


def utc_now() -> str:
    """Horario atual em UTC, no formato gravado no banco."""

    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def normalize_timestamp(value: str | datetime, label: str) -> str:
    """Converte data e hora com fuso para UTC ISO com microssegundos.

    Recusa data e hora sem fuso: o banco so guarda horarios em UTC.
    """

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(label + " invalida.") from error
    else:
        raise ValueError(label + " e obrigatoria.")

    if parsed.tzinfo is None:
        raise ValueError(label + " precisa ter fuso horario (UTC).")

    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def normalize_iso_date(value: str | date, label: str) -> str:
    """Valida uma data AAAA-MM-DD (sem hora)."""

    if isinstance(value, datetime):
        raise ValueError(label + " deve ser uma data, sem hora.")

    if isinstance(value, date):
        return value.isoformat()

    if not isinstance(value, str) or ISO_DATE.fullmatch(value.strip()) is None:
        raise ValueError(label + " deve estar no formato AAAA-MM-DD.")

    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError as error:
        raise ValueError(label + " invalida.") from error
