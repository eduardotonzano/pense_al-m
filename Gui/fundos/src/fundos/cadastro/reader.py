"""Leitura do cadastro de fundos da CVM (registro_fundo_classe.zip), sem banco.

O ZIP e lido inteiro em memoria; nada e extraido em disco. Cada CSV e
decodificado em cp1252 estrito, e o cabecalho tem de ser exatamente o de
columns.py (mesmos nomes, mesma ordem). Os valores sao normalizados: CNPJ sem
mascara e com os zeros a esquerda restaurados, S/N para booleano, data
AAAA-MM-DD e decimal exato como texto.

Dados pessoais (docs/decisoes-em-aberto.md, decisao 3 de Fundos): o CPF e o
nome do gestor pessoa fisica sao descartados aqui, antes de qualquer
repositorio, e so contados. O nome de um papel so fica quando o
identificador do papel e um CNPJ valido. A coluna Diretor e exigida no
cabecalho e descartada sem ser guardada nem contada.

Valor fora do formato numa coluna de data, numero ou S/N falha a leitura
quando a linha e do escopo (FIDC ou FIAGRO). Fora do escopo, o valor e
descartado e contado por coluna. As mensagens citam arquivo, linha e coluna,
nunca o valor.
"""

import csv
import hashlib
import io
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from fundos.cadastro import columns as spec
from fundos.cnpj import InvalidCnpjError
from fundos.cnpj import looks_like_cpf
from fundos.cnpj import normalize_cnpj
from fundos.database import normalize_iso_date
from fundos.repositories.observation_repository import canonical_decimal


ENCODING = "cp1252"
DELIMITER = ";"
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 200 * 1024 * 1024

# Rotulo das linhas fora do escopo nas contagens.
OUT_OF_SCOPE = "outros"

# Situacao do identificador de uma linha.
EMPTY = "vazio"
CNPJ = "cnpj"
CPF = "cpf"
INVALID = "invalido"
IDENTIFIER_STATUSES = (EMPTY, CNPJ, CPF, INVALID)


class CadastroFormatError(ValueError):
    """O arquivo nao tem o formato esperado; nada foi lido."""


@dataclass(frozen=True)
class ZipManifest:
    """Manifesto do ZIP: nome, tamanho, SHA-256 e datas dos membros."""

    file_name: str
    size_bytes: int
    sha256: str
    member_dates: tuple[str, ...]


@dataclass(frozen=True)
class MemberManifest:
    """Manifesto de um CSV do ZIP (tamanho descomprimido, linhas de dados)."""

    file_name: str
    size_bytes: int
    sha256: str
    line_count: int
    column_count: int


@dataclass(frozen=True)
class PartyValue:
    """Um papel de uma linha. So existe com CNPJ valido."""

    role: str
    field_name: str
    cnpj: str
    name_field_name: str | None
    name: str | None


@dataclass(frozen=True)
class CadastroRow:
    """Uma linha normalizada de registro_fundo ou registro_classe.

    scope e FIDC, FIAGRO ou None. Fora do escopo, values so tem as colunas
    da escolha do registro vigente, e parties fica vazio. invalid_columns
    lista as colunas descartadas por formato (so fora do escopo).
    """

    table: str
    line: int
    scope: str | None
    cnpj: str | None
    values: MappingProxyType
    parties: tuple[PartyValue, ...]
    invalid_columns: frozenset[str]


@dataclass(frozen=True)
class CadastroFile:
    """O ZIP lido: manifestos, linhas normalizadas e contagens."""

    zip: ZipManifest
    members: tuple[MemberManifest, ...]
    fund_rows: tuple[CadastroRow, ...]
    class_rows: tuple[CadastroRow, ...]
    counts: Counter
    max_registration_date: str | None

    def member(self, table):
        """Manifesto do CSV da tabela."""

        name = table + ".csv"

        for member in self.members:
            if member.file_name == name:
                return member

        raise KeyError(name)


def classify_identifier(value):
    """Devolve (situacao, CNPJ normalizado ou None).

    11 digitos ou CPF com mascara e CPF: o valor e descartado. CNPJ com 12 ou
    13 digitos ganha os zeros a esquerda; nunca um valor de 11 digitos.
    """

    if not value.strip():
        return EMPTY, None

    if looks_like_cpf(value):
        return CPF, None

    try:
        return CNPJ, normalize_cnpj(value, allow_missing_leading_zeros=True)
    except InvalidCnpjError:
        return INVALID, None


def convert(kind, value):
    """Converte o texto do CSV para o tipo da coluna; vazio vira None.

    O texto fica como veio. Levanta ValueError se o valor estiver fora do
    formato do tipo.
    """

    if not value.strip():
        return None

    if kind == spec.TEXT:
        return value

    if kind == spec.DATE:
        return normalize_iso_date(value, "A data")

    if kind == spec.NUMERIC:
        return canonical_decimal(value)

    if kind == spec.BOOLEAN:
        flag = spec.YES_NO.get(value.strip())

        if flag is None:
            raise ValueError("Valor fora de S/N.")

        return flag

    raise ValueError("Tipo de coluna sem conversao.")


def _location(member, line, column):
    return member + ", linha " + str(line) + ", coluna " + column


def _check_header(member, header, expected):
    """Exige exatamente as colunas esperadas, na mesma ordem.

    A mensagem so cita nomes da lista esperada: se o arquivo vier sem
    cabecalho, a primeira linha seria dado.
    """

    if header is None:
        raise CadastroFormatError(member + " esta vazio: falta o cabecalho.")

    if list(header) == list(expected):
        return

    missing = [column for column in expected if column not in header]
    unknown = [column for column in header if column not in expected]
    problems = []

    if missing:
        problems.append("faltam " + ", ".join(missing))

    if unknown:
        problems.append(str(len(unknown)) + " coluna(s) desconhecida(s)")

    if len(header) != len(set(header)):
        problems.append("ha coluna repetida")

    if not problems:
        position = next(
            index
            for index, (found, wanted) in enumerate(zip(header, expected))
            if found != wanted
        )
        problems.append(
            "colunas fora de ordem: a posicao "
            + str(position + 1)
            + " deveria ser "
            + expected[position]
        )

    raise CadastroFormatError(
        "Cabecalho de "
        + member
        + " diferente do esperado ("
        + "; ".join(problems)
        + "). A CVM pode ter mudado o arquivo; nada foi lido."
    )


def _decode(member, data):
    try:
        return data.decode(ENCODING)
    except UnicodeDecodeError as error:
        raise CadastroFormatError(
            member
            + " nao decodifica como "
            + ENCODING
            + " (byte na posicao "
            + str(error.start)
            + ")."
        ) from error


def _iter_csv(member, text, expected):
    """Confere o cabecalho e devolve (linha, campos) de cada linha de dados."""

    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=DELIMITER,
        quoting=csv.QUOTE_NONE,
    )
    _check_header(member, next(reader, None), expected)

    for line, fields in enumerate(reader, start=2):
        if len(fields) != len(expected):
            raise CadastroFormatError(
                member
                + ", linha "
                + str(line)
                + ": "
                + str(len(fields))
                + " campo(s), o cabecalho tem "
                + str(len(expected))
                + "."
            )

        yield line, fields


def _parse_parties(table, record, scope_key, keep, counts):
    """Papeis da linha; descarta CPF, CNPJ invalido e gestor pessoa fisica."""

    natural_person = (
        spec.PERSON_TYPE_COLUMN in record
        and record[spec.PERSON_TYPE_COLUMN].strip() == spec.NATURAL_PERSON
    )

    if natural_person:
        counts[
            ("pf", spec.field_name(table, spec.PERSON_TYPE_COLUMN), scope_key)
        ] += 1

    parties = []

    for role, id_column, name_column in spec.PARTIES[table]:
        id_field = spec.field_name(table, id_column)
        name_field = spec.field_name(table, name_column)
        status, cnpj = classify_identifier(record[id_column])
        counts[("identificador", id_field, status, scope_key)] += 1
        name = record[name_column] if record[name_column].strip() else None
        discarded_as_person = natural_person and role == spec.PERSON_TYPE_ROLE

        if discarded_as_person and status == CNPJ:
            counts[("pf_cnpj", id_field, scope_key)] += 1

        if status != CNPJ or discarded_as_person:
            if name is not None:
                counts[("nome_descartado", name_field, scope_key)] += 1

            continue

        if keep:
            parties.append(
                PartyValue(
                    role=role,
                    field_name=id_field,
                    cnpj=cnpj,
                    name_field_name=None if name is None else name_field,
                    name=name,
                )
            )

    return tuple(parties)


def _parse_row(table, member, line, fields, counts):
    record = dict(zip(spec.HEADERS[table], fields))
    scope = spec.SCOPE[table].get(record[spec.TYPE_COLUMN[table]].strip())
    scope_key = scope or OUT_OF_SCOPE
    counts[("linhas_por_tipo", table, scope_key)] += 1

    identity_field = spec.field_name(table, spec.IDENTITY_COLUMN[table])
    status, cnpj = classify_identifier(record[spec.IDENTITY_COLUMN[table]])
    counts[("identificador", identity_field, status, scope_key)] += 1

    keep = None if scope is not None else spec.SELECTION_COLUMNS[table]
    values = {}
    invalid = set()

    for column, kind in spec.COLUMNS[table]:
        if kind not in spec.VALUE_KINDS:
            continue

        try:
            value = convert(kind, record[column])
        except ValueError as error:
            if scope is not None:
                raise CadastroFormatError(
                    _location(member, line, column)
                    + ": valor fora do formato "
                    + kind
                    + "."
                ) from error

            counts[("fora_do_formato", spec.field_name(table, column), scope_key)] += 1
            invalid.add(column)
            continue

        if value is None or (keep is not None and column not in keep):
            continue

        values[column] = value

    parties = _parse_parties(table, record, scope_key, scope is not None, counts)

    return CadastroRow(
        table=table,
        line=line,
        scope=scope,
        cnpj=cnpj,
        values=MappingProxyType(values),
        parties=parties,
        invalid_columns=frozenset(invalid),
    )


def _member_manifest(member, data, line_count, column_count):
    return MemberManifest(
        file_name=member,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        line_count=line_count,
        column_count=column_count,
    )


def _check_members(archive, max_member_bytes):
    infos = archive.infolist()
    names = [info.filename for info in infos]
    missing = [name for name in spec.MEMBERS if name not in names]
    unexpected = len([name for name in names if name not in spec.MEMBERS])

    if missing or unexpected or len(names) != len(set(names)):
        problems = []

        if missing:
            problems.append("faltam " + ", ".join(missing))

        if unexpected:
            problems.append(str(unexpected) + " membro(s) inesperado(s)")

        if len(names) != len(set(names)):
            problems.append("ha membro repetido")

        raise CadastroFormatError(
            "O ZIP nao tem exatamente "
            + ", ".join(spec.MEMBERS)
            + " ("
            + "; ".join(problems)
            + "). Nada foi lido."
        )

    for info in infos:
        if info.file_size > max_member_bytes:
            raise CadastroFormatError(
                info.filename
                + " passa do limite de "
                + str(max_member_bytes)
                + " bytes descomprimidos."
            )

    return {info.filename: info for info in infos}


def read_cadastro_bytes(data, file_name, *, max_member_bytes=MAX_MEMBER_BYTES):
    """Le o ZIP ja carregado em memoria; devolve CadastroFile."""

    zip_hash = hashlib.sha256(data).hexdigest()

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise CadastroFormatError(
            file_name + " nao e um ZIP valido."
        ) from error

    counts = Counter()
    members = []
    rows = {}

    with archive:
        infos = _check_members(archive, max_member_bytes)
        member_dates = tuple(
            sorted(
                {
                    "%04d-%02d-%02d" % infos[name].date_time[:3]
                    for name in spec.MEMBERS
                }
            )
        )

        for table in (spec.FUND_TABLE, spec.CLASS_TABLE, spec.SUBCLASS_TABLE):
            member = table + ".csv"
            raw = archive.read(infos[member])

            if len(raw) > max_member_bytes:
                raise CadastroFormatError(
                    member
                    + " passa do limite de "
                    + str(max_member_bytes)
                    + " bytes descomprimidos."
                )

            text = _decode(member, raw)
            expected = spec.HEADERS[table]
            parsed = []
            line_count = 0

            for line, fields in _iter_csv(member, text, expected):
                line_count += 1

                if table != spec.SUBCLASS_TABLE:
                    parsed.append(_parse_row(table, member, line, fields, counts))

            del text
            members.append(_member_manifest(member, raw, line_count, len(expected)))
            rows[table] = tuple(parsed)

    registration_dates = [
        row.values["Data_Registro"]
        for table in (spec.FUND_TABLE, spec.CLASS_TABLE)
        for row in rows[table]
        if "Data_Registro" in row.values
    ]

    return CadastroFile(
        zip=ZipManifest(
            file_name=file_name,
            size_bytes=len(data),
            sha256=zip_hash,
            member_dates=member_dates,
        ),
        members=tuple(members),
        fund_rows=rows[spec.FUND_TABLE],
        class_rows=rows[spec.CLASS_TABLE],
        counts=counts,
        max_registration_date=max(registration_dates, default=None),
    )


def read_cadastro_zip(path, *, max_member_bytes=MAX_MEMBER_BYTES):
    """Le o registro_fundo_classe.zip do disco, sem extrair nada."""

    zip_path = Path(path)

    if not zip_path.is_file():
        raise FileNotFoundError("ZIP nao encontrado: " + str(zip_path))

    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise CadastroFormatError(
            zip_path.name
            + " passa do limite de "
            + str(MAX_ZIP_BYTES)
            + " bytes."
        )

    return read_cadastro_bytes(
        zip_path.read_bytes(),
        zip_path.name,
        max_member_bytes=max_member_bytes,
    )
