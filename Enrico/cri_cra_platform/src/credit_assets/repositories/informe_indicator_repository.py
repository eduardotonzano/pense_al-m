"""Indicadores do Informe Mensal (migration 003): cada linha aponta para o documento
e para o arquivo exato que foi lido."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

SOURCE = "fundosnet_informe_mensal_xml"


class IndicatorConflictError(ValueError):
    """O mesmo campo da mesma versao do arquivo ja esta gravado com outro valor."""


@dataclass(frozen=True)
class InformeIndicator:
    field: str
    occurrence: str
    value: str | None
    value_kind: str
    unit: str | None = None


class InformeIndicatorRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add_many(
        self,
        *,
        asset_id: int,
        document_id: int,
        version_id: int,
        reference_period: str,
        indicators: Iterable[InformeIndicator],
        run_id: str,
        parser_version: str,
        collected_at: str | None = None,
        source: str = SOURCE,
    ) -> int:
        """Grava os indicadores de uma versao do arquivo sem confirmar a transacao.

        Devolve quantas linhas entraram. Ler de novo o mesmo arquivo nao grava nada;
        o mesmo campo com outro valor levanta ``IndicatorConflictError`` antes de
        gravar qualquer linha. Dado fora das regras do schema levanta
        ``sqlite3.IntegrityError``.
        """

        existing = {
            (row["field"], row["occurrence"]): (
                row["value"], row["value_kind"], row["unit"], row["reference_period"],
            )
            for row in self.connection.execute(
                """SELECT field, occurrence, value, value_kind, unit, reference_period
                   FROM informe_indicators WHERE version_id = ?""",
                (version_id,),
            )
        }
        seen: set[tuple[str, str]] = set()
        pending = []

        for item in indicators:
            key = (item.field, item.occurrence)

            if key in seen:
                raise ValueError(f"Campo repetido na mesma leitura: {key}")

            seen.add(key)
            current = existing.get(key)
            incoming = (item.value, item.value_kind, item.unit, reference_period)

            if current is None:
                pending.append(item)
            elif current != incoming:
                raise IndicatorConflictError(
                    f"{item.field} {item.occurrence!r} ja esta gravado com outro valor "
                    f"na versao {version_id}"
                )

        stamp = collected_at or datetime.now(timezone.utc).isoformat()
        self.connection.executemany(
            """INSERT INTO informe_indicators (
                asset_id, document_id, version_id, reference_period, field, occurrence,
                value, value_kind, unit, source, collected_at, parser_version, run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    asset_id, document_id, version_id, reference_period, item.field,
                    item.occurrence, item.value, item.value_kind, item.unit, source,
                    stamp, parser_version, run_id,
                )
                for item in pending
            ],
        )
        return len(pending)

    def count_for_version(self, version_id: int) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM informe_indicators WHERE version_id = ?",
                (version_id,),
            ).fetchone()[0]
        )

    def list_for_document(self, document_id: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT * FROM informe_indicators
               WHERE document_id = ? ORDER BY indicator_id""",
            (document_id,),
        ).fetchall()
