"""Extração determinística (regex, sem IA) de valores cadastrais do texto de um Termo de Securitização.

Só para triagem: os valores aqui são *candidatos*, nunca parâmetros aprovados, e não alimentam alerta
contratual. Cada valor guarda a página e o trecho de onde saiu.
Campos: data de emissão, datas de vencimento, valor total da emissão, quantidade de títulos, valor nominal unitário.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MONTHS = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
          "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
DATE = r"(\d{1,2})\s*(?:º|o)?\s+de\s+([a-zç]+)\s+de\s+(\d{4})|(\d{2})/(\d{2})/(\d{4})"
MONEY = r"r\$\s*([\d.]{1,20},\d{2})"

PATTERNS = {
    "data_emissao": [rf"data de emiss[aã]o(?: dos (?:cra|cri))?\W{{0,4}}(?:[^.;\d]{{0,60}}?)(?:{DATE})",
                     rf"data de emiss[aã]o(?: dos (?:cra|cri))?[^.;]{{0,120}}?(?:{DATE})"],
    "data_vencimento": [rf"vencendo(?:-se)?,?\s+(?:portanto,?\s+)?em\s+(?:{DATE})",
                        rf"data de vencimento(?: final)?(?: dos (?:cra|cri))?[^.;]{{0,160}}?(?:{DATE})"],
    "valor_total": [rf"valor total da (?:emiss[aã]o|oferta)[^.;]{{0,120}}?{MONEY}",
                    rf"valor global(?: dos (?:cra|cri))?[^.;]{{0,80}}?{MONEY}"],
    "quantidade": [r"(?:compreende|ser[aã]o emitidos|emiss[aã]o de|quantidade de (?:cra|cri)[^\d]{0,60}?)\s*([\d.]{3,15})\s*\(",
                   r"\b([\d.]{3,15})\s*\([^)]{3,80}\)\s*(?:cra|cri|certificados)\b"],
    "valor_nominal_unitario": [rf"valor nominal unit[aá]rio[^.;]{{0,80}}?{MONEY}"],
}


LASTRO_WORDS = re.compile(r"deb[eê]ntures?|notas? comerciais|nota comercial|\bccbs?\b|c[eé]dulas? de cr[eé]dito|\bcdcas?\b|\bcpr(?:-f)?s?\b|\bccis?\b")
SECURITY_WORDS = re.compile(r"\bcra\b|\bcri\b|certificados de receb[ií]veis")


def is_lastro_context(text_before: str) -> bool:
    """A data de vencimento fala do lastro (debênture, nota comercial, CCB, CDCA, CPR, CCI) e não do CRA/CRI
    quando a palavra do lastro aparece depois da última menção a CRA/CRI no trecho anterior."""

    lastro = [m.end() for m in LASTRO_WORDS.finditer(text_before)]
    security = [m.end() for m in SECURITY_WORDS.finditer(text_before)]
    return bool(lastro) and (not security or lastro[-1] > security[-1])


@dataclass(frozen=True)
class Candidate:
    field: str
    value: str
    page: int
    excerpt: str
    strength: int = 0  # 0 = padrão principal do campo; 1 = padrão alternativo, mais solto


def _date(groups: tuple[str | None, ...]) -> str | None:
    day, month_name, year, d2, m2, y2 = groups[-6:]
    try:
        if day:
            month = MONTHS.get(unicodedata.normalize("NFKD", month_name).encode("ascii", "ignore").decode())
            if not month:
                return None
            return f"{int(year):04d}-{month:02d}-{int(day):02d}"
        if d2:
            return f"{int(y2):04d}-{int(m2):02d}-{int(d2):02d}"
    except ValueError:
        return None
    return None


def _money(text: str) -> str | None:
    try:
        return format(Decimal(text.replace(".", "").replace(",", ".")), "f")
    except InvalidOperation:
        return None


def _integer(text: str) -> str | None:
    digits = text.replace(".", "")
    return digits if digits.isdigit() and int(digits) > 0 else None


def extract(pages: list[tuple[int, str]]) -> list[Candidate]:
    found: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for number, text in pages:
        flat = re.sub(r"\s+", " ", text)
        lower = flat.lower()
        for field, patterns in PATTERNS.items():
            for strength, pattern in enumerate(patterns):
                for match in re.finditer(pattern, lower):
                    if field in ("data_emissao", "data_vencimento"):
                        value = _date(match.groups())
                    elif field in ("valor_total", "valor_nominal_unitario"):
                        value = _money(match.group(1))
                    else:
                        value = _integer(match.group(1))
                    if value is None:
                        continue
                    kept_field = field
                    if field == "data_vencimento" and is_lastro_context(lower[max(0, match.start() - 250):match.start()]):
                        kept_field = "data_vencimento_lastro"
                    if (kept_field, value) in seen:
                        continue
                    seen.add((kept_field, value))
                    start = max(0, match.start() - 40)
                    found.append(Candidate(kept_field, value, number, flat[start:match.end() + 20].strip(), strength))
    return found


def by_field(candidates: list[Candidate]) -> dict[str, list[Candidate]]:
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.field, []).append(candidate)
    return grouped


def best(candidates: list[Candidate], field: str) -> list[Candidate]:
    """Candidatos que valem para comparação:
    - data de emissão: só a primeira ocorrência do Termo (as seguintes costumam ser outras datas da mesma frase);
    - demais campos: os do padrão principal, se houver; senão, os do padrão alternativo."""

    items = [c for c in candidates if c.field == field]
    if not items:
        return []
    if field == "data_emissao":
        return [min(items, key=lambda c: c.page)]
    strongest = min(c.strength for c in items)
    chosen = [c for c in items if c.strength == strongest]
    if field == "data_vencimento" and strongest > 0:
        # padrão solto: só a primeira página em que aparece (o resto costuma ser anexo de outro título)
        first_page = min(c.page for c in chosen)
        chosen = [c for c in chosen if c.page == first_page]
    return chosen


REMUNERATION_ANCHOR = re.compile(r"juros remunerat[oó]rios|remunera[cç][aã]o (?:dos (?:cra|cri)|da (?:\d+ª )?s[eé]rie)|"
                                 r"far[aã]o jus a|sobretaxa|spread")


def remuneration_numbers(pages: list[tuple[int, str]], window: int = 360) -> set[str]:
    """Números de taxa (multiplicador do índice e taxa/spread) citados perto das cláusulas de remuneração.

    Usa o leitor por fichas de credit_assets.cross_checks e arredonda em 2 casas. Serve para checar se a taxa
    informada à CVM aparece no Termo; não reconstrói a remuneração série a série."""

    from decimal import Decimal as _D

    from credit_assets.cross_checks import tokenize

    numbers: set[str] = set()
    for _, text in pages:
        flat = re.sub(r"\s+", " ", text)
        lower = flat.lower()
        for match in REMUNERATION_ANCHOR.finditer(lower):
            chunk = lower[match.start(): match.start() + window]
            for token in tokenize(chunk, "remuneracao"):
                slot, _, value = token.partition("=")
                if slot in ("mult", "taxa"):
                    numbers.add(f"{slot}={format(round(_D(value), 2).normalize(), 'f')}")
    return numbers


CNPJ_TEXT = re.compile(r"\d{2}\.?\d{3}\.?\d{3}\s*/\s*\d{4}\s*-?\s*\d{2}")
DEBTOR_ANCHOR = re.compile(r"devedor[ae]?s?\b|cedentes?\b|emitente\b|avalistas?\b|fiador[ae]?s?\b")


def debtor_cnpjs(pages: list[tuple[int, str]], window: int = 600) -> set[str]:
    """CNPJs válidos citados logo depois de uma menção a devedor, cedente, emitente, avalista ou fiador."""

    from credit_assets.debtor_exposure import normalize_cnpj

    found: set[str] = set()
    # o documento inteiro de uma vez: a definição de "Devedora" muitas vezes termina na página seguinte
    for text in [" ".join(t for _, t in pages)]:
        flat = re.sub(r"\s+", " ", text)
        lower = flat.lower()
        for anchor in DEBTOR_ANCHOR.finditer(lower):
            chunk = flat[anchor.start(): anchor.start() + window]
            for raw in CNPJ_TEXT.findall(chunk):
                cnpj = normalize_cnpj(raw)
                if cnpj:
                    found.add(cnpj)
    return found
