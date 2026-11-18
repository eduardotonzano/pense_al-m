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
