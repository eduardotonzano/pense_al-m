"""Posicoes em cotas de fundos (migration 004): identificadas e confidenciais.

Posicao e valor no tempo, nao relacao de identidade: o detentor e um fundo
ou uma classe ja cadastrados; o investido e so o CNPJ, sem FK. A guarda de
dados pessoais roda antes de qualquer SQL: o investido so aceita CNPJ
valido e normalizado, e o nome (EMISSOR) nunca tem formato de CPF.

holdings: chave assunto + investido + competencia + line_order (a ordem da
linha na chave, decisao 2 da FU6.1); o valor e a quantidade, o valor de
mercado e o nome. Linhas da mesma (assunto, investido, competencia) com
ordens diferentes sao posicoes distintas, sem conflito entre si; nenhuma
soma e gravada. confidential_holdings: chave assunto +
competencia; o valor e o valor de mercado e a data do fim da
confidencialidade. O checksum cobre a chave, a fonte e o valor: gravar de
novo o mesmo valor devolve a linha existente. Valor diferente para a mesma
chave gera linha nova e conflito aberto (holding_conflicts ou
confidential_holding_conflicts); nada e sobrescrito.

Limitacao: a posicao que some numa reapresentacao da mesma competencia nao
gera conflito, e um valor que volta a um valor anterior nao grava linha
nova (o checksum ja existe).
"""

import hashlib
import json
from dataclasses import dataclass

from fundos.cnpj import is_valid_cnpj
from fundos.cnpj import looks_like_cpf
from fundos.database import normalize_iso_date
from fundos.database import normalize_timestamp
from fundos.personal_data import PersonalDataError
from fundos.personal_data import check_observation
from fundos.personal_data import column_of
from fundos.personal_data import is_identification_column
from fundos.repositories.observation_repository import FIELD_NAME
from fundos.repositories.observation_repository import canonical_decimal


SUBJECTS = (
    ("fund_id", "funds"),
    ("fund_class_id", "fund_classes"),
)


@dataclass(frozen=True)
class HoldingRecord:
    """Uma posicao identificada gravada, com toda a proveniencia."""

    id: int
    fund_id: int | None
    fund_class_id: int | None
    investee_field_name: str
    investee_cnpj: str
    name_field_name: str | None
    investee_name: str | None
    quantity_field_name: str | None
    quantity: str | None
    value_field_name: str
    market_value: str
    source_id: int
    collection_run_id: int
    raw_record_id: int
    reference_date: str
    line_order: int
    collected_at: str
    checksum: str


@dataclass(frozen=True)
class ConfidentialHoldingRecord:
    """Um consolidado confidencial gravado, com toda a proveniencia."""

    id: int
    fund_id: int | None
    fund_class_id: int | None
    value_field_name: str
    market_value: str
    confidential_until_field_name: str
    confidential_until: str
    source_id: int
    collection_run_id: int
    raw_record_id: int
    reference_date: str
    collected_at: str
    checksum: str


@dataclass(frozen=True)
class HoldingRecordResult:
    """Resultado de record(): a posicao, se foi criada e os ids dos conflitos novos."""

    holding: HoldingRecord | ConfidentialHoldingRecord
    created: bool
    conflicts: tuple[int, ...]


# Por tabela: (registro, tabela de conflito, colunas do par, colunas da
# chave alem do assunto, colunas do valor).
_TABLES = {
    "holdings": (
        HoldingRecord,
        "holding_conflicts",
        ("holding_a_id", "holding_b_id"),
        ("investee_cnpj", "reference_date", "line_order"),
        ("quantity", "market_value", "investee_name"),
    ),
    "confidential_holdings": (
        ConfidentialHoldingRecord,
        "confidential_holding_conflicts",
        ("confidential_holding_a_id", "confidential_holding_b_id"),
        ("reference_date",),
        ("market_value", "confidential_until"),
    ),
}


def _field_name(value, label):
    if not isinstance(value, str) or FIELD_NAME.fullmatch(value) is None:
        raise ValueError("O campo " + label + " deve ser tabela.coluna da CVM.")

    return value


def _value_field(value, label):
    """Campo de valor: tabela.coluna, sem cpf nem cnpj no nome da coluna."""

    _field_name(value, label)

    if is_identification_column(column_of(value)):
        raise PersonalDataError(
            "O campo " + label + " nao pode ser de identificacao: " + value + ". Nada foi gravado."
        )

    check_observation(value, "numeric", "0")
    return value


def _decimal(value, label):
    try:
        return canonical_decimal(value)
    except ValueError as error:
        raise ValueError(label + " fora do formato decimal.") from error


class HoldingRepository:
    """Grava e le as posicoes em cotas de fundos e classes."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def subject(fund_id=None, fund_class_id=None):
        """Devolve (coluna, tabela, id) do unico assunto informado."""

        given = [
            (column, table, value)
            for (column, table), value in zip(SUBJECTS, (fund_id, fund_class_id))
            if value is not None
        ]

        if len(given) != 1:
            raise ValueError("Informe exatamente um assunto: fundo ou classe.")

        return given[0]

    @staticmethod
    def checksum(table, subject_column, subject_id, source_id, key, value):
        """SHA-256 da tabela, do assunto, da fonte, da chave e do valor."""

        data = {
            "table": table,
            "subject": subject_column,
            "subject_id": int(subject_id),
            "source_id": int(source_id),
            "key": list(key),
            "value": list(value),
        }
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_by_id(self, table, row_id):
        """Busca uma posicao pelo ID (table: holdings ou confidential_holdings)."""

        record_type = _TABLES[table][0]
        row = self.connection.execute("SELECT * FROM " + table + " WHERE id = ?", (row_id,)).fetchone()

        if row is None:
            return None

        return record_type(**{name: row[name] for name in record_type.__dataclass_fields__})

    def _provenance(self, subject_table, subject_id, source_id, collection_run_id, raw_record_id, collected_at):
        """Confere o assunto, a coleta e o manifesto; devolve collected_at normalizado."""

        if self.connection.execute(
            "SELECT id FROM " + subject_table + " WHERE id = ?",
            (subject_id,),
        ).fetchone() is None:
            raise ValueError("O assunto informado nao existe.")

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

        if collected_at is None:
            return str(raw["collected_at"])

        return normalize_timestamp(collected_at, "A data de coleta")

    def record(
        self,
        *,
        fund_id=None,
        fund_class_id=None,
        investee_field_name,
        investee_cnpj,
        name_field_name=None,
        investee_name=None,
        quantity_field_name=None,
        quantity=None,
        value_field_name,
        market_value,
        source_id,
        collection_run_id,
        raw_record_id,
        reference_date,
        line_order,
        collected_at=None,
    ):
        """Grava a posicao identificada; devolve HoldingRecordResult.

        line_order e a ordem da linha (1, 2, 3...) entre as linhas da mesma
        (assunto, investido, competencia) no arquivo. O nome so entra com o
        campo do nome, e a quantidade so com o campo da quantidade. Mesmo
        assunto, fonte, investido, competencia, ordem e valor: devolve a
        linha existente (idempotente).
        """

        if isinstance(line_order, bool) or not isinstance(line_order, int) or line_order < 1:
            raise ValueError("A ordem da linha na chave deve ser inteiro a partir de 1.")

        _field_name(investee_field_name, "do investido")

        # Guarda de dados pessoais antes de qualquer SQL: o investido so
        # aceita CNPJ valido e normalizado.
        check_observation(investee_field_name, "text", investee_cnpj)

        if not is_valid_cnpj(investee_cnpj):
            raise PersonalDataError(
                "Posicao so aceita CNPJ valido e normalizado: " + investee_field_name + ". Nada foi gravado."
            )

        if (name_field_name is None) != (investee_name is None):
            raise ValueError("O nome do investido e o campo do nome vem juntos ou nao vem.")

        if investee_name is not None:
            _field_name(name_field_name, "do nome")
            check_observation(name_field_name, "text", investee_name)

            if not isinstance(investee_name, str) or not investee_name.strip():
                raise ValueError("Nome ausente nao e gravado.")

            if looks_like_cpf(investee_name):
                raise PersonalDataError(
                    "Nome com formato de CPF: " + name_field_name + ". Nada foi gravado."
                )

        if (quantity_field_name is None) != (quantity is None):
            raise ValueError("A quantidade e o campo da quantidade vem juntos ou nao vem.")

        if quantity is not None:
            _value_field(quantity_field_name, "da quantidade")
            quantity = _decimal(quantity, "A quantidade")

        _value_field(value_field_name, "do valor")
        market_value = _decimal(market_value, "O valor de mercado")
        reference = normalize_iso_date(reference_date, "A competencia")

        return self._insert(
            "holdings",
            fund_id,
            fund_class_id,
            {
                "investee_field_name": investee_field_name,
                "investee_cnpj": investee_cnpj,
                "name_field_name": name_field_name,
                "investee_name": investee_name,
                "quantity_field_name": quantity_field_name,
                "quantity": quantity,
                "value_field_name": value_field_name,
                "market_value": market_value,
                "reference_date": reference,
                "line_order": line_order,
            },
            source_id,
            collection_run_id,
            raw_record_id,
            collected_at,
        )

    def record_confidential(
        self,
        *,
        fund_id=None,
        fund_class_id=None,
        value_field_name,
        market_value,
        confidential_until_field_name,
        confidential_until,
        source_id,
        collection_run_id,
        raw_record_id,
        reference_date,
        collected_at=None,
    ):
        """Grava o consolidado confidencial; devolve HoldingRecordResult."""

        _value_field(value_field_name, "do valor")
        _value_field(confidential_until_field_name, "da data de confidencialidade")

        return self._insert(
            "confidential_holdings",
            fund_id,
            fund_class_id,
            {
                "value_field_name": value_field_name,
                "market_value": _decimal(market_value, "O valor de mercado"),
                "confidential_until_field_name": confidential_until_field_name,
                "confidential_until": normalize_iso_date(confidential_until, "A data de confidencialidade"),
                "reference_date": normalize_iso_date(reference_date, "A competencia"),
            },
            source_id,
            collection_run_id,
            raw_record_id,
            collected_at,
        )

    def find_existing(self, table, subject_column, subject_id, source_id, values):
        """A linha com o mesmo checksum, ou None (so le)."""

        _, _, _, key_columns, value_columns = _TABLES[table]
        checksum = self.checksum(
            table,
            subject_column,
            subject_id,
            source_id,
            [values[c] for c in key_columns],
            [values[c] for c in value_columns],
        )
        row = self.connection.execute("SELECT id FROM " + table + " WHERE checksum = ?", (checksum,)).fetchone()

        return None if row is None else int(row[0])

    def has_key(self, table, subject_column, subject_id, values):
        """Indica se ja existe alguma linha com a mesma chave (so le)."""

        key_columns = _TABLES[table][3]

        return self.connection.execute(
            "SELECT 1 FROM "
            + table
            + " WHERE "
            + subject_column
            + " = ? AND "
            + " AND ".join(column + " = ?" for column in key_columns)
            + " LIMIT 1",
            (subject_id, *[values[c] for c in key_columns]),
        ).fetchone() is not None

    def _insert(self, table, fund_id, fund_class_id, values, source_id, collection_run_id, raw_record_id, collected_at):
        record_type, conflict_table, pair, key_columns, value_columns = _TABLES[table]
        subject_column, subject_table, subject_id = self.subject(fund_id, fund_class_id)
        normalized_collected_at = self._provenance(
            subject_table, subject_id, source_id, collection_run_id, raw_record_id, collected_at
        )
        checksum = self.checksum(
            table,
            subject_column,
            subject_id,
            source_id,
            [values[c] for c in key_columns],
            [values[c] for c in value_columns],
        )
        existing = self.connection.execute("SELECT id FROM " + table + " WHERE checksum = ?", (checksum,)).fetchone()

        if existing is not None:
            return HoldingRecordResult(self.get_by_id(table, int(existing[0])), False, ())

        row = {
            subject_column: subject_id,
            **values,
            "source_id": source_id,
            "collection_run_id": collection_run_id,
            "raw_record_id": raw_record_id,
            "collected_at": normalized_collected_at,
            "checksum": checksum,
        }
        savepoint = "fundos_" + table + "_record"
        self.connection.execute("SAVEPOINT " + savepoint)

        try:
            cursor = self.connection.execute(
                "INSERT INTO " + table + " (" + ", ".join(row) + ") VALUES (" + ", ".join("?" * len(row)) + ")",
                tuple(row.values()),
            )
            new_id = cursor.lastrowid
            others = self.connection.execute(
                "SELECT id, "
                + ", ".join(value_columns)
                + " FROM "
                + table
                + " WHERE "
                + subject_column
                + " = ? AND "
                + " AND ".join(column + " = ?" for column in key_columns)
                + " AND id <> ?",
                (subject_id, *[values[c] for c in key_columns], new_id),
            ).fetchall()
            value = tuple(values[c] for c in value_columns)
            conflicts = []

            for other in others:
                if tuple(other[c] for c in value_columns) == value:
                    continue

                first, second = sorted((int(other["id"]), new_id))
                inserted = self.connection.execute(
                    "INSERT OR IGNORE INTO "
                    + conflict_table
                    + " (reference_date, "
                    + ", ".join(pair)
                    + ") VALUES (?, ?, ?)",
                    (values["reference_date"], first, second),
                )

                if inserted.rowcount == 1:
                    conflicts.append(int(inserted.lastrowid))

            self.connection.execute("RELEASE SAVEPOINT " + savepoint)
        except BaseException:
            self.connection.execute("ROLLBACK TO SAVEPOINT " + savepoint)
            self.connection.execute("RELEASE SAVEPOINT " + savepoint)
            raise

        return HoldingRecordResult(self.get_by_id(table, new_id), True, tuple(conflicts))

    def list_open_conflicts(self, table):
        """Ids dos conflitos abertos (table: holding_conflicts ou confidential_holding_conflicts)."""

        if table not in ("holding_conflicts", "confidential_holding_conflicts"):
            raise ValueError("Tabela de conflito invalida.")

        return [
            int(row[0])
            for row in self.connection.execute("SELECT id FROM " + table + " WHERE status = 'open' ORDER BY id")
        ]
