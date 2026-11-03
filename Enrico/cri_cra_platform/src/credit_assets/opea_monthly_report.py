"""Leitor do "Relatório Mensal de Gestão" da Opea: comentário da gestão, saldo e a tabela de Monitoramentos.

A tabela de Monitoramentos traz, por garantia, obrigação ou covenant, o valor e a condição de referência (o que o
contrato exige), o valor e a condição apurados ("Atendido", "Nao atendido", "Nao Verificado"…) e as datas de
verificação. É o dado do módulo de covenants da plataforma (situação de cumprimento e data da verificação).

O texto do PDF desalinha células de várias linhas, então a leitura é pela posição das palavras (PyMuPDF): as colunas
vêm do cabeçalho da tabela; cada item é a linha com conteúdo nas colunas de condição apurada ou de datas, e as linhas
vizinhas (texto quebrado) vão para o item mais próximo. Valores são copiados como estão no relatório, sem conversão.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

PARSER = "opea_relatorio_mensal 0.1"
COLUMNS = ("item", "valor_referencia", "condicao_referencia", "valor_apurado", "condicao_apurada",
           "data_verificacao", "proxima_verificacao")
HEADER_WORDS = ("Valor", "Condição", "Valor", "Condição", "Data", "Próxima")
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
GROUP = re.compile(r"^(Garantia|Obriga[çc][ãa]o|Covenant|Evento|Monitoramento|Condi[çc][ãa]o)[^:]*:$", re.IGNORECASE)
END_MARKERS = ("Este relatório foi elaborado", "Para mais informações")
STATUS = {
    "atendido": "atendido", "nao atendido": "nao_atendido", "não atendido": "nao_atendido",
    "nao verificado": "nao_verificado", "não verificado": "nao_verificado",
    "nao se aplica": "nao_se_aplica", "não se aplica": "nao_se_aplica", "-": "",
}


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
class MonthlyReport:
    competencia: str
    cetip: str
    comentario: str
    saldo_devedor: str
    monitoramentos: list[Monitoring]


def _lines(words: list[tuple]) -> list[tuple[float, list[tuple[float, str]]]]:
    """Agrupa palavras em linhas pela posição vertical (tolerância de 2 pt)."""

    lines: list[tuple[float, list[tuple[float, str]]]] = []
    for x0, y0, _x1, _y1, text, *_ in sorted(words, key=lambda w: (round(w[1]), w[0])):
        if lines and abs(lines[-1][0] - y0) <= 2:
            lines[-1][1].append((x0, text))
        else:
            lines.append((y0, [(x0, text)]))
    return [(y, sorted(items)) for y, items in lines]


def _header_bounds(lines: list[tuple[float, list[tuple[float, str]]]], index: int) -> list[float] | None:
    """Limites das colunas a partir dos títulos; o cabeçalho às vezes vem em alturas diferentes (o "Valor" de
    "Valor Apurado" alguns pontos abaixo), então junta os títulos das linhas a até 12 pt da linha com "Próxima"."""

    y, line = lines[index]
    texts = [t for _, t in line]
    if "Próxima" not in texts or "Condição" not in texts:
        return None
    starts = sorted(x for other_y, other in lines if abs(other_y - y) <= 12
                    for x, t in other if t in ("Valor", "Condição", "Data", "Próxima"))
    if len(starts) < 6:
        return None
    valor_ref, cond_ref, valor_apu, cond_apu, data, proxima = starts[:6]
    # valor de referência começa à esquerda do título ("R$" antes de "Valor"); condição de referência quase alinhada;
    # nas demais colunas o texto de uma célula longa ("Recebido 16.12.25") pode começar antes do título, então o
    # limite fica no meio do caminho entre os títulos vizinhos
    return [valor_ref - 30, cond_ref - 10, (cond_ref + valor_apu) / 2, (valor_apu + cond_apu) / 2,
            (cond_apu + data) / 2, (data + proxima) / 2]


def _column(x: float, bounds: list[float]) -> int:
    index = 0
    for i, bound in enumerate(bounds, start=1):
        if x >= bound:
            index = i
    return index


def _status(text: str) -> str:
    key = re.sub(r"\s+", " ", text.strip().lower())
    return STATUS.get(key, "outro" if key else "")


def parse_monitoring(pages_words: list[list[tuple]]) -> list[Monitoring]:
    """``pages_words``: palavras de cada página (``page.get_text('words')``)."""

    items: list[Monitoring] = []
    bounds: list[float] | None = None
    started = False
    group_type, group = "", ""
    for number, words in enumerate(pages_words, start=1):
        rows = []  # (y, tipo, conteúdo)
        page_lines = _lines(words)
        header_band: float | None = None
        for line_index, (y, line) in enumerate(page_lines):
            text = " ".join(t for _, t in line)
            if not started:
                started = text.startswith("Monitoramentos")
                continue
            if any(text.startswith(marker) for marker in END_MARKERS):
                break
            found = _header_bounds(page_lines, line_index)
            if found:
                bounds, header_band = found, y
                continue
            if header_band is not None and abs(y - header_band) <= 12:
                continue  # resto do cabeçalho ("Descrição", "Referência", "Valor Apurado")
            if bounds is None or text.startswith(("Descrição", "Referência")):
                continue
            # título de grupo ("Obrigaçao: Demonstrações Financeiras", "Garantia Acessória: Seguro Patrimonial",
            # "Rating: Rating Primário"): começa na margem, tem dois-pontos numa das três primeiras palavras e nunca
            # tem conteúdo nas colunas de condição apurada ou de datas
            head_words = [t for _, t in line[:3]]
            if (line[0][0] < 45 and any(t.endswith(":") for t in head_words)
                    and all(x < bounds[3] for x, _ in line)):
                rows.append((y, "grupo", text))
                continue
            cells = [[] for _ in COLUMNS]
            for x, t in line:
                cells[_column(x, bounds)].append(t)
            # o item é a linha com data de verificação ou com uma situação reconhecível; texto longo do valor apurado
            # que quebra de linha pode cair na área da condição apurada e não é item
            has_date = any(DATE.match(t) for t in cells[5] + cells[6])
            has_status = _status(" ".join(cells[4])) not in ("", "outro") or " ".join(cells[4]).strip() == "-"
            anchor = has_date or has_status
            if not anchor and cells[4]:
                cells[3], cells[4] = cells[3] + cells[4], []
            rows.append((y, "item" if anchor else "resto", cells))
        if not started:
            continue
        anchors = [i for i, r in enumerate(rows) if r[1] == "item"]
        pieces = {i: [[(rows[i][0], c)] for c in rows[i][2]] for i in anchors}  # por coluna: (altura, palavras)
        for i, (y, kind, cells) in enumerate(rows):
            if kind != "resto":
                continue
            # linha quebrada: vai para o item mais próximo sem atravessar um título de grupo
            candidates = [a for a in anchors if not any(rows[k][1] == "grupo" for k in range(min(a, i) + 1, max(a, i)))]
            if not candidates:
                continue
            target = min(candidates, key=lambda a: abs(rows[a][0] - y))
            if cells[1] and cells[1][0] == "-" and cells[0]:
                cells = [cells[0] + ["-"], cells[1][1:], *cells[2:]]  # hífen de fim de linha da descrição
            for col, words_in_cell in enumerate(cells):
                if words_in_cell:
                    pieces[target][col].append((y, words_in_cell))
        # as linhas de uma célula ficam na ordem de leitura (de cima para baixo)
        merged = {i: [[t for _, part in sorted(col, key=lambda p: p[0]) for t in part] for col in pieces[i]] for i in anchors}
        for i, (y, kind, content) in enumerate(rows):
            if kind == "grupo":
                head, _, rest = content.partition(":")
                group_type, group = head.strip(), rest.strip()
            elif kind == "item":
                c = [" ".join(words_in_cell) for words_in_cell in merged[i]]
                items.append(Monitoring(group_type, group, c[0], c[1], c[2], c[3], c[4], _status(c[4]),
                                        c[5], c[6], number))
    return items


def _section(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    return re.sub(r"\s+", " ", text[i + len(start): j if j > 0 else None]).strip()


def parse_report(path: Path) -> MonthlyReport:
    import pymupdf

    with pymupdf.open(path) as document:
        pages_words = [page.get_text("words") for page in document]
        text = "\n".join(page.get_text() for page in document)
    title = re.search(r"\b(Janeiro|Fevereiro|Março|Marco|Abril|Maio|Junho|Julho|Agosto|Setembro|Outubro|Novembro|"
                      r"Dezembro)/(\d{4})", text)
    cetip = re.search(r"\n\s*([0-9A-Z]{10,12})\s*\|", text)
    balance = re.search(r"Saldo Devedor Total:\s*(R\$\s*[\d.,]+)", text)
    return MonthlyReport(
        competencia=f"{title.group(1)}/{title.group(2)}" if title else "",
        cetip=cetip.group(1) if cetip else "",
        comentario=_section(text, "Comentários da Gestão", "Características")[:1500],
        saldo_devedor=balance.group(1) if balance else "",
        monitoramentos=parse_monitoring(pages_words),
    )


def as_rows(base: dict, report: MonthlyReport) -> list[dict]:
    head = {**base, "competencia": report.competencia, "cetip_no_relatorio": report.cetip,
            "saldo_devedor": report.saldo_devedor, "parser": PARSER}
    if not report.monitoramentos:
        return [{**head, "grupo_tipo": "", "grupo": "", "item": "(sem monitoramentos)", "valor_referencia": "",
                 "condicao_referencia": "", "valor_apurado": "", "condicao_apurada": "", "situacao": "",
                 "data_verificacao": "", "proxima_verificacao": "", "pagina": ""}]
    return [{**head, **asdict(item)} for item in report.monitoramentos]
