"""Leitor do relatório de acompanhamento da Bari Securitizadora (fundos, índices e "termômetro dos covenants").

A Bari publica o relatório em vários modelos (o "Relatório Mensal de Acompanhamento" em dois painéis e o antigo
"Relatório de Acompanhamento do CRI" em seções A), B)...), todos de uma página. O leitor reconstrói as linhas pela
posição das palavras e lê três formas de quadro:
  - tabela com cabeçalho (Valor atual / Valor mínimo / Status, Saldo atual / Mínimo / Verificação...): uma linha por
    fundo, cada valor na coluna do cabeçalho mais próxima;
  - bloco que termina numa linha "Situação" ou "Status": exigido = linha de mínimo/limite/gatilho, apurado = linha do
    valor (saldo final, índice apurado, atual...); com vários meses lado a lado, só a coluna do mês mais recente;
  - linha com rótulo e situação no fim (termômetro dos covenants, "Situação da cobertura").
No modelo de dois painéis cada painel é lido à parte. Quadro ambíguo (mais de um valor candidato, situação sem
quadro) não vira item: entra em `nao_lidos`. Valores copiados como estão; a situação é a que a Bari informa
(Enquadrado = atendido, Desenquadrado = não atendido, inclusive "Desenquadrado - waiver"), sem dedução.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

PARSER = "bari_relatorio_acompanhamento 1.0"
MONTHS = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
          "Novembro", "Dezembro")
SHORT = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

STATUS = re.compile(r"^(?:enquadrad[oa]|desenquadrad[oa](?:\s*-\s*waiver)?|atendido|n[ãa]o atendido|coberto|descoberto)$", re.I)
STATUS_LABEL = re.compile(r"^(?:[a-z]\s*-\s*)?(?:situa[çc][ãa]o|status|verifica[çc][ãa]o|status verifica[çc][ãa]o)$", re.I)
NUMBER = re.compile(r"^\(?-?(?:R\$\s*)?\d[\d.]*(?:,\d+)?\)?\s*(?:%|x)?$|^-$")
MONTH = re.compile(r"^(?P<m>jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zç]*[/-](?P<y>\d{2,4})$|"
                   r"^\d{2}/(?P<mm>\d{2})/(?P<yy>\d{4})$", re.I)
EXIGIDO = re.compile(r"m[íi]nim|exigid|gatilho|target|limite|m[áa]xim", re.I)
APURADO = re.compile(r"apurad|saldo final|^saldo$|^atual$|resultado|[íi]ndice|^saldo fundo|^[A-Z]{2,5}$", re.I)
CETIP = re.compile(r"^\d{2}[A-L]\d{7}$")
HEADER_ACTUAL = re.compile(r"(?:valor|saldo)\s+atual|^atual$", re.I)
HEADER_MINIMUM = re.compile(r"m[íi]nim|target|valor inicial", re.I)


@dataclass(frozen=True)
class Monitoring:
    grupo_tipo: str
    grupo: str
    item: str
    valor_referencia: str
    condicao_referencia: str
    valor_apurado: str
    condicao_apurada: str
    situacao: str
    data_verificacao: str
    proxima_verificacao: str
    pagina: int


@dataclass(frozen=True)
class MonthlyReport:
    competencia: str
    cetip: str
    comentario: str
    saldo_devedor: str
    modelo: str
    monitoramentos: list = field(default_factory=list)
    nao_lidos: list = field(default_factory=list)


@dataclass(frozen=True)
class Cell:
    x0: float
    x1: float
    text: str

    @property
    def center(self) -> float:
        return (self.x0 + self.x1) / 2


def competencia_label(month: str) -> str:
    try:
        year, number = month.split("-")
        return f"{MONTHS[int(number) - 1]}/{year}"
    except (ValueError, IndexError):
        return ""


def situation(text: str) -> str:
    text = text.strip().lower()
    if text.startswith("desenquadrad") or text.startswith("não atendido") or text.startswith("nao atendido") or text == "descoberto":
        return "nao_atendido"
    if text.startswith("enquadrad") or text in ("atendido", "coberto"):
        return "atendido"
    return ""


def month_of(text: str) -> date | None:
    match = MONTH.match(text.strip())
    if not match:
        return None
    if match.group("m"):
        year = int(match.group("y"))
        return date(year + 2000 if year < 100 else year, SHORT.index(match.group("m").lower()) + 1, 1)
    return date(int(match.group("yy")), int(match.group("mm")), 1)


def clean(text: str) -> str:
    text = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹*]+\s*$", "", re.sub(r"\s+", " ", text)).strip()
    return re.sub(r"^(?:[A-Za-z]|\d{1,2})\s*[)\-.]\s+", "", text).strip()


def is_value(cell: Cell) -> bool:
    return bool(NUMBER.match(cell.text.strip())) or cell.text.strip() in ("R$",)


def is_text(cell: Cell) -> bool:
    return not is_value(cell) and not STATUS.match(cell.text.strip()) and month_of(cell.text) is None


def rows_of(page) -> list[list[Cell]]:
    cells = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join(span["text"] for span in line["spans"]).strip()
            if text:
                x0, y0, x1, _ = line["bbox"]
                cells.append((y0, Cell(x0, x1, text)))
    cells.sort(key=lambda yc: (round(yc[0]), yc[1].x0))
    rows: list[tuple[float, list[Cell]]] = []
    for y, cell in cells:
        if rows and abs(rows[-1][0] - y) <= 3:
            rows[-1][1].append(cell)
        else:
            rows.append((y, [cell]))
    return [sorted(row, key=lambda c: c.x0) for _, row in rows]


def panel_split(rows: list[list[Cell]]) -> float | None:
    """Modelo de dois painéis: fronteira entre eles pelos títulos de quadro em caixa alta lado a lado."""
    candidates = []
    for row in rows:
        if len(row) == 2 and all(c.text.isupper() and len(c.text) > 5 and not re.search(r"\d", c.text) for c in row):
            candidates.append(round(row[1].x0 - 8))
    if len(candidates) < 2:
        return None
    return max(set(candidates), key=candidates.count)


def streams(rows: list[list[Cell]]) -> list[list[list[Cell]]]:
    split = panel_split(rows)
    if split is None:
        return [rows]
    left = [[c for c in row if c.x0 < split] for row in rows]
    right = [[c for c in row if c.x0 >= split] for row in rows]
    return [[r for r in left if r], [r for r in right if r]]


def value_at(row: list[Cell], center: float | None, start: float) -> str:
    values = [c for c in row if c.x0 >= start - 10 and is_value(c) and c.text.strip() != "R$"]
    if not values:
        return ""
    if center is None or len(values) == 1:
        return values[-1].text.strip() if center is None else values[0].text.strip()
    best = min(values, key=lambda c: abs(c.center - center))
    return best.text.strip() if abs(best.center - center) < 45 else ""


def label_of(row: list[Cell], start: float = 0) -> str:
    texts = [c for c in row if c.x0 >= start - 10 and is_text(c) and not STATUS_LABEL.match(c.text.strip())]
    return texts[0].text.strip() if texts else ""


def kind_of(name: str) -> str:
    lowered = name.lower()
    if "fundo" in lowered or "valor retido" in lowered:
        return "Fundo"
    if "termômetro" in lowered or "termometro" in lowered:
        return "Covenant"
    return "Índice"


def condition_of(label: str) -> str:
    lowered = label.lower()
    if "gerencial" in lowered:
        return "mínimo gerencial (não contratual)"
    if "máxim" in lowered or "maxim" in lowered or "limite" in lowered:
        return "limite" if "limite" in lowered else "máximo"
    if "gatilho" in lowered:
        return "gatilho"
    if "target" in lowered or "inicial" in lowered:
        return "target/mínimo" if "mínim" in lowered or "minim" in lowered else "target"
    return "mínimo"


GENERIC = re.compile(r"^(?:saldo(?: final)?(?: \(R\$\))?|atual|[íi]ndice(?: apurado)?|resultado)$", re.I)


def read_stream(rows: list[list[Cell]], page_number: int, items: list[Monitoring], missed: list[str],
                panels: bool = False) -> None:
    section, subsection = "", ""
    block: list[list[Cell]] = []
    table: dict | None = None
    for row in rows:
        texts = [c.text.strip() for c in row]
        statuses = [c for c in row if STATUS.match(c.text.strip()) or (c.text.strip() == "-" and table is None)]
        status_label = next((c for c in row if STATUS_LABEL.match(c.text.strip())), None)

        # título de seção: uma única célula de texto curta (no modelo de painéis, em caixa alta) ou "I) Título ..."
        single = (len(row) == 1 and is_text(row[0]) and len(texts[0]) <= 80 and not STATUS_LABEL.match(texts[0])
                  and (not panels or texts[0].isupper()))
        if single or re.match(r"^[A-Z]\)\s", texts[0]):
            section, subsection, block, table = clean(texts[0]), "", [], None
            continue
        # cabeçalho de tabela: atual × mínimo × status
        header_status = next((c for c in row if STATUS_LABEL.match(c.text.strip())), None)
        if (header_status and any(HEADER_ACTUAL.search(t) for t in texts) and any(HEADER_MINIMUM.search(t) for t in texts)
                and not any(STATUS.match(t) for t in texts)):
            table = {"actual": next(c for c in row if HEADER_ACTUAL.search(c.text)),
                     "minimum": next(c for c in row if HEADER_MINIMUM.search(c.text) and not HEADER_ACTUAL.search(c.text)),
                     "status": header_status}
            block = []
            continue
        if table is not None:
            found = [c for c in row if STATUS.match(c.text.strip())]
            label = label_of(row)
            if found and label:
                values = [c for c in row if is_value(c) and c.text.strip() != "R$"]
                pick = lambda header: min(values, key=lambda c: abs(c.center - header.center)).text.strip() if values else ""
                actual = pick(table["actual"]) if values else ""
                minimum = ""
                if len(values) >= 2:
                    ordered = sorted(values, key=lambda c: abs(c.center - table["minimum"].center))
                    minimum = ordered[0].text.strip()
                    if minimum == actual:
                        minimum = ordered[1].text.strip()
                name = clean(label)
                items.append(Monitoring(kind_of(name + " " + section), section, name, minimum,
                                        condition_of(table["minimum"].text), actual, found[0].text.strip(),
                                        situation(found[0].text), "", "", page_number))
                continue
            if values_or_text := [c for c in row if is_value(c) or is_text(c)]:
                if not found and not any(is_value(c) for c in values_or_text):
                    table = None  # fim da tabela
                elif not found:
                    continue  # linha de total
            if table is not None:
                continue

        # bloco que termina numa linha de situação
        if status_label is not None or (statuses and all(STATUS.match(t) or t == "-" for t in texts)):
            start = status_label.x1 if status_label is not None else min(c.x0 for c in statuses)
            columns = [c for c in statuses if c.x0 >= start - 5 or status_label is None]
            if not columns:
                block = []
                continue
            months = []
            for previous in reversed(block):
                months = [(month_of(c.text), c) for c in previous if month_of(c.text)]
                if months:
                    break
            column = columns[0]
            month_text = ""
            if months and len(columns) > 1:
                latest_month, latest_cell = max(months, key=lambda mc: mc[0])
                column = min(columns, key=lambda c: abs(c.center - latest_cell.center))
                month_text = latest_cell.text.strip()
            elif months:
                month_text = max(months, key=lambda mc: mc[0])[1].text.strip()
            center = column.center if len(columns) > 1 else None
            region = (status_label.x0 if status_label is not None else 0)
            data = [r for r in block if not any(month_of(c.text) for c in r)]
            required = [r for r in data if EXIGIDO.search(label_of(r, region))]
            measured = [r for r in data if not EXIGIDO.search(label_of(r, region)) and APURADO.search(label_of(r, region))
                        and value_at(r, center, region)]
            if not measured:
                measured = [r for r in data if not EXIGIDO.search(label_of(r, region)) and value_at(r, center, region)]
                if len(measured) > 1:
                    measured = []
            limit = next((m for r in block for c in r for m in [re.search(r"M[íi]nim[oa]\s*=>?\s*([\d.,]+%?)", c.text)] if m), None)
            text = column.text.strip()
            if text == "-" or not (measured or required or limit or situation(text)):
                block = []
                continue
            if not measured and not required and len([r for r in data if value_at(r, center, region)]) > 1:
                missed.append(f"p{page_number} {section or subsection}: situação sem quadro inequívoco")
                block = []
                continue
            measured_row = measured[-1] if measured else None
            required_row = required[-1] if required else None
            specific = clean(label_of(measured_row, region)) if measured_row is not None else ""
            if re.match(r"^[A-Z]{2,5}$", specific):
                name = specific  # sigla do índice (ICM, ITO) basta
            else:
                name_parts = [p for p in (subsection, specific if specific and not GENERIC.match(specific) else "") if p]
                name = " · ".join(name_parts) or section or "Situação"
            items.append(Monitoring(
                kind_of(f"{section} {name}"), section, name,
                (value_at(required_row, center, region) if required_row is not None else (limit.group(1) if limit else "")),
                condition_of(label_of(required_row, region)) if required_row is not None else ("mínimo" if limit else ""),
                value_at(measured_row, center, region) if measured_row is not None else "",
                text, situation(text), month_text, "", page_number))
            block = []
            continue

        # linha com rótulo e situação no fim (termômetro, "Situação da cobertura")
        if statuses and STATUS.match(texts[-1]) and label_of(row):
            label = clean(label_of(row))
            values = [c for c in row if is_value(c) and c.text.strip() not in ("R$", "-")]
            if EXIGIDO.search(label) and block:  # "Mínimo | 40.000,00 | Desenquadrado" sob "c - Saldo Fundo Despesas | 5.071,82"
                above = block[-1]
                measured = [c for c in above if is_value(c) and c.text.strip() != "R$"]
                name = clean(label_of(above)) or section
                items.append(Monitoring(kind_of(f"{section} {name}"), section, name,
                                        values[-1].text.strip() if values else "", condition_of(label),
                                        measured[-1].text.strip() if measured else "", texts[-1],
                                        situation(texts[-1]), "", "", page_number))
                block = []
                continue
            limit = next((m for r in block for c in r for m in [re.search(r"M[íi]nim[oa]\s*=>?\s*([\d.,]+%?)", c.text)] if m), None)
            items.append(Monitoring(kind_of(f"{section} {label}"), section, label, limit.group(1) if limit else "",
                                    "mínimo" if limit else "", values[-1].text.strip() if values else "", texts[-1],
                                    situation(texts[-1]), "", "", page_number))
            continue
        if statuses and STATUS.match(texts[-1]) and not label_of(row):
            values = [c for c in row if is_value(c) and c.text.strip() not in ("R$", "-")]
            if values:  # "187,41% | Atendido" sob o título do quadro
                limit = next((m for r in block + [row] for c in r for m in [re.search(r"M[íi]nim[oa]\s*=>?\s*([\d.,]+%?)", c.text)] if m), None)
                items.append(Monitoring(kind_of(section), section, section or "Situação", limit.group(1) if limit else "",
                                        "mínimo" if limit else "", values[-1].text.strip(), texts[-1],
                                        situation(texts[-1]), "", "", page_number))
                block = []
                continue

        # linha de meses com rótulo ("b - Fundo de Reserva | ago/26 | jul/26"): subtítulo do quadro
        if any(month_of(t) for t in texts) and label_of(row):
            first_month = min(c.x0 for c in row if month_of(c.text))
            left = [c for c in row if is_text(c) and c.x1 <= first_month + 2]
            subsection, block = clean(left[-1].text if left else label_of(row)), [row]
            continue
        block.append(row)


def fill_minimum_after(items: list[Monitoring], rows: list[list[Cell]]) -> list[Monitoring]:
    """"Mínima => 150%" logo abaixo do apurado (modelo da 7ª emissão)."""
    text = " ".join(c.text for row in rows for c in row)
    match = re.search(r"M[íi]nim[oa]\s*=>\s*([\d.,]+%?)", text)
    if not match:
        return items
    return [Monitoring(**{**asdict(i), "valor_referencia": match.group(1), "condicao_referencia": "mínimo"})
            if not i.valor_referencia and i.valor_apurado.endswith("%") else i for i in items]


def header_value(rows: list[list[Cell]], title: str) -> str:
    for index, row in enumerate(rows[:-1]):
        for cell in row:
            if cell.text.strip().upper().startswith(title):
                below = [c for c in rows[index + 1] if is_value(c)]
                if below:
                    return min(below, key=lambda c: abs(c.x0 - cell.x0)).text.strip()
    return ""


def parse_report(path: Path) -> MonthlyReport:
    import pymupdf

    document = pymupdf.open(path)
    items: list[Monitoring] = []
    missed: list[str] = []
    cetip, saldo, model = "", "", "acompanhamento_cri"
    for number, page in enumerate(document, start=1):
        rows = rows_of(page)
        first = " ".join(c.text for row in rows[:4] for c in row).upper()
        if "RELATÓRIO MENSAL DE ACOMPANHAMENTO" in first:
            model = "mensal_paineis"
        elif "GERENCIAMENTO" in first:
            model = "gerenciamento"
        if not cetip:
            cetip = next((c.text.strip() for row in rows for c in row if CETIP.match(c.text.strip())), "")
        if not saldo:
            saldo = header_value(rows, "SALDO DEVEDOR (R$)")
        found: list[Monitoring] = []
        parts = streams(rows)
        for stream in parts:
            read_stream(stream, number, found, missed, panels=len(parts) > 1)
        coverage = next((value for row in rows for index, c in enumerate(row)
                         if c.text.strip().lower().startswith("cobertura de garantias")
                         for value in [next((v.text.strip() for v in row[index + 1:] if is_value(v)), "")] if value), "")
        found = [Monitoring(**{**asdict(i), "valor_apurado": f"cobertura de garantias {coverage}"})
                 if i.item == "Situação da cobertura" and not i.valor_apurado and coverage else i for i in found]
        items.extend(fill_minimum_after(found, rows))
    verdicts: dict[tuple, set] = {}
    for item in items:
        verdicts.setdefault((item.grupo, item.item, item.valor_apurado), set()).add(item.situacao)
    seen, unique = set(), []
    for item in items:
        key = (item.grupo, item.item, item.valor_apurado, item.situacao)
        if len(verdicts[key[:3]]) > 1:  # mesmo valor com "Atendido" e "Não Atendido": não dá para saber qual vale
            if key[:3] not in seen:
                seen.add(key[:3])
                missed.append(f"p{item.pagina} {item.grupo} {item.item}: situações contraditórias para {item.valor_apurado}")
            continue
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return MonthlyReport("", cetip, "", saldo, model, unique, missed)


def as_rows(base: dict, report: MonthlyReport) -> list[dict]:
    head = {**base, "competencia": report.competencia, "cetip_no_relatorio": report.cetip,
            "saldo_devedor": report.saldo_devedor, "parser": PARSER}
    if not report.monitoramentos:
        return [{**head, "grupo_tipo": "", "grupo": "", "item": "(sem monitoramentos)", "valor_referencia": "",
                 "condicao_referencia": "", "valor_apurado": "", "condicao_apurada": "", "situacao": "",
                 "data_verificacao": "", "proxima_verificacao": "", "pagina": ""}]
    return [{**head, **asdict(item)} for item in report.monitoramentos]
