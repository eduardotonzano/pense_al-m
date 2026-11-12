"""Garantias e covenants estruturados a partir do texto do Termo de Securitização e dos aditamentos.

Extrator determinístico (regex) para os módulos "Análise de garantias" e "Covenants" da plataforma. Para cada
ativo devolve itens com tipo, situação, valores do trecho, documento, página e trecho literal. É triagem: nada vira
parâmetro aprovado sem revisão humana (o mesmo vale para texto de OCR, que precisa de conferência no PDF).

Garantia: "presente" com duas menções ou mais fora de frase negativa; "citada" com uma; "negada" quando só
aparece em frase negativa ("não contarão com fiança"). Covenant: indicador financeiro com operador e limite
lidos na mesma frase; sem limite legível, o item sai com o trecho e o limite vazio.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

EXTRACTOR = "garantias_covenants 0.1"

GUARANTEE_TYPES: dict[str, tuple[str, str]] = {
    "alienacao_fiduciaria_imovel": ("Alienação fiduciária de imóvel",
                                    r"Aliena[çc][ãa]o Fiduci[áa]ria (?:de |do |dos |da |das )?(?:Im[óo]ve|Fra[çc][ãa]o|Terreno|Unidade)"),
    "alienacao_fiduciaria_participacao": ("Alienação fiduciária de ações ou quotas",
                                          r"Aliena[çc][ãa]o Fiduci[áa]ria (?:de |das |dos )?(?:A[çc][õo]es|Quotas|Cotas|Participa)"),
    "alienacao_fiduciaria_bens": ("Alienação fiduciária de bens móveis",
                                  r"Aliena[çc][ãa]o Fiduci[áa]ria (?:de |das |dos )?(?:Equipamentos|M[áa]quinas|Bens M[óo]veis|Ve[íi]culos|Estoques?|Produtos|Gr[ãa]os|Caf[ée]|Soja|Milho|Gado|Animais)"),
    "cessao_fiduciaria": ("Cessão fiduciária de recebíveis ou direitos",
                          r"Cess[ãa]o Fiduci[áa]ria"),
    "fianca": ("Fiança", r"\bFian[çc]a\b"),
    "aval": ("Aval", r"\bAval(?:istas?)?\b"),
    "hipoteca": ("Hipoteca", r"\bHipoteca\b"),
    "penhor": ("Penhor", r"\bPenhor\b"),
    "coobrigacao": ("Coobrigação", r"\b[Cc]oobriga[çc][ãa]o\b"),
    "garantia_flutuante": ("Garantia flutuante da securitizadora", r"\b[Gg]arantia [Ff]lutuante\b"),
    "fundo_reserva": ("Fundo de reserva", r"\bFundo de Reserva\b"),
    "fundo_liquidez": ("Fundo de liquidez, retenção ou amortização",
                       r"\bFundo de (?:Liquidez|Reten[çc][ãa]o|Amortiza[çc][ãa]o)\b"),
    "fundo_despesas": ("Fundo de despesas", r"\bFundo de Despesas\b"),
    "seguro": ("Seguro garantia ou de crédito", r"\bSeguro[- ](?:Garantia|de Cr[ée]dito)\b"),
}

COVENANT_TYPES: dict[str, tuple[str, str]] = {
    "razao_garantia": ("Razão mínima de garantia / cobertura",
                       r"Raz[ãa]o (?:M[íi]nima )?de Garantia|[ÍI]ndice de Cobertura|Raz[ãa]o de Cobertura"),
    "ltv": ("LTV (saldo / valor da garantia)", r"\bLTV\b|Loan[- ]to[- ]Value"),
    "divida_liquida_ebitda": ("Dívida líquida / EBITDA",
                              r"D[íi]vida (?:Financeira )?L[íi]quida(?: Consolidada)?\s*(?:/|sobre|dividida pelo|e o)\s*(?:o )?EBITDA"),
    "ebitda_despesa_financeira": ("EBITDA / despesa financeira",
                                  r"EBITDA(?: Ajustado)?\s*(?:/|sobre|dividido pel[ao]s?)\s*(?:as |a |o )?(?:Despesas? Financeiras?|Resultado Financeiro)"),
    "liquidez_corrente": ("Liquidez corrente", r"[ÍI]ndice de Liquidez(?: Corrente)?|\bLiquidez Corrente\b"),
    "endividamento_patrimonio": ("Endividamento / patrimônio líquido",
                                 r"(?:D[íi]vida|Endividamento)[^.;]{0,30}(?:/|sobre)\s*(?:o )?Patrim[ôo]nio L[íi]quido"),
}

NEGATION = re.compile(
    r"\bn[ãa]o\s+(?:contar[ãa]o|contar[áa]|conta(?:m)?|haver[áa]|h[áa]|ser[ãa]o\s+constitu[íi]d[ao]s|ser[áa]\s+constitu[íi]d[ao]|"
    r"possui|possuem|contam?|est[ãa]o\s+sujeit[ao]s)\b|\bsem\s+(?:qualquer\s+)?(?:garantia|coobriga)|\bn[ãa]o\s+se\s+aplica",
    re.IGNORECASE,
)
OPERATOR = re.compile(
    r"(n[ãa]o\s+(?:poder[áa]\s+ser\s+|ser[áa]\s+|seja\s+|deve(?:r[áa])?\s+ser\s+)?(?:superior|maior|inferior|menor)"
    r"|igual\s+ou\s+(?:inferior|superior|menor|maior)|(?:inferior|superior|menor|maior)\s+ou\s+igual"
    r"|(?:inferior|superior|menor|maior)(?:\s+(?:a|que|do\s+que))?|(?:no\s+|ao\s+)?m[áa]ximo(?:\s+de)?,?|(?:no\s+|ao\s+)?m[íi]nimo(?:\s+de)?,?"
    r"|pelo\s+menos|≤|≥|<=|>=|<|>)"
    r"\s*(?:a\s+|que\s+|de\s+)?\(?\s*(\d{1,3}(?:[.,]\d+)?)\s*(%|x\b|vezes)?",
    re.IGNORECASE,
)
PERIODICITY = re.compile(r"\b(trimestral(?:mente)?|semestral(?:mente)?|anual(?:mente)?|mensal(?:mente)?)\b", re.IGNORECASE)
MONEY = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")
PERCENT = re.compile(r"\d{1,3}(?:,\d+)?\s?%")


@dataclass(frozen=True)
class Item:
    grupo: str  # garantia | covenant
    item: str
    rotulo: str
    situacao: str  # garantia: presente | citada | negada; covenant: com_limite | sem_limite
    operador: str
    limite: str
    unidade: str
    periodicidade: str
    valores_no_trecho: str
    documento: str
    pagina: int
    ocr: bool
    trecho: str


BOUNDARY = re.compile(r"[.;:](?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ(\"“'(])|[.;](?=\s*\n)")
# rótulo de campo seguido de negação: "Garantia flutuante: não.", "(xiv) Coobrigação da Emissora – Não há", "não existe"
LABEL_NEGATION = re.compile(r"[:–-]\s*n[ãa]o\b|\bn[ãa]o\s+exist|\binexist", re.IGNORECASE)
HEADING = re.compile(r"^\(?[0-9ivxlc.]*\)?\s*[\w\sçãõáéíóúâêô]{0,45}[.:]?$", re.IGNORECASE)
# anexo do Termo com as outras emissões em que o agente fiduciário atua: cita garantias de outras operações
OTHER_ISSUES = re.compile(
    r"Inadimplementos? no per[íi]odo|Valor (?:Total )?da Emiss[ãa]o:|Quantidade de (?:ativos|t[íi]tulos|CR[IA]s?|valores)|"
    r"\bAdimplente\b|\bInadimplente\b|Data de Vencimento:|Esp[ée]cie:|Remunera[çc][ãa]o:|Emissora:",
    re.IGNORECASE,
)
DEFINITION = re.compile(r"tem o significado|significa|ter[áa] o significado", re.IGNORECASE)


STATUS_WORDS = re.compile(r"(?:Adimplente|Inadimplente|Inadimplementos? no per[íi]odo)", re.IGNORECASE)


ISSUE_STATUS = re.compile(r"Adimplente|Inadimplente|Inadimplementos? no per[íi]odo", re.IGNORECASE)


def other_issues_page(text: str) -> bool:
    status = len(ISSUE_STATUS.findall(text))
    return status >= 2 or (status >= 1 and len(OTHER_ISSUES.findall(text)) >= 5)


def _sentence(text: str, start: int, end: int) -> str:
    left = 0
    for found in BOUNDARY.finditer(text, 0, start):
        left = found.end()
    after = BOUNDARY.search(text, end)
    right = after.end() if after else len(text)
    sentence = re.sub(r"\s+", " ", text[left:right]).strip()
    if len(sentence) < 70 and after:  # título de cláusula ("Coobrigação da Emissora.") seguido de "Não há."
        following = BOUNDARY.search(text, right)
        tail = re.sub(r"\s+", " ", text[right:following.end() if following else len(text)]).strip()
        if len(tail) <= 40:
            sentence = f"{sentence} {tail}"
    return sentence


def normalize_operator(raw: str) -> str:
    """"não poderá ser superior a"/"máximo de" → <=; "igual ou superior a"/"mínimo de" → >=; "superior a" → >."""

    low = re.sub(r"\s+", " ", raw.lower()).strip()
    symbols = {"≤": "<=", "<=": "<=", "<": "<", "≥": ">=", ">=": ">=", ">": ">"}
    if low in symbols:
        return symbols[low]
    negated = bool(re.match(r"n[ãa]o", low))
    negated = low.startswith(("não ", "nao "))
    if "máximo" in low or "maximo" in low:
        return "<="
    if "mínimo" in low or "minimo" in low or "pelo menos" in low:
        return ">="
    if "superior" in low or "maior" in low:
        return "<=" if negated else ">=" if "igual" in low else ">"
    if "inferior" in low or "menor" in low:
        return ">=" if negated else "<=" if "igual" in low else "<"
    return ""


def extract(pages: list[tuple[str, int, str, bool]]) -> list[Item]:
    """``pages``: (documento, página, texto, veio_do_ocr), na ordem de leitura (Termo antes dos aditamentos)."""

    items: list[Item] = []
    for key, (label, pattern) in GUARANTEE_TYPES.items():
        regex = re.compile(pattern)
        positive, negative = [], []
        for document, number, text, ocr in pages:
            if other_issues_page(text):
                continue
            for match in regex.finditer(text):
                sentence = _sentence(text, match.start(), match.end())
                if NEGATION.search(sentence) or LABEL_NEGATION.search(sentence):
                    negative.append((document, number, ocr, sentence))
                elif HEADING.match(sentence):  # só o título da cláusula: decide pelo que vem logo depois
                    window = re.sub(r"\s+", " ", text[match.end():match.end() + 250])
                    if NEGATION.search(window) or LABEL_NEGATION.search(window[:40]):
                        negative.append((document, number, ocr, f"{sentence} {window[:160]}"))
                else:
                    positive.append((document, number, ocr, sentence))
        if not positive and not negative:
            continue
        status = "presente" if len(positive) >= 2 else "citada" if positive else "negada"
        substantive = [p for p in positive if not DEFINITION.search(p[3])]
        document, number, ocr, sentence = (substantive or positive or negative)[0]
        values = "; ".join(dict.fromkeys(MONEY.findall(sentence) + PERCENT.findall(sentence)))
        items.append(Item("garantia", key, label, status, "", "", "", "", values[:200], document, number, ocr,
                          sentence[:400]))
    for key, (label, pattern) in COVENANT_TYPES.items():
        regex = re.compile(pattern, re.IGNORECASE if key in ("ltv",) else 0)
        best = None
        for document, number, text, ocr in pages:
            if other_issues_page(text):
                continue
            for match in regex.finditer(text):
                sentence = _sentence(text, match.start(), match.end())
                tail = sentence[sentence.find(match.group(0)) if match.group(0) in sentence else 0:]
                found = OPERATOR.search(tail)
                candidate = (document, number, ocr, sentence, found)
                if found and (best is None or best[4] is None):
                    best = candidate
                    break
                if best is None:
                    best = candidate
            if best and best[4]:
                break
        if best is None:
            continue
        document, number, ocr, sentence, found = best
        operator = normalize_operator(found.group(1)) if found else ""
        limit = found.group(2).replace(",", ".") if found else ""
        unit = (found.group(3) or "").lower().replace("vezes", "x") if found else ""
        period = PERIODICITY.search(sentence)
        others = "; ".join(f"{normalize_operator(m.group(1))} {m.group(2)}{m.group(3) or ''}"
                           for m in list(OPERATOR.finditer(sentence))[:4])
        items.append(Item("covenant", key, label, "com_limite" if found else "sem_limite", operator, limit, unit,
                          period.group(1).lower() if period else "", others[:200], document, number, ocr,
                          sentence[:400]))
    return items


def as_rows(codigo_cetip: str, tipo: str, items: list[Item]) -> list[dict]:
    return [{"codigo_cetip": codigo_cetip, "tipo": tipo, **asdict(item), "extrator": EXTRACTOR, "revisao": "a revisar"}
            for item in items]
