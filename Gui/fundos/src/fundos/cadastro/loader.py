"""Gravacao do cadastro filtrado (FIDC e FIAGRO) no banco de Fundos.

Roda dentro da transacao de quem chama (Database.transaction()): uma coleta
da fonte CVM_DADOS_ABERTOS, o manifesto do ZIP e dos 3 CSV (hash e linhas),
fundos, classes, observacoes e papeis. O registro_subclasse entra so no
manifesto, com processing_status 'ignored'. Antes do COMMIT, verify() confere
integridade, chaves estrangeiras, colunas com 'cpf' e procura texto com
formato de CPF no que esta coleta gravou; qualquer problema desfaz tudo.

A competencia (reference_date) e a do retrato do cadastro, informada por
quem chama; nunca a data da coleta (ADR-010).
"""

from collections import Counter
from dataclasses import dataclass

from fundos.cadastro import columns as spec
from fundos.database import normalize_iso_date
from fundos.personal_data import find_cpf_columns
from fundos.repositories import IdentityConflictError
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.fund_class_repository import FundClassRepository
from fundos.repositories.fund_repository import FundRepository
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


SOURCE_CODE = "CVM_DADOS_ABERTOS"
PARSER_VERSION = "fundos.cadastro.v1"
REQUIRED_MIGRATIONS = {
    1: "initial_schema",
    2: "party_observations",
}

# Texto inteiro com formato de CPF: 11 digitos ou a mascara NNN.NNN.NNN-NN.
# Medido no cadastro de 27/10/2026: nenhum texto gravado tem esse formato
# (nem ID_Registro_*, nem Codigo_CVM, nem nomes), entao a varredura nao
# desfaz a carga por falso positivo.
CPF_GLOBS = (
    "[0-9]" * 11,
    "[0-9][0-9][0-9].[0-9][0-9][0-9].[0-9][0-9][0-9]-[0-9][0-9]",
)


class LoadError(Exception):
    """A carga foi recusada ou falhou; nada foi gravado."""


@dataclass(frozen=True)
class LoadedZip:
    """O ZIP ja carregado e as competencias gravadas a partir dele."""

    raw_record_id: int
    reference_dates: tuple[str, ...]


@dataclass(frozen=True)
class LoadResult:
    """Resultado da carga: a coleta e as contagens."""

    run_id: int
    status: str
    counts: Counter


def applied_migrations(connection):
    """{versao: nome} das migrations registradas (vazio sem schema_migrations)."""

    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()

    if exists is None:
        return {}

    return {
        int(row[0]): str(row[1])
        for row in connection.execute("SELECT version, name FROM schema_migrations")
    }


def missing_migrations(connection):
    """Migrations que a carga exige e o banco nao tem, como NNN_nome."""

    applied = applied_migrations(connection)

    return [
        format(version, "03d") + "_" + name
        for version, name in sorted(REQUIRED_MIGRATIONS.items())
        if applied.get(version) != name
    ]


def find_loaded_zip(connection, zip_manifest):
    """O ZIP (mesmo SHA-256) ja processado nesta fonte, ou None."""

    row = connection.execute(
        """
        SELECT r.id
        FROM raw_records r
        JOIN sources s ON s.id = r.source_id
        WHERE s.code = ?
          AND r.parent_raw_record_id IS NULL
          AND r.sha256 = ?
          AND r.processing_status = 'processed'
        ORDER BY r.id
        LIMIT 1
        """,
        (SOURCE_CODE, zip_manifest.sha256),
    ).fetchone()

    if row is None:
        return None

    dates = connection.execute(
        """
        SELECT reference_date FROM observations
        WHERE raw_record_id IN (SELECT id FROM raw_records WHERE parent_raw_record_id = ?)
        UNION
        SELECT reference_date FROM party_observations
        WHERE raw_record_id IN (SELECT id FROM raw_records WHERE parent_raw_record_id = ?)
        ORDER BY 1
        """,
        (row["id"], row["id"]),
    ).fetchall()

    return LoadedZip(
        raw_record_id=int(row["id"]),
        reference_dates=tuple(str(date[0]) for date in dates),
    )


def count_cpf_like(connection, run_id):
    """(observations, party_observations) desta coleta com texto em formato de CPF."""

    observations = connection.execute(
        "SELECT COUNT(*) FROM observations WHERE collection_run_id = ?"
        " AND value_type = 'text' AND (trim(value_text) GLOB ? OR trim(value_text) GLOB ?)",
        (run_id,) + CPF_GLOBS,
    ).fetchone()[0]
    parties = connection.execute(
        "SELECT COUNT(*) FROM party_observations WHERE collection_run_id = ?"
        " AND (trim(party_name) GLOB ? OR trim(party_name) GLOB ?"
        " OR party_cnpj GLOB ? OR party_cnpj GLOB ?)",
        (run_id,) + CPF_GLOBS + CPF_GLOBS,
    ).fetchone()[0]

    return int(observations), int(parties)


def verify(connection, run_id):
    """Problemas encontrados antes do COMMIT (lista vazia se nenhum)."""

    problems = []
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

    if integrity != "ok":
        problems.append("integrity_check retornou: " + str(integrity))

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

    if foreign_key_errors:
        problems.append(
            "foreign_key_check encontrou "
            + str(len(foreign_key_errors))
            + " problema(s)."
        )

    for column in find_cpf_columns(connection):
        problems.append("Coluna ou objeto com 'cpf' no nome: " + column + ".")

    observations, parties = count_cpf_like(connection, run_id)

    if observations or parties:
        problems.append(
            "Texto com formato de CPF gravado nesta coleta: "
            + str(observations)
            + " em observations, "
            + str(parties)
            + " em party_observations."
        )

    return problems


class _Writer:
    """Grava fundos, classes, observacoes e papeis de uma coleta."""

    def __init__(self, connection, source_id, run_id, reference_date, counts):
        self.source_id = source_id
        self.run_id = run_id
        self.reference_date = reference_date
        self.counts = counts
        self.observations = ObservationRepository(connection)
        self.parties = PartyObservationRepository(connection)

    def subject(self, table, subject_id, selected, raw_record_id):
        subject = {"fund_id" if table == spec.FUND_TABLE else "fund_class_id": subject_id}

        for column, value in selected.values.items():
            kind = spec.KINDS[table][column]
            result = self.observations.record(
                **subject,
                source_id=self.source_id,
                collection_run_id=self.run_id,
                raw_record_id=raw_record_id,
                field_name=spec.field_name(table, column),
                value_type=kind,
                value=value,
                reference_date=self.reference_date,
            )
            self.counts[("observacoes", table, kind, "criadas" if result.created else "existentes")] += 1
            self.counts[("conflitos", "data_conflicts")] += len(result.conflicts)

        for party in selected.parties:
            result = self.parties.record(
                **subject,
                role=party.role,
                field_name=party.field_name,
                party_cnpj=party.cnpj,
                name_field_name=party.name_field_name,
                party_name=party.name,
                source_id=self.source_id,
                collection_run_id=self.run_id,
                raw_record_id=raw_record_id,
                reference_date=self.reference_date,
            )
            self.counts[("papeis", party.role, "criados" if result.created else "existentes")] += 1
            self.counts[("conflitos", "party_conflicts")] += len(result.conflicts)


def load_cadastro(connection, cadastro, selection, reference_date):
    """Grava a selecao na transacao aberta; devolve LoadResult.

    Levanta LoadError se a verificacao antes do COMMIT falhar; quem chama
    desfaz a transacao.
    """

    reference = normalize_iso_date(reference_date, "A competencia")
    source = SourceRepository(connection).get_by_code(SOURCE_CODE)

    if source is None:
        raise LoadError("A fonte " + SOURCE_CODE + " nao existe no banco.")

    runs = CollectionRunRepository(connection)
    run = runs.start(
        source.id,
        requested_items=len(selection.funds) + len(selection.classes),
    )
    raws = RawRecordRepository(connection)
    zip_raw, _ = raws.register_file(
        source_id=source.id,
        collection_run_id=run.id,
        file_name=cadastro.zip.file_name,
        size_bytes=cadastro.zip.size_bytes,
        sha256=cadastro.zip.sha256,
        collected_at=run.started_at,
    )
    member_raws = {}

    for member in cadastro.members:
        record, _ = raws.register_file(
            source_id=source.id,
            collection_run_id=run.id,
            file_name=member.file_name,
            size_bytes=member.size_bytes,
            sha256=member.sha256,
            line_count=member.line_count,
            parent_raw_record_id=zip_raw.id,
            collected_at=run.started_at,
        )
        member_raws[member.file_name] = record

    counts = Counter()
    writer = _Writer(connection, source.id, run.id, reference, counts)
    funds = FundRepository(connection)
    fund_classes = FundClassRepository(connection)
    fund_raw = member_raws[spec.FUND_TABLE + ".csv"]
    class_raw = member_raws[spec.CLASS_TABLE + ".csv"]
    fund_ids = {}

    for selected in selection.funds:
        fund, created = funds.get_or_create(selected.cnpj)
        counts[("funds", "criados" if created else "existentes")] += 1
        fund_ids[selected.registro_id] = fund.id
        writer.subject(spec.FUND_TABLE, fund.id, selected, fund_raw.id)

    for selected in selection.classes:
        try:
            fund_class, created = fund_classes.get_or_create(
                selected.cnpj,
                fund_ids[selected.fund_registro_id],
            )
        except IdentityConflictError:
            counts[("fund_classes", "bloqueadas")] += 1
            continue

        counts[("fund_classes", "criadas" if created else "existentes")] += 1
        writer.subject(spec.CLASS_TABLE, fund_class.id, selected, class_raw.id)

    raws.update_processing(zip_raw.id, "processed", parser_version=PARSER_VERSION)

    for name, record in member_raws.items():
        status = "ignored" if name == spec.SUBCLASS_TABLE + ".csv" else "processed"
        raws.update_processing(record.id, status, parser_version=PARSER_VERSION)

    blocked = counts[("fund_classes", "bloqueadas")]
    status = "partial" if blocked else "success"
    runs.finish(
        run.id,
        status,
        successful_items=len(selection.funds) + len(selection.classes) - blocked,
        failed_items=blocked,
        error_summary=(
            {"classes_bloqueadas_por_vinculo_de_fundo": blocked} if blocked else None
        ),
    )

    observations, parties = count_cpf_like(connection, run.id)
    counts[("varredura_cpf", "observations")] = observations
    counts[("varredura_cpf", "party_observations")] = parties
    problems = verify(connection, run.id)

    if problems:
        raise LoadError("Verificacao antes do COMMIT falhou: " + " ".join(problems))

    return LoadResult(run_id=run.id, status=status, counts=counts)
