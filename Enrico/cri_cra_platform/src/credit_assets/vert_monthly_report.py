"""Leitor do "Relatório Mensal de Acompanhamento" da Vert: os blocos "Índices e Acompanhamentos", "Índices
Financeiros", "Indicadores de Monitoramento" e "Informações Adicionais", com o que o contrato exige (valor mínimo,
máximo, limite ou threshold), o valor apurado e o status "Enquadrado"/"Desenquadrado".

O PDF vem de um modelo Excel e o layout muda de uma operação para outra, então a leitura é pela posição das palavras
(PyMuPDF) e ancorada no status:
  - tabela horizontal: cabeçalho com "Status"/"Situação" na coluna do status ("Valor Atual | Valor Mínimo | Status",
    "Nome do Índice | Valor Calculado | Limite | Situação", "Data Verificação | ... | Fluxo mínimo Mensal | % |
    Status"); cada linha com conteúdo na coluna de status é um item e as células vão para a coluna do cabeçalho com
    que se sobrepõem (o "R$" solto à esquerda vai junto do número seguinte);
  - tabela vertical: rótulos à esquerda e valores numa coluna ("Dívida Líquida / EBITDA 2,27", "Threshold 3,50",
    "Verificação Enquadrado"), às vezes duas colunas lado a lado (um ano em cada) ou um período por coluna
    ("1T25 ... 2T26", "dez/25 mar/26 jun/26"), em que vale o mais recente;
  - status solto ("Saldo Mínimo  R$ 58.970,19  Enquadrado"), sem cabeçalho.
As páginas são lidas em sequência (cabeçalho no fim de uma página, linhas na outra). Limite escrito no nome do item
("menor ou igual a 1,5", "(Desenquadramento: >4,00 ...)") vira o valor de referência.
Tabela com histórico (DL/EBITDA por ano, fluxo mínimo por mês) fica só com a linha de data mais recente por item.
Valores copiados como estão no relatório, sem conversão; a situação é a que a Vert informa.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

PARSER = "vert_relatorio_mensal 0.1"
STATUS_WORD = re.compile(r"^(n[ãa]o[\s-]+)?(des)?enquadrad[oa]s?\W*\d*$", re.IGNORECASE)
STATUS_HEADER = re.compile(r"^(status|staus|stauts|situa[çc][ãa]o|verifica[çc][ãa]o)\W*\d*$", re.IGNORECASE)
REFERENCE = re.compile(r"m[íi]nim|m[áa]xim|limite|threshold|exig|refer[êe]ncia|gatilho|par[âa]metro", re.IGNORECASE)
MEASURED = re.compile(r"atual|apurad|calculad|realizad|^ltv$|^contratos$|recebid|arrecadad", re.IGNORECASE)
NOT_VALUE = re.compile(r"^data|^per[íi]odo|observa|detalhe|coment|status|situa[çc]|^nome|descri|indicador|^[íi]ndice$",
                       re.IGNORECASE)
NAME = re.compile(r"^(nome|[íi]ndice$|indicador|item|covenant|crit[ée]rio|tipo)", re.IGNORECASE)
DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
PERIOD_ROW = re.compile(r"^(data|exerc[íi]cio|per[íi]odo|trimestre|ano\b|compet[êe]ncia)", re.IGNORECASE)
INLINE_LIMIT = re.compile(r"((?:igual\s+ou\s+)?(?:maior|menor|superior|inferior)(?:\s+ou\s+igual)?(?:\s+(?:a|que|de))?|[<>]=?|[≤≥])\s*"
                          r"((?:R\$\s*)?\d[\d.,]*\s*(?:x|%)?)", re.IGNORECASE)
PERIOD_LABEL = re.compile(r"^((jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zç]*[/ .-]?\d{2,4}|[1-4]T\d{2,4}|20\d{2})$",
                          re.IGNORECASE)
GENERIC_LABEL = re.compile(r"^(valor(\s+(apurado|atual|calculado))?|[íi]ndice(\s+apurado)?|resultado|apurado|%)$",
                           re.IGNORECASE)
FOOTER = re.compile(r"^#?\s*(\[?RESTRITO\]?)?\s*#?$|^#?\s*\[?(P[ÚU]BLICO|INTERNO|CONFIDENCIAL)\]?$", re.IGNORECASE)
MONEY_TOKEN = {"R$", "-R$", "R$-", "(R$)"}
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro")
SITUATIONS = {
    "enquadrado": "atendido", "enquadrada": "atendido",
    "desenquadrado": "nao_atendido", "desenquadrada": "nao_atendido",
    "nao enquadrado": "nao_atendido", "não enquadrado": "nao_atendido",
    "n/a": "nao_se_aplica", "na": "nao_se_aplica", "nao se aplica": "nao_se_aplica", "não se aplica": "nao_se_aplica",
    "nao aplicavel": "nao_se_aplica", "não aplicável": "nao_se_aplica",
    "nao verificado": "nao_verificado", "não verificado": "nao_verificado", "nao apurado": "nao_verificado",
    "não apurado": "nao_verificado", "pendente": "nao_verificado", "em apuração": "nao_verificado",
    "-": "",
}

Line = tuple[float, list[tuple[float, float, str]]]  # (altura, [(x0, x1, palavra)])


@dataclass(frozen=True)
class Monitoring:
    grupo_tipo: str  # Fundo | Garantia | Covenant (pelo nome do item)
    grupo: str  # título do bloco no relatório ("Fundo de Despesas", "Índice Financeiro", "Fluxo Mínimo Mensal LTM")
    item: str
    valor_referencia: str
    condicao_referencia: str  # Mínimo | Máximo | "" (threshold sem sentido explícito)
    valor_apurado: str
    condicao_apurada: str  # texto do status como está ("Enquadrado", "DESENQUADRADO")
    situacao: str  # atendido | nao_atendido | nao_verificado | nao_se_aplica | outro | ""
    data_verificacao: str
    proxima_verificacao: str
    pagina: int


@dataclass(frozen=True)
class MonthlyReport:
    competencia: str
    cetip: str
    comentario: str
    saldo_devedor: str
    monitoramentos: list[Monitoring]


def situation(text: str) -> str:
    key = re.sub(r"[\d¹²³⁴⁵*]+$", "", re.sub(r"\s+", " ", text.strip().lower())).strip()
    if not key:
        return ""
    return SITUATIONS.get(key, "outro")


def _lines(words: list[tuple]) -> list[Line]:
    """Agrupa palavras em linhas pela posição vertical (tolerância de 2 pt)."""

    lines: list[Line] = []
    for x0, y0, x1, _y1, text, *_ in sorted(words, key=lambda w: (round(w[1]), w[0])):
        if lines and abs(lines[-1][0] - y0) <= 2:
            lines[-1][1].append((x0, x1, text))
        else:
            lines.append((y0, [(x0, x1, text)]))
    return [(y, sorted(items)) for y, items in lines]


def _text(words) -> str:
    return " ".join(t for _, _, t in words)


def _clusters(words: list[tuple[float, float, str]], gap: float = 7.0) -> list[tuple[float, float, str]]:
    """Junta palavras vizinhas em células; um "R$" solto vai junto do número seguinte, por mais longe que esteja."""

    cells: list[list] = []
    glue = False
    for x0, x1, t in sorted(words):
        if cells and (glue or x0 - cells[-1][1] <= gap) and t not in MONEY_TOKEN:
            cells[-1][1] = max(cells[-1][1], x1)
            cells[-1][2] += " " + t
        else:
            cells.append([x0, x1, t])
        glue = t in MONEY_TOKEN
    return [(a, b, t) for a, b, t in cells]


def _status_cell(words) -> tuple[float, float, str] | None:
    """A célula de status da linha ("Enquadrado", "Não Enquadrado", "DESENQUADRADO³"), se houver."""

    for i, (x0, x1, t) in enumerate(words):
        if STATUS_WORD.match(t):
            if i and words[i - 1][2].lower() in ("não", "nao") and x0 - words[i - 1][1] < 7:
                return (words[i - 1][0], x1, words[i - 1][2] + " " + t)
            return (x0, x1, t)
    return None


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


def _kind(item: str, group: str = "") -> str:
    found = _kind_of(item)
    return found if found != "Covenant" or not group else _kind_of(group)


def _kind_of(name: str) -> str:
    low = name.lower()
    # "Fundo de Despesas", "Reserva de Amortização"; não "EBITDA / Despesa Financeira" (índice tem barra)
    if (re.search(r"fundo|reserva|despesas?$|obra|sobrecusto|reten[çc][ãa]o|saldo m[íi]nimo", low)
            and not re.search(r"cobertura|garantia|/", low)):
        return "Fundo"
    if re.search(r"garantia|cobertura|ltv|loan|aliena|cess[ãa]o|lastro|raz[ãa]o|colateral|subordina", low):
        return "Garantia"
    return "Covenant"


def _condition(label: str, value: str) -> str:
    if re.search(r"m[íi]nim|maior|superior", label, re.IGNORECASE) or value.lstrip().startswith(">"):
        return "Mínimo"
    if re.search(r"m[áa]xim|menor|inferior", label, re.IGNORECASE) or value.lstrip().startswith("<"):
        return "Máximo"
    return ""


def _date_key(text: str) -> tuple:
    found = DATE.search(text)
    if found:
        return (int(found.group(3)), int(found.group(2)), int(found.group(1)))
    year = re.search(r"\b(20\d{2})\b", text)
    return (int(year.group(1)), 12, 31) if year else (0, 0, 0)


def _is_title(words, max_x: float) -> bool:
    text = _text(words)
    return (bool(words) and words[0][0] < max_x and len(words) <= 8 and not re.search(r"\d{2}[/.,]\d", text)
            and not STATUS_WORD.match(words[-1][2]) and not text.endswith(".") and not text.startswith(("*", "(")))


def _horizontal(lines: list[Line], index: int, page_of: list[int], width: float, used: set[int]) -> list[dict]:
    """Tabela com cabeçalho; ``index`` é a linha do cabeçalho com "Status"/"Situação"."""

    head_y = lines[index][0]
    status_head = [c for c in _clusters(lines[index][1], gap=6.0) if STATUS_HEADER.match(c[2])][-1]
    # linhas de dados: daqui para baixo, enquanto aparecer status na coluna (ou o bloco continuar sem buraco grande)
    rows: list[int] = []
    last_y = head_y
    column = (status_head[0] - 25, status_head[1] + 25)
    for j in range(index + 1, len(lines)):
        y, words = lines[j]
        if y - last_y > 40:
            break
        if any(STATUS_HEADER.match(c[2]) and _overlap(c[0], c[1], status_head[0] - 15, status_head[1] + 15) > 0
               for c in _clusters(words, gap=6.0)):
            break  # outra tabela começa (não "Verificação em 01/2026" numa célula)
        cell = _status_cell(words)
        in_column = " ".join(w[2] for w in words if _overlap(w[0], w[1], *column) > 0)
        if cell and _overlap(cell[0], cell[1], *column) > 0:
            rows.append(j)
            last_y = y
        elif in_column and situation(in_column) in ("nao_se_aplica", "nao_verificado"):
            rows.append(j)  # status sem "enquadrado" ("N/A", "Pendente")
            last_y = y
        elif in_column:
            last_y = y  # linha da tabela que não é item monitorado (garantia "Não será atualizado")
        elif rows and (_is_title(words, width * 0.15) or y - last_y > 14):
            break
    if not any(_status_cell(lines[j][1]) for j in rows):
        return []
    first_row_y = lines[rows[0]][0]
    # cabeçalho: linhas de 12 pt acima a 6 pt abaixo da linha do status (títulos em alturas diferentes), antes da
    # primeira linha de dados; uma linha só com um título na margem ("Fundo de Despesas") não é cabeçalho
    left_margin = width * 0.15
    lone_title = lambda ws: len(_clusters(ws, gap=6.0)) == 1 and ws[0][0] < left_margin
    band = [k for k in range(max(0, index - 4), rows[0]) if -12 <= lines[k][0] - head_y <= 6
            and lines[k][0] < first_row_y - 3.5 and not lone_title(lines[k][1]) and (k == index or not DATE.search(_text(lines[k][1])))]
    head_words = sorted(w for k in band for w in lines[k][1])
    labels = [list(c) for c in _clusters(head_words, gap=6.0)]
    title, title_date = "", ""
    # título embutido no cabeçalho, à esquerda e longe dos rótulos ("Fundo de Despesas      Valor Atual  Valor Mínimo")
    if (len(labels) > 2 and labels[0][0] < left_margin and labels[1][0] - labels[0][1] > 40
            and not NAME.match(labels[0][2]) and not re.match(r"(data|valor|per[íi]odo|%)", labels[0][2], re.IGNORECASE)
            and not any(re.search(r"\d", c[2]) and not DATE.fullmatch(c[2]) and _overlap(c[0], c[1], labels[0][0], labels[0][1]) > 0
                        for j in rows for c in _clusters(lines[j][1]))):  # sem número embaixo dele
        title = labels.pop(0)[2]
    k = band[0] if band else index
    above = k - 1
    while not title and above >= 0 and head_y - lines[above][0] <= 24:
        ws = lines[above][1]
        first = _clusters(ws, gap=12.0)[0][2]  # sem rótulos de colunas ou datas na mesma linha
        # "LTC (Calculado pelo Agente de Monitoramento)   Data-Base 31/08/2026   Data de Verificação 16/09/2026"
        dated_title = (DATE.search(_text(ws)) and re.search(r"Data|Verifica", _text(ws)) and ws[0][0] < width * 0.15
                       and not re.search(r"\d", first))
        if above not in used and (_is_title(ws, width * 0.35) or dated_title) and not _status_cell(ws):
            title = first
            found = re.search(r"Verifica\w*\s+(\d{2}/\d{2}/\d{4})", _text(ws))
            title_date = found.group(1) if found else ""
            break
        above -= 1
    data: list[dict] = []
    for j in rows:
        y, words = lines[j]
        near = [w for k2, (y2, ws) in enumerate(lines) if k2 not in rows and k2 not in band and abs(y2 - y) <= 4.5
                for w in ws]  # rótulo da linha um pouco acima ou abaixo ("LTV" ao lado de "Data de Apuração")
        cells = _clusters(sorted(words + near))
        row: dict[int, list[str]] = {}
        row_title, loose = [], []
        left = min(l[0] for l in labels)
        for x0, x1, t in cells:
            if x1 < left - 5:
                (loose if re.search(r"\d,\d{2}$", t) and not DATE.fullmatch(t) else row_title).append(t)
                continue
            if all(_overlap(x0, x1, l[0], l[1]) <= 0 for l in labels) and (x0 + x1) / 2 < left:
                # descrição sem coluna no cabeçalho ("Aplicado em CDB com liquidez diária"); um valor solto ali é o
                # saldo atual quando o cabeçalho só traz "Valor Mínimo"
                if re.search(r"\d,\d{2}$", t) and not DATE.fullmatch(t):
                    loose.append(t)
                continue
            best = max(range(len(labels)), key=lambda i: (_overlap(x0, x1, labels[i][0], labels[i][1]),
                                                          -abs((x0 + x1) / 2 - (labels[i][0] + labels[i][1]) / 2)))
            row.setdefault(best, []).append(t)
        data.append({"row": row, "row_title": row_title, "loose": loose, "line": j})
    order = sorted(range(len(labels)), key=lambda i: labels[i][0])
    names = [l[2] for l in labels]
    status_i = max(range(len(labels)), key=lambda i: _overlap(labels[i][0], labels[i][1], status_head[0], status_head[1]))
    cells_of = lambda i: [" ".join(d["row"].get(i, [])) for d in data if d["row"].get(i)]
    # coluna de datas pelo rótulo ("Data Verificação") ou pelo conteúdo ("Verificação" com 21/07/2026)
    dated = {i for i in order if cells_of(i) and all(DATE.fullmatch(c) for c in cells_of(i))}
    next_i = next((i for i in order if i != status_i and re.match(r"pr[óo]xim", names[i], re.IGNORECASE)), None)
    date_i = next((i for i in order if i not in (status_i, next_i) and (re.match(r"data", names[i], re.IGNORECASE)
                                                                         or i in dated)), None)
    refs = [i for i in order if i not in (status_i, next_i) and i not in dated and REFERENCE.search(names[i])
            and not re.match(r"data", names[i], re.I) and not MEASURED.search(names[i])]
    # "Percentual Mínimo 150%" e "Valor Mínimo R$ 3.261.378,34": vale o valor, na mesma unidade do apurado
    ref_i = next((i for i in refs if re.match(r"valor", names[i], re.IGNORECASE)), refs[0] if refs else None)
    name_i = next((i for i in order if i not in (status_i, date_i, ref_i) and NAME.match(names[i])), None)
    candidates = [i for i in order if i not in (status_i, date_i, name_i, next_i) and i not in dated and i not in refs
                  and not NOT_VALUE.search(names[i])]
    measured_i = next((i for i in candidates if MEASURED.search(names[i])), None)
    # colunas por período ("dez/25  mar/26  jun/26  Status"): o status é o do período mais recente, à direita
    periods = [i for i in candidates if PERIOD_LABEL.match(names[i].strip())]
    period_i = periods[-1] if measured_i is None and len(periods) >= 2 else None
    if period_i is not None:
        measured_i = period_i
    if measured_i is None:
        measured_i = next((i for i in candidates if re.search(r"m[ée]dia", names[i], re.IGNORECASE)), None)
    if measured_i is None and ref_i is not None:
        # "LTC Máximo" × "LTC", "IRL Mínimo" × "IRL"
        bare = re.sub(r"\s*\b(m[íi]nim[oa]|m[áa]xim[oa])\b\s*", " ", names[ref_i], flags=re.IGNORECASE).strip().lower()
        measured_i = next((i for i in candidates if names[i].strip().lower() == bare), None)
    numeric = [i for i in candidates if any(re.search(r"\d", " ".join(d["row"].get(i, []))) for d in data)]
    if measured_i is None and ref_i is not None and any("%" in c for c in cells_of(ref_i)):
        # "Total Integralizado R$ 89.947.986,39 | Percentual Mínimo 165% | Razão de Garantia 191%": exigido em %,
        # o apurado é a coluna em %, não o valor em R$ ao lado
        measured_i = next((i for i in numeric if cells_of(i) and all("%" in c for c in cells_of(i))), None)
    if measured_i is None and ref_i is not None:
        left_of = [i for i in numeric if labels[i][0] < labels[ref_i][0]]
        measured_i = left_of[-1] if left_of else None
    if measured_i is None and numeric:
        measured_i = numeric[0]
    out = []
    for d in data:
        row = d["row"]
        get = lambda i: " ".join(row.get(i, [])) if i is not None else ""
        measured = get(measured_i) or (d["loose"][-1] if d["loose"] else "")
        cell = _status_cell(lines[d["line"]][1])
        status_text = cell[2] if cell else get(status_i)  # sem a observação colada ("Enquadrado Aplicado em CDB")
        name_cell = get(name_i) if re.search(r"[A-Za-zÀ-ú]{2,}", get(name_i).replace("R$", "")) else ""
        reference, ref_label = get(ref_i), names[ref_i] if ref_i is not None else ""
        row_title = " ".join(d["row_title"])
        # "Fundo de Despesas  Valor Mínimo  R$20.000,00": o exigido vem na linha, à esquerda das colunas
        inline = re.match(r"(.*?)\s*(Valor\s+)?(M[íi]nimo|M[áa]ximo)$", row_title, re.IGNORECASE)
        if inline and not reference:
            row_title, ref_label = inline.group(1), inline.group(3)
            # o exigido é o primeiro valor à direita do rótulo; o apurado, o seguinte
            spare = [i for i in order if i not in (status_i, date_i, next_i) and re.search(r"\d|N/?A", get(i))]
            reference = get(spare[0]) if spare else ""
            if spare and spare[0] == name_i:
                name_cell = ""
            if spare and spare[0] == measured_i:
                measured = get(spare[1]) if len(spare) > 1 else ""
        elif d["row_title"]:
            row_title = d["row_title"][0] if re.search(r"[A-Za-zÀ-ú]{2,}", d["row_title"][0].replace("R$", "")) else ""  # o nome do item; o resto é descrição ("Aplicado em CDB...")
        row_date = next((t for t in d["row_title"] if DATE.fullmatch(t)), "")  # data embaixo do título do bloco
        name = name_cell or row_title or title or (names[measured_i] if measured_i is not None else "")
        out.append({
            "grupo": title or name, "item": name, "valor_referencia": reference,
            "condicao_referencia": _condition(ref_label, reference),
            "valor_apurado": measured, "condicao_apurada": status_text, "situacao": situation(status_text),
            "data_verificacao": get(date_i) or row_date or title_date or (names[period_i] if period_i is not None else ""),
            "proxima_verificacao": get(next_i), "pagina": page_of[d["line"]],
            "line": d["line"]})
        used.add(d["line"])
    return out


def _vertical(lines: list[Line], index: int, page_of: list[int], width: float) -> list[dict]:
    """Tabela de rótulo × valor: a linha ``index`` tem "Situação"/"Verificação"/"Status" à esquerda e o status à
    direita. Duas formas: pares rótulo-status lado a lado (um ano em cada coluna, com seus rótulos) ou um rótulo e
    vários status (um período por coluna: "1T25 2T25 ... 2T26"), em que vale a coluna mais à direita (a mais recente).
    Sobe pelas linhas acima juntando rótulo e valor da coluna até a data-base ou o bloco anterior."""

    y, words = lines[index]
    shape = _vertical_shape(words)
    cells = _clusters(words)
    if shape == "periodos":
        status = _status_cell([w for w in words if w[0] >= cells[-1][0] - 1]) or cells[-1]
        columns = [(0.0, status, width, cells[1][0] - 3)]  # rótulo só até a primeira coluna de período
    else:
        pairs = [(a, _status_cell([w for w in words if w[0] >= b[0] - 1])) for a, b in zip(cells, cells[1:])
                 if STATUS_HEADER.match(a[2])]
        columns = [(pairs[n - 1][1][1] + 5 if n else 0.0, st, pairs[n + 1][0][0] - 5 if n + 1 < len(pairs) else width,
                    st[0] - 14) for n, (_label, st) in enumerate(pairs)]
    out = []
    for label_x0, status, value_x1, label_x1 in columns:
        value_x0 = status[0] - 14
        rows, texts = [], []  # (rótulo, valor) de baixo para cima; linhas só de texto (o título do covenant)
        date_text, last_y, top = "", y, index
        for j in range(index - 1, max(-1, index - 40), -1):
            y2, ws = lines[j]
            if last_y - y2 > 25:
                break
            lab = _text([w for w in ws if label_x0 <= w[0] < label_x1 and w[1] <= label_x1 + 3])
            in_value = [w for w in ws if value_x0 <= w[0] < value_x1]
            val = " ".join(c[2] for c in _clusters(in_value))
            if not lab and not val:
                continue
            last_y, top = y2, j
            if PERIOD_ROW.match(lab) or re.fullmatch(r"\d{2}/\d{2}/\d{4}", lab):
                # a data-base pode ficar entre o rótulo e a coluna de valores ("Data base   31/12/2023")
                dated = [w[2] for w in ws if label_x0 <= w[0] < value_x1 and re.match(r"\d{2}/\d{2}/\d{4}$|20\d{2}$", w[2])]
                date_text = val or (dated[0] if dated else "")
                break
            if _status_cell(in_value):
                break  # outro bloco acima
            if val:
                rows.append((lab, val))
            elif lab:
                # a linha toda: o limite pode passar da coluna dos rótulos
                texts.append(_text(ws))
        # título do covenant: por período, a linha de texto entre os valores ("(b) Liquidez Corrente maior ou igual
        # a 1,5"); senão a linha logo acima do cabeçalho ("a) (Dívida Líquida + ...)/PL < 0,8", "Índices Financeiros")
        title = next((t for t in reversed(texts) if len(t.split()) >= 3), "") if shape == "periodos" else ""
        for j in range(top - 1, max(-1, top - 3), -1):
            ws = lines[j][1]
            if title:
                break
            if lines[top][0] - lines[j][0] <= 20 and not _status_cell(ws) and re.search(r"[A-Za-zÀ-ú]{3,}", _text(ws))                     and not PERIOD_ROW.match(_text(ws)) and not any(value_x0 <= w[0] < value_x1 for w in ws):
                title = _text(ws)
        if not date_text and shape == "periodos":
            # cabeçalho de períodos compartilhado por vários blocos ("Data Base", "Exercício")
            for j in range(top - 1, max(-1, top - 40), -1):
                ws = lines[j][1]
                if PERIOD_ROW.match(_text(ws)):
                    date_text = " ".join(w[2] for w in ws if _overlap(w[0], w[1], value_x0, value_x1) > 0)
                    break
        ref = next(((lab, val) for lab, val in rows if REFERENCE.search(lab)), ("", ""))
        measured = next(((lab, val) for lab, val in rows if not REFERENCE.search(lab)), ("", ""))
        if not measured[1] and not ref[1]:
            continue
        if not ref[1] and title:
            # "(b) Liquidez Corrente maior ou igual a 1,5": o exigido vem no título do covenant
            limit = INLINE_LIMIT.search(title)
            if limit:
                ref = (limit.group(1), limit.group(0).strip())
        generic = len(re.sub(r"\W", "", measured[0])) <= 3 or GENERIC_LABEL.match(measured[0])
        item = (title or measured[0] or ref[0]) if generic else re.sub(r"\s*R\$$", "", measured[0])
        out.append({"grupo": "", "item": item, "valor_referencia": ref[1],
                    "condicao_referencia": _condition(ref[0], ref[1]), "valor_apurado": measured[1],
                    "condicao_apurada": status[2], "situacao": situation(status[2]), "data_verificacao": date_text,
                    "pagina": page_of[index], "line": index})
    return out


def parse_monitoring(pages_words: list[list[tuple]], page_widths: list[float] | None = None) -> list[Monitoring]:
    """``pages_words``: palavras de cada página (``page.get_text('words')``)."""

    # as páginas viram uma sequência só de linhas (uma tabela pode começar no fim de uma página e seguir na outra);
    # o rodapé "# [RESTRITO]" sai
    lines: list[Line] = []
    page_of: list[int] = []
    for number, words in enumerate(pages_words, start=1):
        page_lines = [line for line in _lines(words) if not FOOTER.match(_text(line[1]))]
        if not page_lines:
            continue
        shift = (lines[-1][0] + 12 - page_lines[0][0]) if lines else 0
        lines.extend((y + shift, ws) for y, ws in page_lines)
        page_of.extend([number] * len(page_lines))
    width = max([w for w in page_widths or [] if w] or [max((w[2] for ws in pages_words for w in ws), default=600)])
    found: list[dict] = []
    used: set[int] = set()
    for i, (_y, ws) in enumerate(lines):
        if i in used:
            continue
        # rótulo de coluna "Status" sozinho na célula (não o título "Status dos Créditos - setembro/26")
        heads = [c for c in _clusters(ws, gap=6.0) if STATUS_HEADER.match(c[2])]
        if _status_cell(ws) and _vertical_shape(ws):
            items = _vertical(lines, i, page_of, width)
            title = _block_title(lines, i, width)
            for item in items:
                item["grupo"] = title or item["item"]
            found.extend(items)
            used.add(i)
        elif heads and not _status_cell(ws):
            found.extend(_horizontal(lines, i, page_of, width, used))
    # status solto, sem cabeçalho ("Saldo Mínimo  R$ 58.970,19  Enquadrado"): rótulo, valor e status da linha
    for i, (_y, ws) in enumerate(lines):
        alone = [c for c in _clusters(ws) if STATUS_WORD.match(c[2].split()[-1]) and len(c[2].split()) <= 2
                 and not c[2].endswith(":")]
        if i in used or not alone or _vertical_shape(ws):
            continue  # status no meio de frase ("permanecerão desenquadradas até...") ou nota ("³ DESENQUADRADO: ...")
        cells = [c[2] for c in _clusters(ws) if not STATUS_WORD.match(c[2].split()[-1])]
        label = next((c for c in cells if re.search(r"[A-Za-zÀ-ú]{3,}", c.replace("R$", ""))), "")
        values = [c for c in cells if c != label and re.search(r"\d", c)]
        if not label and not values:
            continue
        x_label = next((c[0] for c in _clusters(ws) if c[2] == label), ws[0][0])
        # quadro do fundo ("Fundo de Despesa   Fundo de Reserva" lado a lado): o título mais próximo acima, na mesma
        # coluna do rótulo; o saldo atual é o "Saldo Final" logo acima
        title, measured = (label, "") if re.match(r"(fundo|reserva|conta)", label, re.IGNORECASE) else ("", "")
        for k in range(i - 1, max(-1, i - 14), -1):
            if lines[i][0] - lines[k][0] > 90:
                break
            heads = [c for c in _clusters(lines[k][1], gap=12.0) if re.match(r"(fundo|reserva|conta|saldo m[íi]nimo)", c[2], re.I)
                     and not re.search(r"\d", c[2])]
            if heads and not title:
                title = min(heads, key=lambda c: abs(c[0] - x_label))[2]
            row = _clusters(lines[k][1])
            if not measured and row and re.match(r"saldo\s+(final|atual)", row[0][2], re.IGNORECASE) and values:
                money = [c for c in row if re.search(r"\d,\d{2}$", c[2]) and not DATE.fullmatch(c[2])]
                measured = money[0][2] if money else ""
        if not title:
            title = next((_text(lines[k][1]) for k in range(i - 1, max(-1, i - 6), -1)
                          if _is_title(lines[k][1], width * 0.15) and not _status_cell(lines[k][1])), "")
        is_ref = bool(REFERENCE.search(label))
        status = _status_cell(ws)[2]
        found.append({"grupo": title or label, "item": label or title, "valor_referencia": values[0] if is_ref and values else "",
                      "condicao_referencia": _condition(label, values[0]) if is_ref and values else "",
                      "valor_apurado": measured if is_ref else (values[-1] if values else ""), "condicao_apurada": status,
                      "situacao": situation(status), "data_verificacao": "", "pagina": page_of[i], "line": i})
    # histórico: fica a linha de data mais recente de cada item
    latest: dict[tuple, dict] = {}
    for item in found:
        key = (item["grupo"], item["item"])
        if key not in latest or _date_key(item["data_verificacao"]) >= _date_key(latest[key]["data_verificacao"]):
            latest[key] = item
    keep = sorted(latest.values(), key=lambda it: it["line"])
    for it in keep:
        # limite escrito no nome do item ("Dívida Bancária Líquida / Ebitda : igual ou inferior a 2,5",
        # "(Desenquadramento: >4,00 em 2 trimestres)"): no desenquadramento, o exigido é o contrário
        limit = None if it["valor_referencia"] else INLINE_LIMIT.search(it["item"])
        if limit:
            it["valor_referencia"] = limit.group(0).strip()
            condition = _condition(limit.group(1), limit.group(0).strip())
            if re.search(r"desenquadra\w*\W{0,3}$", it["item"][:limit.start()].strip(), re.IGNORECASE):
                condition = {"Mínimo": "Máximo", "Máximo": "Mínimo"}.get(condition, "")
            it["condicao_referencia"] = condition
    return [Monitoring(_kind(it["item"], it["grupo"]), it["grupo"], it["item"], it["valor_referencia"],
                       it["condicao_referencia"], it["valor_apurado"], it["condicao_apurada"], it["situacao"],
                       it["data_verificacao"], it.get("proxima_verificacao", ""), it["pagina"]) for it in keep]


def _vertical_shape(words) -> str:
    """"pares" para "Situação  ENQUADRADO  Situação  DESENQUADRADO" (rótulo e status alternados), "periodos" para
    "Status  Enquadrado  Enquadrado ... Desenquadrado*" (um rótulo e um status por período), "" para o resto (numa
    tabela horizontal a linha de dados não tem rótulo de status)."""

    cells = _clusters(words)
    is_status = [bool(STATUS_WORD.match(c[2].split()[-1])) and len(c[2].split()) <= 2 for c in cells]
    if len(cells) >= 3 and STATUS_HEADER.match(cells[0][2]) and all(is_status[1:]):
        return "periodos"
    pairs = sum(1 for a, ok in zip(cells, is_status[1:]) if STATUS_HEADER.match(a[2]) and ok)
    return "pares" if pairs and len(cells) == 2 * pairs else ""


def _block_title(lines: list[Line], index: int, width: float) -> str:
    """Título do bloco vertical: a linha curta mais próxima acima do "Data base"."""

    for j in range(index - 1, max(-1, index - 45), -1):
        if re.match(r"data\s+base", _text(lines[j][1]), re.IGNORECASE):
            for k in range(j - 1, max(-1, j - 4), -1):
                if _is_title(lines[k][1], width * 0.3) and lines[j][0] - lines[k][0] <= 30:
                    return _text(lines[k][1])
            return ""
    return ""


def _money_after(lines: list[Line], anchor: str, label: str) -> str:
    seen = False
    for _y, ws in lines:
        text = _text(ws)
        if text.startswith(anchor):
            seen = True
        elif seen and text.startswith(label):
            numbers = [c[2] for c in _clusters(ws) if re.search(r"\d,\d{2}$", c[2])]
            return numbers[-1] if numbers else ""
    return ""


def parse_report(path: Path) -> MonthlyReport:
    import pymupdf

    with pymupdf.open(path) as document:
        pages_words = [page.get_text("words") for page in document]
        widths = [page.rect.width for page in document]
        text = "\n".join(page.get_text() for page in document)
    all_lines = [line for words in pages_words for line in _lines(words)]
    month = re.search(r"\b(" + "|".join(MONTHS) + r")\s*(?:,|de|/)?\s*(\d{4})\b", text[:3000], re.IGNORECASE)
    cetip = re.search(r"\b(CR[AI]0\d{2}[0-9A-Z]{5,6}|\d{2}[A-L]\d{7})\b", text)
    balance = _money_after(all_lines, "Dados Gerais na Data", "Valor Financeiro")
    return MonthlyReport(
        competencia=f"{month.group(1).capitalize()}/{month.group(2)}" if month else "",
        cetip=cetip.group(1) if cetip else "",
        comentario="",
        saldo_devedor=balance,
        monitoramentos=parse_monitoring(pages_words, widths),
    )


def competencia_from_date(reference_date: str) -> str:
    """"2026-09-30" -> "Setembro/2026" (quando o relatório não traz a data-base legível)."""

    try:
        d = date.fromisoformat(reference_date[:10])
    except ValueError:
        return ""
    return f"{MONTHS[d.month - 1].capitalize()}/{d.year}"


def as_rows(base: dict, report: MonthlyReport) -> list[dict]:
    head = {**base, "competencia": report.competencia, "cetip_no_relatorio": report.cetip,
            "saldo_devedor": report.saldo_devedor, "parser": PARSER}
    if not report.monitoramentos:
        return [{**head, "grupo_tipo": "", "grupo": "", "item": "(sem monitoramentos)", "valor_referencia": "",
                 "condicao_referencia": "", "valor_apurado": "", "condicao_apurada": "", "situacao": "",
                 "data_verificacao": "", "proxima_verificacao": "", "pagina": ""}]
    return [{**head, **asdict(item)} for item in report.monitoramentos]
