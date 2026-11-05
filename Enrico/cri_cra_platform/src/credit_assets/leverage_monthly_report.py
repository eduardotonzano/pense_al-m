"""Leitor do "Relatório Mensal de Acompanhamento" da Leverage (PDF gerado por sistema, texto nativo).

O que é monitorado aparece em dois tipos de bloco, cada um com a situação que a Leverage informa ("Enquadrado",
"Desenquadrado", "Não Apurado"):
  - fundos (reserva, despesa, por empreendimento...): "Saldo Inicial | Rendimento (+) | Resgate (-) | Recomposição (+) |
    Saldo Final | Saldo Mínimo | Situação | R$ | <valores>". Só entram os que têm "Situação"; fundos sem saldo mínimo
    (obra, revolvência, despesas flat) não são monitorados no relatório;
  - índices (LTV, ICSD, subordinação, liquidez de garantias...): "<nome> - <sigla> | Apurado | Mínimo/Máximo | Situação |
    Variáveis para Cálculo: | <variáveis> | . | <apurado> | <referência> | <situação>".
O número de páginas e os blocos variam por emissão. Não há data de verificação por item: vale a competência do
relatório ("Setembro de 2026"). Valores são copiados como estão no relatório, sem conversão.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

PARSER = "leverage_relatorio_mensal 0.1"
FOOTER = re.compile(r"^(CERTIFICADO DE RECEB[IÍ]VEIS|P[áa]gina \d+ de \d+$)", re.IGNORECASE)
SERIES = re.compile(r"^\d+ª$")
CETIP = re.compile(r"^(\d{2}[A-L]\d{7,8}|CR[AI]\w{8})$")
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro")
STATUS = {
    "enquadrado": "atendido", "desenquadrado": "nao_atendido", "nao apurado": "nao_verificado",
    "sem referencia": "nao_se_aplica", "-": "",
}
SITUATION = ("Situação", "Status")
# "Apurado", "IS Mínimo", "RGFM Apurado (Sem Aporte)", "Apurado - Sem Aporte"; nomes com "Mínimo" ("Fluxo Mínimo - FM") não são título
INDEX_HEADER = re.compile(r"^([A-Z0-9]+ )?(Apurado( - .*)?|M[íi]nimo|M[áa]ximo)( \(.*\))?$")
VALUE = re.compile(r"^\(?-?[\d.,]+%?\)?$")
PORTFOLIO = "Saldo Devedor da Carteira - Nominal"
FUND_HEADER = ("Saldo Inicial", "Rendimento (+)", "Resgate (-)", "Recomposição (+)", "Saldo Final")


@dataclass(frozen=True)
class Monitoring:
    grupo_tipo: str  # Fundo | Índice
    grupo: str  # aplicação do fundo ou sigla do índice
    item: str
    valor_referencia: str
    condicao_referencia: str  # Mínimo | Máximo
    valor_apurado: str
    condicao_apurada: str  # situação como está no relatório
    situacao: str  # atendido | nao_atendido | nao_verificado | nao_se_aplica | outro | ""
    data_verificacao: str  # competência MM/AAAA (o relatório não traz data por item)
    proxima_verificacao: str
    pagina: int


@dataclass(frozen=True)
class MonthlyReport:
    competencia: str  # "Setembro/2026", como no relatório da Opea
    competencia_mm_aaaa: str
    series: list[tuple[str, str]]  # (série, código IF)
    saldo_devedor: str
    monitoramentos: list[Monitoring]


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower().strip()


def status(text: str) -> str:
    key = re.sub(r"\s+", " ", _plain(text))
    return STATUS.get(key, "outro" if key else "")


def _condition(header: str) -> str:
    plain = _plain(header)
    return "Mínimo" if "minim" in plain else "Máximo" if "maxim" in plain else header


def _lines(pages_text: list[str]) -> list[tuple[int, str]]:
    """(página, linha) sem linhas vazias e sem o rodapé de cada página."""

    found = []
    for number, text in enumerate(pages_text, start=1):
        for line in text.splitlines():
            line = re.sub(r"\s+", " ", line).strip()  # o PDF usa espaço não separável em alguns títulos
            if line and not FOOTER.match(line):
                found.append((number, line))
    return found


def _funds(lines: list[tuple[int, str]], when: str) -> list[tuple[int, Monitoring]]:
    """(posição da linha "Situação", item) de cada fundo com saldo mínimo. No layout antigo (Power BI) o "R$" vem
    antes dos títulos, que vêm em minúsculas ("Saldo final | Saldo mínimo | Situação")."""

    texts = [t for _, t in lines]
    plain = [_plain(t) for t in texts]
    head = tuple(_plain(t) for t in FUND_HEADER)
    items = []
    for i in range(len(texts)):
        if tuple(plain[i:i + 5]) != head:
            continue
        k = i + 5
        while k < len(texts) and texts[k] != "R$" and not VALUE.match(texts[k]) and k - i < 12:
            k += 1
        headers = plain[i:k]
        if k >= len(texts) or "situacao" not in headers or headers.index("situacao") < 6:
            continue  # fundo sem saldo mínimo nem situação: não é monitorado
        first = k + 1 if texts[k] == "R$" else k
        values = texts[first:first + len(headers)]
        if len(values) < len(headers):
            continue
        cell = dict(zip(headers, values))
        position = i + headers.index("situacao")
        reference = texts[position - 1]
        # nome do fundo e, logo abaixo, a aplicação ("Itaú RF Referenciado DI..."); às vezes sem a aplicação
        before = i - 1 if i and texts[i - 1] == "R$" else i
        if before >= 2 and not texts[before - 1].startswith("Fundo"):
            name, investment = texts[before - 2], texts[before - 1]
        else:
            name, investment = texts[before - 1] if before else "", ""
        items.append((position, Monitoring(
            "Fundo", investment, name, cell[_plain(reference)], _condition(reference), cell["saldo final"],
            cell["situacao"], status(cell["situacao"]), when, "", lines[position][0])))
    return items


def _qualifier(header: str) -> str:
    return re.sub(r"^.*?Apurado\s*", "", header).strip("()- ") or header


def _index_header(text: str) -> bool:
    return text in SITUATION or bool(INDEX_HEADER.search(text))


def _indices(lines: list[tuple[int, str]], when: str, fund_status: set[int]) -> list[tuple[int, Monitoring]]:
    """Cabeçalho do índice em qualquer ordem ("Apurado | Mínimo | Situação", "IS Apurado | IS Mínimo | Situação",
    "RGFM Apurado (Sem Aporte) | RGFM Apurado (Com Aporte) | Situação | RGFM Mínimo"); os valores vêm na mesma
    ordem depois da linha "." que fecha as variáveis de cálculo. Índice repetido por empreendimento leva o nome do
    empreendimento (título do bloco de carteira que o antecede) no grupo."""

    texts = [t for _, t in lines]
    items = []
    for i, text in enumerate(texts):
        if text not in SITUATION or i in fund_status:
            continue
        start = i
        while start > 0 and _index_header(texts[start - 1]) and texts[start - 1] not in SITUATION:
            start -= 1
        end = i + 1
        while end < len(texts) and _index_header(texts[end]) and texts[end] not in SITUATION:
            end += 1
        headers = texts[start:end]
        apurado = [h for h in headers if "apurado" in _plain(h)]
        reference = [h for h in headers if _condition(h) in ("Mínimo", "Máximo")]
        dot = next((j for j in range(end, min(end + 40, len(texts))) if texts[j] == "."), None)
        if start == 0 or not apurado or not reference or dot is None or dot + len(headers) >= len(texts):
            continue
        # no layout antigo (Power BI, coluna "Status") os valores vêm antes do "."
        first = dot - len(headers) if text == "Status" else dot + 1
        cell = dict(zip(headers, texts[first:first + len(headers)]))
        cell["Situação"] = cell[text]
        if len(apurado) == 1:
            measured = cell[apurado[0]]
        else:  # "93% (Sem Aporte); 93% (Com Aporte)"
            measured = "; ".join(f"{cell[h]} ({_qualifier(h)})" for h in apurado)
        name = texts[start - 1]
        title, _, acronym = name.rpartition(" - ")
        project = ""
        if texts.count(name) > 1:
            project = next((texts[j - 1] for j in range(start - 1, 0, -1) if texts[j] == PORTFOLIO), "")
        group = " · ".join(part for part in (acronym if title else "", project) if part)
        items.append((i, Monitoring("Índice", group, title or name, cell[reference[0]], _condition(reference[0]),
                                    measured, cell["Situação"], status(cell["Situação"]), when, "", lines[i][0])))
    return items


def _series(texts: list[str]) -> list[tuple[str, str]]:
    """Séries e códigos IF da tabela de características (página 1); emissão de série única não tem a tabela
    ("Código IF" é um campo das características), e a série fica como "única"."""

    if "Série" not in texts or "Valor Total da Oferta" not in texts:
        stop = texts.index("Pagamento aos Investidores") if "Pagamento aos Investidores" in texts else min(len(texts), 120)
        return [("única", t) for t in texts[:stop] if CETIP.match(t)][:1]
    start, end = texts.index("Série"), texts.index("Valor Total da Oferta")
    width = end - start + 1
    found, k = [], end + 1
    while k + width <= len(texts) and SERIES.match(texts[k]):
        if texts[k + 1] != "-":
            found.append((texts[k], texts[k + 1]))
        k += width
    return found


def _balance(texts: list[str]) -> str:
    """"1ª: 74.972.148,69; 3ª: 75.348.895,75" da tabela de saldo devedor por série."""

    head = ["Saldo Devedor", "Quantidade", "Preço Unitário", "Saldo Devedor"]
    for i in range(len(texts) - 4):
        if texts[i:i + 4] == head:
            if i + 7 < len(texts) and texts[i + 4] == "R$":  # série única
                return texts[i + 7]
            parts, k = [], i + 4
            while k + 4 <= len(texts) and SERIES.match(texts[k]):
                if texts[k + 3] != "-":
                    parts.append(f"{texts[k]}: {texts[k + 3]}")
                k += 4
            return "; ".join(parts)
    return ""


def parse_text(pages_text: list[str]) -> MonthlyReport:
    """``pages_text``: texto de cada página (``page.get_text()``)."""

    lines = _lines(pages_text)
    texts = [t for _, t in lines]
    month = next((re.match(r"^(\w+) de (\d{4})$", t) for t in texts[:5] if re.match(r"^\w+ de \d{4}$", t)), None)
    competencia = when = ""
    if month and month.group(1).lower() in MONTHS:
        competencia = f"{month.group(1)}/{month.group(2)}"
        when = f"{MONTHS.index(month.group(1).lower()) + 1:02d}/{month.group(2)}"
    funds = _funds(lines, when)
    found = sorted(funds + _indices(lines, when, {position for position, _ in funds}), key=lambda pair: pair[0])
    monitoring = [item for _, item in found]
    return MonthlyReport(competencia, when, _series(texts), _balance(texts), monitoring)


def parse_report(path: Path) -> MonthlyReport:
    import pymupdf

    with pymupdf.open(path) as document:
        return parse_text([page.get_text() for page in document])


def as_rows(base: dict, report: MonthlyReport) -> list[dict]:
    head = {**base, "competencia": report.competencia,
            "cetip_no_relatorio": ",".join(code for _, code in report.series),
            "saldo_devedor": report.saldo_devedor, "parser": PARSER}
    if not report.monitoramentos:
        return [{**head, "grupo_tipo": "", "grupo": "", "item": "(sem monitoramentos)", "valor_referencia": "",
                 "condicao_referencia": "", "valor_apurado": "", "condicao_apurada": "", "situacao": "",
                 "data_verificacao": report.competencia_mm_aaaa, "proxima_verificacao": "", "pagina": ""}]
    return [{**head, **asdict(item)} for item in report.monitoramentos]
