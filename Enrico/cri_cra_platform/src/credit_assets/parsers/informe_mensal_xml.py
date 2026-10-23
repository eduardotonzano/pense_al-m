"""Leitura generica do XML do Informe Mensal de CRA e CRI (S-09).

Nao conhece nenhuma tag do informe: percorre o arquivo e devolve, para cada folha e
cada atributo, o caminho, a ocorrencia, o texto e a forma do texto. O que a ficha
exibe e decisao da S-09. Onde esta o periodo de referencia e como o XML declara a
unidade dependem do arquivo real e ficam fora deste modulo.

O arquivo vem de uma fonte externa: DOCTYPE e ENTITY sao recusados antes do parse, e
o tamanho e a profundidade tem teto.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree

PARSER_VERSION = "informe_mensal_xml/1"
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 100

_DECLARATIONS = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class InformeXmlError(ValueError):
    """O arquivo nao e um XML que este leitor aceite."""


@dataclass(frozen=True)
class XmlValue:
    """Uma folha (ou atributo) do XML.

    ``field`` e o caminho sem indices, estavel entre meses (atributo: ``caminho@nome``).
    ``occurrence`` lista, como ``profundidade:posicao`` separados por virgula, as
    posicoes maiores que 1 entre irmaos de mesmo nome; fica vazia na primeira.
    """

    field: str
    occurrence: str
    value: str | None
    value_kind: str


@dataclass(frozen=True)
class ParsedXml:
    root: str
    namespaces: tuple[str, ...]
    values: tuple[XmlValue, ...]


def classify_value(text: str | None) -> str:
    """empty, number, date ou text, pela forma do texto e nunca pelo nome do campo.

    Number so com digitos ASCII e ponto decimal; date so AAAA-MM-DD valida. Formato
    local (virgula decimal, dd/mm/aaaa) fica text: nada e adivinhado.
    """

    stripped = (text or "").strip()

    if not stripped:
        return "empty"

    if _NUMBER.fullmatch(stripped):
        return "number"

    if _ISO_DATE.fullmatch(stripped):
        try:
            date.fromisoformat(stripped)
        except ValueError:
            return "text"

        return "date"

    return "text"


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _note_namespace(name: str, namespaces: set[str]) -> None:
    if name.startswith("{"):
        namespaces.add(name[1:].split("}", 1)[0])


def _value(field: str, occurrence: str, text: str | None) -> XmlValue:
    stripped = (text or "").strip()
    return XmlValue(field, occurrence, stripped or None, classify_value(stripped))


def _walk(
    element: ElementTree.Element,
    parent_path: str,
    positions: tuple[tuple[int, int], ...],
    depth: int,
    out: list[XmlValue],
    namespaces: set[str],
) -> None:
    if depth > MAX_DEPTH:
        raise InformeXmlError(f"XML com mais de {MAX_DEPTH} niveis de profundidade")

    _note_namespace(element.tag, namespaces)
    field = f"{parent_path}/{_local(element.tag)}"
    occurrence = ",".join(f"{level}:{position}" for level, position in positions)

    for name, raw in element.attrib.items():
        _note_namespace(name, namespaces)
        out.append(_value(f"{field}@{_local(name)}", occurrence, raw))

    children = list(element)
    text = (element.text or "").strip()

    if text or not children:
        out.append(_value(field, occurrence, text))

    seen: Counter[str] = Counter()

    for child in children:
        if (child.tail or "").strip():
            raise InformeXmlError(
                f"Conteudo misto em {field}: ha texto depois de um elemento filho"
            )

        name = _local(child.tag)
        seen[name] += 1
        child_positions = (
            positions + ((depth + 1, seen[name]),) if seen[name] > 1 else positions
        )
        _walk(child, field, child_positions, depth + 1, out, namespaces)


def parse_informe_xml(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> ParsedXml:
    """Todas as folhas e atributos do XML, em ordem de documento.

    O texto sai sem os espacos das pontas e o resto nao e alterado. Levanta
    ``InformeXmlError`` para arquivo grande demais, em UTF-16 ou UTF-32, com DOCTYPE
    ou ENTITY, mal formado, fundo demais ou com texto misto (texto depois de filho).
    """

    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("O XML deve ser entregue como bytes")

    if len(data) > max_bytes:
        raise InformeXmlError(f"Arquivo maior que o limite de {max_bytes} bytes")

    if b"\x00" in data[:64]:
        raise InformeXmlError("Codificacao nao suportada (UTF-16 ou UTF-32)")

    if _DECLARATIONS.search(data):
        raise InformeXmlError("DOCTYPE e ENTITY nao sao aceitos")

    try:
        root = ElementTree.fromstring(bytes(data))
    except (ElementTree.ParseError, ValueError, LookupError) as error:
        raise InformeXmlError(f"XML mal formado: {error}") from error

    values: list[XmlValue] = []
    namespaces: set[str] = set()
    _walk(root, "", (), 1, values, namespaces)
    keys = Counter((item.field, item.occurrence) for item in values)
    repeated = sorted(key for key, total in keys.items() if total > 1)

    if repeated:
        raise InformeXmlError(f"Campo repetido no XML: {repeated[0]}")

    return ParsedXml(_local(root.tag), tuple(sorted(namespaces)), tuple(values))
