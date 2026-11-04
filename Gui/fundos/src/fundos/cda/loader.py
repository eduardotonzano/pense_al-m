"""Gravacao das posicoes em cotas de fundos do CDA no banco de Fundos.

Roda dentro da transacao de quem chama (Database.transaction()). Exige as
migrations 001 a 004 e o cadastro carregado. A identidade do detentor vem
do cadastro: TP_FUNDO_CLASSE "CLASSES - FIDC" e "CLASSES - FIAGRO" casam
com a classe (fund_classes), "FIDC" e "FIAGRO" com o fundo (funds), pelo
SubjectResolver do informe de FIDC. Nenhum fundo nem classe e criado aqui:
o detentor fora do cadastro carregado, de outro tipo (CLASSES FIIM, ate a
sigla ser entendida) ou classe que so existe como fundo so e contado, por
motivo. O investido e so o CNPJ, sem FK.

Grava uma coleta da fonte CVM_DADOS_ABERTOS, o manifesto do ZIP e dos 12
CSV (os 10 cda_fi_* como 'ignored', sem numero de linhas), as posicoes
identificadas (holdings) e as confidenciais (confidential_holdings), com a
competencia = DT_COMPTC.

Chave natural (detentor, investido, DT_COMPTC) ainda nao decidida (FU6.1,
decisao 2): o arquivo com chave repetida, nas identificadas, ou com mais de
uma linha confidencial de cotas do mesmo detentor e recusado.

Reapresentacao: o mesmo ZIP (mesmo SHA-256) nao e carregado de novo. Outro
ZIP da mesma competencia so entra com o Last-Modified dele na CVM,
estritamente posterior ao do ZIP mais novo ja carregado (ou, se esse nao
tiver a data, ao inicio da carga dele). Valor igual nao grava; valor
diferente grava linha nova e conflito aberto. A posicao que sumiu so e
contada.

Antes do COMMIT: o verify() do cadastro e a varredura das posicoes desta
coleta (todo investee_cnpj com DV valido; nenhum nome nem CNPJ com formato
de CPF). Qualquer problema desfaz tudo.
"""

from collections import Counter

from fundos.cadastro import columns as cadastro_spec
from fundos.cadastro.loader import CPF_GLOBS
from fundos.cadastro.loader import SOURCE_CODE
from fundos.cadastro.loader import LoadError
from fundos.cadastro.loader import LoadResult
from fundos.cadastro.loader import missing_migrations
from fundos.cadastro.loader import verify
from fundos.cda import columns as spec
from fundos.cda.reader import CONFIDENTIAL
from fundos.cda.reader import IDENTIFIED
from fundos.cnpj import is_valid_cnpj
from fundos.informe_fidc import columns as informe_spec
from fundos.informe_fidc.loader import CLASS_NOT_FOUND
from fundos.informe_fidc.loader import CLASS_ONLY_FUND
from fundos.informe_fidc.loader import FUND_NOT_FOUND
from fundos.informe_fidc.loader import FUND_ONLY_CLASS
from fundos.informe_fidc.loader import REQUIRED_MIGRATIONS as INFORME_MIGRATIONS
from fundos.informe_fidc.loader import UNKNOWN_TYPE
from fundos.informe_fidc.loader import LoadedZip
from fundos.informe_fidc.loader import SubjectResolver
from fundos.informe_fidc.loader import cadastro_loaded
from fundos.informe_fidc.loader import normalize_last_modified
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.holding_repository import HoldingRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


PARSER_VERSION = "fundos.cda.v1"
REQUIRED_MIGRATIONS = {**INFORME_MIGRATIONS, 4: "holdings"}

# TP_FUNDO_CLASSE do detentor no CDA -> assunto do SubjectResolver.
HOLDER_TYPES = {
    "CLASSES - FIDC": informe_spec.CLASS_SUBJECT,
    "CLASSES - FIAGRO": informe_spec.CLASS_SUBJECT,
    "FIDC": informe_spec.FUND_SUBJECT,
    "FIAGRO": informe_spec.FUND_SUBJECT,
}

CLASS_SUBJECT = "classe"
FUND_SUBJECT = "fundo"

# Motivos para o detentor nao casar com o cadastro carregado: os do
# SubjectResolver; UNKNOWN_TYPE e o TP_FUNDO_CLASSE sem regra (CLASSES FIIM).
# O CNPJ invalido do detentor nao chega aqui: o leitor ja o descarta.
REASONS = (CLASS_ONLY_FUND, CLASS_NOT_FOUND, FUND_ONLY_CLASS, FUND_NOT_FOUND, UNKNOWN_TYPE)

# Tipo do investido no cadastro carregado (so para o relatorio).
OUTSIDE = "fora do cadastro carregado"
MIXED = "misto"
INVESTEE_TYPES = cadastro_spec.SCOPE_LABELS + (MIXED, OUTSIDE)

# Comparacao com o que ja esta no banco.
NEW = "novas"
EQUAL = "iguais"
CHANGED = "valor diferente"
COMPARISON = (NEW, EQUAL, CHANGED)

ALREADY_LOADED = "mesmo ZIP"
SAME_COMPETENCE = "mesma competencia"

KINDS = (IDENTIFIED, CONFIDENTIAL)
TABLES = {IDENTIFIED: "holdings", CONFIDENTIAL: "confidential_holdings"}
MEMBERS = {IDENTIFIED: spec.FIE, CONFIDENTIAL: spec.FIE_CONFID}


def loaded_zips(connection, cda):
    """ZIPs do CDA processados com o mesmo AAAAMM (pelo manifesto do cda_fie)."""

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
        (SOURCE_CODE, spec.member_name(spec.FIE, cda.zip.period)),
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


def find_loaded_cda(connection, cda):
    """ALREADY_LOADED, SAME_COMPETENCE (outro ZIP do mesmo mes) ou None."""

    hashes = {z.sha256 for z in loaded_zips(connection, cda)}

    if cda.zip.sha256 in hashes:
        return ALREADY_LOADED

    return SAME_COMPETENCE if hashes else None


def reapresentation_problem(connection, cda, last_modified):
    """Por que outro ZIP da competencia nao pode ser carregado, ou None.

    Mesma regra do informe de FIDC: last_modified (ja normalizado) tem de
    ser estritamente posterior ao do ZIP mais novo carregado, ou ao inicio
    da carga do ZIP que nao tem a data.
    """

    month = cda.competence[:7]

    if last_modified is None:
        return (
            "Ja existe CDA carregado para a competencia "
            + month
            + " (outro ZIP). Para carregar este ZIP como reapresentacao, informe"
            " --last-modified: o Last-Modified do ZIP na CVM, com fuso (por exemplo"
            " 2026-10-29T03:58:52Z ou Thu, 29 Oct 2026 03:58:52 GMT)."
        )

    loaded = loaded_zips(connection, cda)
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


def repeated_key_problem(cda):
    """Mensagem da recusa por chave repetida no arquivo (decisao 2), ou None."""

    keys = cda.counts[(IDENTIFIED, "chave_repetida", "chaves")]
    confidential = cda.counts[(CONFIDENTIAL, "detentor_repetido")]

    if not keys and not confidential:
        return None

    return (
        "O arquivo tem chave repetida: "
        + str(keys)
        + " chave(s) (detentor, investido, DT_COMPTC) nas cotas identificadas e "
        + str(confidential)
        + " detentor(es) com mais de uma linha confidencial de cotas. A chave"
        " natural das posicoes ainda nao foi decidida; nada foi gravado."
    )


def database_problem(connection):
    """Migration ou cadastro faltando no banco, ou None."""

    missing = missing_migrations(connection, REQUIRED_MIGRATIONS)

    if missing:
        return (
            "Faltam as migrations "
            + ", ".join(missing)
            + "; aplique antes com scripts/apply_migration.py."
        )

    if not cadastro_loaded(connection):
        return (
            "O cadastro nao foi carregado: carregue antes o "
            "registro_fundo_classe.zip com scripts/load_cadastro.py."
        )

    return None


def prerequisite_problem(connection, cda):
    """Por que a carga seria recusada antes de olhar o que ja foi carregado, ou None."""

    return database_problem(connection) or repeated_key_problem(cda)


def resolve(resolver, position):
    """(coluna do assunto, id) ou (None, motivo) do detentor da posicao."""

    subject_type = HOLDER_TYPES.get(position.holder_type)

    if subject_type is None:
        return None, UNKNOWN_TYPE

    return resolver.resolve(subject_type, position.holder_cnpj)


def _outcome(column):
    return CLASS_SUBJECT if column == "fund_class_id" else FUND_SUBJECT


def iter_matched(cda, kind, resolver, counts):
    """Posicoes cujo detentor casa com o cadastro: (posicao, coluna, id).

    Conta as linhas e os detentores distintos por resultado.
    """

    positions = cda.holdings() if kind == IDENTIFIED else cda.confidential_holdings()
    holders = {}

    for position in positions:
        column, value = resolve(resolver, position)
        outcome = value if column is None else _outcome(column)
        counts[("casamento", kind, outcome)] += 1
        holders.setdefault((position.holder_type, position.holder_cnpj), outcome)

        if column is not None:
            yield position, column, value

    for outcome in holders.values():
        counts[("detentores", kind, outcome)] += 1


def _holding_values(position):
    if position.investee_name is None:
        name_field, name = None, None
    else:
        name_field, name = spec.INVESTEE_NAME_FIELD, position.investee_name

    if position.quantity is None:
        quantity_field, quantity = None, None
    else:
        quantity_field, quantity = spec.QUANTITY_FIELD, position.quantity

    return {
        "investee_field_name": spec.INVESTEE_FIELD,
        "investee_cnpj": position.investee_cnpj,
        "name_field_name": name_field,
        "investee_name": name,
        "quantity_field_name": quantity_field,
        "quantity": quantity,
        "value_field_name": spec.VALUE_FIELD,
        "market_value": position.market_value,
        "reference_date": position.competence,
    }


def _confidential_values(position):
    return {
        "value_field_name": spec.CONFIDENTIAL_VALUE_FIELD,
        "market_value": position.market_value,
        "confidential_until_field_name": spec.CONFIDENTIAL_UNTIL_FIELD,
        "confidential_until": position.confidential_until,
        "reference_date": position.competence,
    }


VALUES = {IDENTIFIED: _holding_values, CONFIDENTIAL: _confidential_values}


def _keys_in_file(cda, kind, resolver):
    """Chaves (assunto, id[, investido]) das posicoes do arquivo que casam."""

    return {
        (column, subject_id) + ((position.investee_cnpj,) if kind == IDENTIFIED else ())
        for position, column, subject_id in iter_matched(cda, kind, resolver, Counter())
    }


def vanished_counts(connection, cda, resolver, source_id):
    """Posicoes da competencia ja no banco cuja chave nao esta no arquivo (so contadas)."""

    counts = Counter()

    for kind in KINDS:
        table = TABLES[kind]
        in_file = _keys_in_file(cda, kind, resolver)
        extra = ", investee_cnpj" if kind == IDENTIFIED else ""
        rows = connection.execute(
            "SELECT DISTINCT fund_id, fund_class_id" + extra + " FROM " + table
            + " WHERE reference_date = ? AND source_id = ?",
            (cda.competence, source_id),
        ).fetchall()

        for row in rows:
            column, subject_id = ("fund_id", row[0]) if row[0] is not None else ("fund_class_id", row[1])
            key = (column, int(subject_id)) + ((row[2],) if kind == IDENTIFIED else ())

            if key not in in_file:
                counts[("reapresentacao", kind, "sumiram")] += 1

    return counts


def compare_counts(connection, cda, resolver):
    """Contagens do dry-run com banco, sem escrever: casamento e comparacao."""

    counts = Counter()
    repository = HoldingRepository(connection)
    source = SourceRepository(connection).get_by_code(SOURCE_CODE)

    for kind in KINDS:
        table = TABLES[kind]

        for position, column, subject_id in iter_matched(cda, kind, resolver, counts):
            values = VALUES[kind](position)

            if repository.find_existing(table, column, subject_id, source.id, values) is not None:
                status = EQUAL
            elif repository.has_key(table, column, subject_id, values):
                status = CHANGED
            else:
                status = NEW

            counts[("comparacao", kind, status)] += 1

    counts.update(vanished_counts(connection, cda, resolver, source.id))
    return counts


def _types_by_cnpj(connection, subject_table, field_name, scope):
    """{CNPJ: rotulo FIDC/FIAGRO ou o texto fora do escopo} pelo valor atual."""

    column = "fund_class_id" if subject_table == "fund_classes" else "fund_id"
    rows = connection.execute(
        "SELECT t.cnpj, o.value_text FROM current_observations o"
        " JOIN " + subject_table + " t ON t.id = o." + column
        + " WHERE o.field_name = ?",
        (field_name,),
    ).fetchall()

    return {str(row[0]): scope.get(str(row[1]).strip(), OUTSIDE) for row in rows}


def investee_type_counts(connection, cda):
    """Linhas e investidos distintos por tipo no cadastro carregado (so leitura).

    O tipo e o Tipo_Classe atual da classe ou, sem classe, o Tipo_Fundo do
    fundo; classe e fundo com tipos diferentes contam como misto. Investido
    FIF, FII ou FIP fica como fora do cadastro carregado (o banco so tem
    FIDC e FIAGRO).
    """

    classes = _types_by_cnpj(
        connection,
        "fund_classes",
        cadastro_spec.field_name(cadastro_spec.CLASS_TABLE, "Tipo_Classe"),
        cadastro_spec.SCOPE[cadastro_spec.CLASS_TABLE],
    )
    funds = _types_by_cnpj(
        connection,
        "funds",
        cadastro_spec.field_name(cadastro_spec.FUND_TABLE, "Tipo_Fundo"),
        cadastro_spec.SCOPE[cadastro_spec.FUND_TABLE],
    )
    counts = Counter()
    investees = {}

    for holding in cda.holdings():
        cnpj = holding.investee_cnpj
        found = {t for t in (classes.get(cnpj), funds.get(cnpj)) if t is not None}

        if cnpj in classes:
            label = MIXED if len(found) > 1 else classes[cnpj]
        else:
            label = funds.get(cnpj, OUTSIDE)

        counts[("tipo_investido", "linhas", label)] += 1
        investees[cnpj] = label

    for label in investees.values():
        counts[("tipo_investido", "investidos", label)] += 1

    return counts


def scan_positions(connection, run_id):
    """(investee_cnpj com DV invalido, nome ou CNPJ com formato de CPF) desta coleta."""

    invalid = sum(
        1
        for (cnpj,) in connection.execute(
            "SELECT investee_cnpj FROM holdings WHERE collection_run_id = ?",
            (run_id,),
        )
        if not is_valid_cnpj(cnpj)
    )
    cpf_like = connection.execute(
        "SELECT COUNT(*) FROM holdings WHERE collection_run_id = ?"
        " AND (trim(investee_name) GLOB ? OR trim(investee_name) GLOB ?"
        " OR investee_cnpj GLOB ? OR investee_cnpj GLOB ?)",
        (run_id,) + CPF_GLOBS + CPF_GLOBS,
    ).fetchone()[0]

    return invalid, int(cpf_like)


def load_cda(connection, cda, *, last_modified=None):
    """Grava as posicoes do CDA na transacao aberta; devolve LoadResult.

    last_modified e o Last-Modified do ZIP na CVM (normalize_last_modified),
    gravado no manifesto do ZIP; e obrigatorio quando a competencia ja tem
    outro ZIP carregado. Levanta LoadError se faltar migration, se o
    cadastro nao estiver carregado, se o arquivo tiver chave repetida, se o
    mesmo ZIP ja estiver no banco, se o ZIP nao for comprovadamente mais
    novo que os ja carregados da competencia ou se a verificacao antes do
    COMMIT falhar; quem chama desfaz a transacao.
    """

    if last_modified is not None:
        try:
            last_modified = normalize_last_modified(last_modified)
        except ValueError as error:
            raise LoadError(str(error)) from error

    problem = prerequisite_problem(connection, cda)

    if problem is not None:
        raise LoadError(problem)

    loaded = find_loaded_cda(connection, cda)

    if loaded == ALREADY_LOADED:
        raise LoadError(
            "Ja existe CDA carregado para a competencia "
            + cda.competence
            + " ("
            + loaded
            + "); nada a carregar."
        )

    if loaded == SAME_COMPETENCE:
        problem = reapresentation_problem(connection, cda, last_modified)

        if problem is not None:
            raise LoadError(problem)

    source = SourceRepository(connection).get_by_code(SOURCE_CODE)

    if source is None:
        raise LoadError("A fonte " + SOURCE_CODE + " nao existe no banco.")

    resolver = SubjectResolver(connection)
    counts = Counter()

    if loaded == SAME_COMPETENCE:
        # Antes de qualquer gravacao: o que ja estava no banco e sumiu.
        counts.update(vanished_counts(connection, cda, resolver, source.id))
        counts[("reapresentacao", "zips")] = len(loaded_zips(connection, cda))

    positions = sum(cda.counts[(kind, "posicoes")] for kind in KINDS)
    runs = CollectionRunRepository(connection)
    run = runs.start(source.id, requested_items=positions)
    raws = RawRecordRepository(connection)
    zip_raw, _ = raws.register_file(
        source_id=source.id,
        collection_run_id=run.id,
        file_name=cda.zip.file_name,
        size_bytes=cda.zip.size_bytes,
        sha256=cda.zip.sha256,
        last_modified=last_modified,
        collected_at=run.started_at,
    )
    member_raws = {}

    for table in spec.TABLES:
        member = cda.member(table)
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

    repository = HoldingRepository(connection)
    loaded_positions = 0

    for kind in KINDS:
        record = repository.record if kind == IDENTIFIED else repository.record_confidential
        raw_record_id = member_raws[MEMBERS[kind]].id

        for position, column, subject_id in iter_matched(cda, kind, resolver, counts):
            values = VALUES[kind](position)
            values.pop("reference_date")
            result = record(
                **{column: subject_id},
                **values,
                source_id=source.id,
                collection_run_id=run.id,
                raw_record_id=raw_record_id,
                reference_date=position.competence,
            )
            loaded_positions += 1
            counts[("gravadas", kind, "criadas" if result.created else "existentes")] += 1
            counts[("conflitos", kind)] += len(result.conflicts)

    raws.update_processing(zip_raw.id, "processed", parser_version=PARSER_VERSION)

    for table, record in member_raws.items():
        status = "ignored" if table in spec.IGNORED_TABLES else "processed"
        raws.update_processing(record.id, status, parser_version=PARSER_VERSION)

    out = sum(counts[("casamento", kind, reason)] for kind in KINDS for reason in REASONS)
    runs.finish(
        run.id,
        "success",
        successful_items=loaded_positions,
        failed_items=0,
        error_summary={"posicoes_com_detentor_fora_do_cadastro": out} if out else None,
    )

    invalid, cpf_like = scan_positions(connection, run.id)
    counts[("varredura", "cnpj_invalido")] = invalid
    counts[("varredura", "formato_cpf")] = cpf_like
    problems = verify(connection, run.id)

    if invalid or cpf_like:
        problems.append(
            "Posicoes desta coleta com investee_cnpj invalido: "
            + str(invalid)
            + "; com nome ou CNPJ em formato de CPF: "
            + str(cpf_like)
            + "."
        )

    if problems:
        raise LoadError("Verificacao antes do COMMIT falhou: " + " ".join(problems))

    return LoadResult(run_id=run.id, status="success", counts=counts)
