"""Leitura das observacoes por competencia, so para leitura (FU11.1).

A view current_observations guarda so a competencia mais recente de cada
assunto e campo. Serve ao valor atual, mas nao a serie mensal, e misturaria
competencias num mesmo indicador: um campo que viesse vazio no mes novo
continuaria com o valor do mes anterior. Aqui vale a mesma regra de ordem da
view (so fontes ativas; prioridade da fonte, depois coleta mais recente,
depois id), aplicada DENTRO de cada competencia. Na competencia mais recente,
o resultado e o mesmo da view, exceto quando uma fonte de prioridade maior so
tem competencia antiga: a view poe a prioridade antes da competencia e mostra
esse valor antigo; aqui cada competencia fica com o que foi informado nela.

Conexao (open_read_only): URI mode=ro e PRAGMA query_only conferido. Recusa
caminho de rede e banco em WAL (mode=ro num banco em WAL pode deixar os
arquivos -wal e -shm ao lado dele). As leituras acontecem numa transacao
(BEGIN) fechada sempre com ROLLBACK, para que o retrato seja consistente.

So assuntos de classe e de fundo (series ficam de fora). Valor ausente nao
tem linha e volta como sem_dado (campo_ausente), nunca zero. Valor que nao
veio como numero volta como sem_dado (tipo_inesperado), sem repetir o valor.
Campo de identificacao (CPF ou CNPJ no nome) e coluna da lista de cedentes
da tab_I (TAB_I2A12_* e TAB_I2B12_*, que cedentes le de party_observations)
sao recusados antes de consultar o banco. As mensagens de erro nunca trazem
caminho, CNPJ ou valor.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date
from datetime import timedelta
from decimal import Decimal
from decimal import InvalidOperation
from pathlib import Path

from fundos.cnpj import normalize_cnpj
from fundos.database import normalize_iso_date
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject
from fundos.personal_data import is_identification_column


SQLITE_HEADER = b"SQLite format 3\x00"
HEADER_SIZE = 100
# Bytes 18 e 19 do cabecalho: 1 = diario de rollback, 2 = WAL.
WAL_VERSION = 2

FIELD_NAME = re.compile(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+")
_CEDENTE_LIST = ("TAB_I2A12_", "TAB_I2B12_")


class IndicatorDatabaseError(Exception):
    """O banco de Fundos nao pode ser aberto para leitura."""


def _check_path(path):
    text = os.fspath(path)

    if not isinstance(text, str) or not text.strip():
        raise IndicatorDatabaseError("O caminho do banco e obrigatorio.")

    absolute = Path(text).absolute()

    if text.startswith(("\\\\", "//")) or absolute.as_posix().startswith("//"):
        raise IndicatorDatabaseError(
            "Caminho de rede recusado: use um banco em disco local."
        )

    try:
        with open(absolute, "rb") as handle:
            header = handle.read(HEADER_SIZE)
    except OSError:
        raise IndicatorDatabaseError("Nao foi possivel ler o banco.") from None

    if len(header) < HEADER_SIZE or not header.startswith(SQLITE_HEADER):
        raise IndicatorDatabaseError("O arquivo informado nao e um banco SQLite.")

    if WAL_VERSION in (header[18], header[19]):
        raise IndicatorDatabaseError(
            "Banco em modo WAL recusado: a leitura usa so banco em modo de "
            "diario de rollback."
        )

    # as_uri codifica espaco, acento, # e ? e, no Windows, da file:///C:/...
    return absolute.as_uri() + "?mode=ro"


def open_read_only(path):
    """Abre um banco de Fundos existente so para leitura (mode=ro e query_only).

    Quem chama fecha a conexao.
    """

    uri = _check_path(path)

    try:
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    except sqlite3.Error:
        raise IndicatorDatabaseError("Nao foi possivel abrir o banco.") from None

    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")

        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise IndicatorDatabaseError(
                "Nao foi possivel ligar o modo so leitura."
            )
    except BaseException:
        connection.close()
        raise

    return connection


@contextmanager
def read_snapshot(connection):
    """Transacao de leitura (BEGIN ... ROLLBACK) para um retrato consistente.

    Se a conexao ja estiver numa transacao, usa a de quem chama.
    """

    if connection.in_transaction:
        yield connection
        return

    connection.execute("BEGIN")

    try:
        yield connection
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")


def check_field_names(field_names):
    """Lista fechada de campos tabela.coluna, sem campo de identificacao."""

    names = tuple(field_names)

    if not names:
        raise ValueError("Informe pelo menos um campo.")

    for name in names:
        if not isinstance(name, str) or FIELD_NAME.fullmatch(name) is None:
            raise ValueError("Campo fora do formato tabela.coluna.")

        column = name.split(".", 1)[1]

        if is_identification_column(column) or column.upper().startswith(_CEDENTE_LIST):
            raise ValueError(
                "Campo de identificacao (CPF ou CNPJ) ou da lista de cedentes "
                "nao e lido aqui."
            )

    if len(set(names)) != len(names):
        raise ValueError("Campo repetido na lista.")

    return names


def previous_month_end(reference_date):
    """Ultimo dia do mes anterior; a competencia tem de ser fim de mes."""

    current = date.fromisoformat(normalize_iso_date(reference_date, "Competencia"))

    if (current + timedelta(days=1)).day != 1:
        raise ValueError("A competencia deve ser o ultimo dia do mes.")

    return (current.replace(day=1) - timedelta(days=1)).isoformat()


def _placeholders(values):
    return ",".join("?" * len(values))


def subjects_by_cnpj(connection, cnpj):
    """Os assuntos (fundo e/ou classe) com este CNPJ; nunca casa por nome."""

    normalized = normalize_cnpj(cnpj)
    found = []

    for kind, table in ((FUND_SUBJECT, "funds"), (CLASS_SUBJECT, "fund_classes")):
        row = connection.execute(
            "SELECT id FROM " + table + " WHERE cnpj = ?", (normalized,)
        ).fetchone()

        if row is not None:
            found.append(Subject(kind, row[0], normalized))

    return tuple(sorted(found))


def loaded_competences(connection, field_names):
    """Competencias (em ordem) com alguma observacao dos campos, de fonte ativa."""

    names = check_field_names(field_names)
    rows = connection.execute(
        "SELECT DISTINCT o.reference_date FROM observations o"
        " JOIN sources s ON s.id = o.source_id"
        " WHERE s.active = 1 AND o.quota_series_id IS NULL"
        " AND o.field_name IN (" + _placeholders(names) + ")"
        " ORDER BY o.reference_date",
        names,
    ).fetchall()

    return tuple(row[0] for row in rows)


def subject_filter(subjects, alias="o"):
    """Trecho " AND (...)" e parametros que limitam a consulta aos assuntos."""

    funds = sorted({s.id for s in subjects if s.kind == FUND_SUBJECT})
    classes = sorted({s.id for s in subjects if s.kind == CLASS_SUBJECT})
    clauses = []

    if funds:
        clauses.append(alias + ".fund_id IN (" + _placeholders(funds) + ")")

    if classes:
        clauses.append(alias + ".fund_class_id IN (" + _placeholders(classes) + ")")

    return " AND (" + " OR ".join(clauses) + ")", tuple(funds) + tuple(classes)


def check_subjects(subjects):
    """Tupla de Subject de classe ou fundo; recusa qualquer outra coisa."""

    subjects = tuple(subjects)

    for subject in subjects:
        if not isinstance(subject, Subject) or subject.kind not in (
            CLASS_SUBJECT,
            FUND_SUBJECT,
        ):
            raise ValueError("Assunto invalido: use Subject de classe ou fundo.")

    return subjects


def _numeric(value_type, value_numeric):
    if value_type != "numeric" or value_numeric is None:
        return None

    try:
        return Decimal(value_numeric)
    except InvalidOperation:
        return None


def read_competence(connection, reference_date, field_names, subjects=None):
    """Valores dos campos numa competencia, por assunto.

    Devolve {Subject: {campo: FieldValue}} so para os assuntos com pelo menos
    um dos campos na competencia; o campo que o assunto nao tem volta como
    sem_dado (campo_ausente). subjects (opcional) limita a leitura.
    """

    reference = normalize_iso_date(reference_date, "Competencia")
    names = check_field_names(field_names)
    where, parameters = "", ()

    if subjects is not None:
        subjects = check_subjects(subjects)

        if not subjects:
            return {}

        where, parameters = subject_filter(subjects)

    with read_snapshot(connection):
        rows = connection.execute(
            "SELECT o.id, o.fund_id, o.fund_class_id, o.field_name,"
            " o.value_type, o.value_numeric, o.collected_at, o.source_code,"
            " f.cnpj AS fund_cnpj, c.cnpj AS class_cnpj"
            " FROM (SELECT o.*, s.code AS source_code, ROW_NUMBER() OVER ("
            "   PARTITION BY o.fund_id, o.fund_class_id, o.field_name, o.reference_date"
            "   ORDER BY s.priority DESC, o.collected_at DESC, o.id DESC) AS rn"
            "  FROM observations o JOIN sources s ON s.id = o.source_id"
            "  WHERE s.active = 1 AND o.quota_series_id IS NULL"
            "  AND o.reference_date = ?"
            "  AND o.field_name IN (" + _placeholders(names) + ")"
            + where
            + ") o"
            " LEFT JOIN funds f ON f.id = o.fund_id"
            " LEFT JOIN fund_classes c ON c.id = o.fund_class_id"
            " WHERE o.rn = 1",
            (reference,) + names + parameters,
        ).fetchall()
        conflicts = {
            (row[0], row[1], row[2])
            for row in connection.execute(
                "SELECT o.fund_id, o.fund_class_id, o.field_name"
                " FROM data_conflicts d JOIN observations o"
                " ON o.id = d.observation_a_id OR o.id = d.observation_b_id"
                " WHERE d.status = 'open' AND d.reference_date = ?"
                " AND d.field_name IN (" + _placeholders(names) + ")",
                (reference,) + names,
            )
        }

    found = {}

    for row in rows:
        fund_id, class_id = row[1], row[2]

        if fund_id is not None:
            subject = Subject(FUND_SUBJECT, fund_id, row[8])
        else:
            subject = Subject(CLASS_SUBJECT, class_id, row[9])

        value = _numeric(row[4], row[5])
        provenance = {
            "observation_id": row[0],
            "source_code": row[7],
            "collected_at": row[6],
            "open_conflict": (fund_id, class_id, row[3]) in conflicts,
        }

        if value is None:
            field_value = FieldValue(
                field_name=row[3],
                reference_date=reference,
                state=NO_DATA,
                reason=REASON_UNEXPECTED_TYPE,
                **provenance,
            )
        else:
            field_value = FieldValue(
                field_name=row[3],
                reference_date=reference,
                state=PRESENT,
                value=value,
                **provenance,
            )

        found.setdefault(subject, {})[row[3]] = field_value

    return {
        subject: {
            name: values.get(name) or FieldValue.missing(name, reference)
            for name in names
        }
        for subject, values in sorted(found.items())
    }
