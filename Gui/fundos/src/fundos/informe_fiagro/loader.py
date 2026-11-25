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

Chave repetida no arquivo com a maior Versao numa linha so: essa linha
entra e as outras (versao anterior no mesmo arquivo) so sao contadas; as
subclasses dessa classe nao entram, porque o arquivo de subclasse nao tem
Versao, e sao contadas com motivo proprio. A outra chave repetida (Versao
igual, empate na maior ou Versao vazia), e as subclasses dela, e o par
(classe, rotulo) repetido nao sao carregados: so contados.

Reapresentacao (FU5.3, a regra da FU4.2 do FIDC): o mesmo ZIP (mesmo
SHA-256) nao e carregado de novo. Outro ZIP de uma competencia ja
carregada so entra com o Last-Modified dele na CVM, estritamente posterior
ao do ZIP mais novo ja carregado (ou, se esse nao tiver a data, ao inicio
da carga dele). A carga compara o ZIP com o ultimo valor carregado
(compare.py): a celula igual nao e gravada de novo, a alterada e a nova
sao gravadas, e a que volta a um valor anterior vira linha reapresentada
(restatement), para ser o valor atual. Nada e apagado: o que sumiu e a
classe que sumiu so sao contados. A classe cuja Versao no ZIP novo e menor
que a Versao atual dela na competencia nao entra (nem os papeis nem as
subclasses dela) e e contada: o valor carregado continua o atual.
Data_Entrega nao ordena nada.

A competencia carregada pela versao anterior do leitor (v1) serve de base
para a reapresentacao: os field_name, as series e os papeis sao os mesmos.
Competencia carregada por versao desconhecida do leitor e recusada.
"""

import time
from collections import Counter
from decimal import Decimal

from fundos.cadastro.loader import REQUIRED_MIGRATIONS
from fundos.cadastro.loader import SOURCE_CODE
from fundos.cadastro.loader import LoadError
from fundos.cadastro.loader import LoadResult
from fundos.cadastro.loader import count_cpf_like
from fundos.cadastro.loader import missing_migrations
from fundos.cadastro.loader import verify
from fundos.informe_fiagro import columns as spec
from fundos.informe_fiagro.compare import Comparison
from fundos.informe_fidc.compare import EQUAL
from fundos.informe_fidc.compare import RETURNS
from fundos.informe_fidc.loader import LoadedZip
from fundos.informe_fidc.loader import cadastro_loaded
from fundos.informe_fidc.loader import normalize_last_modified
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


PARSER_VERSION = "fundos.informe_fiagro.v2"
# A v1 (FU5.1) grava os mesmos campos, series e papeis: serve de base.
COMPATIBLE_VERSIONS = ("fundos.informe_fiagro.v1", PARSER_VERSION)

LOADED = "classe"

# Motivos para uma linha (ou uma classe) nao ser carregada.
INVALID_CNPJ = "CNPJ_Classe vazio, CPF ou invalido"
REPEATED_KEY = "chave repetida no arquivo"
ONLY_FUND = "CNPJ so como fundo"
NOT_FOUND = "CNPJ fora do cadastro carregado"
LOWER_VERSION = "Versao menor que a carregada"
REASONS = (INVALID_CNPJ, REPEATED_KEY, ONLY_FUND, NOT_FOUND, LOWER_VERSION)

# Motivo so da linha de classe: a classe entra pela linha de maior Versao.
SUPERSEDED = "versao anterior no mesmo arquivo"
CLASS_LINE_REASONS = (INVALID_CNPJ, REPEATED_KEY, SUPERSEDED, ONLY_FUND, NOT_FOUND, LOWER_VERSION)

# Motivos so da linha de subclasse.
NO_CLASS_ROW = "sem linha no arquivo de classe"
VERSIONED_SUBCLASS = "subclasse de classe com mais de uma Versao no arquivo"
EMPTY_LABEL = "rotulo vazio"
REPEATED_SERIES = "par (classe, rotulo) repetido"
SUBCLASS_REASONS = (
    INVALID_CNPJ, NO_CLASS_ROW, REPEATED_KEY, ONLY_FUND, NOT_FOUND, LOWER_VERSION, VERSIONED_SUBCLASS,
    EMPTY_LABEL, REPEATED_SERIES,
)

# Linhas que a carga retem e os arquivos em que a reapresentacao nao
# compara o banco da classe (compare.py): nunca contadas como sumidas.
WITHHELD_FILES = {
    VERSIONED_SUBCLASS: (spec.SUBCLASS_TABLE,),
    LOWER_VERSION: spec.TABLES,
}

ALREADY_LOADED = "mesmo ZIP"
SAME_COMPETENCE = "mesma competencia"
UNKNOWN_VERSION = "versao desconhecida do leitor"


def loaded_zips(connection, informe):
    """ZIPs processados com o mesmo AAAAMM, de qualquer versao do leitor.

    Procura o manifesto processado do arquivo de classe do mesmo AAAAMM
    (inf_mensal_fiagro_AAAAMM.csv): o do FIDC tem outro nome.
    """

    rows = connection.execute(
        """
        SELECT z.id, z.sha256, z.parser_version, z.last_modified, z.collected_at
        FROM raw_records r
        JOIN raw_records z ON z.id = r.parent_raw_record_id
        JOIN sources s ON s.id = r.source_id
        WHERE s.code = ?
          AND r.file_name = ?
          AND z.processing_status = 'processed'
        ORDER BY z.id
        """,
        (SOURCE_CODE, spec.member_name(spec.CLASS_TABLE, informe.zip.period)),
    ).fetchall()

    return [
        LoadedZip(
            id=int(row[0]),
            sha256=str(row[1]),
            parser_version=str(row[2]),
            last_modified=None if row[3] is None else str(row[3]),
            collected_at=str(row[4]),
        )
        for row in rows
    ]


def find_loaded_informe(connection, informe):
    """UNKNOWN_VERSION, ALREADY_LOADED, SAME_COMPETENCE (outro ZIP do mesmo AAAAMM) ou None.

    UNKNOWN_VERSION: a competencia foi carregada por uma versao do leitor
    que nao e a v1 nem esta; vem antes dos outros casos.
    """

    loaded = loaded_zips(connection, informe)

    if any(z.parser_version not in COMPATIBLE_VERSIONS for z in loaded):
        return UNKNOWN_VERSION

    hashes = {z.sha256 for z in loaded}

    if informe.zip.sha256 in hashes:
        return ALREADY_LOADED

    return SAME_COMPETENCE if hashes else None


def reapresentation_problem(connection, informe, last_modified):
    """Por que outro ZIP da competencia nao pode ser carregado, ou None.

    A mesma regra da FU4.2 (informe_fidc/loader.py): last_modified ja
    normalizado, estritamente posterior ao maior Last-Modified dos ZIPs
    carregados; ZIP carregado sem a data (como os da v1 sem --last-modified)
    entra pelo inicio da carga dele, porque foi baixado antes.
    """

    month = informe.competence[:7]

    if last_modified is None:
        return (
            "Ja existe informe de FIAGRO carregado para a competencia "
            + month
            + " (outro ZIP). Para carregar este ZIP como reapresentacao, informe"
            " --last-modified: o Last-Modified do ZIP na CVM, com fuso (por exemplo"
            " 2026-10-24T11:46:15Z ou Sat, 24 Oct 2026 11:46:15 GMT)."
        )

    loaded = loaded_zips(connection, informe)
    dated = [z.last_modified for z in loaded if z.last_modified is not None]
    undated = [z.collected_at for z in loaded if z.last_modified is None]

    if dated and last_modified <= max(dated):
        return (
            "O Last-Modified deste ZIP ("
            + last_modified
            + ") nao e posterior ao do ZIP mais novo ja carregado da competencia "
            + month
            + " ("
            + max(dated)
            + "): carregar um ZIP mais antigo depois de um mais novo faria o valor"
            " antigo virar o atual."
        )

    if undated and last_modified <= max(undated):
        return (
            "O ZIP ja carregado da competencia "
            + month
            + " nao tem Last-Modified, e o deste ZIP ("
            + last_modified
            + ") nao e posterior ao inicio da carga dele ("
            + max(undated)
            + "): nao da para provar que este ZIP e mais novo."
        )

    return None


def unknown_version_message(connection, informe):
    """Mensagem da recusa de competencia carregada por versao desconhecida do leitor."""

    versions = sorted(
        {z.parser_version for z in loaded_zips(connection, informe) if z.parser_version not in COMPATIBLE_VERSIONS}
    )

    return (
        "O informe de FIAGRO da competencia "
        + informe.competence[:7]
        + " foi carregado por uma versao do leitor que esta nao conhece ("
        + ", ".join(versions)
        + "). Esta versao nao atualiza esse carregamento."
    )


class ClassResolver:
    """Casa o CNPJ_Classe com a classe do cadastro, aplicando as regras do arquivo.

    lower_version: os CNPJ_Classe com Versao menor que a carregada na
    competencia (so na reapresentacao; lower_version_classes).
    """

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
        self.lower_version = frozenset()

    def class_id(self, cnpj):
        """Id da classe do cadastro, ou None."""

        return self.classes.get(cnpj)

    def resolve(self, row):
        """(id da classe, LOADED) ou (None, motivo)."""

        cnpj = row.cnpj

        if cnpj is None:
            return None, INVALID_CNPJ

        if row.table == spec.SUBCLASS_TABLE and cnpj not in self.informe.class_keys:
            return None, NO_CLASS_ROW

        versioned = cnpj in self.informe.versioned_keys

        if cnpj in self.informe.repeated_keys and not versioned:
            return None, REPEATED_KEY

        if versioned and row.table == spec.CLASS_TABLE and row.line != self.informe.chosen_lines[cnpj]:
            return None, SUPERSEDED

        if cnpj not in self.classes:
            return None, ONLY_FUND if cnpj in self.funds else NOT_FOUND

        if cnpj in self.lower_version:
            return None, LOWER_VERSION

        if row.table == spec.SUBCLASS_TABLE:
            if versioned:
                return None, VERSIONED_SUBCLASS

            if row.series_key is None:
                return None, EMPTY_LABEL

            if (cnpj, row.series_key) in self.informe.repeated_series:
                return None, REPEATED_SERIES

        return self.classes[cnpj], LOADED


def lower_version_classes(informe, resolver, versions):
    """CNPJ_Classe cuja Versao no ZIP e menor que a atual da classe (versions)."""

    found = set()

    for row in informe.rows(spec.CLASS_TABLE):
        class_id, _ = resolver.resolve(row)
        new = row.values.get(spec.VERSION_COLUMN)
        old = None if class_id is None else versions.get(class_id)

        if new is not None and old is not None and Decimal(new) < Decimal(old):
            found.add(row.cnpj)

    return frozenset(found)


def iter_matched(informe, table, resolver, counts, classes, withheld=None):
    """Linhas do arquivo que entram: (linha, id da classe).

    Conta por arquivo as linhas que entram e as que ficam fora, por motivo;
    classes guarda o resultado de cada CNPJ do arquivo de classe (o da
    linha escolhida, quando a classe tem mais de uma Versao no arquivo).
    withheld(id da classe, motivo), se informado, recebe as linhas que a
    carga retem (WITHHELD_FILES).
    """

    for row in informe.rows(table):
        class_id, outcome = resolver.resolve(row)
        counts[("casamento", table, outcome)] += 1

        if table == spec.CLASS_TABLE and outcome != SUPERSEDED:
            classes.setdefault(row.cnpj, outcome)

        if withheld is not None and outcome in WITHHELD_FILES:
            withheld(resolver.class_id(row.cnpj), outcome)

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


def start_comparison(connection, informe, resolver):
    """Estado da competencia no banco, antes de qualquer gravacao.

    Le a Versao atual de cada classe e marca no resolver as classes com
    Versao menor no ZIP novo, que nao entram.
    """

    comparison = Comparison(connection, informe, [z.id for z in loaded_zips(connection, informe)])
    resolver.lower_version = lower_version_classes(informe, resolver, comparison.versions())
    return comparison


def _withheld(comparison):
    def withheld(class_id, reason):
        comparison.withhold(class_id, reason, WITHHELD_FILES[reason])

    return withheld


def reapresentation_counts(connection, informe, resolver):
    """Contagens do dry-run de outro ZIP da competencia ja carregada, sem escrever.

    Casamento com o cadastro e comparacao com o ultimo valor carregado
    (compare.py), arquivo por arquivo.
    """

    counts = Counter()
    classes = {}
    comparison = start_comparison(connection, informe, resolver)
    parties = comparison.parties()

    for table in spec.TABLES:
        state = comparison.table(table)

        for row, class_id in iter_matched(informe, table, resolver, counts, classes, _withheld(comparison)):
            series_id = comparison.series_id(class_id, row.series_key) if table == spec.SUBCLASS_TABLE else None
            state.row(row, class_id, series_id)

            for party in row.parties:
                parties.party(class_id, party)

        state.finish()

    parties.finish()
    count_classes(classes, counts)
    counts.update(comparison.finish())
    return counts


class _Writer:
    """Grava as linhas casadas: observacoes, series e papeis.

    Na reapresentacao (comparison), a celula e o papel iguais ao ultimo
    valor carregado nao passam pelo repositorio: o checksum deles ja existe,
    entao record() devolveria a linha existente sem gravar nada. O que volta
    a um valor anterior e gravado como linha reapresentada.
    """

    def __init__(self, connection, informe, source_id, run_id, counts, comparison=None):
        self.informe = informe
        self.source_id = source_id
        self.run_id = run_id
        self.counts = counts
        self.observations = ObservationRepository(connection)
        self.parties = PartyObservationRepository(connection)
        self.series = QuotaSeriesRepository(connection)
        self.series_ids = {}
        self.comparison = comparison
        self.state = None
        self.party_state = None if comparison is None else comparison.parties()

    def start(self, table):
        """Le o estado do arquivo no banco antes de gravar nele."""

        self.state = None if self.comparison is None else self.comparison.table(table)

    def finish(self):
        if self.state is not None:
            self.state.finish()

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
            series_id = self.series_id(class_id, row)
            target = {"quota_series_id": series_id}
        else:
            series_id = None
            target = {"fund_class_id": class_id}

        statuses = {} if self.state is None else self.state.row(row, class_id, series_id)

        for name, value in row.values.items():
            value_type = spec.VALUE_TYPE[spec.KINDS[table][name]]
            compared = statuses.get(name)

            if compared == EQUAL:
                self.counts[("observacoes", table, value_type, "existentes")] += 1
                continue

            result = self.observations.record(
                **target,
                source_id=self.source_id,
                collection_run_id=self.run_id,
                raw_record_id=raw_record_id,
                field_name=spec.field_name(table, name),
                value_type=value_type,
                value=value,
                reference_date=self.informe.competence,
                restatement=compared == RETURNS,
            )
            status = "criadas" if result.created else "existentes"
            self.counts[("observacoes", table, value_type, status)] += 1
            self.counts[("conflitos", "data_conflicts")] += len(result.conflicts)

        for party in row.parties:
            compared = None if self.party_state is None else self.party_state.party(class_id, party)

            if compared == EQUAL:
                self.counts[("papeis", party.role, "existentes")] += 1
                continue

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
                restatement=compared == RETURNS,
            )
            self.counts[("papeis", party.role, "criados" if result.created else "existentes")] += 1
            self.counts[("conflitos", "party_conflicts")] += len(result.conflicts)


def load_informe(connection, informe, *, progress=None, last_modified=None):
    """Grava o informe na transacao aberta; devolve LoadResult.

    last_modified e o Last-Modified do ZIP na CVM (normalize_last_modified),
    gravado no manifesto do ZIP; e obrigatorio quando a competencia ja tem
    outro ZIP carregado. progress(tabela, observacoes, segundos), se
    informado, e chamado ao fim de cada arquivo. Levanta LoadError se o
    Last-Modified for invalido, se faltar migration, se o cadastro nao
    estiver carregado, se o mesmo ZIP ja estiver no banco, se a competencia
    foi carregada por versao desconhecida do leitor, se o ZIP nao for
    comprovadamente mais novo que os ja carregados da competencia ou se a
    verificacao antes do COMMIT falhar; quem chama desfaz a transacao.
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

    if loaded == UNKNOWN_VERSION:
        raise LoadError(unknown_version_message(connection, informe))

    if loaded == ALREADY_LOADED:
        raise LoadError(
            "Ja existe informe de FIAGRO carregado para a competencia "
            + informe.competence
            + " ("
            + loaded
            + "); nada a carregar."
        )

    resolver = ClassResolver(connection, informe)
    comparison = None

    if loaded == SAME_COMPETENCE:
        problem = reapresentation_problem(connection, informe, last_modified)

        if problem is not None:
            raise LoadError(problem)

        # Antes de qualquer gravacao: o estado da competencia no banco.
        comparison = start_comparison(connection, informe, resolver)

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
    writer = _Writer(connection, informe, source.id, run.id, counts, comparison)
    withheld = None if comparison is None else _withheld(comparison)

    for table in spec.TABLES:
        started = time.perf_counter()
        before = sum(n for key, n in counts.items() if key[0] == "observacoes")
        writer.start(table)

        for row, class_id in iter_matched(informe, table, resolver, counts, classes, withheld):
            writer.write(table, row, class_id, member_raws[table].id)

        writer.finish()

        if progress is not None:
            after = sum(n for key, n in counts.items() if key[0] == "observacoes")
            progress(table, after - before, time.perf_counter() - started)

    count_classes(classes, counts)

    if comparison is not None:
        writer.party_state.finish()
        counts.update(comparison.finish())

    raws.update_processing(zip_raw.id, "processed", parser_version=PARSER_VERSION)

    for record in member_raws.values():
        raws.update_processing(record.id, "processed", parser_version=PARSER_VERSION)

    summary = {}

    for label, total in (
        ("chaves_repetidas_nao_carregadas", counts[("classes", REPEATED_KEY)]),
        ("classes_fora_do_cadastro", counts[("classes", ONLY_FUND)] + counts[("classes", NOT_FOUND)]),
        ("linhas_com_cnpj_classe_invalido", counts[("casamento", spec.CLASS_TABLE, INVALID_CNPJ)]),
        ("linhas_de_versao_anterior_nao_carregadas", counts[("casamento", spec.CLASS_TABLE, SUPERSEDED)]),
        (
            "subclasses_de_classe_com_mais_de_uma_versao",
            counts[("casamento", spec.SUBCLASS_TABLE, VERSIONED_SUBCLASS)],
        ),
        ("classes_com_versao_menor_que_a_carregada", counts[("classes", LOWER_VERSION)]),
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
