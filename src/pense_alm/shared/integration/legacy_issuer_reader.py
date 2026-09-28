"""Leitura controlada de emissores do banco legado."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from .records import DebentureIssuerRecord


class LegacyDebentureIssuerReader:
    """Le emissores legados sem alterar o banco de origem."""

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        if not isinstance(database_path, (str, Path)):
            raise TypeError(
                "database_path deve ser texto ou Path."
            )

        if isinstance(database_path, str) and not database_path.strip():
            raise ValueError(
                "database_path nao pode ser vazio."
            )

        self._database_path = Path(database_path)

        if not self._database_path.is_file():
            raise FileNotFoundError(
                f"Banco legado nao encontrado: "
                f"{self._database_path}"
            )

    @property
    def database_path(self) -> Path:
        """Retorna o caminho do banco legado."""

        return self._database_path

    def count(self) -> int:
        """Conta os emissores disponíveis."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM issuers
                """
            ).fetchone()

        return int(row["total"])

    def iter_records(
        self,
        batch_size: int = 100,
    ) -> Iterator[DebentureIssuerRecord]:
        """Percorre emissores em lotes determinísticos."""

        if not isinstance(batch_size, int):
            raise TypeError(
                "batch_size deve ser inteiro."
            )

        if batch_size <= 0:
            raise ValueError(
                "batch_size deve ser maior que zero."
            )

        offset = 0

        while True:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        cnpj,
                        legal_name,
                        trade_name,
                        created_at,
                        updated_at
                    FROM issuers
                    ORDER BY id
                    LIMIT ?
                    OFFSET ?
                    """,
                    (
                        batch_size,
                        offset,
                    ),
                ).fetchall()

            if not rows:
                return

            for row in rows:
                yield DebentureIssuerRecord(
                    legacy_id=int(row["id"]),
                    cnpj=row["cnpj"],
                    legal_name=str(row["legal_name"]),
                    trade_name=row["trade_name"],
                    created_at=str(row["created_at"]),
                    updated_at=str(row["updated_at"]),
                )

            offset += len(rows)

    def _connect(self) -> sqlite3.Connection:
        """Abre conexao protegida contra gravacoes."""

        connection = sqlite3.connect(
            str(self._database_path),
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")

        return connection
