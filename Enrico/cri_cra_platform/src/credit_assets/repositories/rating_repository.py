"""Ratings (migration 003): agencia e nota como estao no documento, com a pagina ou o
caminho do campo de onde vieram. Nada vai para a ficha sem revisao humana."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

REVIEW_STATUSES = ("pending_review", "verified", "rejected")


@dataclass(frozen=True)
class Rating:
    asset_id: int
    agency: str
    grade: str
    rating_date: str
    document_id: int
    version_id: int
    quoted_text: str
    page: int | None = None
    source_ref: str | None = None


class RatingRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add(
        self,
        rating: Rating,
        *,
        run_id: str,
        parser_version: str,
        collected_at: str | None = None,
    ) -> bool:
        """Grava como ``pending_review`` sem confirmar a transacao.

        Devolve False quando a mesma nota do mesmo arquivo ja estava gravada. Dado fora
        das regras do schema levanta ``sqlite3.IntegrityError``.
        """

        agency, grade = rating.agency.strip(), rating.grade.strip()
        already = self.connection.execute(
            """SELECT 1 FROM ratings
               WHERE version_id = ? AND agency = ? AND grade = ? AND rating_date = ?""",
            (rating.version_id, agency, grade, rating.rating_date),
        ).fetchone()

        if already is not None:
            return False

        self.connection.execute(
            """INSERT INTO ratings (
                asset_id, agency, grade, rating_date, document_id, version_id, page,
                source_ref, quoted_text, collected_at, parser_version, run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rating.asset_id, agency, grade, rating.rating_date, rating.document_id,
                rating.version_id, rating.page, rating.source_ref, rating.quoted_text.strip(),
                collected_at or datetime.now(timezone.utc).isoformat(), parser_version, run_id,
            ),
        )
        return True

    def review(
        self,
        rating_id: int,
        status: str,
        reviewed_at: str | None = None,
    ) -> None:
        """Marca a revisao humana. ``pending_review`` desfaz e limpa a data."""

        if status not in REVIEW_STATUSES:
            raise ValueError(f"Status de revisao invalido: {status!r}")

        stamp = (
            None
            if status == "pending_review"
            else reviewed_at or datetime.now(timezone.utc).isoformat()
        )
        updated = self.connection.execute(
            "UPDATE ratings SET review_status = ?, reviewed_at = ? WHERE rating_id = ?",
            (status, stamp, rating_id),
        ).rowcount

        if updated != 1:
            raise ValueError(f"Rating inexistente: {rating_id}")

    def list_for_asset(self, asset_id: int, *, verified_only: bool = False) -> list[sqlite3.Row]:
        table = "ratings_verified" if verified_only else "ratings"
        return self.connection.execute(
            f"SELECT * FROM {table} WHERE asset_id = ? ORDER BY rating_date, rating_id",
            (asset_id,),
        ).fetchall()
