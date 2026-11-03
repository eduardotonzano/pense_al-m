"""Observacoes de CNPJ dos ativos (migration 002): CNPJ, decisao, fonte e data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

CNPJ_FIELDS = ("cnpj_securitizadora", "cnpj_devedor")

# applied e confirmed descrevem o mesmo fato: o CNPJ esta em assets com esta
# evidencia. Reler o mesmo arquivo depois de gravar nao cria outra linha.
_DECISION_CLASS = {"applied": "in_assets", "confirmed": "in_assets"}


@dataclass(frozen=True)
class CnpjObservation:
    asset_id: int
    field: str
    cnpj: str
    decision: str
    source_id: str
    matched_by: str
    reference_first: str
    reference_last: str
    filings: int
    evidence: dict
    delivered_last: str | None = None

    def evidence_json(self) -> str:
        return json.dumps(self.evidence, ensure_ascii=False, sort_keys=True)

    def checksum(self) -> str:
        """Hash da evidencia e da decisao, sem a hora da leitura."""

        payload = json.dumps(
            {
                "asset_id": self.asset_id,
                "field": self.field,
                "cnpj": self.cnpj,
                "decision": _DECISION_CLASS.get(self.decision, self.decision),
                "source_id": self.source_id,
                "matched_by": self.matched_by,
                "reference_first": self.reference_first,
                "reference_last": self.reference_last,
                "filings": self.filings,
                "delivered_last": self.delivered_last,
                "evidence": self.evidence,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CnpjObservationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add(
        self,
        observation: CnpjObservation,
        run_id: str,
        observed_at: str | None = None,
    ) -> bool:
        """Grava a observacao sem confirmar a transacao.

        Devolve False quando a mesma evidencia e decisao ja estavam gravadas.
        Dado fora das regras do schema levanta sqlite3.IntegrityError.
        """

        checksum = observation.checksum()
        already = self.connection.execute(
            "SELECT 1 FROM asset_cnpj_observations WHERE checksum = ?",
            (checksum,),
        ).fetchone()

        if already is not None:
            return False

        self.connection.execute(
            """INSERT INTO asset_cnpj_observations (
                asset_id, field, cnpj, decision, source_id, matched_by,
                reference_first, reference_last, filings, delivered_last,
                evidence_json, observed_at, run_id, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                observation.asset_id,
                observation.field,
                observation.cnpj,
                observation.decision,
                observation.source_id,
                observation.matched_by,
                observation.reference_first,
                observation.reference_last,
                observation.filings,
                observation.delivered_last,
                observation.evidence_json(),
                observed_at or datetime.now(timezone.utc).isoformat(),
                run_id,
                checksum,
            ),
        )
        return True

    def for_asset(self, asset_id: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT * FROM asset_cnpj_observations
               WHERE asset_id = ? ORDER BY observation_id""",
            (asset_id,),
        ).fetchall()

    def provenance(self, asset_id: int, field: str) -> sqlite3.Row | None:
        """Fonte e data do CNPJ que esta hoje em assets, ou None se nao tem."""

        return self.connection.execute(
            """SELECT * FROM asset_cnpj_provenance
               WHERE asset_id = ? AND field = ?""",
            (asset_id, field),
        ).fetchone()
