import hashlib
import json
import sqlite3
from dataclasses import dataclass
from decimal import Decimal

from debenture_search.database import database
from debenture_search.repositories.observation_repository import (
    ObservationRepository,
)


ALLOWED_EVENT_TYPES = {
    "amortizacao",
    "atualizacao",
    "juros",
    "opcao_venda",
    "participacao",
    "premio",
    "premio_permanencia",
    "repactuacao",
    "resgate_total_antecipado",
    "vencimento",
}

EVENT_COLUMNS = """
    id, debenture_id, event_type, event_date, value_numeric, unit,
    source_id, raw_record_id, observed_at, collected_at, confidence,
    checksum
"""


@dataclass(frozen=True)
class DebentureEventRecord:
    """Representa um evento da agenda de uma debenture."""

    id: int
    debenture_id: int
    event_type: str
    event_date: str
    value_numeric: object
    unit: str | None
    source_id: int
    raw_record_id: int | None
    observed_at: str
    collected_at: str
    confidence: str
    checksum: str

    @property
    def value(self):
        """Retorna o valor do evento como Decimal, quando houver."""

        if self.value_numeric is None:
            return None

        return Decimal(str(self.value_numeric))


class DebentureEventRepository:
    """Gerencia a agenda de eventos das debentures."""

    def __init__(self, db=database):
        self.db = db
        self.observations = ObservationRepository(db)

    @staticmethod
    def normalize_event_type(event_type):
        """Valida o tipo do evento."""

        if event_type is None:
            raise ValueError("O tipo do evento e obrigatorio.")

        normalized = "_".join(
            str(event_type).strip().lower().split()
        )

        if not normalized:
            raise ValueError("O tipo do evento e obrigatorio.")

        if normalized not in ALLOWED_EVENT_TYPES:
            raise ValueError("Tipo de evento invalido.")

        return normalized

    @staticmethod
    def normalize_event_date(event_date):
        """Converte a data do evento para o formato ISO."""

        if event_date is None or not str(event_date).strip():
            raise ValueError("A data do evento e obrigatoria.")

        try:
            return ObservationRepository.normalize_date(event_date)
        except ValueError as error:
            raise ValueError("Data do evento invalida.") from error

    @staticmethod
    def normalize_value(value):
        """Converte o valor opcional do evento para Decimal."""

        if value is None:
            return None

        return ObservationRepository.normalize_numeric(value)

    @staticmethod
    def canonical_value(value):
        """Representa o valor sem zeros a direita (1.50 e 1.5 coincidem)."""

        if value is None:
            return None

        if value == 0:
            return "0"

        return format(value.normalize(), "f")

    @staticmethod
    def generate_checksum(
        debenture_id,
        source_id,
        event_type,
        event_date,
        value,
        unit,
    ):
        """Gera a chave unica do evento, sem o horario da observacao."""

        checksum_data = {
            "debenture_id": int(debenture_id),
            "source_id": int(source_id),
            "event_type": str(event_type),
            "event_date": str(event_date),
            "value": DebentureEventRepository.canonical_value(value),
            "unit": unit,
        }

        serialized = json.dumps(
            checksum_data,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def row_to_record(row):
        """Converte uma linha do banco em DebentureEventRecord."""

        return DebentureEventRecord(
            id=int(row["id"]),
            debenture_id=int(row["debenture_id"]),
            event_type=str(row["event_type"]),
            event_date=str(row["event_date"]),
            value_numeric=row["value_numeric"],
            unit=row["unit"],
            source_id=int(row["source_id"]),
            raw_record_id=row["raw_record_id"],
            observed_at=str(row["observed_at"]),
            collected_at=str(row["collected_at"]),
            confidence=str(row["confidence"]),
            checksum=str(row["checksum"]),
        )

    def get_by_id(self, event_id):
        """Busca um evento pelo ID."""

        row = self.db.fetch_one(
            "SELECT " + EVENT_COLUMNS
            + " FROM debenture_events WHERE id = ?",
            (event_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_checksum(self, checksum):
        """Busca um evento pelo checksum."""

        row = self.db.fetch_one(
            "SELECT " + EVENT_COLUMNS
            + " FROM debenture_events WHERE checksum = ?",
            (checksum,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def create(
        self,
        debenture_id,
        source_id,
        event_type,
        event_date,
        value=None,
        unit=None,
        observed_at=None,
        raw_record_id=None,
        confidence="reported",
    ):
        """
        Cria um evento sem duplicar dados.

        O evento e identificado por debenture, fonte, tipo, data, valor e
        unidade. Repeti-lo devolve o registro existente, sem alterar o
        observed_at original. Valor ou unidade diferentes geram novo
        registro, e o historico de revisoes da agenda fica preservado.
        """

        if not self.observations.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        if not self.observations.source_exists(source_id):
            raise ValueError("A fonte informada nao existe.")

        if not self.observations.raw_record_exists(raw_record_id):
            raise ValueError(
                "O registro bruto informado nao existe."
            )

        normalized_type = self.normalize_event_type(event_type)
        normalized_date = self.normalize_event_date(event_date)
        normalized_value = self.normalize_value(value)
        normalized_unit = ObservationRepository.normalize_optional_text(
            unit
        )

        if normalized_unit is not None and normalized_value is None:
            raise ValueError("A unidade exige um valor.")

        normalized_observed_at = ObservationRepository.normalize_datetime(
            observed_at
        )
        normalized_confidence = ObservationRepository.normalize_confidence(
            confidence
        )

        checksum = self.generate_checksum(
            debenture_id,
            source_id,
            normalized_type,
            normalized_date,
            normalized_value,
            normalized_unit,
        )

        existing = self.get_by_checksum(checksum)

        if existing is not None:
            return existing, False

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO debenture_events (
                        debenture_id,
                        source_id,
                        raw_record_id,
                        event_type,
                        event_date,
                        value_numeric,
                        unit,
                        observed_at,
                        confidence,
                        checksum
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        debenture_id,
                        source_id,
                        raw_record_id,
                        normalized_type,
                        normalized_date,
                        self.canonical_value(normalized_value),
                        normalized_unit,
                        normalized_observed_at,
                        normalized_confidence,
                        checksum,
                    ),
                )
                event_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            existing = self.get_by_checksum(checksum)

            if existing is not None:
                return existing, False

            raise

        created = self.get_by_id(event_id)

        if created is None:
            raise RuntimeError(
                "O evento foi gravado, mas nao foi localizado."
            )

        return created, True

    def list_by_debenture(
        self,
        debenture_id,
        event_type=None,
        date_from=None,
        date_until=None,
        limit=500,
        offset=0,
    ):
        """Lista a agenda da debenture em ordem de data do evento."""

        if not self.observations.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        clauses = ["debenture_id = ?"]
        parameters = [debenture_id]

        if event_type is not None:
            clauses.append("event_type = ?")
            parameters.append(self.normalize_event_type(event_type))

        normalized_from = None
        normalized_until = None

        if date_from is not None:
            normalized_from = self.normalize_event_date(date_from)
            clauses.append("event_date >= ?")
            parameters.append(normalized_from)

        if date_until is not None:
            normalized_until = self.normalize_event_date(date_until)
            clauses.append("event_date <= ?")
            parameters.append(normalized_until)

        if (
            normalized_from is not None
            and normalized_until is not None
            and normalized_until < normalized_from
        ):
            raise ValueError(
                "A data final nao pode ser anterior a data inicial."
            )

        safe_limit = max(1, min(int(limit), 1000))
        safe_offset = max(0, int(offset))
        parameters.extend([safe_limit, safe_offset])

        rows = self.db.fetch_all(
            "SELECT " + EVENT_COLUMNS
            + " FROM debenture_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY event_date ASC, event_type ASC,"
            + " observed_at DESC, id DESC LIMIT ? OFFSET ?",
            tuple(parameters),
        )

        return [self.row_to_record(row) for row in rows]

    def count(self, debenture_id=None, event_type=None):
        """Conta eventos com filtros opcionais."""

        clauses = []
        parameters = []

        if debenture_id is not None:
            clauses.append("debenture_id = ?")
            parameters.append(debenture_id)

        if event_type is not None:
            clauses.append("event_type = ?")
            parameters.append(self.normalize_event_type(event_type))

        sql = "SELECT COUNT(*) AS total FROM debenture_events"

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        row = self.db.fetch_one(sql, tuple(parameters))
        if row is None:
            return 0

        return int(row["total"])


debenture_event_repository = DebentureEventRepository()
