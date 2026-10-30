"""Gravacao do informe mensal de FIDC no banco de Fundos.

Roda dentro da transacao de quem chama (Database.transaction()). A
identidade vem do cadastro ja carregado: o assunto e a classe (TP_FUNDO_CLASSE
Classe e CNPJ em fund_classes) ou o fundo (Fundo e CNPJ em funds); qualquer
outro caso nao carrega e e contado, por tabela e por assunto. Nenhum fundo
nem classe e criado aqui.

Grava uma coleta da fonte CVM_DADOS_ABERTOS, o manifesto do ZIP e dos 18 CSV
(tab_VIII e tab_X_4 como 'ignored'), as observacoes (competencia =
DT_COMPTC), as series (quota_series, pela chave do rotulo normalizado), a
administradora e os cedentes de CNPJ valido (party_observations, com o
percentual em party_observation_shares). Exige as migrations 001 a 003. O
ID_SUBCLASSE so vira chave da serie quando aparece num unico assunto e
rotulo do arquivo; se o banco o recusar (IdentityConflictError), a serie
fica so com o rotulo, as linhas sao carregadas e a coleta fica 'partial'.

Uma competencia = um ZIP ate a FU4.2 (reapresentacao): o mesmo ZIP nao e
carregado de novo, e outro ZIP da mesma competencia e recusado. Competencia
carregada por outra versao do leitor tambem e recusada (mesmo ZIP ou
outro): esta versao nao atualiza esse carregamento.
"""

import time
from collections import Counter

from fundos.cadastro.loader import REQUIRED_MIGRATIONS as CADASTRO_MIGRATIONS
from fundos.cadastro.loader import SOURCE_CODE
from fundos.cadastro.loader import LoadError
from fundos.cadastro.loader import LoadResult
from fundos.cadastro.loader import count_cpf_like
from fundos.cadastro.loader import missing_migrations
from fundos.cadastro.loader import verify
from fundos.informe_fidc import columns as spec
from fundos.repositories import IdentityConflictError
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


PARSER_VERSION = "fundos.informe_fidc.v2"

# O cedente precisa da 003 (percentual em party_observation_shares).
REQUIRED_MIGRATIONS = {**CADASTRO_MIGRATIONS, 3: "party_observation_shares"}

# Cache da conexao da carga (KiB): ~1,5 milhao de observacoes por mes.
CACHE_KIB = 200_000

CLASS_SUBJECT = "classe"
FUND_SUBJECT = "fundo"

# Motivos para uma linha (ou um assunto) nao casar com o cadastro carregado.
CLASS_ONLY_FUND = "Classe: CNPJ so como fundo"
CLASS_NOT_FOUND = "Classe: CNPJ fora do cadastro carregado"
FUND_ONLY_CLASS = "Fundo: CNPJ so como classe"
FUND_NOT_FOUND = "Fundo: CNPJ fora do cadastro carregado"
UNKNOWN_TYPE = "TP_FUNDO_CLASSE desconhecido"
INVALID_CNPJ = "CNPJ_FUNDO_CLASSE invalido"
REASONS = (
    CLASS_ONLY_FUND,
    CLASS_NOT_FOUND,
    FUND_ONLY_CLASS,
    FUND_NOT_FOUND,
    UNKNOWN_TYPE,
    INVALID_CNPJ,
)

ALREADY_LOADED = "mesmo ZIP"
SAME_COMPETENCE = "mesma competencia"
OLDER_VERSION = "versao anterior do leitor"


def cadastro_loaded(connection):
    """Indica se o cadastro ja foi carregado (manifesto processado e fundos)."""

    manifest = connection.execute(
        """
        SELECT 1
        FROM raw_records r
        JOIN sources s ON s.id = r.source_id
        WHERE s.code = ?
          AND r.file_name = 'registro_fundo.csv'
          AND r.processing_status = 'processed'
        LIMIT 1
        """,
        (SOURCE_CODE,),
    ).fetchone()
    funds = connection.execute("SELECT 1 FROM funds LIMIT 1").fetchone()

    return manifest is not None and funds is not None


def _loaded_zips(connection, informe):
    """(SHA-256, versao do leitor) dos ZIPs processados com o mesmo AAAAMM.

    Cada ZIP tem uma so competencia, do mes do AAAAMM dos membros; por isso
    basta procurar o manifesto da tab_I do mesmo AAAAMM ja processado, de
    qualquer versao do leitor.
    """

    rows = connection.execute(
        """
        SELECT z.sha256, z.parser_version
        FROM raw_records r
        JOIN raw_records z ON z.id = r.parent_raw_record_id
        JOIN sources s ON s.id = r.source_id
        WHERE s.code = ?
          AND r.file_name = ?
          AND z.processing_status = 'processed'
        """,
        (SOURCE_CODE, spec.member_name("tab_I", informe.zip.period)),
    ).fetchall()

    return [(str(row[0]), str(row[1])) for row in rows]


def find_loaded_informe(connection, informe):
    """OLDER_VERSION, ALREADY_LOADED, SAME_COMPETENCE (outro ZIP do mesmo mes) ou None.

    OLDER_VERSION: a competencia foi carregada por outra versao do leitor,
    com este ZIP ou com outro; vem antes dos outros casos.
    """

    loaded = _loaded_zips(connection, informe)

    if any(version != PARSER_VERSION for _, version in loaded):
        return OLDER_VERSION

    hashes = {sha256 for sha256, _ in loaded}

    if informe.zip.sha256 in hashes:
        return ALREADY_LOADED

    return SAME_COMPETENCE if hashes else None


def older_version_message(connection, informe):
    """Mensagem da recusa de competencia carregada por outra versao do leitor."""

    versions = sorted(
        {version for _, version in _loaded_zips(connection, informe) if version != PARSER_VERSION}
    )

    return (
        "O informe da competencia "
        + informe.competence[:7]
        + " foi carregado por versao anterior do leitor ("
        + ", ".join(versions)
        + "). Esta versao nao atualiza esse carregamento: use um banco novo e"
        " carregue de novo."
    )


class SubjectResolver:
    """Casa (TP_FUNDO_CLASSE, CNPJ) com a classe ou o fundo do cadastro."""

    def __init__(self, connection):
        self.classes = {
            str(row[1]): int(row[0])
            for row in connection.execute("SELECT id, cnpj FROM fund_classes")
        }
        self.funds = {
            str(row[1]): int(row[0])
            for row in connection.execute("SELECT id, cnpj FROM funds")
        }

    def resolve(self, subject_type, cnpj):
        """(coluna do assunto, id) ou (None, motivo)."""

        if cnpj is None:
            return None, INVALID_CNPJ

        if subject_type == spec.CLASS_SUBJECT:
            if cnpj in self.classes:
                return "fund_class_id", self.classes[cnpj]

            return None, CLASS_ONLY_FUND if cnpj in self.funds else CLASS_NOT_FOUND

        if subject_type == spec.FUND_SUBJECT:
            if cnpj in self.funds:
                return "fund_id", self.funds[cnpj]

            return None, FUND_ONLY_CLASS if cnpj in self.classes else FUND_NOT_FOUND

        return None, UNKNOWN_TYPE


def _outcome(column):
    return CLASS_SUBJECT if column == "fund_class_id" else FUND_SUBJECT


def iter_matched(informe, table, resolver, counts, subjects):
    """Linhas da tabela que casam com o cadastro: (linha, coluna, id).

    Conta por tabela as linhas que casam e as que ficam fora, por motivo;
    subjects guarda o resultado de cada assunto (TP, CNPJ).
    """

    for row in informe.rows(table):
        column, value = resolver.resolve(row.subject_type, row.cnpj)
        outcome = value if column is None else _outcome(column)
        counts[("casamento", table, outcome)] += 1
        subjects.setdefault((row.subject_type, row.cnpj), outcome)

        if column is not None:
            yield row, column, value


def count_subjects(subjects, counts):
    """Assuntos distintos por resultado (classe, fundo ou motivo)."""

    for outcome in subjects.values():
        counts[("assuntos", outcome)] += 1


def match_counts(informe, resolver):
    """Contagens do dry-run com banco: casamento e candidatos, sem escrever."""

    counts = Counter()
    subjects = {}
    series = set()

    for table in spec.TABLES:
        for row, column, subject_id in iter_matched(informe, table, resolver, counts, subjects):
            if table in spec.NOT_LOADED:
                continue

            if table in spec.SERIES_TABLES and row.series_key is not None:
                series.add((column, subject_id, row.series_key))

            for name, value in row.values.items():
                value_type = spec.VALUE_TYPE[spec.KINDS[table][name]]
                counts[("candidatas", table, value_type)] += 1

                if value_type == "numeric" and value == "0":
                    counts[("candidatas_zero",)] += 1

            for party in row.parties:
                counts[("papeis_candidatos", party.role)] += 1

                if party.share is not None:
                    counts[("percentuais_candidatos",)] += 1

    count_subjects(subjects, counts)
    counts[("series_candidatas",)] = len(series)
    return counts


class _Writer:
    """Grava as linhas casadas de uma tabela: observacoes, series e papeis."""

    def __init__(self, connection, informe, source_id, run_id, counts):
        self.informe = informe
        self.source_id = source_id
        self.run_id = run_id
        self.counts = counts
        self.observations = ObservationRepository(connection)
        self.parties = PartyObservationRepository(connection)
        self.series = QuotaSeriesRepository(connection)
        self.series_ids = {}
        self.refused_ids = set()

    def series_id(self, column, subject_id, row):
        """Serie pelo rotulo; o ID_SUBCLASSE so como chave quando e seguro."""

        key = (column, subject_id, row.series_key)

        if key in self.series_ids:
            return self.series_ids[key]

        parent = {column: subject_id}
        subclass_id = row.subclass_id or None

        if subclass_id in self.informe.shared_subclass_ids:
            subclass_id = None

        try:
            series, created = self.series.get_or_create(
                **parent,
                label=row.series_label,
                cvm_subclass_id=subclass_id,
            )
        except IdentityConflictError:
            if subclass_id is None:
                raise

            # O banco recusou o ID como chave: a serie fica so com o
            # rotulo, que e a identidade das outras tabelas de serie.
            self.refused_ids.add(subclass_id)
            series, created = self.series.get_or_create(**parent, label=row.series_label)
            subclass_id = None

        self.counts[("series", "criadas" if created else "existentes")] += 1

        if subclass_id is not None:
            self.counts[("id_subclasse", "chave")] += 1

        self.series_ids[key] = series.id
        return series.id

    def write(self, table, row, column, subject_id, raw_record_id):
        if table in spec.SERIES_TABLES:
            if row.series_key is None:
                self.counts[("rotulo_vazio_carga", table)] += 1
                return

            target = {"quota_series_id": self.series_id(column, subject_id, row)}
        else:
            target = {column: subject_id}

        for name, value in row.values.items():
            value_type = spec.VALUE_TYPE[spec.KINDS[table][name]]
            result = self.observations.record(
                **target,
                source_id=self.source_id,
                collection_run_id=self.run_id,
                raw_record_id=raw_record_id,
                field_name=spec.field_name(table, name),
                value_type=value_type,
                value=value,
                reference_date=self.informe.competence,
            )
            status = "criadas" if result.created else "existentes"
            self.counts[("observacoes", table, value_type, status)] += 1
            self.counts[("conflitos", "data_conflicts")] += len(result.conflicts)

        for party in row.parties:
            result = self.parties.record(
                **{column: subject_id},
                role=party.role,
                field_name=party.field_name,
                party_cnpj=party.cnpj,
                name_field_name=party.name_field_name,
                party_name=party.name,
                share_field_name=party.share_field_name,
                share_value=party.share,
                source_id=self.source_id,
                collection_run_id=self.run_id,
                raw_record_id=raw_record_id,
                reference_date=self.informe.competence,
            )
            status = "criados" if result.created else "existentes"
            self.counts[("papeis", party.role, status)] += 1

            if party.share is not None:
                self.counts[("percentuais", status)] += 1

            self.counts[("conflitos", "party_conflicts")] += len(result.conflicts)


def load_informe(connection, informe, *, progress=None):
    """Grava o informe na transacao aberta; devolve LoadResult.

    progress(tabela, observacoes, segundos), se informado, e chamado ao fim
    de cada tabela. Levanta LoadError se faltar migration, se o cadastro
    nao estiver carregado, se o ZIP ou a competencia ja estiverem no banco
    (tambem por outra versao do leitor), ou se a verificacao antes do
    COMMIT falhar; quem chama desfaz a transacao.
    """

    missing = missing_migrations(connection, REQUIRED_MIGRATIONS)

    if missing:
        raise LoadError(
            "Faltam as migrations "
            + ", ".join(missing)
            + "; aplique antes com scripts/apply_migration.py."
        )

    if not cadastro_loaded(connection):
        raise LoadError(
            "O cadastro nao foi carregado: carregue antes o "
            "registro_fundo_classe.zip com scripts/load_cadastro.py."
        )

    loaded = find_loaded_informe(connection, informe)

    if loaded == OLDER_VERSION:
        raise LoadError(older_version_message(connection, informe))

    if loaded is not None:
        raise LoadError(
            "Ja existe informe de FIDC carregado para a competencia "
            + informe.competence
            + " ("
            + loaded
            + "); reapresentacao e a FU4.2."
        )

    connection.execute("PRAGMA cache_size = -" + str(CACHE_KIB))
    source = SourceRepository(connection).get_by_code(SOURCE_CODE)

    if source is None:
        raise LoadError("A fonte " + SOURCE_CODE + " nao existe no banco.")

    subjects_in_file = sum(n for key, n in informe.counts.items() if key[0] == "assuntos")
    runs = CollectionRunRepository(connection)
    run = runs.start(source.id, requested_items=subjects_in_file)
    raws = RawRecordRepository(connection)
    zip_raw, _ = raws.register_file(
        source_id=source.id,
        collection_run_id=run.id,
        file_name=informe.zip.file_name,
        size_bytes=informe.zip.size_bytes,
        sha256=informe.zip.sha256,
        collected_at=run.started_at,
    )
    member_raws = {}

    for table in spec.TABLES:
        member = informe.member(table)
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
        member_raws[table] = record

    counts = Counter()
    subjects = {}
    resolver = SubjectResolver(connection)
    writer = _Writer(connection, informe, source.id, run.id, counts)

    for table in spec.TABLES:
        started = time.perf_counter()
        before = sum(n for key, n in counts.items() if key[0] == "observacoes")

        for row, column, subject_id in iter_matched(informe, table, resolver, counts, subjects):
            if table not in spec.NOT_LOADED:
                writer.write(table, row, column, subject_id, member_raws[table].id)

        if progress is not None:
            after = sum(n for key, n in counts.items() if key[0] == "observacoes")
            progress(table, after - before, time.perf_counter() - started)

    count_subjects(subjects, counts)
    raws.update_processing(zip_raw.id, "processed", parser_version=PARSER_VERSION)

    for table, record in member_raws.items():
        status = "ignored" if table in spec.NOT_LOADED else "processed"
        raws.update_processing(record.id, status, parser_version=PARSER_VERSION)

    refused = len(writer.refused_ids)
    counts[("id_subclasse", "recusado")] = refused
    out = sum(counts[("assuntos", reason)] for reason in REASONS)
    loaded_subjects = counts[("assuntos", CLASS_SUBJECT)] + counts[("assuntos", FUND_SUBJECT)]
    summary = {}

    if out:
        summary["assuntos_fora_do_cadastro"] = out

    if refused:
        summary["id_subclasse_recusado"] = refused

    status = "partial" if refused else "success"
    runs.finish(
        run.id,
        status,
        successful_items=loaded_subjects,
        failed_items=refused,
        error_summary=summary or None,
    )

    observations, parties = count_cpf_like(connection, run.id)
    counts[("varredura_cpf", "observations")] = observations
    counts[("varredura_cpf", "party_observations")] = parties
    problems = verify(connection, run.id)

    if problems:
        raise LoadError("Verificacao antes do COMMIT falhou: " + " ".join(problems))

    return LoadResult(run_id=run.id, status=status, counts=counts)
