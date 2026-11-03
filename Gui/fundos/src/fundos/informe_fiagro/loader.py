"""Gravacao do informe mensal de FIAGRO no banco de Fundos.

Roda dentro da transacao de quem chama (Database.transaction()). A
identidade vem do cadastro ja carregado: o CNPJ_Classe tem de estar em
fund_classes; nada e criado aqui, e nunca se casa por nome. O que nao casa
e contado por arquivo e por classe, por motivo.

Grava uma coleta da fonte CVM_DADOS_ABERTOS, o manifesto do ZIP (com o
Last-Modified, quando informado) e dos 2 CSV, as observacoes da classe
(inf_mensal_fiagro.<Coluna>), as series das subclasses (quota_series, pela
chave do rotulo normalizado, sem ID da CVM) com as observacoes delas
(inf_mensal_fiagro_subclasse.<Coluna>) e o administrador e o gestor de
CNPJ valido (party_observations da classe). A competencia gravada e o
ultimo dia do mes (reader.py). Exige as migrations 001 e 002, como o
cadastro: nao ha cedente.

Os field_name do FIAGRO nao coincidem com os do FIDC (tab_*.COLUNA) nem
com os do cadastro (registro_*.Coluna): a classe que esta em mais de um
informe nao abre conflito falso.

Linha de chave repetida no arquivo, e as subclasses dela, e par
(classe, rotulo) repetido nao sao carregados: so contados.

Uma competencia = um ZIP: o mesmo ZIP (mesmo SHA-256) nao e carregado de
novo, e outro ZIP da mesma competencia e recusado. A reapresentacao do
informe de FIAGRO e tarefa propria.
"""

import time
from collections import Counter

from fundos.cadastro.loader import REQUIRED_MIGRATIONS
from fundos.cadastro.loader import SOURCE_CODE
from fundos.cadastro.loader import LoadError
from fundos.cadastro.loader import LoadResult
from fundos.cadastro.loader import count_cpf_like
from fundos.cadastro.loader import missing_migrations
from fundos.cadastro.loader import verify
from fundos.informe_fiagro import columns as spec
from fundos.informe_fidc.loader import cadastro_loaded
from fundos.informe_fidc.loader import normalize_last_modified
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


PARSER_VERSION = "fundos.informe_fiagro.v1"

LOADED = "classe"

# Motivos para uma linha (ou uma classe) nao ser carregada.
INVALID_CNPJ = "CNPJ_Classe vazio, CPF ou invalido"
REPEATED_KEY = "chave repetida no arquivo"
ONLY_FUND = "CNPJ so como fundo"
NOT_FOUND = "CNPJ fora do cadastro carregado"
REASONS = (INVALID_CNPJ, REPEATED_KEY, ONLY_FUND, NOT_FOUND)

# Motivos so da linha de subclasse.
NO_CLASS_ROW = "sem linha no arquivo de classe"
EMPTY_LABEL = "rotulo vazio"
REPEATED_SERIES = "par (classe, rotulo) repetido"
SUBCLASS_REASONS = (INVALID_CNPJ, NO_CLASS_ROW, REPEATED_KEY, ONLY_FUND, NOT_FOUND, EMPTY_LABEL, REPEATED_SERIES)

ALREADY_LOADED = "mesmo ZIP"
SAME_COMPETENCE = "mesma competencia"


def find_loaded_informe(connection, informe):
    """ALREADY_LOADED, SAME_COMPETENCE (outro ZIP do mesmo AAAAMM) ou None.

    Procura o manifesto processado do arquivo de classe do mesmo AAAAMM
    (inf_mensal_fiagro_AAAAMM.csv): o do FIDC tem outro nome.
    """

    rows = connection.execute(
        """
        SELECT z.sha256
        FROM raw_records r
        JOIN raw_records z ON z.id = r.parent_raw_record_id
        JOIN sources s ON s.id = r.source_id
        WHERE s.code = ?
          AND r.file_name = ?
          AND z.processing_status = 'processed'
        """,
        (SOURCE_CODE, spec.member_name(spec.CLASS_TABLE, informe.zip.period)),
    ).fetchall()
    hashes = {str(row[0]) for row in rows}

    if informe.zip.sha256 in hashes:
        return ALREADY_LOADED

    return SAME_COMPETENCE if hashes else None


def same_competence_message(informe):
    return (
        "Ja existe informe de FIAGRO carregado para a competencia "
        + informe.competence[:7]
        + " (outro ZIP). A reapresentacao do informe de FIAGRO ainda nao existe"
        " (tarefa propria)."
    )


class ClassResolver:
    """Casa o CNPJ_Classe com a classe do cadastro, aplicando as regras do arquivo."""

    def __init__(self, connection, informe):
        self.informe = informe
        self.classes = {
            str(row[1]): int(row[0])
            for row in connection.execute("SELECT id, cnpj FROM fund_classes")
        }
        self.funds = {
            str(row[0])
            for row in connection.execute("SELECT cnpj FROM funds")
        }

    def resolve(self, row):
        """(id da classe, LOADED) ou (None, motivo)."""

        cnpj = row.cnpj

        if cnpj is None:
            return None, INVALID_CNPJ

        if row.table == spec.SUBCLASS_TABLE and cnpj not in self.informe.class_keys:
            return None, NO_CLASS_ROW

        if cnpj in self.informe.repeated_keys:
            return None, REPEATED_KEY

        if cnpj not in self.classes:
            return None, ONLY_FUND if cnpj in self.funds else NOT_FOUND

        if row.table == spec.SUBCLASS_TABLE:
            if row.series_key is None:
                return None, EMPTY_LABEL

            if (cnpj, row.series_key) in self.informe.repeated_series:
                return None, REPEATED_SERIES

        return self.classes[cnpj], LOADED


def iter_matched(informe, table, resolver, counts, classes):
    """Linhas do arquivo que entram: (linha, id da classe).

    Conta por arquivo as linhas que entram e as que ficam fora, por motivo;
    classes guarda o resultado de cada CNPJ do arquivo de classe.
    """

    for row in informe.rows(table):
        class_id, outcome = resolver.resolve(row)
        counts[("casamento", table, outcome)] += 1

        if table == spec.CLASS_TABLE:
            classes.setdefault(row.cnpj, outcome)

        if class_id is not None:
            yield row, class_id


def count_classes(classes, counts):
    """Classes distintas do arquivo de classe por resultado."""

    for outcome in classes.values():
        counts[("classes", outcome)] += 1


def match_counts(informe, resolver):
    """Contagens do dry-run com banco: casamento e candidatos, sem escrever."""

    counts = Counter()
    classes = {}
    series = set()

    for table in spec.TABLES:
        for row, class_id in iter_matched(informe, table, resolver, counts, classes):
            if table == spec.SUBCLASS_TABLE:
                series.add((class_id, row.series_key))

            for name, value in row.values.items():
                value_type = spec.VALUE_TYPE[spec.KINDS[table][name]]
                counts[("candidatas", table, value_type)] += 1

                if value_type == "numeric" and value == "0":
                    counts[("candidatas_zero",)] += 1

            for party in row.parties:
                counts[("papeis_candidatos", party.role)] += 1

    count_classes(classes, counts)
    counts[("series_candidatas",)] = len(series)
    return counts


class _Writer:
    """Grava as linhas casadas: observacoes, series e papeis."""

    def __init__(self, connection, informe, source_id, run_id, counts):
        self.informe = informe
        self.source_id = source_id
        self.run_id = run_id
        self.counts = counts
        self.observations = ObservationRepository(connection)
        self.parties = PartyObservationRepository(connection)
        self.series = QuotaSeriesRepository(connection)
        self.series_ids = {}

    def series_id(self, class_id, row):
        """Serie da subclasse pelo rotulo normalizado (o arquivo nao traz ID)."""

        key = (class_id, row.series_key)

        if key not in self.series_ids:
            series, created = self.series.get_or_create(fund_class_id=class_id, label=row.series_label)
            self.counts[("series", "criadas" if created else "existentes")] += 1
            self.series_ids[key] = series.id

        return self.series_ids[key]

    def write(self, table, row, class_id, raw_record_id):
        if table == spec.SUBCLASS_TABLE:
            target = {"quota_series_id": self.series_id(class_id, row)}
        else:
            target = {"fund_class_id": class_id}

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
                fund_class_id=class_id,
                role=party.role,
                field_name=party.field_name,
                party_cnpj=party.cnpj,
                name_field_name=party.name_field_name,
                party_name=party.name,
                source_id=self.source_id,
                collection_run_id=self.run_id,
                raw_record_id=raw_record_id,
                reference_date=self.informe.competence,
            )
            self.counts[("papeis", party.role, "criados" if result.created else "existentes")] += 1
            self.counts[("conflitos", "party_conflicts")] += len(result.conflicts)


def load_informe(connection, informe, *, progress=None, last_modified=None):
    """Grava o informe na transacao aberta; devolve LoadResult.

    last_modified e o Last-Modified do ZIP na CVM (opcional;
    normalize_last_modified), gravado no manifesto do ZIP. progress(tabela,
    observacoes, segundos), se informado, e chamado ao fim de cada arquivo.
    Levanta LoadError se o Last-Modified for invalido, se faltar migration,
    se o cadastro nao estiver carregado, se a competencia ja tiver ZIP
    carregado (o mesmo ou outro) ou se a verificacao antes do COMMIT
    falhar; quem chama desfaz a transacao.
    """

    if last_modified is not None:
        try:
            last_modified = normalize_last_modified(last_modified)
        except ValueError as error:
            raise LoadError(str(error)) from error

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

    if loaded == ALREADY_LOADED:
        raise LoadError(
            "Ja existe informe de FIAGRO carregado para a competencia "
            + informe.competence
            + " ("
            + loaded
            + "); nada a carregar."
        )

    if loaded == SAME_COMPETENCE:
        raise LoadError(same_competence_message(informe))

    source = SourceRepository(connection).get_by_code(SOURCE_CODE)

    if source is None:
        raise LoadError("A fonte " + SOURCE_CODE + " nao existe no banco.")

    runs = CollectionRunRepository(connection)
    run = runs.start(source.id, requested_items=informe.counts[("chaves", "distintas")])
    raws = RawRecordRepository(connection)
    zip_raw, _ = raws.register_file(
        source_id=source.id,
        collection_run_id=run.id,
        file_name=informe.zip.file_name,
        size_bytes=informe.zip.size_bytes,
        sha256=informe.zip.sha256,
        last_modified=last_modified,
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
    classes = {}
    resolver = ClassResolver(connection, informe)
    writer = _Writer(connection, informe, source.id, run.id, counts)

    for table in spec.TABLES:
        started = time.perf_counter()
        before = sum(n for key, n in counts.items() if key[0] == "observacoes")

        for row, class_id in iter_matched(informe, table, resolver, counts, classes):
            writer.write(table, row, class_id, member_raws[table].id)

        if progress is not None:
            after = sum(n for key, n in counts.items() if key[0] == "observacoes")
            progress(table, after - before, time.perf_counter() - started)

    count_classes(classes, counts)
    raws.update_processing(zip_raw.id, "processed", parser_version=PARSER_VERSION)

    for record in member_raws.values():
        raws.update_processing(record.id, "processed", parser_version=PARSER_VERSION)

    summary = {}

    for label, total in (
        ("chaves_repetidas_nao_carregadas", counts[("classes", REPEATED_KEY)]),
        ("classes_fora_do_cadastro", counts[("classes", ONLY_FUND)] + counts[("classes", NOT_FOUND)]),
        ("linhas_com_cnpj_classe_invalido", counts[("casamento", spec.CLASS_TABLE, INVALID_CNPJ)]),
    ):
        if total:
            summary[label] = total

    runs.finish(
        run.id,
        "success",
        successful_items=counts[("classes", LOADED)],
        failed_items=0,
        error_summary=summary or None,
    )

    observations, parties = count_cpf_like(connection, run.id)
    counts[("varredura_cpf", "observations")] = observations
    counts[("varredura_cpf", "party_observations")] = parties
    problems = verify(connection, run.id)

    if problems:
        raise LoadError("Verificacao antes do COMMIT falhou: " + " ".join(problems))

    return LoadResult(run_id=run.id, status="success", counts=counts)
