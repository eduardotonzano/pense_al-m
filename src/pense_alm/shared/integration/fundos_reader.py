"""Leitor do banco de Fundos para a camada compartilhada (FU7.2).

Le o SQLite do modulo de Fundos direto, sem importar o pacote fundos: a
camada nao depende de modulo de produto. A conexao e so de leitura em duas
camadas, URI com mode=ro e PRAGMA query_only = ON conferido depois de
abrir. Toda a leitura acontece numa transacao (BEGIN), fechada sempre com
ROLLBACK, para que o retrato seja consistente mesmo com uma carga do modulo
de Fundos rodando ao lado.

Recusas, antes de conectar:
- caminho de rede (UNC): use um banco em disco local;
- arquivo inexistente, curto ou que nao e SQLite;
- banco em WAL (bytes 18 e 19 do cabecalho): mode=ro num banco em WAL pode
  deixar arquivos -wal e -shm ao lado dele.

Retrato do cadastro (ADR-012 e ADR-013):
- a competencia R e a maior reference_date de registro_fundo.Situacao;
- a coleta e a completa mais recente que gravou R; sem nenhuma completa, a
  mais recente que gravou R. Completa: status success na fonte
  CVM_DADOS_ABERTOS, com registro_fundo.csv e registro_classe.csv
  processados e com line_count. Incompleta: o retrato leva o motivo, a
  primeira checagem que falha, nessa ordem (CadastroIncompleteReason);
- os valores sao os brutos de R, todos os distintos de cada campo;
- agrupamento por CNPJ (D6): o fundo com a classe de mesmo CNPJ; a classe
  com CNPJ de outro fundo vai para o grupo desse fundo; a classe que so
  existe como classe forma grupo proprio. Vale o lado do fundo: a classe
  cujo CNPJ e de fundo sem dado em R nao abre grupo;
- papeis so das linhas do cadastro (F-05): administrador e gestor em
  registro_fundo.*, custodiante em registro_classe.*. A classe que so existe
  como classe fica so com o custodiante dela (decisao B1).

CDA (fase 4, INVESTS_IN; PR C): a migration 004 e opcional. Sem ela, ou sem
coleta de CDA, o retrato do CDA so traz o motivo, e o do cadastro nao muda.
Com dados: o L_H de cada detentor e a maior competencia em que ele tem
posicao (identificada ou confidencial), achada pelo MAX do SQL; so as linhas
de holdings do L_H viram objeto. Reapresentacoes da mesma competencia entram
como uniao. Nome e valor da posicao nunca sao lidos.

As mensagens de erro nunca trazem CNPJ, nome ou caminho.
"""

import os
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

from .fundos_records import (
    CadastroIncompleteReason,
    CadastroSnapshot,
    CdaCompetence,
    CdaEmptyPeriod,
    CdaHolderRecord,
    CdaHoldingLink,
    CdaIncompleteReason,
    CdaSnapshot,
    CdaUnavailableReason,
    FundosPartyLink,
    FundosSubjectRecord,
)


SOURCE_CODE = "CVM_DADOS_ABERTOS"
FUND_MEMBER = "registro_fundo.csv"
CLASS_MEMBER = "registro_classe.csv"
REQUIRED_MIGRATIONS = (1, 2)

SQLITE_HEADER = b"SQLite format 3\x00"
HEADER_SIZE = 100
# Bytes 18 e 19 do cabecalho: 1 = diario de rollback, 2 = WAL.
ROLLBACK_JOURNAL_VERSION = 1
WAL_VERSION = 2

FUND_NAME = "registro_fundo.Denominacao_Social"
FUND_SITUATION = "registro_fundo.Situacao"
FUND_TYPE = "registro_fundo.Tipo_Fundo"
FUND_PERSON_TYPE = "registro_fundo.Tipo_Pessoa_Gestor"
CLASS_NAME = "registro_classe.Denominacao_Social"
CLASS_SITUATION = "registro_classe.Situacao"
CLASS_TYPE = "registro_classe.Tipo_Classe"
FIELDS = (
    FUND_NAME,
    FUND_SITUATION,
    FUND_TYPE,
    FUND_PERSON_TYPE,
    CLASS_NAME,
    CLASS_SITUATION,
    CLASS_TYPE,
)

UNC_MESSAGE = "Caminho de rede nao e aceito; use um banco em disco local."

_Q_VALUES = (
    "SELECT fund_id, fund_class_id, field_name, value_text, collection_run_id"
    " FROM observations WHERE reference_date = ? AND field_name IN ("
    + ", ".join("?" * len(FIELDS))
    + ")"
)
_Q_PARTIES = (
    "SELECT id, fund_id, fund_class_id, role, party_cnpj, party_name"
    " FROM party_observations WHERE reference_date = ? AND ("
    "(role IN ('administrador', 'gestor') AND fund_id IS NOT NULL"
    " AND field_name GLOB 'registro_fundo.*')"
    " OR (role = 'custodiante' AND fund_class_id IS NOT NULL"
    " AND field_name GLOB 'registro_classe.*'))"
)
_Q_FUNDS_WITH_DATA = (
    "SELECT DISTINCT fund_id FROM observations WHERE reference_date = ?"
    " AND fund_id IS NOT NULL AND field_name GLOB 'registro_fundo.*'"
)
_Q_CLASSES_WITH_DATA = (
    "SELECT DISTINCT fund_class_id FROM observations WHERE reference_date = ?"
    " AND fund_class_id IS NOT NULL AND field_name GLOB 'registro_classe.*'"
)
_Q_MEMBER = (
    "SELECT processing_status, line_count FROM raw_records"
    " WHERE collection_run_id = ? AND parent_raw_record_id IS NOT NULL"
    " AND file_name = ?"
)

# CDA (fase 4): so ids, CNPJs e datas; nunca nome nem valor da posicao.
CDA_MIGRATION = 4
CDA_TABLES = ("holdings", "confidential_holdings")
CDA_MEMBERS = ("cda_fie_{}.csv", "cda_fie_CONFID_{}.csv")
_CDA_REASONS = tuple(CdaIncompleteReason)
# A coleta do CDA e achada pelo membro cda_fie_AAAAMM.csv e pelas linhas de
# posicao, nao pelo ZIP cda_fi_AAAAMM.zip, e isso basta (conferido no modulo
# de Fundos em 19/11/2026): load_cda (fundos/cda/loader.py) grava a coleta,
# o ZIP, os 12 membros e as posicoes na transacao de quem chama
# (scripts/load_cda.py, Database.transaction(): BEGIN IMMEDIATE ... COMMIT),
# so termina em success e, em qualquer erro, tudo e desfeito; o leitor do
# ZIP recusa ZIP sem os 12 membros. Coleta que falhou ou em andamento nao
# deixa nada visivel. Se o modulo de Fundos passar a gravar a coleta fora
# dessa transacao, a coleta so com o ZIP tem de entrar aqui (C6).
_Q_CDA_MANIFEST = (
    "SELECT DISTINCT collection_run_id, substr(file_name, 9, 6) FROM raw_records"
    " WHERE parent_raw_record_id IS NOT NULL"
    " AND file_name GLOB 'cda_fie_[0-9][0-9][0-9][0-9][0-9][0-9].csv'"
)
_Q_CDA_RUN_DATES = (
    "SELECT collection_run_id, reference_date FROM holdings"
    " UNION SELECT collection_run_id, reference_date FROM confidential_holdings"
)
_Q_CDA_RUN = (
    "SELECT c.started_at, c.status, s.code FROM collection_runs c"
    " JOIN sources s ON s.id = c.source_id WHERE c.id = ?"
)
_CDA_HOLDER = "COALESCE(f.cnpj, c.cnpj)"
_CDA_JOIN = (
    " LEFT JOIN funds f ON f.id = {0}.fund_id"
    " LEFT JOIN fund_classes c ON c.id = {0}.fund_class_id"
)
# L_H pelo MAX do SQL, por detentor (decisao b de 19/11/2026): nenhuma linha
# de competencia antiga vira objeto em Python.
_CDA_LATEST = (
    "WITH latest(holder, competence) AS (SELECT holder, MAX(reference_date)"
    " FROM (SELECT " + _CDA_HOLDER + " AS holder, h.reference_date FROM holdings h"
    + _CDA_JOIN.format("h")
    + " UNION ALL SELECT " + _CDA_HOLDER + ", q.reference_date"
    " FROM confidential_holdings q" + _CDA_JOIN.format("q")
    + ") GROUP BY holder) "
)
_Q_CDA_LATEST = _CDA_LATEST + "SELECT holder, competence FROM latest"
_Q_CDA_LINKS = (
    _CDA_LATEST
    + "SELECT h.id, l.holder, h.investee_cnpj, h.collection_run_id FROM holdings h"
    + _CDA_JOIN.format("h")
    + " JOIN latest l ON l.holder = " + _CDA_HOLDER
    + " AND l.competence = h.reference_date"
)
_Q_CDA_CONFIDENTIAL = (
    _CDA_LATEST
    + "SELECT DISTINCT l.holder FROM confidential_holdings q"
    + _CDA_JOIN.format("q")
    + " JOIN latest l ON l.holder = " + _CDA_HOLDER
    + " AND l.competence = q.reference_date"
)


class FundosReaderError(Exception):
    """Erro da leitura do banco de Fundos (a mensagem nunca traz dado)."""


class FundosDatabaseUnavailable(FundosReaderError):
    """O banco nao pode ser aberto ou lido so para leitura."""


class FundosSchemaError(FundosReaderError):
    """O banco nao tem as migrations ou o formato que o leitor exige."""


class CadastroNotFound(FundosReaderError):
    """O banco nao tem nenhum retrato do cadastro carregado."""


def build_read_only_uri(path) -> str:
    """URI SQLite so de leitura, sem tocar no disco.

    No Windows o resultado e sempre file:///C:/..., nunca file://C:/...
    (o SQLite leria C: como servidor). Espaco, acento, #, % e ? sao
    codificados. Caminho de rede (UNC) e recusado.
    """

    text = os.fspath(path)

    if not isinstance(text, str):
        raise FundosDatabaseUnavailable(
            "O caminho do banco de Fundos deve ser texto."
        )

    if text.startswith(("\\\\", "//")):
        raise FundosDatabaseUnavailable(UNC_MESSAGE)

    posix = Path(text).absolute().as_posix()

    if posix.startswith("//"):
        raise FundosDatabaseUnavailable(UNC_MESSAGE)

    if not posix.startswith("/"):
        posix = "/" + posix

    return "file://" + quote(posix, safe="/:") + "?mode=ro"


def _check_header(path: Path) -> None:
    try:
        with open(path, "rb") as handle:
            header = handle.read(HEADER_SIZE)
    except FileNotFoundError:
        raise FundosDatabaseUnavailable(
            "Banco de Fundos nao encontrado."
        ) from None
    except OSError:
        raise FundosDatabaseUnavailable(
            "Nao foi possivel ler o banco de Fundos."
        ) from None

    if len(header) < HEADER_SIZE or not header.startswith(SQLITE_HEADER):
        raise FundosDatabaseUnavailable(
            "O arquivo informado nao e um banco SQLite."
        )

    versions = (header[18], header[19])

    if WAL_VERSION in versions:
        raise FundosDatabaseUnavailable(
            "O banco de Fundos esta em modo WAL; a camada so le banco "
            "em modo de diario de rollback."
        )

    if versions != (ROLLBACK_JOURNAL_VERSION, ROLLBACK_JOURNAL_VERSION):
        raise FundosDatabaseUnavailable(
            "Versao de arquivo SQLite nao reconhecida."
        )


def _parse_timestamp(value) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise FundosSchemaError(
            "Data de inicio de coleta invalida no banco de Fundos."
        ) from None

    if parsed.utcoffset() is None:
        raise FundosSchemaError(
            "Data de inicio de coleta sem fuso horario no banco de Fundos."
        )

    return parsed.astimezone(UTC)


def _sorted_values(values) -> tuple[str, ...]:
    return tuple(sorted(values or ()))


def _present(value) -> str | None:
    """O texto, ou None se vier ausente, vazio ou so com espacos.

    O CHECK do banco de Fundos usa o trim do SQLite, que so tira espacos:
    tabulacao, quebra de linha e espaco nao separavel passam no banco. Aqui
    vale o criterio do record (str.strip): o que ele recusaria como vazio
    conta como ausente, e a leitura nao para.
    """

    if value is None:
        return None

    text = str(value)

    return text if text.strip() else None


def _check_migrations(connection: sqlite3.Connection) -> None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master"
        " WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()

    if exists is None:
        raise FundosSchemaError(
            "O banco nao tem schema_migrations; nao e um banco de Fundos."
        )

    applied = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations")
    }
    missing = [
        version for version in REQUIRED_MIGRATIONS if version not in applied
    ]

    if missing:
        raise FundosSchemaError(
            "Faltam as migrations "
            + ", ".join(format(version, "03d") for version in missing)
            + " no banco de Fundos."
        )


def _member_reason(connection, run_id, member):
    """Motivo do membro no manifesto da coleta; None quando esta em ordem."""

    rows = connection.execute(_Q_MEMBER, (run_id, member)).fetchall()

    if not rows:
        return CadastroIncompleteReason.MEMBRO_AUSENTE

    processed = [line_count for status, line_count in rows if status == "processed"]

    if not processed:
        return CadastroIncompleteReason.MEMBRO_NAO_PROCESSADO

    if all(line_count is None for line_count in processed):
        return CadastroIncompleteReason.LINE_COUNT_NULO

    return None


def _incomplete_reason(connection, run_id, status, source_code):
    """A primeira checagem que falha, na ordem do CadastroIncompleteReason."""

    if status != "success":
        return CadastroIncompleteReason.STATUS_NAO_SUCCESS

    if source_code != SOURCE_CODE:
        return CadastroIncompleteReason.FONTE_DIFERENTE

    reasons = {
        _member_reason(connection, run_id, member)
        for member in (FUND_MEMBER, CLASS_MEMBER)
    }

    for reason in (
        CadastroIncompleteReason.MEMBRO_AUSENTE,
        CadastroIncompleteReason.MEMBRO_NAO_PROCESSADO,
        CadastroIncompleteReason.LINE_COUNT_NULO,
    ):
        if reason in reasons:
            return reason

    return None


def _choose_run(
    connection,
    run_ids,
) -> tuple[int, datetime, CadastroIncompleteReason | None]:
    """Coleta completa mais recente que gravou R; sem completa, a mais recente."""

    candidates = []

    for run_id in run_ids:
        row = connection.execute(
            "SELECT c.started_at, c.status, s.code FROM collection_runs c"
            " JOIN sources s ON s.id = c.source_id WHERE c.id = ?",
            (run_id,),
        ).fetchone()

        if row is None:
            continue

        reason = _incomplete_reason(connection, run_id, row[1], row[2])
        candidates.append((reason, _parse_timestamp(row[0]), run_id))

    if not candidates:
        raise CadastroNotFound("Nenhuma coleta gravou o retrato do cadastro.")

    complete_ones = [item for item in candidates if item[0] is None]
    pool = complete_ones or candidates
    reason, started_at, run_id = max(pool, key=lambda item: (item[1], item[2]))

    return run_id, started_at, reason


def _read_snapshot(connection: sqlite3.Connection) -> CadastroSnapshot:
    row = connection.execute(
        "SELECT MAX(reference_date) FROM observations WHERE field_name = ?",
        (FUND_SITUATION,),
    ).fetchone()

    if row is None or row[0] is None:
        raise CadastroNotFound("O banco de Fundos nao tem cadastro carregado.")

    reference_text = str(row[0])

    try:
        reference_date = date.fromisoformat(reference_text)
    except ValueError:
        raise FundosSchemaError(
            "Competencia do cadastro invalida no banco de Fundos."
        ) from None

    values = defaultdict(lambda: defaultdict(set))
    run_ids = set()

    for fund_id, class_id, field_name, value, run_id in connection.execute(
        _Q_VALUES,
        (reference_text, *FIELDS),
    ):
        run_ids.add(int(run_id))
        value = _present(value)

        if value is None:
            continue

        if fund_id is not None:
            key = ("funds", int(fund_id))
        elif class_id is not None:
            key = ("fund_classes", int(class_id))
        else:
            continue

        values[key][field_name].add(value)

    collection_run_id, started_at, incomplete_reason = _choose_run(
        connection,
        sorted(run_ids),
    )

    parties = defaultdict(list)

    for party_id, fund_id, class_id, role, cnpj, name in connection.execute(
        _Q_PARTIES,
        (reference_text,),
    ):
        key = (
            ("funds", int(fund_id))
            if fund_id is not None
            else ("fund_classes", int(class_id))
        )
        parties[key].append(
            FundosPartyLink(
                role=str(role),
                cnpj=str(cnpj),
                name=_present(name),
                party_observation_id=int(party_id),
            )
        )

    funds = {
        int(fund_id): str(cnpj)
        for fund_id, cnpj in connection.execute("SELECT id, cnpj FROM funds")
    }
    classes = [
        (int(class_id), int(fund_id), str(cnpj))
        for class_id, fund_id, cnpj in connection.execute(
            "SELECT id, fund_id, cnpj FROM fund_classes"
        )
    ]
    funds_with_data = {
        int(row[0])
        for row in connection.execute(_Q_FUNDS_WITH_DATA, (reference_text,))
    } & funds.keys()
    class_ids = {class_id for class_id, _, _ in classes}
    classes_with_data = {
        int(row[0])
        for row in connection.execute(_Q_CLASSES_WITH_DATA, (reference_text,))
    } & class_ids

    fund_by_cnpj = {cnpj: fund_id for fund_id, cnpj in funds.items()}
    attached = defaultdict(list)
    class_only = []
    same_cnpj = other_fund_cnpj = of_fund_without_data = 0

    for class_id, parent_id, cnpj in sorted(classes):
        if class_id not in classes_with_data:
            continue

        owner = fund_by_cnpj.get(cnpj)

        if owner is None:
            class_only.append((class_id, cnpj))
        elif owner not in funds_with_data:
            of_fund_without_data += 1
        else:
            if owner == parent_id:
                same_cnpj += 1
            else:
                other_fund_cnpj += 1

            attached[owner].append(class_id)

    def ordered(links):
        return tuple(
            sorted(links, key=lambda link: (link.role, link.party_observation_id))
        )

    subjects = []

    for fund_id in sorted(funds_with_data):
        fund_values = values.get(("funds", fund_id), {})
        class_keys = [
            ("fund_classes", class_id) for class_id in attached.get(fund_id, ())
        ]
        class_types = set()
        links = list(parties.get(("funds", fund_id), ()))

        for class_key in class_keys:
            class_types |= values.get(class_key, {}).get(CLASS_TYPE, set())
            links.extend(parties.get(class_key, ()))

        subjects.append(
            FundosSubjectRecord(
                cnpj=funds[fund_id],
                source_table="funds",
                source_id=fund_id,
                names=_sorted_values(fund_values.get(FUND_NAME)),
                situacoes=_sorted_values(fund_values.get(FUND_SITUATION)),
                tipos_fundo=_sorted_values(fund_values.get(FUND_TYPE)),
                tipos_classe=_sorted_values(class_types),
                tipos_pessoa_gestor=_sorted_values(
                    fund_values.get(FUND_PERSON_TYPE)
                ),
                parties=ordered(links),
            )
        )

    for class_id, cnpj in class_only:
        class_values = values.get(("fund_classes", class_id), {})
        subjects.append(
            FundosSubjectRecord(
                cnpj=cnpj,
                source_table="fund_classes",
                source_id=class_id,
                names=_sorted_values(class_values.get(CLASS_NAME)),
                situacoes=_sorted_values(class_values.get(CLASS_SITUATION)),
                tipos_fundo=(),
                tipos_classe=_sorted_values(class_values.get(CLASS_TYPE)),
                tipos_pessoa_gestor=(),
                parties=ordered(parties.get(("fund_classes", class_id), ())),
            )
        )

    return CadastroSnapshot(
        reference_date=reference_date,
        collection_run_id=collection_run_id,
        started_at=started_at,
        complete=incomplete_reason is None,
        incomplete_reason=incomplete_reason,
        funds_in_table=len(funds),
        classes_in_table=len(classes),
        funds_read=len(funds_with_data),
        classes_read=len(classes_with_data),
        classes_same_cnpj=same_cnpj,
        classes_other_fund_cnpj=other_fund_cnpj,
        classes_only_class=len(class_only),
        classes_of_fund_without_data=of_fund_without_data,
        subjects=tuple(subjects),
    )


def _cda_unavailable(connection) -> CdaUnavailableReason | None:
    versions = {
        int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")
    }
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?)",
            CDA_TABLES,
        )
    }

    if CDA_MIGRATION not in versions or tables != set(CDA_TABLES):
        return CdaUnavailableReason.SEM_MIGRATION_004

    return None


def _cda_run_reason(connection, run_id, status, source_code, periods, days):
    """A primeira checagem que falha na coleta do CDA, na ordem do CdaIncompleteReason."""

    if status != "success":
        return CdaIncompleteReason.STATUS_NAO_SUCCESS

    if source_code != SOURCE_CODE:
        return CdaIncompleteReason.FONTE_DIFERENTE

    if not periods:
        return CdaIncompleteReason.MEMBRO_AUSENTE

    found = {
        CdaIncompleteReason(reason.value)
        for period in periods
        for member in CDA_MEMBERS
        if (reason := _member_reason(connection, run_id, member.format(period)))
        is not None
    }

    for reason in _CDA_REASONS:
        if reason in found:
            return reason

    months = {day[:4] + day[5:7] for day in days}

    if len(periods) > 1 or len(days) > 1 or not months <= periods:
        return CdaIncompleteReason.COMPETENCIA_DIVERGENTE

    return None


def _read_cda(connection) -> CdaSnapshot:
    """O CDA do banco de Fundos (fase 4); sem a 004 ou sem coleta, so o motivo."""

    unavailable = _cda_unavailable(connection)

    if unavailable is not None:
        return CdaSnapshot(available=False, unavailable_reason=unavailable)

    periods = defaultdict(set)
    days = defaultdict(set)

    for run_id, period in connection.execute(_Q_CDA_MANIFEST):
        periods[int(run_id)].add(str(period))

    for run_id, day in connection.execute(_Q_CDA_RUN_DATES):
        days[int(run_id)].add(str(day))

    run_ids = sorted(periods.keys() | days.keys())

    if not run_ids:
        return CdaSnapshot(
            available=False,
            unavailable_reason=CdaUnavailableReason.SEM_COLETA_DE_CDA,
        )

    started, reasons = {}, {}

    for run_id in run_ids:
        row = connection.execute(_Q_CDA_RUN, (run_id,)).fetchone()

        if row is None:
            raise FundosSchemaError("Coleta do CDA sem registro em collection_runs.")

        started[run_id] = _parse_timestamp(row[0])
        reasons[run_id] = _cda_run_reason(
            connection, run_id, row[1], row[2], periods[run_id], days[run_id]
        )

    def first_reason(ids):
        found = {reasons[run_id] for run_id in ids}
        return next((reason for reason in _CDA_REASONS if reason in found), None)

    # Coleta sem nenhuma posicao: conta no mes do manifesto (C6).
    empty_by_period = defaultdict(set)
    by_day = defaultdict(set)

    for run_id in run_ids:
        if not days[run_id]:
            for period in periods[run_id]:
                empty_by_period[period].add(run_id)

        for day in days[run_id]:
            by_day[day].add(run_id)

    competences = []

    for day in sorted(by_day):
        with_rows = by_day[day]
        ids = sorted(with_rows | empty_by_period.get(day[:4] + day[5:7], set()))
        closing = max(with_rows, key=lambda run_id: (started[run_id], run_id))
        competences.append(
            CdaCompetence(
                date.fromisoformat(day),
                tuple(ids),
                closing,
                started[closing],
                first_reason(ids),
            )
        )

    months = {item.period for item in competences}
    empty_periods = tuple(
        CdaEmptyPeriod(period, tuple(sorted(ids)), first_reason(ids))
        for period, ids in sorted(empty_by_period.items())
        if period not in months
    )
    links = defaultdict(list)

    for holding_id, holder, investee, run_id in connection.execute(_Q_CDA_LINKS):
        links[str(holder)].append(
            CdaHoldingLink(
                investee_cnpj=str(investee),
                holding_id=int(holding_id),
                collected_at=started[int(run_id)],
            )
        )

    confidential = {str(row[0]) for row in connection.execute(_Q_CDA_CONFIDENTIAL)}
    holders = tuple(
        CdaHolderRecord(
            cnpj=str(holder),
            competence=date.fromisoformat(str(competence)),
            has_identified=bool(links.get(str(holder))),
            has_confidential=str(holder) in confidential,
            links=tuple(
                sorted(links.get(str(holder), ()), key=lambda link: link.holding_id)
            ),
        )
        for holder, competence in sorted(connection.execute(_Q_CDA_LATEST).fetchall())
    )

    return CdaSnapshot(
        available=True,
        competences=tuple(competences),
        empty_periods=empty_periods,
        holders=holders,
    )


class FundosDatabaseReader:
    """Le o retrato do cadastro do banco de Fundos, so para leitura."""

    def __init__(self, database_path) -> None:
        self._database_path = database_path

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        """Conexao mode=ro com query_only conferido, dentro de BEGIN.

        A transacao e sempre fechada com ROLLBACK, e a conexao, fechada.
        """

        uri = build_read_only_uri(self._database_path)
        _check_header(Path(os.fspath(self._database_path)).absolute())

        try:
            connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        except sqlite3.Error:
            raise FundosDatabaseUnavailable(
                "Nao foi possivel abrir o banco de Fundos."
            ) from None

        try:
            try:
                connection.execute("PRAGMA query_only = ON")
                query_only = connection.execute("PRAGMA query_only").fetchone()[0]

                if query_only != 1:
                    raise FundosDatabaseUnavailable(
                        "Nao foi possivel ligar o modo so leitura."
                    )

                connection.execute("BEGIN")
            except sqlite3.Error:
                raise FundosDatabaseUnavailable(
                    "Nao foi possivel abrir a leitura do banco de Fundos."
                ) from None

            try:
                yield connection
            finally:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
        finally:
            connection.close()

    def read_cadastro(self) -> CadastroSnapshot:
        """Le o retrato do cadastro mais recente (competencia R)."""

        with self.session() as connection:
            try:
                _check_migrations(connection)
                return _read_snapshot(connection)
            except sqlite3.Error as error:
                # So o tipo do erro: a mensagem do SQLite fica de fora.
                raise FundosDatabaseUnavailable(
                    "Erro de leitura no banco de Fundos ("
                    + type(error).__name__
                    + ")."
                ) from None

    def _read(self, reader):
        with self.session() as connection:
            try:
                _check_migrations(connection)
                return reader(connection)
            except sqlite3.Error as error:
                raise FundosDatabaseUnavailable(
                    "Erro de leitura no banco de Fundos ("
                    + type(error).__name__
                    + ")."
                ) from None

    def read_cda(self) -> CdaSnapshot:
        """Le o CDA (fase 4); sem a migration 004 ou sem coleta, so o motivo."""

        return self._read(_read_cda)

    def read_all(self) -> tuple[CadastroSnapshot, CdaSnapshot]:
        """Le o cadastro e o CDA numa sessao so (um BEGIN): retrato consistente."""

        return self._read(lambda connection: (_read_snapshot(connection), _read_cda(connection)))
