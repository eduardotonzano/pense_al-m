"""Leitor do "Relatório Mensal" (Relatório investidor) da Canal: séries (CETIP, ISIN, saldo devedor) e o quadro de
garantias (fundos e índices: exigido × apurado × Enquadrado/Desenquadrado).

Dois modelos aparecem:
  - atual (A4 deitado, 2025 em diante): bloco "GARANTIAS" com as colunas Limite Mínimo | Razão (%) | Status, a
    data em "Saldos finais em:" e, à direita, os saldos das contas ("Aplicação/Fundo:"); notas de rodapé marcadas
    com asterisco ("*Fundo reenquadrado", "**Assunto sendo deliberado em AGT") ficam junto ao item marcado;
  - antigo (A4 em pé, até 2024): página "Fundos" com um bloco por fundo ou índice ("Fundo de Reservas jun-24",
    "(a) Saldo", "(b) Valor Mínimo do Fundo", "Situação do Fundo Enquadrado"; o índice traz o cálculo aberto e
    "Situação do Índice").
A leitura é pela posição das palavras (PyMuPDF). Valores copiados como estão; a situação normalizada sai do status
informado (Enquadrado = atendido, Desenquadrado = não atendido). Os saldos de conta do modelo atual saem como itens
"Saldo de conta" sem situação: o relatório não diz qual saldo atende qual limite, e o leitor não faz esse pareamento.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

PARSER = "canal_relatorio_mensal 0.1"
MONTH_NAMES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
               "Novembro", "Dezembro")
SHORT_MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10,
                "nov": 11, "dez": 12}
STATUS = {"enquadrado": "atendido", "enquadrada": "atendido", "desenquadrado": "nao_atendido",
          "desenquadrada": "nao_atendido", "n/a": "nao_se_aplica", "na": "nao_se_aplica", "-": ""}
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
SHORT_DATE = re.compile(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-z]*[-/.]\d{2,4}$", re.IGNORECASE)
NOTE = re.compile(r"^(\*+)\s*(.+)$")
SERIES_FOOTER = re.compile(r"^S[ée]rie \d")


@dataclass(frozen=True)
class Monitoring:
    grupo_tipo: str
    grupo: str
    item: str
    valor_referencia: str
    condicao_referencia: str
    valor_apurado: str
    condicao_apurada: str
    situacao: str  # atendido | nao_atendido | nao_verificado | nao_se_aplica | outro | ""
    data_verificacao: str
    proxima_verificacao: str
    pagina: int


@dataclass(frozen=True)
class Series:
    cetip: str
    isin: str
    saldo_devedor: str


@dataclass(frozen=True)
class MonthlyReport:
    competencia: str
    cetip: str
    comentario: str
    saldo_devedor: str
    monitoramentos: list[Monitoring]
    modelo: str = ""
    series: list[Series] = field(default_factory=list)


Line = tuple[float, list[tuple[float, str]]]


def _lines(words: list[tuple]) -> list[Line]:
    """Agrupa palavras em linhas pela posição vertical (tolerância de 2 pt)."""

    lines: list[Line] = []
    for x0, y0, _x1, _y1, text, *_ in sorted(words, key=lambda w: (round(w[1]), w[0])):
        if lines and abs(lines[-1][0] - y0) <= 2:
            lines[-1][1].append((x0, text))
        else:
            lines.append((y0, [(x0, text)]))
    return [(y, sorted(items)) for y, items in lines]


def _join(words: list[str]) -> str:
    return " ".join(words).strip()


def status(text: str) -> str:
    key = re.sub(r"\s+", " ", text.strip().lower())
    if not key:
        return ""
    if key in STATUS:
        return STATUS[key]
    first = key.split(" ")[0]
    return STATUS.get(first, "outro") if first in ("enquadrado", "desenquadrado", "enquadrada", "desenquadrada") else "outro"


def _value_split(words: list[tuple[float, str]], min_x: float) -> tuple[str, str]:
    """(rótulo, valor) de uma linha "rótulo .... valor": o valor são as palavras à direita de ``min_x``."""

    label = _join([t for x, t in words if x < min_x])
    value = _join([t for x, t in words if x >= min_x])
    return label, value


# ---------------------------------------------------------------- modelo atual: quadro GARANTIAS em colunas


def _garantias_header(lines: list[Line]) -> tuple[int, dict[str, float]] | None:
    for index, (_y, line) in enumerate(lines):
        texts = [t for _, t in line]
        if "Limite" in texts and "Status" in texts:
            pos = {t: x for x, t in line}
            right = min((x for x, t in line if t in ("Saldos", "Aplicação/Fundo:") and x > pos["Status"]), default=None)
            razao = next((x for x, t in line if t.startswith("Raz")), None)
            return index, {"limite": pos["Limite"], "razao": razao if razao is not None else (pos["Limite"] + pos["Status"]) / 2,
                           "status": pos["Status"], "right": right if right is not None else 10_000,
                           "aplicacao": pos.get("Aplicação/Fundo:", right if right is not None else 10_000)}
    return None


def parse_garantias(pages_words: list[list[tuple]]) -> list[Monitoring]:
    items: list[Monitoring] = []
    for number, words in enumerate(pages_words, start=1):
        lines = _lines(words)
        found = _garantias_header(lines)
        if not found:
            continue
        index, col = found
        header_y = lines[index][0]
        base_date = next((t for x, t in lines[index][1] if DATE.match(t) and x >= col["right"] - 5), "")
        title = next((_join([t for _, t in line]) for y, line in reversed(lines[:index]) if header_y - y < 40
                      and any(t == "GARANTIAS" for _, t in line)), "GARANTIAS")
        group = re.sub(r"^GARANTIAS\s*", "", title).strip() or "Garantias"
        bounds = (col["limite"] - 25, (col["limite"] + col["razao"]) / 2 + 10, (col["razao"] + col["status"]) / 2,
                  col["right"] - 5)
        rows: list[list] = []  # [y, item, limite, razão, status]
        notes: dict[str, str] = {}
        balances: list[tuple[str, str]] = []
        for y, line in lines[index + 1:]:
            text = _join([t for _, t in line])
            if SERIES_FOOTER.match(text) and all(t.startswith(("Série", "Serie")) or t.isdigit() for _, t in line):
                break
            left = [(x, t) for x, t in line if x < bounds[3]]
            right = [(x, t) for x, t in line if x >= bounds[3]]
            # painel da direita: "Centralizada: R$ x" e "<conta> R$ x"
            if right:
                parts, current = [], []
                for x, t in right:
                    if t.endswith(":") and current and any(w.startswith(("R$", "-R$")) for _, w in current):
                        parts.append(current)
                        current = []
                    if x >= col["aplicacao"] - 5 and current and any(w.startswith(("R$", "-R$")) for _, w in current) \
                            and not t.startswith(("R$", "-R$")) and not re.match(r"^-?[\d.,]+$", t):
                        parts.append(current)
                        current = []
                    current.append((x, t))
                if current:
                    parts.append(current)
                for part in parts:
                    label = _join([t for _, t in part if not (t.startswith(("R$", "-R$")) or re.match(r"^-?[\d.,]+%?$", t))])
                    value = _join([t for _, t in part if t.startswith(("R$", "-R$")) or re.match(r"^-?[\d.,]+%?$", t)])
                    if label and value:
                        balances.append((label.rstrip(":"), value))
            left_text = _join([t for _, t in left])
            if not left_text:
                continue
            note = NOTE.match(left_text)
            if note and left[0][0] < bounds[0]:
                notes[note.group(1)] = note.group(2)
                continue
            cells = [[], [], [], []]
            for x, t in left:
                cells[sum(1 for b in bounds[:3] if x >= b)].append(t)
            cells = [_join(c) for c in cells]
            if any(cells[1:]):
                rows.append([y, *cells])
            elif rows and y - rows[-1][0] <= 10:
                rows[-1][1] = _join([rows[-1][1], cells[0]])  # nome do item quebrado em duas linhas
            else:
                rows.append([y, *cells])
        for _y, name, limit, ratio, state in rows:
            if not (limit or ratio or state):
                continue
            marks = re.search(r"(\*+)$", name)
            clean = re.sub(r"\s*\*+$", "", name).strip()
            condition = state
            if marks and marks.group(1) in notes:
                condition = f"{state} ({marks.group(1)}{notes[marks.group(1)]})".strip()
            kind = "Índice" if not limit.startswith("R$") and not clean.lower().startswith("fundo") else "Fundo"
            items.append(Monitoring(kind, group, clean, limit, "Limite Mínimo" if limit else "", ratio, condition,
                                    status(state), base_date, "", number))
        for label, value in balances:
            if label.lower().startswith("aplicação/fundo"):
                continue
            items.append(Monitoring("Saldo de conta", f"Saldos finais em {base_date}".strip(), label, "", "", value, "",
                                    "", base_date, "", number))
    return items


# ---------------------------------------------------------------- modelo antigo: página "Fundos" em blocos


def parse_fundos(pages_words: list[list[tuple]]) -> list[Monitoring]:
    items: list[Monitoring] = []
    for number, words in enumerate(pages_words, start=1):
        lines = _lines(words)
        block: dict | None = None
        for _y, line in lines:
            texts = [t for _, t in line]
            text = _join(texts)
            if not text:
                continue
            if SHORT_DATE.match(texts[-1]) and not text.startswith("(") and len(texts) >= 2 \
                    and not text.startswith("Situa"):
                block = {"title": _join(texts[:-1]), "date": texts[-1], "rows": []}
                continue
            if block is None:
                continue
            if text.startswith("Situação") or text.startswith("Situacao"):
                label, value = _value_split(line, 150)
                if not value:
                    label, value = text, ""
                rows = block["rows"]
                reference = next(((lb, v) for lb, v in rows if re.search(r"M[íi]nimo|M[áa]ximo|Limite", lb)), ("", ""))
                measured = next(((lb, v) for lb, v in rows if re.search(r"\bSaldo\b", lb)), None)
                index_row = next(((lb, v) for lb, v in reversed(rows) if re.search(r"[ÍI]ndice", lb)
                                  and not re.search(r"M[íi]nimo|M[áa]ximo|Limite", lb)), None)
                chosen = index_row if "ndice" in label else (measured or index_row or (rows[-1] if rows else ("", "")))
                kind = "Índice" if "ndice" in label or "ndice" in block["title"] else "Fundo"
                ref_label = re.sub(r"^\([a-z]\)\s*", "", reference[0])
                items.append(Monitoring(kind, "Fundos", block["title"], reference[1], ref_label, chosen[1], value,
                                        status(value), block["date"], "", number))
                block = None
                continue
            if re.match(r"^\([a-z]{1,2}\)", text):
                label, value = _value_split(line, 150)
                block["rows"].append((label, value))
    return items


# ---------------------------------------------------------------- modelo do agente de monitoramento: "Enquadramento:"

NUMBER = re.compile(r"^-?[\d.]+(,\d+)?%?$")


def parse_enquadramento(pages_words: list[list[tuple]]) -> list[Monitoring]:
    """Relatório de agente de monitoramento contratado ("RELATÓRIO MENSAL Ref. setembro/26"): bloco "Apuração Razão
    de Garantia set-26", linhas do cálculo, "Razão entre (I/II) 153,56%" e "Enquadramento: Enquadrado"; o mínimo
    vem na legenda do gráfico ("Razão Mínima 60%"). O valor é o primeiro número depois do rótulo (o resto da linha
    é do gráfico)."""

    items: list[Monitoring] = []
    for number, words in enumerate(pages_words, start=1):
        lines = _lines(words)
        title, when, result = "", "", ("", "")
        minimum = ""
        for _y, line in lines:
            texts = [t for _, t in line]
            for i, t in enumerate(texts[:-1]):
                if re.match(r"^M[íi]nim[ao]$", t) and NUMBER.match(texts[i + 1]) and not minimum:
                    minimum = texts[i + 1]
        for _y, line in lines:
            texts = [t for _, t in line]
            text = _join(texts)
            if text.startswith("Apuração") or text.startswith("Apuracao"):
                dates = [t for t in texts if SHORT_DATE.match(t)]
                when = dates[-1] if dates else ""
                title = _join([t for t in texts[1:] if not SHORT_DATE.match(t)])
                result = ("", "")
                continue
            if re.match(r"^(Raz[ãa]o|[ÍI]ndice|LTV|ILG)\b", text) and not re.search(r"Apurada|M[íi]nima", text):
                values = [t for t in texts if NUMBER.match(t)]
                if values:
                    label = _join(texts[: texts.index(values[0])])
                    result = (label, values[0])
                continue
            match = re.match(r"^(Enquadramento|Situa[çc][ãa]o|Status)\s*:?\s*(\S+)", text)
            if match and (title or result[0]):
                state = match.group(2)
                items.append(Monitoring("Índice", "Garantias", title or result[0], minimum,
                                        "Mínimo" if minimum else "", result[1], state, status(state), when, "", number))
                title, result = "", ("", "")
    return items


# ---------------------------------------------------------------- cabeçalho: competência, séries e saldo


def _series(pages_words: list[list[tuple]]) -> tuple[list[Series], str]:
    """Séries do RESUMO (modelo atual: "Código CETIP"/"Código ISIN" em colunas; "Saldo devedor após pagamento" com
    Total e Unitário por série) ou dos blocos de série do modelo antigo ("Código CETIP" de cada série)."""

    cetips: list[str] = []
    isins: list[str] = []
    balances: list[str] = []
    consolidated = ""
    for words in pages_words:
        for _y, line in _lines(words):
            texts = [t for _, t in line]
            text = _join(texts)
            if text.startswith("Código CETIP") and not cetips:
                cetips = [t for x, t in line if x > 150 and t not in ("CETIP",)][:4]
                cetips = [t for t in cetips if re.match(r"^[0-9A-Z]{8,12}$", t) or t in ("N/A", "NÃO", "-")]
            elif text.startswith("Código CETIP"):
                cetips += [t for x, t in line if x > 150 and re.match(r"^[0-9A-Z]{8,12}$", t) and t != "CETIP"]
            elif text.startswith("Código ISIN") and not isins:
                isins = [t for x, t in line if x > 150]
                isins = [("" if t in ("N/A", "-") else t) for t in _merge_tem(isins)]
            elif re.match(r"^Saldo [Dd]evedor [Aa]p[óo]s [Pp]agamento", text) and not balances:
                values = [t for t in texts if re.match(r"^-?[\d.]+,\d+$", t)]
                balances = values[0::2]
                consolidated = consolidated or (f"R$ {values[0]}" if values else "")
            elif text.startswith("Covernants") and not isins:
                found = [t for t in texts if re.match(r"^BR[0-9A-Z]{10}$", t)]
                isins = found or isins
    series = []
    for i, cetip in enumerate(cetips):
        if not re.match(r"^[0-9A-Z]{8,12}$", cetip) or cetip in ("N/A",):
            continue
        isin = isins[i] if i < len(isins) and re.match(r"^BR[0-9A-Z]{10}$", isins[i] or "") else ""
        saldo = f"R$ {balances[i]}" if i < len(balances) else ""
        series.append(Series(cetip, isin, saldo))
    return series, consolidated


def _merge_tem(tokens: list[str]) -> list[str]:
    """"NÃO TEM" vem em duas palavras: junta para não deslocar as colunas das séries seguintes."""

    merged: list[str] = []
    for token in tokens:
        if token == "TEM" and merged and merged[-1] == "NÃO":
            merged[-1] = ""
        else:
            merged.append(token)
    return merged


def competencia_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month - 1]}/{year}" if 1 <= month <= 12 else ""


def _competencia(text: str) -> str:
    """Do título: "121ªE CRI BRGD 05/2026" ou "165ªE CRI TALLIN 01_2026" (modelo atual) ou "junho de 2024" (modelo
    antigo). Só as primeiras linhas com o título contam: a data de emissão do RESUMO não é a competência."""

    head = text[:600]
    names = "|".join(m.lower() for m in MONTH_NAMES) + "|marco"
    match = (re.search(r"\b(" + names + r")\s+de\s+(20\d{2})", head.lower())
             or re.search(r"ref\.?\s*(" + names + r")\s*/\s*(\d{2}|20\d{2})\b", head.lower()))  # "Ref. setembro/26"
    if match:
        name = "março" if match.group(1) == "marco" else match.group(1)
        year = match.group(2) if len(match.group(2)) == 4 else "20" + match.group(2)
        return f"{name.capitalize()}/{year}"
    for line in head.splitlines()[:8]:
        if re.search(r"\d+\s*[ªºo°]\s*E\b|\bCR[IA]\b|Emiss", line):
            match = re.search(r"(?<!\d)(0[1-9]|1[0-2])\s*[/_.\-]\s*(20\d{2})(?!\d)", line)
            if match and not re.search(r"\d{2}/(0[1-9]|1[0-2])/20\d{2}", line):
                return competencia_label(int(match.group(2)), int(match.group(1)))
    return ""


def parse_words(pages_words: list[list[tuple]], text: str) -> MonthlyReport:
    items = parse_garantias(pages_words)
    model = "garantias" if items or any("Limite" in t and "Status" in t for t in [text]) else ""
    if not items:
        items = parse_fundos(pages_words)
        model = "fundos" if items else model
    if not items:
        items = parse_enquadramento(pages_words)
        model = "agente_monitoramento" if items else model
    series, consolidated = _series(pages_words)
    return MonthlyReport(competencia=_competencia(text), cetip=series[0].cetip if series else "", comentario="",
                         saldo_devedor=consolidated, monitoramentos=items, modelo=model, series=series)


def parse_report(path: Path) -> MonthlyReport:
    import pymupdf

    with pymupdf.open(path) as document:
        pages_words = [page.get_text("words") for page in document]
        text = "\n".join(page.get_text() for page in document)
    return parse_words(pages_words, text)


def as_rows(base: dict, report: MonthlyReport) -> list[dict]:
    """Linhas do CSV para uma série (``base`` traz codigo_cetip, isin e os dados da emissão)."""

    cetip = str(base.get("codigo_cetip") or "").upper()
    own = next((s for s in report.series if s.cetip.upper() == cetip), None)
    head = {**base, "isin": base.get("isin") or (own.isin if own else ""), "competencia": report.competencia,
            "cetip_no_relatorio": own.cetip if own else ",".join(s.cetip for s in report.series),
            "saldo_devedor": (own.saldo_devedor if own and own.saldo_devedor else report.saldo_devedor), "parser": PARSER}
    if not report.monitoramentos:
        return [{**head, "grupo_tipo": "", "grupo": "", "item": "(sem monitoramentos)", "valor_referencia": "",
                 "condicao_referencia": "", "valor_apurado": "", "condicao_apurada": "", "situacao": "",
                 "data_verificacao": "", "proxima_verificacao": "", "pagina": ""}]
    return [{**head, **asdict(item)} for item in report.monitoramentos]


def with_competencia(report: MonthlyReport, value: str) -> MonthlyReport:
    return replace(report, competencia=value)
