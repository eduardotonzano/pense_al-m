"""Leitura do informe mensal de FIDC da CVM (inf_mensal_fidc_AAAAMM.zip), sem banco.

O ZIP e lido inteiro em memoria; nada e extraido em disco. Uma primeira
passada confere tudo antes de qualquer gravacao: os 18 membros (e so eles)
com o mesmo AAAAMM, o cabecalho exato de cada tabela (columns.py), a largura
das linhas, o formato de cada valor e a competencia. A competencia e o
DT_COMPTC: um so valor, do mes do AAAAMM e nao posterior a hoje (UTC).
Depois, rows(tabela) entrega as linhas normalizadas de uma tabela por vez,
sem manter as ~200 mil linhas em memoria.

Normalizacao: CNPJ sem mascara, S/N para booleano, decimal exato como
texto. Notacao cientifica ("e" ou "E" seguido de expoente inteiro) e
convertida de forma exata, sem expoente, e contada por coluna; qualquer
outro formato fora do decimal com ponto aborta a leitura.

Dados pessoais (decisao 3 de Fundos): nas 36 colunas de cedente, so o
cedente com CNPJ valido vira papel cedente, sem nome, com o percentual da
mesma posicao do mesmo grupo. 11 digitos ou mascara de CPF sao tratados
como CPF e descartados, mesmo que fechem como CNPJ com zeros a esquerda;
o percentual da mesma posicao vai junto. Tudo e contado por grupo. A
administradora so fica com CNPJ valido; o nome sem CNPJ valido e
descartado e contado. Nenhum objeto mostra CNPJ, nome ou valor no repr.
As mensagens citam arquivo, linha e coluna, nunca o valor.
"""

import hashlib
import io
import re
import zipfile
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from fundos.cadastro.reader import PartyValue
from fundos.cvm_csv import CNPJ
from fundos.cvm_csv import EMPTY
from fundos.cvm_csv import MAX_MEMBER_BYTES
from fundos.cvm_csv import MAX_ZIP_BYTES
from fundos.cvm_csv import NUMERIC
from fundos.cvm_csv import CvmFormatError
from fundos.cvm_csv import MemberManifest
from fundos.cvm_csv import classify_identifier
from fundos.cvm_csv import convert
from fundos.cvm_csv import decode
from fundos.cvm_csv import iter_csv
from fundos.cvm_csv import location
from fundos.cvm_csv import member_manifest
from fundos.database import normalize_iso_date
from fundos.informe_fidc import columns as spec
from fundos.repositories.observation_repository import canonical_decimal
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


InformeFormatError = CvmFormatError

MEMBER = re.compile(r"inf_mensal_fidc_(tab_[IVX0-9_]+?)_([0-9]{6})\.csv")
ZIP_NAME = re.compile(r"inf_mensal_fidc_([0-9]{6})\.zip")

# Notacao cientifica aceita: mantissa decimal com ponto e expoente inteiro.
SCIENTIFIC = re.compile(r"-?[0-9]+(\.[0-9]+)?[eE][+-]?[0-9]{1,3}")
MAX_EXPONENT = 30

# Rotulo das linhas cujo TP_FUNDO_CLASSE nao e Classe nem Fundo.
OTHER_SUBJECT = "outro"


@dataclass(frozen=True)
class InformeZipManifest:
    """Manifesto do ZIP: nome, tamanho, SHA-256, datas dos membros e AAAAMM."""

    file_name: str
    size_bytes: int
    sha256: str
    member_dates: tuple[str, ...]
    period: str


@dataclass(frozen=True)
class InformeRow:
    """Uma linha normalizada de uma das 18 tabelas.

    subject_type e Classe, Fundo ou None (outro valor); cnpj e o
    CNPJ_FUNDO_CLASSE sem mascara, ou None se invalido. values tem so o que
    vira observacao (sem chave, sem cedente, sem a administradora e sem
    DENOM_SOCIAL fora da tab_I). name e a DENOM_SOCIAL, para conferencia.
    parties tem a administradora e os cedentes de CNPJ valido. CNPJ, nome,
    rotulo e valores nunca aparecem no repr.
    """

    table: str
    line: int
    subject_type: str | None
    cnpj: str | None = field(repr=False)
    competence: str
    name: str | None = field(repr=False)
    series_label: str | None = field(repr=False)
    series_key: str | None = field(repr=False)
    subclass_id: str | None = field(repr=False)
    values: MappingProxyType = field(repr=False)
    parties: tuple[PartyValue, ...]


@dataclass(frozen=True)
class InformeFile:
    """O ZIP lido e conferido: manifestos, competencia e contagens.

    rows(tabela) le de novo o membro (guardado em bytes) e entrega as linhas
    normalizadas. Os bytes nunca aparecem no repr: trazem os cedentes.
    """

    zip: InformeZipManifest
    members: tuple[MemberManifest, ...]
    competence: str
    counts: Counter
    shared_subclass_ids: frozenset[str] = field(repr=False)
    contents: MappingProxyType = field(repr=False, compare=False)

    def member(self, table):
        """Manifesto do CSV da tabela."""

        name = spec.member_name(table, self.zip.period)

        for member in self.members:
            if member.file_name == name:
                return member

        raise KeyError(name)

    def rows(self, table):
        """Linhas normalizadas da tabela, na ordem do arquivo."""

        member = spec.member_name(table, self.zip.period)
        text = decode(member, self.contents[table])

        for line, fields in iter_csv(member, text, spec.HEADERS[table]):
            yield parse_row(table, member, line, fields)


def convert_numeric(value):
    """(decimal exato em texto, se veio em notacao cientifica).

    A notacao cientifica e escrita sem expoente, sem arredondar (Decimal).
    Levanta ValueError para qualquer outro formato fora do decimal com
    ponto.
    """

    text = value.strip()

    if SCIENTIFIC.fullmatch(text) is None:
        return canonical_decimal(value), False

    number = Decimal(text)

    if abs(number.adjusted()) > MAX_EXPONENT:
        raise ValueError("Expoente fora do limite.")

    return canonical_decimal(format(number, "f")), True


def _format_error(member, line, column, kind):
    return InformeFormatError(
        location(member, line, column) + ": valor fora do formato " + kind + "."
    )


def _parse_admin(table, record, counts):
    """A administradora da linha (so com CNPJ valido)."""

    status, cnpj = classify_identifier(record[spec.ADMIN_ID_COLUMN])
    name = (
        record[spec.ADMIN_NAME_COLUMN]
        if record[spec.ADMIN_NAME_COLUMN].strip()
        else None
    )

    if counts is not None:
        counts[("administradora", status)] += 1

    if status != CNPJ:
        if name is not None and counts is not None:
            counts[("nome_descartado", spec.field_name(table, spec.ADMIN_NAME_COLUMN))] += 1

        return ()

    return (
        PartyValue(
            role=spec.ADMIN_ROLE,
            field_name=spec.field_name(table, spec.ADMIN_ID_COLUMN),
            cnpj=cnpj,
            name_field_name=(
                None if name is None else spec.field_name(table, spec.ADMIN_NAME_COLUMN)
            ),
            name=name,
        ),
    )


def _count_cedente(counts, prefix, value, status, share):
    """Conta uma posicao de cedente (identificador e percentual) do grupo."""

    if status != EMPTY:
        counts[("cedente_identificador", prefix, status)] += 1

    if status == CNPJ and value.strip().isdigit() and len(value.strip()) < 14:
        counts[("cedente_zeros_restaurados", prefix)] += 1

    if share is None:
        if status == CNPJ:
            counts[("cedente_sem_percentual", prefix)] += 1

        return

    if status != CNPJ:
        # Percentual sem identificador gravavel (vazio, CPF ou invalido):
        # so contado, nunca gravado.
        counts[("cedente_percentual", prefix, "sem_identificador")] += 1
        return

    counts[("cedente_percentual", prefix, "com_identificador")] += 1
    number = Decimal(share)

    if number < 0:
        counts[("cedente_percentual_negativo", prefix)] += 1

    if number > 100:
        counts[("cedente_percentual_acima_de_100", prefix)] += 1


def _parse_cedentes(table, member, line, record, counts):
    """Os cedentes da linha com CNPJ valido, cada um com o percentual da posicao.

    O identificador n vai com o percentual n do mesmo grupo. CPF (11 digitos
    ou mascara), vazio e invalido nao viram papel. O percentual e decimal
    exato (notacao cientifica convertida, como nas colunas numericas); fora
    do formato, aborta a leitura.
    """

    parties = []
    groups = defaultdict(set)

    for prefix, _ in spec.CEDENTE_GROUPS:
        seen = set()

        for position in spec.CEDENTE_POSITIONS:
            id_column, share_column = spec.cedente_columns(prefix, position)
            value = record[id_column]
            status, cnpj = classify_identifier(value)
            share = None

            if record[share_column].strip():
                try:
                    share, scientific = convert_numeric(record[share_column])
                except ValueError as error:
                    raise _format_error(member, line, share_column, NUMERIC) from error

                if scientific and counts is not None:
                    counts[("notacao_cientifica", spec.field_name(table, share_column))] += 1

            if counts is not None:
                _count_cedente(counts, prefix, value, status, share)

            if status != CNPJ:
                continue

            if cnpj in seen and counts is not None:
                counts[("cedente_repetido_no_grupo", prefix)] += 1

            seen.add(cnpj)
            parties.append(
                PartyValue(
                    role=spec.CEDENTE_ROLE,
                    field_name=spec.field_name(table, id_column),
                    cnpj=cnpj,
                    name_field_name=None,
                    name=None,
                    share_field_name=(
                        None if share is None else spec.field_name(table, share_column)
                    ),
                    share=share,
                )
            )

        for cnpj in seen:
            groups[cnpj].add(prefix)

    if counts is not None:
        counts[("cedente_nos_dois_grupos",)] += sum(
            1 for prefixes in groups.values() if len(prefixes) > 1
        )

        if parties:
            counts[("cedente_assuntos_com_gravavel",)] += 1

    return tuple(parties)


def parse_row(table, member, line, fields, counts=None):
    """Normaliza uma linha; com counts, conta o que foi descartado."""

    record = dict(zip(spec.HEADERS[table], fields))
    kinds = spec.KINDS[table]
    raw_type = record[spec.SUBJECT_TYPE_COLUMN].strip()
    subject_type = raw_type if raw_type in spec.SUBJECT_TYPES else None
    status, cnpj = classify_identifier(record[spec.SUBJECT_COLUMN])

    try:
        competence = normalize_iso_date(record[spec.COMPETENCE_COLUMN], "A competencia")
    except ValueError as error:
        raise _format_error(member, line, spec.COMPETENCE_COLUMN, "date") from error

    if counts is not None:
        counts[("linhas_por_tipo", table, subject_type or OTHER_SUBJECT)] += 1

        if status != CNPJ:
            counts[("cnpj_assunto_invalido", table)] += 1

    name = None
    label = None
    key = None
    subclass_id = None
    values = {}

    for column, kind in kinds.items():
        value = record[column]

        if kind in (spec.KEY, spec.PARTY_ID, spec.PARTY_NAME):
            continue

        if kind in (spec.CEDENTE_ID, spec.CEDENTE_SHARE):
            # Lidos em _parse_cedentes; aqui so o total de celulas
            # preenchidas, que fecha com as contagens por grupo.
            if counts is not None and value.strip():
                counts[("cedentes_preenchidas",)] += 1

            continue

        if kind == spec.CNPJ_TEXT:
            cnpj_status, normalized = classify_identifier(value)

            if counts is not None:
                counts[("cnpj_classe", cnpj_status)] += 1

            if normalized is not None:
                values[column] = normalized

            continue

        if not value.strip():
            if kind == spec.SERIES_LABEL and counts is not None:
                counts[("rotulo_vazio", table)] += 1

            continue

        if kind == spec.NAME:
            name = value

            if table == spec.NAME_TABLE:
                values[column] = value

            continue

        if kind == spec.SERIES_LABEL:
            try:
                key = QuotaSeriesRepository.normalize_series_label(value)
            except ValueError:
                if counts is not None:
                    counts[("rotulo_vazio", table)] += 1

                continue

            label = value
            values[column] = value
            continue

        if kind == spec.SUBCLASS:
            subclass_id = value.strip()
            values[column] = value
            continue

        if kind == NUMERIC:
            try:
                number, scientific = convert_numeric(value)
            except ValueError as error:
                raise _format_error(member, line, column, kind) from error

            if scientific and counts is not None:
                counts[("notacao_cientifica", spec.field_name(table, column))] += 1

            values[column] = number
            continue

        try:
            values[column] = convert(kind, value)
        except ValueError as error:
            raise _format_error(member, line, column, kind) from error

    parties = ()

    if spec.ADMIN_ID_COLUMN in kinds:
        parties = _parse_admin(table, record, counts) + _parse_cedentes(
            table, member, line, record, counts
        )

    return InformeRow(
        table=table,
        line=line,
        subject_type=subject_type,
        cnpj=cnpj,
        competence=competence,
        name=name,
        series_label=label,
        series_key=key,
        subclass_id=subclass_id,
        values=MappingProxyType(values),
        parties=parties,
    )


def _check_members(archive, file_name, max_member_bytes):
    """Exatamente os 18 membros, com o mesmo AAAAMM; devolve (AAAAMM, infos)."""

    found = defaultdict(list)
    unexpected = 0

    for info in archive.infolist():
        match = MEMBER.fullmatch(info.filename)

        if match is None or match.group(1) not in spec.TABLES:
            unexpected += 1
            continue

        found[match.group(1)].append((match.group(2), info))

    missing = [table for table in spec.TABLES if table not in found]
    repeated = [table for table, entries in found.items() if len(entries) > 1]
    periods = sorted({period for entries in found.values() for period, _ in entries})
    problems = []

    if missing:
        problems.append("faltam " + ", ".join(missing))

    if unexpected:
        problems.append(str(unexpected) + " membro(s) inesperado(s)")

    if repeated:
        problems.append("tabela repetida: " + ", ".join(repeated))

    if len(periods) > 1:
        problems.append("AAAAMM diferente entre os membros (" + ", ".join(periods) + ")")

    if problems:
        raise InformeFormatError(
            "O ZIP nao tem exatamente as 18 tabelas do informe de FIDC ("
            + "; ".join(problems)
            + "). Nada foi lido."
        )

    period = periods[0]
    zip_match = ZIP_NAME.fullmatch(file_name)

    if zip_match is not None and zip_match.group(1) != period:
        raise InformeFormatError(
            "O nome do ZIP ("
            + zip_match.group(1)
            + ") nao bate com o AAAAMM dos membros ("
            + period
            + "). Nada foi lido."
        )

    infos = {table: entries[0][1] for table, entries in found.items()}

    for table, info in infos.items():
        if info.file_size > max_member_bytes:
            raise InformeFormatError(
                info.filename
                + " passa do limite de "
                + str(max_member_bytes)
                + " bytes descomprimidos."
            )

    return period, infos


def _check_competence(competences, period):
    """Um so DT_COMPTC, do mes do AAAAMM, nao posterior a hoje (UTC)."""

    if len(competences) != 1:
        raise InformeFormatError(
            "DT_COMPTC com "
            + str(len(competences))
            + " valores diferentes ("
            + ", ".join(sorted(competences))
            + "); o informe deve ter uma so competencia. Nada foi lido."
        )

    competence = next(iter(competences))

    if competence[:4] + competence[5:7] != period:
        raise InformeFormatError(
            "DT_COMPTC "
            + competence
            + " nao e do mes do AAAAMM dos membros ("
            + period
            + "). Nada foi lido."
        )

    today = datetime.now(timezone.utc).date().isoformat()

    if competence > today:
        raise InformeFormatError(
            "DT_COMPTC " + competence + " e posterior a hoje (" + today + ", UTC)."
        )

    return competence


def read_informe_bytes(data, file_name, *, progress=None, max_member_bytes=MAX_MEMBER_BYTES):
    """Le e confere o ZIP ja carregado em memoria; devolve InformeFile.

    progress(tabela, linhas), se informado, e chamado ao fim de cada tabela.
    """

    zip_hash = hashlib.sha256(data).hexdigest()

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise InformeFormatError(file_name + " nao e um ZIP valido.") from error

    counts = Counter()
    members = []
    contents = {}
    competences = set()
    names = {}
    divergent = set()
    subclass_keys = defaultdict(set)
    subclass_rows = Counter()
    series = defaultdict(set)

    with archive:
        period, infos = _check_members(archive, file_name, max_member_bytes)
        member_dates = tuple(
            sorted({"%04d-%02d-%02d" % info.date_time[:3] for info in infos.values()})
        )

        for table in spec.TABLES:
            member = spec.member_name(table, period)
            raw = archive.read(infos[table])

            if len(raw) > max_member_bytes:
                raise InformeFormatError(
                    member
                    + " passa do limite de "
                    + str(max_member_bytes)
                    + " bytes descomprimidos."
                )

            text = decode(member, raw)
            line_count = 0

            for line, fields in iter_csv(member, text, spec.HEADERS[table]):
                line_count += 1
                row = parse_row(table, member, line, fields, counts)
                competences.add(row.competence)
                subject = (row.subject_type, row.cnpj)

                if table == spec.NAME_TABLE:
                    names[subject] = row.name
                elif names.get(subject) != row.name:
                    divergent.add(subject)

                if row.series_key is not None:
                    series[table].add((subject, row.series_key))

                if row.subclass_id:
                    subclass_keys[row.subclass_id].add((subject, row.series_key))
                    subclass_rows[row.subclass_id] += 1

            del text
            members.append(
                member_manifest(member, raw, line_count, len(spec.HEADERS[table]))
            )
            contents[table] = raw

            if progress is not None:
                progress(table, line_count)

    competence = _check_competence(competences, period)
    shared = frozenset(
        subclass_id for subclass_id, keys in subclass_keys.items() if len(keys) > 1
    )

    for subject in names:
        counts[("assuntos", subject[0] or OTHER_SUBJECT)] += 1

    counts[("denom_divergente",)] = len(divergent)
    counts[("id_subclasse", "linhas")] = sum(subclass_rows.values())
    counts[("id_subclasse", "distintos")] = len(subclass_keys)
    counts[("id_subclasse", "repetidos")] = len(shared)
    counts[("id_subclasse", "linhas_repetidos")] = sum(
        subclass_rows[subclass_id] for subclass_id in shared
    )

    for table, keys in series.items():
        counts[("series", table)] = len(keys)

    return InformeFile(
        zip=InformeZipManifest(
            file_name=file_name,
            size_bytes=len(data),
            sha256=zip_hash,
            member_dates=member_dates,
            period=period,
        ),
        members=tuple(members),
        competence=competence,
        counts=counts,
        shared_subclass_ids=shared,
        contents=MappingProxyType(contents),
    )


def read_informe_zip(path, *, progress=None, max_member_bytes=MAX_MEMBER_BYTES):
    """Le e confere o inf_mensal_fidc_AAAAMM.zip do disco, sem extrair nada."""

    zip_path = Path(path)

    if not zip_path.is_file():
        raise FileNotFoundError("ZIP nao encontrado: " + str(zip_path))

    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise InformeFormatError(
            zip_path.name + " passa do limite de " + str(MAX_ZIP_BYTES) + " bytes."
        )

    return read_informe_bytes(
        zip_path.read_bytes(),
        zip_path.name,
        progress=progress,
        max_member_bytes=max_member_bytes,
    )
