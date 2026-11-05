"""Ficha contratual: o trecho literal de cada campo padrão nos Termos e aditamentos de um ativo (só leitura).

Para cada campo escolhe até dois trechos: a **definição** (termo entre aspas seguido de dois-pontos, "significa"
ou "tem o significado") do documento mais recente que a traz, e a **cláusula**: a página do corpo do documento com
mais menções do campo, estendida às páginas vizinhas que também o mencionam (até 6). Páginas de índice ficam de fora
e anexos (a partir da primeira página que abre com "ANEXO I", "ANEXO A"...) só entram se o corpo não mencionar o
campo; os demais anexos aparecem à parte. Só localiza e transcreve: o valor de um campo só vale depois de aprovado
por revisão humana.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

OPENING_QUOTE = re.compile(r"[“\"][^”\"\n]{0,60}$")
DEFINITION_TAIL = re.compile(
    r"^[^”\"\n]{0,60}[”\"]\s*(?:[:\-–—]|,?\s*(?:significa|tem o significado|ter[áa]o? o significado|corresponde|refere-se))",
    re.IGNORECASE)
TOC_LINE = re.compile(r"(\.{4,}|…{2,}|_{4,})\s*\d+\s*$")
ANNEX_TITLE = re.compile(r"^ANEXO\s+(?:[IVXLC]+|[A-Z]|\d+)\b")
# aditamento que traz o Termo consolidado como "ANEXO D": é o texto vigente, não um anexo (já em ``fold``)
CONSOLIDATED_WORD = re.compile(r"consolida")
CONSOLIDATED_TITLE = re.compile(r"^(?:termo de secur?t?izacao|\w+ aditamento ao termo)")
UPDATED_ANNEX = re.compile(r"redacao atualizada do anexo")
# página de glossário: termos entre aspas no começo da linha e "significa"/"tem o significado" (uma ou duas colunas)
DEFINITION_START = re.compile(r"^(?:significa|tem o significado|possui o significado|terao? o significado|tem os significados|"
                              r"correspondem?|refere-se)")
GLOSSARY_MIN = 4
COLUMN_GAP = re.compile(r" {3,}")
# item rotulado: enumeração no começo da linha, o termo logo depois e pontuação em seguida
LABEL_START = re.compile(r"^\s*(?:\(?[ivxlc]{1,6}\)|\(?[a-z]\)|\d+(?:\.\d+)*\.?|[-•])\s+", re.IGNORECASE)
LABEL_TAIL = re.compile(r"^[^.:;—–\n]{0,60}?\s*[.:—–]")
EXCERPT_CHARS = 420
MAX_RANGE = 6


@dataclass(frozen=True)
class Excerpt:
    document: str
    page: int
    line: int
    text: str
    ocr: bool
    kind: str  # "definicao" | "clausula"
    first_page: int = 0  # intervalo de páginas da cláusula; o texto é da página ``page``
    last_page: int = 0

    @property
    def pages(self) -> tuple[int, int]:
        return min(self.page, self.first_page or self.page), max(self.page, self.last_page)


@dataclass(frozen=True)
class FieldResult:
    excerpts: tuple[Excerpt, ...]
    other_pages: tuple[tuple[str, int], ...]
    annex_pages: tuple[tuple[str, int], ...]
    total_pages: int


MONTHS = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).lower().split())


def _thousands(digits: str) -> str:
    return f"{int(digits):,}".replace(",", ".")


def value_variants(value: str, unit: str | None = None) -> list[str]:
    """Como um valor aprovado aparece escrito num Termo (já em ``fold``). Vazio quando o valor é genérico demais
    para conferir no texto (texto livre, sim/não, números pequenos como prazos em dias)."""

    value, unit = (value or "").strip(), fold(unit or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        year, month, day = value.split("-")
        written = f" de {MONTHS[int(month) - 1]} de {year}"
        variants = [f"{day}/{month}/{year}", f"{int(day)}{written}", f"{day}{written}"]
        if int(day) == 1:
            variants.append(f"1o{written}")  # "1º de março", já sem acento
        return list(dict.fromkeys(variants))
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        return []
    number = Decimal(value)
    if "fracao" in unit:
        percent = number * 100
        whole = format(percent.normalize(), "f")
        if "." in whole:
            integer, decimals = whole.split(".")
            variants = [f"{integer},{decimals}%", f"{integer},{decimals.ljust(2, '0')}%"]
        else:
            variants = [f"{whole}%", f"{whole},00%", f"{whole},0%"]
        return [fold(v) for v in dict.fromkeys(variants)]
    if "brl" in unit:
        integer, _, cents = format(number.quantize(Decimal("0.01")), "f").partition(".")
        return [f"{_thousands(integer)},{cents}", f"r$ {_thousands(integer)}"]
    if number == number.to_integral_value() and number >= 1000:
        return [_thousands(str(int(number)))]
    return []


def is_toc_page(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return sum(1 for line in lines if TOC_LINE.search(line)) >= 5


def annex_pages(pages: list[tuple[int, str, bool]]) -> set[int]:
    """Páginas de anexo: a partir de cada página (depois da 3ª) que abre com o título de um anexo.

    Anexo que é o Termo consolidado (aditamentos: "ANEXO D – TERMO DE SECURITIZAÇÃO CONSOLIDADO") volta a ser corpo,
    até o próximo título de anexo (os anexos do próprio Termo consolidado)."""

    inside, found = False, set()
    for number, text, _ in pages:
        top = [line.strip() for line in text.splitlines() if line.strip() and "docusign" not in line.lower()][:5]
        if number > 3 and any(ANNEX_TITLE.match(line) for line in top[:2]):
            folded = [fold(line) for line in top]
            heading = " ".join(folded)
            consolidated = (CONSOLIDATED_WORD.search(heading) or any(CONSOLIDATED_TITLE.match(line) for line in folded))
            inside = not (consolidated and not UPDATED_ANNEX.search(heading))
        if inside:
            found.add(number)
    return found


def annex_start(pages: list[tuple[int, str, bool]]) -> int | None:
    found = annex_pages(pages)
    return min(found) if found else None


def is_glossary_page(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    quoted = sum(1 for line in lines if line[:1] in ("“", '"'))
    meanings = sum(1 for line in lines
                   if DEFINITION_START.match(fold(COLUMN_GAP.split(line, 1)[-1])) or "significa" in fold(line)[:120])
    return quoted >= GLOSSARY_MIN and meanings >= GLOSSARY_MIN - 1


def two_column_definition(text: str, line_index: int, match_start: int, limit: int = EXCERPT_CHARS) -> str | None:
    """Definição numa tabela de duas colunas (termo à esquerda, significado à direita), que o pdftotext desalinha na
    vertical: o n-ésimo termo da página corresponde ao n-ésimo início de significado. Sem duas colunas ou com contagens
    diferentes, devolve None."""

    lines = text.splitlines()
    # fronteira das colunas: onde a coluna da direita mais começa na página
    positions = Counter()
    for row in lines:
        gap = COLUMN_GAP.search(row, len(row) - len(row.lstrip()) + 1) if row.strip() else None
        if gap and gap.end() < len(row) and gap.start() <= 45:
            positions[gap.end()] += 1
    if not positions:
        return None
    boundary, votes = positions.most_common(1)[0]
    if votes < 3 or match_start >= boundary:
        return None

    def split(row: str) -> tuple[str, str]:
        """(coluna da esquerda, coluna da direita): corta no espaço em branco mais perto da fronteira."""

        for gap in re.finditer(r" {2,}", row):
            if boundary - 4 <= gap.end() <= boundary + 4 and gap.end() < len(row):
                return row[:gap.start()].strip(), row[gap.end():].strip()
        if not row[:max(0, boundary - 3)].strip():
            return "", row.strip()
        return row.strip(), ""

    def left(row: str) -> str:
        return split(row)[0]

    def right(row: str) -> str:
        return split(row)[1]

    terms = [i for i, row in enumerate(lines) if left(row)[:1] in ("“", '"')]
    starts = [i for i, row in enumerate(lines) if DEFINITION_START.match(fold(right(row)))]
    if terms and starts and len(starts) == len(terms) + 1 and starts[0] < terms[0]:
        starts = starts[1:]  # o primeiro significado é do último termo da página anterior
    if terms and len(terms) == len(starts) + 1 and (not starts or starts[-1] < terms[-1]):
        terms = terms[:-1]  # o significado do último termo começa na página seguinte
    if line_index not in terms or len(terms) != len(starts):
        return None
    k = terms.index(line_index)
    end = starts[k + 1] if k + 1 < len(starts) else len(lines)
    term_rows = terms[k + 1] if k + 1 < len(terms) else len(lines)
    term = " ".join(left(row) for row in lines[line_index:term_rows] if left(row))
    meaning = " ".join(" ".join(right(row).split()) for row in lines[starts[k]:end] if right(row))
    joined = f"{' '.join(term.split())}: {meaning}"
    return joined if len(joined) <= limit else joined[: limit - 1].rstrip() + "…"


def is_definition(line: str, start: int, end: int) -> bool:
    matched = line[start:end]
    opened = matched[:1] in ("“", '"') or OPENING_QUOTE.search(line[:start]) is not None
    rest = line[end:] if matched[-1:] not in ("”", '"') else '"' + line[end:]
    return opened and DEFINITION_TAIL.match(rest) is not None


def excerpt_at(text: str, line_index: int, before: int = 1, after: int = 6, limit: int = EXCERPT_CHARS) -> str:
    lines = text.splitlines()
    chosen = lines[max(0, line_index - before): line_index + after + 1]
    joined = " ".join(" ".join(line.split()) for line in chosen if line.strip())
    return joined if len(joined) <= limit else joined[: limit - 1].rstrip() + "…"


def is_label(line: str, start: int, end: int) -> bool:
    """Item rotulado de uma lista de características: "(xvi) Prazo e Data de Vencimento —", "4.1.3 Quantidade de CRI."."""

    head = line[:start]
    enumerator = LABEL_START.match(head)
    if not enumerator or len(head) - enumerator.end() > 50:
        return False
    return LABEL_TAIL.match(line[end:]) is not None


def _page_hits(text: str, patterns: list[re.Pattern]) -> tuple[int, int | None, tuple[int, int] | None, int | None]:
    """(menções, linha da primeira menção, (linha, coluna) da primeira definição, linha do primeiro item rotulado)."""

    count, first, definition, label = 0, None, None, None
    for index, line in enumerate(text.splitlines()):
        for pattern in patterns:
            for match in pattern.finditer(line):
                count += 1
                first = index if first is None else first
                if definition is None and is_definition(line, match.start(), match.end()):
                    definition = (index, match.start())
                if label is None and is_label(line, match.start(), match.end()):
                    label = index
    return count, first, definition, label


@dataclass(frozen=True)
class _Hit:
    order: int
    document: str
    page: int
    text: str
    ocr: bool
    count: int
    first: int
    definition: tuple[int, int] | None
    label: int | None
    toc: bool
    annex: bool
    glossary: bool


def field_excerpts(
    documents: Iterable[tuple[str, list[tuple[int, str, bool]]]], patterns: list[re.Pattern], max_refs: int = 8,
) -> FieldResult:
    """``documents``: (id do documento, [(página, texto, veio_do_ocr)]), do mais antigo para o mais novo."""

    hits: list[_Hit] = []
    for order, (doc_id, pages) in enumerate(documents):
        annexes = annex_pages(pages)
        for number, text, ocr in pages:
            count, first, definition, label = _page_hits(text, patterns)
            if count:
                hits.append(_Hit(order, doc_id, number, text, ocr, count, first, definition, label, is_toc_page(text),
                                 number in annexes, is_glossary_page(text)))
    if not hits:
        return FieldResult((), (), (), 0)
    chosen: list[Excerpt] = []
    definitions = [h for h in hits if h.definition is not None and not h.toc]
    definitions = [h for h in definitions if not h.annex] or definitions
    if definitions:
        latest = max(h.order for h in definitions)
        h = min((h for h in definitions if h.order == latest), key=lambda h: h.page)
        line, column = h.definition
        text = two_column_definition(h.text, line, column) or excerpt_at(h.text, line)
        chosen.append(Excerpt(h.document, h.page, line + 1, text, h.ocr, "definicao", h.page, h.page))
    taken = {(e.document, e.page) for e in chosen}
    clauses = [h for h in hits if not h.toc and (h.document, h.page) not in taken]
    clauses = [h for h in clauses if not h.annex] or clauses
    # glossário só traz definições; a cláusula vem do corpo (glossário só se não houver outra página)
    clauses = [h for h in clauses if not h.glossary] or clauses
    if clauses:
        # item rotulado ("(xvi) Prazo e Data de Vencimento —") vence a contagem de menções
        best = max(clauses, key=lambda h: (h.label is not None, h.count, h.order, -h.page))
        pages_with_hits = {h.page for h in clauses
                           if h.document == best.document and h.annex == best.annex and h.glossary == best.glossary}
        low = high = best.page
        while high - low + 1 < MAX_RANGE and (low - 1 in pages_with_hits or high + 1 in pages_with_hits):
            if low - 1 in pages_with_hits:
                low -= 1
            if high - low + 1 < MAX_RANGE and high + 1 in pages_with_hits:
                high += 1
        line = best.label if best.label is not None else best.first
        chosen.append(Excerpt(best.document, best.page, line + 1, excerpt_at(best.text, line), best.ocr,
                              "clausula", low, high))

    def shown(h: _Hit) -> bool:
        return any(e.document == h.document and e.pages[0] <= h.page <= e.pages[1] for e in chosen)

    ordered = sorted(hits, key=lambda h: (h.order, h.page))
    has_body_choice = any(not h.annex for h in hits if shown(h))
    others = [(h.document, h.page) for h in ordered if not shown(h) and not (h.annex and has_body_choice)]
    annexes = [(h.document, h.page) for h in ordered if not shown(h) and h.annex and has_body_choice]
    return FieldResult(tuple(chosen), tuple(others[:max_refs]), tuple(annexes[:max_refs]), len(hits))

