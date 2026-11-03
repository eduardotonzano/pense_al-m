"""Leitura do informe mensal de FIAGRO da CVM (inf_mensal_fiagro_AAAAMM.zip), sem banco.

O ZIP e lido inteiro em memoria; nada e extraido em disco. Uma primeira
passada confere tudo antes de qualquer gravacao: os 2 membros (e so eles)
com o mesmo AAAAMM, o cabecalho exato de cada arquivo (columns.py), a
largura das linhas, o formato de cada valor e a competencia. Depois,
rows(tabela) entrega as linhas normalizadas de um arquivo por vez.

Competencia: o AAAAMM dos membros (e do nome do ZIP, quando segue o
padrao). Data_Referencia tem de ter um so valor nos dois arquivos, o dia 1
desse AAAAMM; senao nada e lido. A competencia gravada e o ultimo dia do
mes, a mesma convencao do DT_COMPTC do FIDC, e nao pode ser posterior a
hoje (UTC). A data gravada nao e a literal do arquivo; a literal e
reconstruivel, porque so o dia 1 e aceito.

Chaves: um CNPJ_Classe que aparece em mais de uma linha do arquivo de
classe nao e carregado (nenhuma das linhas, nem as subclasses dele), e o
par (CNPJ_Classe, rotulo normalizado) repetido no arquivo de subclasse
tambem nao. Nada e escolhido por Versao, Data_Entrega ou nome; tudo e
contado.

Normalizacao: CNPJ sem mascara (12 ou 13 digitos ganham os zeros), S/N
para booleano, data AAAA-MM-DD e decimal exato como texto, com a notacao
cientifica convertida e contada por coluna, como no FIDC; texto como vem.

Dados pessoais (decisao 3 de Fundos): as colunas de contato e
Entidade_Administradora sao descartadas sem serem guardadas. O
administrador e o gestor so ficam com CNPJ valido; CPF (11 digitos ou
mascara), vazio e invalido sao descartados junto com o nome e contados.
Nenhum objeto mostra CNPJ, nome ou valor no repr. As mensagens citam
arquivo, linha e coluna, nunca o valor.
"""

import calendar
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
from pathlib import Path
from types import MappingProxyType

from fundos.cadastro.reader import PartyValue
from fundos.cvm_csv import CNPJ
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
from fundos.informe_fiagro import columns as spec
from fundos.informe_fidc.reader import InformeZipManifest
from fundos.informe_fidc.reader import convert_numeric
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


InformeFormatError = CvmFormatError

MEMBER = re.compile(r"(inf_mensal_fiagro|inf_mensal_fiagro_subclasse)_([0-9]{6})\.csv")
ZIP_NAME = re.compile(r"inf_mensal_fiagro_([0-9]{6})\.zip")

# Rotulos fixos da contagem da Versao (o valor nao vai para o relatorio).
VERSION_ONE = "igual_a_1"
VERSION_OTHER = "diferente_de_1"
VERSION_EMPTY = "vazia"


@dataclass(frozen=True)
class InformeRow:
    """Uma linha normalizada do arquivo de classe ou do de subclasse.

    cnpj e o CNPJ_Classe sem mascara, ou None se vazio, CPF ou invalido.
    values tem so o que vira observacao (sem chave, sem papel, sem contato
    e sem o Nome_Classe da subclasse). name e o Nome_Classe, para
    conferencia. parties tem o administrador e o gestor de CNPJ valido (so
    no arquivo de classe). CNPJ, nome, rotulo e valores nunca aparecem no
    repr.
    """

    table: str
    line: int
    cnpj: str | None = field(repr=False)
    reference: str
    name: str | None = field(repr=False)
    series_label: str | None = field(repr=False)
    series_key: str | None = field(repr=False)
    values: MappingProxyType = field(repr=False)
    parties: tuple[PartyValue, ...]


@dataclass(frozen=True)
class InformeFile:
    """O ZIP lido e conferido: manifestos, competencia, chaves e contagens.

    reference e o Data_Referencia (dia 1); competence e o ultimo dia do mes,
    a data gravada. class_keys tem os CNPJ_Classe validos do arquivo de
    classe; repeated_keys, os que aparecem em mais de uma linha;
    repeated_series, os pares (CNPJ_Classe, rotulo normalizado) repetidos no
    arquivo de subclasse. rows(tabela) le de novo o membro (guardado em
    bytes). Nada disso aparece no repr.
    """

    zip: InformeZipManifest
    members: tuple[MemberManifest, ...]
    reference: str
    competence: str
    counts: Counter
    class_keys: frozenset[str] = field(repr=False)
    repeated_keys: frozenset[str] = field(repr=False)
    repeated_series: frozenset[tuple[str, str]] = field(repr=False)
    contents: MappingProxyType = field(repr=False, compare=False)

    def member(self, table):
        """Manifesto do CSV do arquivo."""

        name = spec.member_name(table, self.zip.period)

        for member in self.members:
            if member.file_name == name:
                return member

        raise KeyError(name)

    def rows(self, table):
        """Linhas normalizadas do arquivo, na ordem do arquivo."""

        member = spec.member_name(table, self.zip.period)
        text = decode(member, self.contents[table])

        for line, fields in iter_csv(member, text, spec.HEADERS[table]):
            yield parse_row(table, member, line, fields)


def _format_error(member, line, column, kind):
    return InformeFormatError(
        location(member, line, column) + ": valor fora do formato " + kind + "."
    )


def _parse_parties(table, record, counts):
    """Administrador e gestor da linha, so com CNPJ valido."""

    parties = []

    for role, id_column, name_column in spec.PARTIES:
        id_field = spec.field_name(table, id_column)
        status, cnpj = classify_identifier(record[id_column])
        name = record[name_column] if record[name_column].strip() else None

        if counts is not None:
            counts[("identificador", id_field, status)] += 1

        if status != CNPJ:
            if name is not None and counts is not None:
                counts[("nome_descartado", spec.field_name(table, name_column))] += 1

            continue

        parties.append(
            PartyValue(
                role=role,
                field_name=id_field,
                cnpj=cnpj,
                name_field_name=(
                    None if name is None else spec.field_name(table, name_column)
                ),
                name=name,
            )
        )

    return tuple(parties)


def parse_row(table, member, line, fields, counts=None):
    """Normaliza uma linha; com counts, conta o que foi descartado."""

    record = dict(zip(spec.HEADERS[table], fields))
    status, cnpj = classify_identifier(record[spec.SUBJECT_COLUMN])

    try:
        reference = normalize_iso_date(record[spec.REFERENCE_COLUMN], "A data de referencia")
    except ValueError as error:
        raise _format_error(member, line, spec.REFERENCE_COLUMN, "date") from error

    if counts is not None:
        counts[("cnpj_classe", table, status)] += 1

    name = None
    label = None
    key = None
    values = {}

    for column, kind in spec.KINDS[table].items():
        if kind in (spec.KEY, spec.EXCLUDED, spec.PARTY_ID, spec.PARTY_NAME):
            continue

        value = record[column]

        if not value.strip():
            if kind == spec.SERIES_LABEL and counts is not None:
                counts[("rotulo_vazio", table)] += 1

            continue

        if kind == spec.NAME:
            name = value

            if table == spec.CLASS_TABLE:
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

    parties = _parse_parties(table, record, counts) if table == spec.CLASS_TABLE else ()

    return InformeRow(
        table=table,
        line=line,
        cnpj=cnpj,
        reference=reference,
        name=name,
        series_label=label,
        series_key=key,
        values=MappingProxyType(values),
        parties=parties,
    )


def _check_members(archive, file_name, max_member_bytes):
    """Exatamente os 2 membros, com o mesmo AAAAMM; devolve (AAAAMM, infos)."""

    found = defaultdict(list)
    unexpected = 0

    for info in archive.infolist():
        match = MEMBER.fullmatch(info.filename)

        if match is None:
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
        problems.append("arquivo repetido: " + ", ".join(repeated))

    if len(periods) > 1:
        problems.append("AAAAMM diferente entre os membros (" + ", ".join(periods) + ")")

    if problems:
        raise InformeFormatError(
            "O ZIP nao tem exatamente os 2 arquivos do informe de FIAGRO ("
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

    for info in infos.values():
        if info.file_size > max_member_bytes:
            raise InformeFormatError(
                info.filename
                + " passa do limite de "
                + str(max_member_bytes)
                + " bytes descomprimidos."
            )

    return period, infos


def _check_reference(references, period):
    """Um so Data_Referencia, o dia 1 do AAAAMM; devolve (dia 1, ultimo dia do mes)."""

    if len(references) != 1:
        raise InformeFormatError(
            "Data_Referencia com "
            + str(len(references))
            + " valores diferentes ("
            + ", ".join(sorted(references))
            + ") nos 2 arquivos; o informe deve ter uma so competencia. Nada foi lido."
        )

    reference = next(iter(references))
    first_day = period[:4] + "-" + period[4:] + "-01"

    if reference != first_day:
        raise InformeFormatError(
            "Data_Referencia "
            + reference
            + " nao e o dia 1 do AAAAMM dos membros ("
            + period
            + "). Nada foi lido."
        )

    year, month = int(period[:4]), int(period[4:])
    competence = first_day[:8] + format(calendar.monthrange(year, month)[1], "02d")
    today = datetime.now(timezone.utc).date().isoformat()

    if competence > today:
        raise InformeFormatError(
            "A competencia "
            + competence
            + " (ultimo dia do mes de Data_Referencia) e posterior a hoje ("
            + today
            + ", UTC)."
        )

    return reference, competence


def _version_status(row):
    version = row.values.get(spec.VERSION_COLUMN)

    if version is None:
        return VERSION_EMPTY

    return VERSION_ONE if version == "1" else VERSION_OTHER


def read_informe_bytes(data, file_name, *, progress=None, max_member_bytes=MAX_MEMBER_BYTES):
    """Le e confere o ZIP ja carregado em memoria; devolve InformeFile.

    progress(tabela, linhas), se informado, e chamado ao fim de cada arquivo.
    """

    zip_hash = hashlib.sha256(data).hexdigest()

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise InformeFormatError(file_name + " nao e um ZIP valido.") from error

    counts = Counter()
    members = []
    contents = {}
    references = set()
    keys = Counter()
    versions = defaultdict(set)
    names = {}
    deliveries = set()
    isins = defaultdict(set)
    pairs = Counter()
    labels = set()
    label_keys = set()

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
                references.add(row.reference)

                if table == spec.CLASS_TABLE:
                    counts[("versao", _version_status(row))] += 1

                    if spec.DELIVERY_COLUMN in row.values:
                        deliveries.add(row.values[spec.DELIVERY_COLUMN])

                    isin = row.values.get(spec.ISIN_COLUMN)

                    if isin is None:
                        counts[("isin", "vazio")] += 1
                    else:
                        counts[("isin", "preenchido")] += 1
                        isins[isin.strip()].add(row.cnpj)

                    if row.cnpj is not None:
                        keys[row.cnpj] += 1
                        versions[row.cnpj].add(row.values.get(spec.VERSION_COLUMN))
                        names[row.cnpj] = row.name

                    continue

                # Arquivo de subclasse: o de classe ja foi lido inteiro.
                if row.series_key is not None:
                    labels.add(row.series_label)
                    label_keys.add(row.series_key)

                if row.cnpj is None:
                    continue

                if row.cnpj not in keys:
                    counts[("subclasse", "sem_classe_no_arquivo")] += 1
                elif keys[row.cnpj] > 1:
                    counts[("subclasse", "de_chave_repetida")] += 1
                elif names[row.cnpj] != row.name:
                    counts[("subclasse", "nome_classe_divergente")] += 1

                if row.series_key is not None:
                    pairs[(row.cnpj, row.series_key)] += 1

            del text
            members.append(
                member_manifest(member, raw, line_count, len(spec.HEADERS[table]))
            )
            contents[table] = raw

            if progress is not None:
                progress(table, line_count)

    reference, competence = _check_reference(references, period)
    repeated_keys = frozenset(cnpj for cnpj, n in keys.items() if n > 1)
    repeated_series = frozenset(pair for pair, n in pairs.items() if n > 1)
    outside = [pair for pair in repeated_series if pair[0] not in repeated_keys]

    counts[("chaves", "distintas")] = len(keys)
    counts[("chaves", "repetidas")] = len(repeated_keys)
    counts[("chaves", "linhas_repetidas")] = sum(keys[cnpj] for cnpj in repeated_keys)
    counts[("chaves", "repetidas_com_versao_diferente")] = sum(
        1 for cnpj in repeated_keys if len(versions[cnpj]) > 1
    )
    counts[("data_entrega", "distintas")] = len(deliveries)
    counts[("isin", "distintos")] = len(isins)
    counts[("isin", "em_varias_classes")] = sum(
        1 for cnpjs in isins.values() if len(cnpjs) > 1
    )
    counts[("subclasse", "pares_repetidos")] = len(repeated_series)
    counts[("subclasse", "linhas_de_pares_repetidos")] = sum(
        pairs[pair] for pair in repeated_series
    )
    counts[("subclasse", "pares_repetidos_fora_das_chaves_repetidas")] = len(outside)
    counts[("subclasse", "linhas_de_pares_repetidos_fora_das_chaves_repetidas")] = sum(
        pairs[pair] for pair in outside
    )
    counts[("rotulos", "distintos")] = len(labels)
    counts[("rotulos", "normalizados_distintos")] = len(label_keys)

    return InformeFile(
        zip=InformeZipManifest(
            file_name=file_name,
            size_bytes=len(data),
            sha256=zip_hash,
            member_dates=member_dates,
            period=period,
        ),
        members=tuple(members),
        reference=reference,
        competence=competence,
        counts=counts,
        class_keys=frozenset(keys),
        repeated_keys=repeated_keys,
        repeated_series=repeated_series,
        contents=MappingProxyType(contents),
    )


def read_informe_zip(path, *, progress=None, max_member_bytes=MAX_MEMBER_BYTES):
    """Le e confere o inf_mensal_fiagro_AAAAMM.zip do disco, sem extrair nada."""

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
