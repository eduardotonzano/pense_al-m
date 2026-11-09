"""Leitura comum dos CSV dos dados abertos da CVM, sem banco.

Extraido de fundos.cadastro.reader, sem mudanca de comportamento, para
servir tambem ao informe mensal de FIDC: decodificacao cp1252 estrita,
cabecalho exato (mesmos nomes, mesma ordem), largura das linhas, conversao
por tipo, situacao do identificador (CNPJ ou CPF) e manifesto do membro do
ZIP. As mensagens citam arquivo, linha e coluna, nunca o valor.
"""

import csv
import hashlib
import io
from dataclasses import dataclass

from fundos.cnpj import InvalidCnpjError
from fundos.cnpj import looks_like_cpf
from fundos.cnpj import normalize_cnpj
from fundos.database import normalize_iso_date
from fundos.repositories.observation_repository import canonical_decimal


TEXT = "text"
DATE = "date"
NUMERIC = "numeric"
BOOLEAN = "boolean"

YES_NO = {
    "S": True,
    "N": False,
}

ENCODING = "cp1252"
DELIMITER = ";"
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 200 * 1024 * 1024

# Situacao do identificador de uma linha.
EMPTY = "vazio"
CNPJ = "cnpj"
CPF = "cpf"
INVALID = "invalido"
IDENTIFIER_STATUSES = (EMPTY, CNPJ, CPF, INVALID)


class CvmFormatError(ValueError):
    """O arquivo nao tem o formato esperado; nada foi lido."""


@dataclass(frozen=True)
class MemberManifest:
    """Manifesto de um CSV do ZIP (tamanho descomprimido, linhas de dados)."""

    file_name: str
    size_bytes: int
    sha256: str
    line_count: int
    column_count: int


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

    if kind == TEXT:
        return value

    if kind == DATE:
        return normalize_iso_date(value, "A data")

    if kind == NUMERIC:
        return canonical_decimal(value)

    if kind == BOOLEAN:
        flag = YES_NO.get(value.strip())

        if flag is None:
            raise ValueError("Valor fora de S/N.")

        return flag

    raise ValueError("Tipo de coluna sem conversao.")


def location(member, line, column):
    return member + ", linha " + str(line) + ", coluna " + column


def check_header(member, header, expected):
    """Exige exatamente as colunas esperadas, na mesma ordem.

    A mensagem so cita nomes da lista esperada: se o arquivo vier sem
    cabecalho, a primeira linha seria dado.
    """

    if header is None:
        raise CvmFormatError(member + " esta vazio: falta o cabecalho.")

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

    raise CvmFormatError(
        "Cabecalho de "
        + member
        + " diferente do esperado ("
        + "; ".join(problems)
        + "). A CVM pode ter mudado o arquivo; nada foi lido."
    )


def decode(member, data):
    try:
        return data.decode(ENCODING)
    except UnicodeDecodeError as error:
        raise CvmFormatError(
            member
            + " nao decodifica como "
            + ENCODING
            + " (byte na posicao "
            + str(error.start)
            + ")."
        ) from error


def iter_csv(member, text, expected):
    """Confere o cabecalho e devolve (linha, campos) de cada linha de dados."""

    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=DELIMITER,
        quoting=csv.QUOTE_NONE,
    )
    check_header(member, next(reader, None), expected)

    for line, fields in enumerate(reader, start=2):
        if len(fields) != len(expected):
            raise CvmFormatError(
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


def member_manifest(member, data, line_count, column_count):
    return MemberManifest(
        file_name=member,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        line_count=line_count,
        column_count=column_count,
    )
