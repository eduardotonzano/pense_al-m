import hashlib
import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal

from debenture_search.database import database


ALLOWED_VALUE_TYPES = {
    "text",
    "numeric",
    "date",
    "boolean",
}

ALLOWED_CONFIDENCE_LEVELS = {
    "reported",
    "verified",
    "manual",
    "conflicting",
    "suspect",
}


@dataclass(frozen=True)
class ObservationRecord:
    """Representa uma observacao historica."""

    id: int
    debenture_id: int
    source_id: int
    raw_record_id: int | None
    field_name: str
    value_type: str
    value_text: str | None
    value_numeric: object
    value_date: str | None
    value_boolean: int | None
    unit: str | None
    observed_at: str
    collected_at: str
    valid_from: str | None
    valid_until: str | None
    confidence: str
    checksum: str

    @property
    def value(self):
        """Retorna o valor conforme o tipo da observacao."""

        if self.value_type == "text":
            return self.value_text

        if self.value_type == "numeric":
            return self.value_numeric

        if self.value_type == "date":
            return self.value_date

        if self.value_type == "boolean":
            if self.value_boolean is None:
                return None
            return bool(self.value_boolean)

        return None


class ObservationRepository:
    """Gerencia observacoes historicas das debentures."""

    def __init__(self, db=database):
        self.db = db

    @staticmethod
    def normalize_field_name(field_name):
        """Normaliza o nome do campo."""

        if field_name is None:
            raise ValueError("O nome do campo e obrigatorio.")

        normalized = "_".join(
            str(field_name).strip().lower().split()
        )

        if not normalized:
            raise ValueError("O nome do campo e obrigatorio.")

        return normalized

    @staticmethod
    def normalize_value_type(value_type):
        """Valida o tipo do valor."""

        if value_type is None:
            raise ValueError("O tipo do valor e obrigatorio.")

        normalized = str(value_type).strip().lower()

        if normalized not in ALLOWED_VALUE_TYPES:
            raise ValueError("Tipo de valor invalido.")

        return normalized

    @staticmethod
    def normalize_confidence(confidence):
        """Valida o nivel de confianca."""

        if confidence is None:
            return "reported"

        normalized = str(confidence).strip().lower()

        if normalized not in ALLOWED_CONFIDENCE_LEVELS:
            raise ValueError("Nivel de confianca invalido.")

        return normalized

    @staticmethod
    def normalize_optional_text(value):
        """Normaliza um texto opcional."""

        if value is None:
            return None

        normalized = " ".join(str(value).split())

        if not normalized:
            return None

        return normalized

    @staticmethod
    def normalize_datetime(value):
        """Converte data e hora para UTC no formato ISO."""

        if value is None:
            return datetime.now(timezone.utc).isoformat()

        if isinstance(value, datetime):
            parsed = value
        else:
            normalized = str(value).strip()

            if not normalized:
                raise ValueError(
                    "A data de observacao e obrigatoria."
                )

            try:
                parsed = datetime.fromisoformat(
                    normalized.replace("Z", "+00:00")
                )
            except ValueError as error:
                raise ValueError(
                    "Data de observacao invalida."
                ) from error

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).isoformat()

    @staticmethod
    def normalize_date(value):
        """Converte uma data para o formato ISO."""

        if isinstance(value, datetime):
            return value.date().isoformat()

        if isinstance(value, date):
            return value.isoformat()

        normalized = str(value).strip()

        try:
            parsed = date.fromisoformat(normalized)
        except ValueError as error:
            raise ValueError("Valor de data invalido.") from error

        return parsed.isoformat()

    @staticmethod
    def normalize_numeric(value):
        """Converte um valor numerico para Decimal."""

        if isinstance(value, bool):
            raise ValueError("Valor numerico invalido.")

        try:
            normalized = Decimal(str(value))
        except Exception as error:
            raise ValueError("Valor numerico invalido.") from error

        if not normalized.is_finite():
            raise ValueError("Valor numerico invalido.")

        return normalized

    @staticmethod
    def normalize_boolean(value):
        """Converte valores conhecidos para booleano."""

        if isinstance(value, bool):
            return value

        if value in (0, 1):
            return bool(value)

        normalized = str(value).strip().lower()
        true_values = {"true", "sim", "yes", "1"}
        false_values = {"false", "nao", "no", "0"}

        if normalized in true_values:
            return True

        if normalized in false_values:
            return False

        raise ValueError("Valor booleano invalido.")

    def normalize_value(self, value_type, value):
        """Normaliza o valor conforme o tipo."""

        normalized_type = self.normalize_value_type(value_type)

        if value is None:
            raise ValueError(
                "O valor da observacao e obrigatorio."
            )

        if normalized_type == "text":
            normalized_value = self.normalize_optional_text(value)

            if normalized_value is None:
                raise ValueError(
                    "O valor textual nao pode ficar vazio."
                )

            return normalized_value

        if normalized_type == "numeric":
            return self.normalize_numeric(value)

        if normalized_type == "date":
            return self.normalize_date(value)

        if normalized_type == "boolean":
            return self.normalize_boolean(value)

        raise ValueError("Tipo de valor invalido.")

    @staticmethod
    def serialize_value(value):
        """Converte o valor para geracao do checksum."""

        if isinstance(value, Decimal):
            return format(value, "f")

        if isinstance(value, bool):
            return "true" if value else "false"

        return str(value)

    @staticmethod
    def generate_checksum(
        debenture_id,
        source_id,
        field_name,
        value_type,
        value,
        observed_at,
    ):
        """Gera uma chave unica para a observacao."""

        checksum_data = {
            "debenture_id": int(debenture_id),
            "source_id": int(source_id),
            "field_name": str(field_name),
            "value_type": str(value_type),
            "value": ObservationRepository.serialize_value(value),
            "observed_at": str(observed_at),
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
        """Converte uma linha do banco em ObservationRecord."""

        return ObservationRecord(
            id=int(row["id"]),
            debenture_id=int(row["debenture_id"]),
            source_id=int(row["source_id"]),
            raw_record_id=row["raw_record_id"],
            field_name=str(row["field_name"]),
            value_type=str(row["value_type"]),
            value_text=row["value_text"],
            value_numeric=row["value_numeric"],
            value_date=row["value_date"],
            value_boolean=row["value_boolean"],
            unit=row["unit"],
            observed_at=str(row["observed_at"]),
            collected_at=str(row["collected_at"]),
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            confidence=str(row["confidence"]),
            checksum=str(row["checksum"]),
        )

    def debenture_exists(self, debenture_id):
        """Verifica se a debenture existe."""

        row = self.db.fetch_one(
            "SELECT id FROM debentures WHERE id = ?",
            (debenture_id,),
        )
        return row is not None

    def source_exists(self, source_id):
        """Verifica se a fonte existe."""

        row = self.db.fetch_one(
            "SELECT id FROM sources WHERE id = ?",
            (source_id,),
        )
        return row is not None

    def raw_record_exists(self, raw_record_id):
        """Verifica se o registro bruto existe."""

        if raw_record_id is None:
            return True

        row = self.db.fetch_one(
            "SELECT id FROM raw_records WHERE id = ?",
            (raw_record_id,),
        )
        return row is not None

    def get_by_id(self, observation_id):
        """Busca uma observacao pelo ID."""

        row = self.db.fetch_one(
            """
            SELECT
                id,
                debenture_id,
                source_id,
                raw_record_id,
                field_name,
                value_type,
                value_text,
                value_numeric,
                value_date,
                value_boolean,
                unit,
                observed_at,
                collected_at,
                valid_from,
                valid_until,
                confidence,
                checksum
            FROM observations
            WHERE id = ?
            """,
            (observation_id,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def get_by_checksum(self, checksum):
        """Busca uma observacao pelo checksum."""

        row = self.db.fetch_one(
            """
            SELECT
                id,
                debenture_id,
                source_id,
                raw_record_id,
                field_name,
                value_type,
                value_text,
                value_numeric,
                value_date,
                value_boolean,
                unit,
                observed_at,
                collected_at,
                valid_from,
                valid_until,
                confidence,
                checksum
            FROM observations
            WHERE checksum = ?
            """,
            (checksum,),
        )

        if row is None:
            return None

        return self.row_to_record(row)

    def create(
        self,
        debenture_id,
        source_id,
        field_name,
        value_type,
        value,
        observed_at=None,
        raw_record_id=None,
        unit=None,
        valid_from=None,
        valid_until=None,
        confidence="reported",
    ):
        """Cria uma observacao sem duplicar dados."""

        if not self.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        if not self.source_exists(source_id):
            raise ValueError("A fonte informada nao existe.")

        if not self.raw_record_exists(raw_record_id):
            raise ValueError(
                "O registro bruto informado nao existe."
            )

        normalized_field = self.normalize_field_name(field_name)
        normalized_type = self.normalize_value_type(value_type)
        normalized_value = self.normalize_value(
            normalized_type,
            value,
        )
        normalized_observed_at = self.normalize_datetime(
            observed_at
        )
        normalized_confidence = self.normalize_confidence(
            confidence
        )
        normalized_unit = self.normalize_optional_text(unit)

        normalized_valid_from = None
        normalized_valid_until = None

        if valid_from is not None:
            normalized_valid_from = self.normalize_datetime(
                valid_from
            )

        if valid_until is not None:
            normalized_valid_until = self.normalize_datetime(
                valid_until
            )

        if (
            normalized_valid_from is not None
            and normalized_valid_until is not None
            and normalized_valid_until < normalized_valid_from
        ):
            raise ValueError(
                "A data final nao pode ser anterior a data inicial."
            )

        checksum = self.generate_checksum(
            debenture_id=debenture_id,
            source_id=source_id,
            field_name=normalized_field,
            value_type=normalized_type,
            value=normalized_value,
            observed_at=normalized_observed_at,
        )

        existing = self.get_by_checksum(checksum)

        if existing is not None:
            return existing, False

        value_text = None
        value_numeric = None
        value_date = None
        value_boolean = None

        if normalized_type == "text":
            value_text = normalized_value
        elif normalized_type == "numeric":
            value_numeric = str(normalized_value)
        elif normalized_type == "date":
            value_date = normalized_value
        elif normalized_type == "boolean":
            value_boolean = int(normalized_value)

        try:
            with self.db.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO observations (
                        debenture_id,
                        source_id,
                        raw_record_id,
                        field_name,
                        value_type,
                        value_text,
                        value_numeric,
                        value_date,
                        value_boolean,
                        unit,
                        observed_at,
                        valid_from,
                        valid_until,
                        confidence,
                        checksum
                    )
                    VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        debenture_id,
                        source_id,
                        raw_record_id,
                        normalized_field,
                        normalized_type,
                        value_text,
                        value_numeric,
                        value_date,
                        value_boolean,
                        normalized_unit,
                        normalized_observed_at,
                        normalized_valid_from,
                        normalized_valid_until,
                        normalized_confidence,
                        checksum,
                    ),
                )
                observation_id = cursor.lastrowid

        except Exception:
            existing = self.get_by_checksum(checksum)

            if existing is not None:
                return existing, False

            raise

        created = self.get_by_id(observation_id)

        if created is None:
            raise RuntimeError(
                "A observacao foi gravada, mas nao foi localizada."
            )

        return created, True

    def list_history(
        self,
        debenture_id,
        field_name=None,
        limit=500,
        offset=0,
    ):
        """Lista o historico de observacoes da debenture."""

        if not self.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        safe_limit = max(1, min(int(limit), 1000))
        safe_offset = max(0, int(offset))

        if field_name is None:
            rows = self.db.fetch_all(
                """
                SELECT
                    id, debenture_id, source_id, raw_record_id,
                    field_name, value_type, value_text,
                    value_numeric, value_date, value_boolean,
                    unit, observed_at, collected_at,
                    valid_from, valid_until, confidence, checksum
                FROM observations
                WHERE debenture_id = ?
                ORDER BY observed_at DESC, collected_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (debenture_id, safe_limit, safe_offset),
            )
        else:
            normalized_field = self.normalize_field_name(
                field_name
            )
            rows = self.db.fetch_all(
                """
                SELECT
                    id, debenture_id, source_id, raw_record_id,
                    field_name, value_type, value_text,
                    value_numeric, value_date, value_boolean,
                    unit, observed_at, collected_at,
                    valid_from, valid_until, confidence, checksum
                FROM observations
                WHERE debenture_id = ?
                  AND field_name = ?
                ORDER BY observed_at DESC, collected_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (
                    debenture_id,
                    normalized_field,
                    safe_limit,
                    safe_offset,
                ),
            )

        return [self.row_to_record(row) for row in rows]

    def get_current(self, debenture_id, field_name):
        """Retorna o valor consolidado atual de um campo."""

        if not self.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        normalized_field = self.normalize_field_name(
            field_name
        )

        row = self.db.fetch_one(
            """
            SELECT
                id, debenture_id, source_id,
                NULL AS raw_record_id,
                field_name, value_type, value_text,
                value_numeric, value_date, value_boolean,
                unit, observed_at, collected_at,
                NULL AS valid_from,
                NULL AS valid_until,
                confidence, '' AS checksum
            FROM current_observations
            WHERE debenture_id = ?
              AND field_name = ?
            LIMIT 1
            """,
            (debenture_id, normalized_field),
        )

        if row is None:
            return None

        original = self.get_by_id(row["id"])
        if original is not None:
            return original

        return self.row_to_record(row)

    def list_current(self, debenture_id):
        """Lista todos os valores consolidados atuais."""

        if not self.debenture_exists(debenture_id):
            raise ValueError(
                "A debenture informada nao existe."
            )

        rows = self.db.fetch_all(
            """
            SELECT id
            FROM current_observations
            WHERE debenture_id = ?
            ORDER BY field_name
            """,
            (debenture_id,),
        )

        records = []
        for row in rows:
            record = self.get_by_id(row["id"])
            if record is not None:
                records.append(record)

        return records

    def count(self, debenture_id=None, field_name=None):
        """Conta observacoes com filtros opcionais."""

        clauses = []
        parameters = []

        if debenture_id is not None:
            clauses.append("debenture_id = ?")
            parameters.append(debenture_id)

        if field_name is not None:
            clauses.append("field_name = ?")
            parameters.append(
                self.normalize_field_name(field_name)
            )

        sql = "SELECT COUNT(*) AS total FROM observations"

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        row = self.db.fetch_one(sql, tuple(parameters))
        if row is None:
            return 0

        return int(row["total"])


observation_repository = ObservationRepository()
