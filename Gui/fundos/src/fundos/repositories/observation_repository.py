"""Observacoes EAV com proveniencia e deteccao de conflito.

field_name = tabela.coluna da CVM, sem renomear e sem mudar maiusculas.
Valor ausente nao vira linha. Reapresentacao (mesma fonte) ou divergencia
(outra fonte) com valor diferente para o mesmo assunto, campo e competencia
gera uma linha nova e um conflito aberto; nenhuma observacao e sobrescrita.

Valor que volta (A, depois B, depois A): por padrao o terceiro A acha o
checksum do primeiro e nao gera linha, e o valor atual continua B. Com
restatement=True (so a carga do informe de FIDC usa), o A volta como linha
reapresentada, com a coleta no checksum, e vira o valor atual; o conflito
A x B, que ja existe, nao e aberto de novo.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation

from fundos.database import normalize_iso_date
from fundos.database import normalize_timestamp
from fundos.personal_data import check_observation
from fundos.repositories.conflict_repository import ConflictRecord
from fundos.repositories.conflict_repository import ConflictRepository


VALUE_TYPES = ("text", "numeric", "date", "boolean")

CONFIDENCE_LEVELS = {
    "reported",
    "verified",
    "manual",
    "conflicting",
    "suspect",
}

FIELD_NAME = re.compile(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+")
DECIMAL_TEXT = re.compile(r"-?[0-9]+(\.[0-9]+)?")

SUBJECTS = (
    ("fund_id", "funds"),
    ("fund_class_id", "fund_classes"),
    ("quota_series_id", "quota_series"),
)

VALUE_COLUMNS = {
    "text": "value_text",
    "numeric": "value_numeric",
    "date": "value_date",
    "boolean": "value_boolean",
}


@dataclass(frozen=True)
class ObservationRecord:
    """Uma observacao gravada, com toda a proveniencia."""

    id: int
    fund_id: int | None
    fund_class_id: int | None
    quota_series_id: int | None
    source_id: int
    collection_run_id: int
    raw_record_id: int
    field_name: str
    value_type: str
    value_text: str | None
    value_numeric: str | None
    value_date: str | None
    value_boolean: int | None
    unit: str | None
    reference_date: str
    collected_at: str
    confidence: str
    checksum: str

    @property
    def value(self):
        """Valor no tipo da observacao (numeric vira Decimal exato)."""

        if self.value_type == "numeric":
            return Decimal(self.value_numeric)

        if self.value_type == "boolean":
            return bool(self.value_boolean)

        if self.value_type == "date":
            return self.value_date

        return self.value_text


@dataclass(frozen=True)
class RecordResult:
    """Resultado de record(): a observacao, se foi criada e os conflitos novos."""

    observation: ObservationRecord
    created: bool
    conflicts: tuple[ConflictRecord, ...]


def canonical_decimal(value):
    """Decimal exato, sem expoente e sem zeros a direita. Nada e arredondado."""

    if isinstance(value, bool):
        raise ValueError("Valor numerico invalido.")

    if isinstance(value, str):
        text = value.strip()

        if DECIMAL_TEXT.fullmatch(text) is None:
            raise ValueError(
                "Valor numerico deve ser decimal com ponto, sem expoente "
                "nem separador de milhar."
            )

        number = Decimal(text)
    elif isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("Valor numerico invalido.") from error
    else:
        raise ValueError("Valor numerico invalido.")

    if not number.is_finite():
        raise ValueError("Valor numerico invalido.")

    text = format(number, "f")

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    if text in ("-0", ""):
        text = "0"

    return text


class ObservationRepository:
    """Grava e le observacoes de fundos, classes e series."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def row_to_record(row):
        return ObservationRecord(
            **{
                field: row[field]
                for field in ObservationRecord.__dataclass_fields__
            }
        )

    @staticmethod
    def subject(fund_id=None, fund_class_id=None, quota_series_id=None):
        """Devolve (coluna, tabela, id) do unico assunto informado."""

        given = [
            (column, table, value)
            for (column, table), value in zip(
                SUBJECTS,
                (fund_id, fund_class_id, quota_series_id),
            )
            if value is not None
        ]

        if len(given) != 1:
            raise ValueError(
                "Informe exatamente um assunto: fundo, classe ou serie."
            )

        return given[0]

    @staticmethod
    def normalize_value(value_type, value):
        """Converte o valor para o que vai na coluna do tipo."""

        if value is None:
            raise ValueError("Valor ausente nao e gravado.")

        if value_type == "text":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Valor ausente nao e gravado.")

            return value

        if value_type == "numeric":
            return canonical_decimal(value)

        if value_type == "date":
            return normalize_iso_date(value, "A data do valor")

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, int) and value in (0, 1):
            return value

        raise ValueError(
            "Valor booleano deve ser True, False, 0 ou 1."
        )

    @staticmethod
    def checksum(subject_column, subject_id, source_id, field_name,
                 reference_date, value_type, value, unit,
                 restated_in_run=None):
        """SHA-256 da chave e do valor.

        A coleta so entra na linha reapresentada: o checksum das outras
        linhas e o mesmo de antes da FU4.2.
        """

        data = {
            "subject": subject_column,
            "subject_id": int(subject_id),
            "source_id": int(source_id),
            "field_name": field_name,
            "reference_date": reference_date,
            "value_type": value_type,
            "value": str(value),
            "unit": unit,
        }

        if restated_in_run is not None:
            data["restated_in_run"] = int(restated_in_run)

        serialized = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_by_id(self, observation_id):
        """Busca uma observacao pelo ID."""

        row = self.connection.execute(
            "SELECT * FROM observations WHERE id = ?",
            (observation_id,),
        ).fetchone()

        return None if row is None else self.row_to_record(row)

    def record(
        self,
        *,
        fund_id=None,
        fund_class_id=None,
        quota_series_id=None,
        source_id,
        collection_run_id,
        raw_record_id,
        field_name,
        value_type,
        value,
        reference_date,
        unit=None,
        confidence="reported",
        collected_at=None,
        restatement=False,
    ):
        """Grava a observacao; devolve RecordResult.

        Mesmo assunto, fonte, campo, competencia, valor e unidade: devolve a
        observacao existente (idempotente). Valor diferente para o mesmo
        assunto, campo e competencia: linha nova e conflito aberto.

        restatement=True: o valor ja foi gravado na chave, mas o atual e
        outro (quem chama confere). Grava a linha reapresentada, com a
        coleta no checksum; exige que o valor ja exista na chave.
        """

        if not isinstance(value_type, str) or value_type not in VALUE_TYPES:
            raise ValueError("Tipo de valor invalido.")

        # Guarda de dados pessoais antes de qualquer SQL.
        check_observation(field_name, value_type, value)

        if FIELD_NAME.fullmatch(field_name) is None:
            raise ValueError(
                "O campo deve ser tabela.coluna da CVM, sem espacos nem "
                "acentos: " + field_name + "."
            )

        stored_value = self.normalize_value(value_type, value)
        normalized_unit = None

        if unit is not None:
            normalized_unit = str(unit).strip() or None

        if confidence not in CONFIDENCE_LEVELS:
            raise ValueError("Nivel de confianca invalido.")

        normalized_reference = normalize_iso_date(
            reference_date,
            "A competencia",
        )
        subject_column, subject_table, subject_id = self.subject(
            fund_id,
            fund_class_id,
            quota_series_id,
        )

        if self.connection.execute(
            "SELECT id FROM " + subject_table + " WHERE id = ?",
            (subject_id,),
        ).fetchone() is None:
            raise ValueError("O assunto informado nao existe.")

        if self.connection.execute(
            "SELECT id FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone() is None:
            raise ValueError("A fonte informada nao existe.")

        run = self.connection.execute(
            "SELECT source_id FROM collection_runs WHERE id = ?",
            (collection_run_id,),
        ).fetchone()

        if run is None:
            raise ValueError("A coleta informada nao existe.")

        if int(run["source_id"]) != int(source_id):
            raise ValueError("A coleta informada e de outra fonte.")

        raw = self.connection.execute(
            "SELECT source_id, collected_at FROM raw_records WHERE id = ?",
            (raw_record_id,),
        ).fetchone()

        if raw is None:
            raise ValueError("O manifesto informado nao existe.")

        if int(raw["source_id"]) != int(source_id):
            raise ValueError("O manifesto informado e de outra fonte.")

        normalized_collected_at = (
            str(raw["collected_at"])
            if collected_at is None
            else normalize_timestamp(collected_at, "A data de coleta")
        )

        key = (
            subject_column,
            subject_id,
            source_id,
            field_name,
            normalized_reference,
            value_type,
            stored_value,
            normalized_unit,
        )
        checksum = self.checksum(*key)
        existing = self.connection.execute(
            "SELECT * FROM observations WHERE checksum = ?",
            (checksum,),
        ).fetchone()

        if restatement:
            if existing is None:
                raise ValueError(
                    "Linha reapresentada so existe para valor ja gravado na chave."
                )

            checksum = self.checksum(*key, restated_in_run=collection_run_id)
            existing = self.connection.execute(
                "SELECT * FROM observations WHERE checksum = ?",
                (checksum,),
            ).fetchone()

        if existing is not None:
            return RecordResult(self.row_to_record(existing), False, ())

        self.connection.execute("SAVEPOINT fundos_observation_record")

        try:
            cursor = self.connection.execute(
                "INSERT INTO observations ("
                + subject_column
                + ", source_id, collection_run_id, raw_record_id, field_name,"
                " value_type, "
                + VALUE_COLUMNS[value_type]
                + ", unit, reference_date, collected_at, confidence, checksum"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    subject_id,
                    source_id,
                    collection_run_id,
                    raw_record_id,
                    field_name,
                    value_type,
                    stored_value,
                    normalized_unit,
                    normalized_reference,
                    normalized_collected_at,
                    confidence,
                    checksum,
                ),
            )
            observation = self.get_by_id(cursor.lastrowid)
            conflicts = self._open_conflicts(observation, subject_column, restatement)
            self.connection.execute(
                "RELEASE SAVEPOINT fundos_observation_record"
            )
        except BaseException:
            self.connection.execute(
                "ROLLBACK TO SAVEPOINT fundos_observation_record"
            )
            self.connection.execute(
                "RELEASE SAVEPOINT fundos_observation_record"
            )
            raise

        return RecordResult(observation, True, conflicts)

    @staticmethod
    def _stored_value(observation):
        return (
            observation["value_type"],
            observation["value_text"],
            observation["value_numeric"],
            observation["value_date"],
            observation["value_boolean"],
            observation["unit"],
        )

    def _conflicting_values(self, rows):
        """Pares de valores da chave que ja tem conflito, de qualquer status."""

        values = {int(row["id"]): self._stored_value(row) for row in rows}
        pairs = self.connection.execute(
            "SELECT observation_a_id, observation_b_id FROM data_conflicts"
            " WHERE observation_a_id IN (" + ", ".join("?" * len(values)) + ")",
            tuple(values),
        ).fetchall()

        return {
            frozenset((values[a], values[b]))
            for a, b in pairs
            if a in values and b in values
        }

    def _open_conflicts(self, observation, subject_column, restated=False):
        """Abre conflito contra cada valor diferente ja gravado para a chave.

        Na linha reapresentada, o par de valores que ja tem conflito nao
        ganha outro.
        """

        row = self.connection.execute(
            "SELECT * FROM observations WHERE id = ?",
            (observation.id,),
        ).fetchone()
        new_value = self._stored_value(row)
        others = self.connection.execute(
            "SELECT * FROM observations WHERE "
            + subject_column
            + " = ? AND field_name = ? AND reference_date = ? AND id <> ?",
            (
                getattr(observation, subject_column),
                observation.field_name,
                observation.reference_date,
                observation.id,
            ),
        ).fetchall()

        created = []
        known = self._conflicting_values([row, *others]) if restated else set()

        for other in others:
            other_value = self._stored_value(other)

            if other_value == new_value:
                continue

            if restated:
                pair = frozenset((other_value, new_value))

                if pair in known:
                    continue

                known.add(pair)

            first, second = sorted((int(other["id"]), observation.id))
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO data_conflicts (
                    field_name, reference_date,
                    observation_a_id, observation_b_id
                ) VALUES (?, ?, ?, ?)
                """,
                (observation.field_name, observation.reference_date, first, second),
            )

            if cursor.rowcount == 1:
                created.append(
                    ConflictRepository(self.connection).get_by_id(
                        cursor.lastrowid
                    )
                )

        return tuple(created)

    def _where_subject(self, fund_id, fund_class_id, quota_series_id):
        column, _, subject_id = self.subject(
            fund_id,
            fund_class_id,
            quota_series_id,
        )
        return column + " = ?", subject_id

    def list_history(
        self,
        *,
        fund_id=None,
        fund_class_id=None,
        quota_series_id=None,
        field_name=None,
    ):
        """Historico completo do assunto (competencia e coleta mais recentes antes)."""

        clause, subject_id = self._where_subject(
            fund_id,
            fund_class_id,
            quota_series_id,
        )
        parameters = [subject_id]

        if field_name is not None:
            clause += " AND field_name = ?"
            parameters.append(field_name)

        rows = self.connection.execute(
            "SELECT * FROM observations WHERE "
            + clause
            + " ORDER BY reference_date DESC, collected_at DESC, id DESC",
            tuple(parameters),
        ).fetchall()

        return [self.row_to_record(row) for row in rows]

    def get_current(
        self,
        *,
        fund_id=None,
        fund_class_id=None,
        quota_series_id=None,
        field_name,
    ):
        """Valor atual de um campo, pela view current_observations."""

        clause, subject_id = self._where_subject(
            fund_id,
            fund_class_id,
            quota_series_id,
        )
        row = self.connection.execute(
            "SELECT id FROM current_observations WHERE "
            + clause
            + " AND field_name = ?",
            (subject_id, field_name),
        ).fetchone()

        return None if row is None else self.get_by_id(row["id"])

    def list_current(self, *, fund_id=None, fund_class_id=None, quota_series_id=None):
        """Valores atuais de todos os campos do assunto."""

        clause, subject_id = self._where_subject(
            fund_id,
            fund_class_id,
            quota_series_id,
        )
        rows = self.connection.execute(
            "SELECT id FROM current_observations WHERE "
            + clause
            + " ORDER BY field_name",
            (subject_id,),
        ).fetchall()

        return [self.get_by_id(row["id"]) for row in rows]
