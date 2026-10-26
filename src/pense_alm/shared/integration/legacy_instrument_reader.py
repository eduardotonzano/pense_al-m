"""Leitura controlada de debentures do banco legado."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from .records import DebentureInstrumentRecord


@dataclass(frozen=True, slots=True)
class LegacyInstrumentReadError:
    """Linha legada que nao virou registro intermediario."""

    legacy_id: int
    error_type: str
    message: str


class LegacyDebentureInstrumentReader:
    """Le debentures legadas sem alterar o banco de origem."""

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
        """Conta as debentures disponiveis."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM debentures
                """
            ).fetchone()

        return int(row["total"])

    def iter_records(
        self,
        batch_size: int = 100,
    ) -> Iterator[
        DebentureInstrumentRecord
        | LegacyInstrumentReadError
    ]:
        """Percorre debentures em lotes deterministicos.

        Uma linha invalida nao interrompe a leitura: ela volta
        como LegacyInstrumentReadError.
        """

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
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT
                        debenture.id AS id,
                        debenture.asset_code AS asset_code,
                        debenture.isin AS isin,
                        debenture.status AS status,
                        debenture.created_at AS created_at,
                        debenture.updated_at AS updated_at,
                        debenture.issuer_id AS issuer_id,
                        issuer.cnpj AS issuer_cnpj
                    FROM debentures AS debenture
                    LEFT JOIN issuers AS issuer
                        ON issuer.id = debenture.issuer_id
                    ORDER BY debenture.id
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
                try:
                    yield self._to_record(row)
                except (TypeError, ValueError) as error:
                    yield LegacyInstrumentReadError(
                        legacy_id=int(row["id"]),
                        error_type=type(error).__name__,
                        message=str(error),
                    )

            offset += len(rows)

    @staticmethod
    def _to_record(
        row: sqlite3.Row,
    ) -> DebentureInstrumentRecord:
        issuer_id = row["issuer_id"]

        return DebentureInstrumentRecord(
            legacy_id=int(row["id"]),
            asset_code=row["asset_code"],
            isin=row["isin"],
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            issuer_legacy_id=(
                None if issuer_id is None else int(issuer_id)
            ),
            issuer_cnpj=row["issuer_cnpj"],
        )

    def _connect(self) -> sqlite3.Connection:
        """Abre conexao protegida contra gravacoes."""

        connection = sqlite3.connect(
            str(self._database_path),
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")

        return connection
