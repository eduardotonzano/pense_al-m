"""Relatórios mensais publicados pela Eco Securitizadora na página pública de cada emissão.

A lista https://ecoagro.agr.br/emissoes (``?page=N``) traz cada emissão numa linha ``<tr class="emissao" data-id="N">``
que abre ``/emissoes-integra/N``; a página traz todos os documentos em ``/public/storage/Arquivo/<timestamp><nome>``.
Dois relatórios mensais:
  - "Relatório de Gestão" (``..._Mes_AAAA-Relatorio Mensal.pdf``): saldo do valor nominal (PU), valor atualizado dos
    créditos e saldos dos fundos de retenção e de despesas;
  - "Relatório de Acompanhamento Mensal" (só algumas emissões): garantias, saldo devedor, aderência ao Termo de
    Securitização (critérios de elegibilidade) e recebíveis vencidos por faixa.
Os valores são copiados como estão; site da securitizadora é a fonte de menor prioridade (regra 3 do projeto).
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

STORAGE = re.compile(r'href="(https://ecoagro\.agr\.br/public/storage/Arquivo/(\d{10})[^"]+)"')
MANAGEMENT = re.compile(r"relat[óo]rio mensal\.pdf|relat[óo]rio de gest", re.IGNORECASE)
FOLLOW_UP = re.compile(r"acompanhamento mensal", re.IGNORECASE)
MONEY = r"R\$\s*-?[\d.]+,\d{2}"
PU = r"R\$\s*[\d.]+,\d{2,8}"


@dataclass(frozen=True)
class Link:
    url: str
    uploaded: int  # carimbo Unix no nome do arquivo = data de publicação
    name: str
    kind: str  # gestao | acompanhamento


def report_links(page_html: str) -> list[Link]:
    """Relatórios mensais da página da emissão, do mais recente ao mais antigo."""

    links = []
    for url, stamp in STORAGE.findall(page_html):
        name = urllib.parse.unquote(url.split("/Arquivo/", 1)[1])[10:]
        kind = "acompanhamento" if FOLLOW_UP.search(name) else "gestao" if MANAGEMENT.search(name) else ""
        if kind:
            links.append(Link(url, int(stamp), name, kind))
    return sorted({link.url: link for link in links}.values(), key=lambda link: link.uploaded, reverse=True)


def _after(text: str, label: str, pattern: str) -> str:
    found = re.search(re.escape(label) + r"[^\n]*\n(?:\s*\n)*\s*(" + pattern + ")", text, re.IGNORECASE)
    return re.sub(r"\s+", " ", found.group(1)).strip() if found else ""


def parse_management(text: str) -> dict[str, str]:
    period = re.search(r"Relat[óo]rio de Gest[ãa]o\s*-\s*([A-Za-zçÇ]+/\d{4})", text)
    start = text.find("Saldo do Valor Nominal Unitário")
    end = text.find("Valor atualizado", start)
    block = text[start:end] if start >= 0 else ""
    # uma linha por série: "1ª Série - 190ª Emissão: R$ 457,03091931"
    series = re.findall(r"(\d+)ª\s*S[ée]rie[^:\n]*:\s*(" + PU + ")", block)
    return {
        "competencia": period.group(1) if period else "",
        "pu_saldo": "; ".join(f"série {n}: {re.sub(r'\s+', ' ', value)}" for n, value in series),
        "valor_creditos": _after(text, "Valor atualizado de todos os Créditos", MONEY),
        "fundo_retencao": _after(text, "(Fundo de Retenção)", MONEY),
        "fundo_despesas": _after(text, "(Fundo de Despesas)", MONEY),
        "fundo_reserva": _after(text, "(Fundo de Reserva)", MONEY),
        "vencimento_final": _after(text, "Data de Vencimento Final", r"\d{2}/\d{2}/\d{4}"),
    }


def _value_below(words: list[tuple], label: str, pattern: str = MONEY, max_dy: float = 45) -> str:
    """Primeiro valor abaixo do rótulo na mesma coluna (layout em várias colunas)."""

    tokens = label.lower().split()
    texts = [w[4].lower() for w in words]
    for i in range(len(words) - len(tokens) + 1):
        if texts[i:i + len(tokens)] == tokens:
            x0, y0 = words[i][0], words[i][1]
            x1 = words[i + len(tokens) - 1][2]
            below = sorted((w for w in words if 0 < w[1] - y0 <= max_dy and x0 - 15 <= w[0] <= x1 + 60),
                           key=lambda w: (round(w[1]), w[0]))
            line = " ".join(w[4] for w in below)
            found = re.search(pattern, line)
            if found:
                return found.group(0)
    return ""


def parse_follow_up(pages_words: list[list[tuple]], text: str) -> dict[str, str]:
    words = [w for page in pages_words for w in page]
    adherence = re.findall(r"(N[ãa]o\s+Aderente|Aderente|Desenquadrad\w*|Enquadrad\w*)", text)
    not_ok = [a for a in adherence if a.lower().startswith(("não", "nao", "desenq"))]
    overdue = _value_below(words, "Total de recebíveis vencidos:")
    return {
        "total_garantias": _value_below(words, "TOTAL DE GARANTIAS:"),
        "saldo_devedor": _value_below(words, "SALDO DEVEDOR:", MONEY, 60),
        "alienacao_fiduciaria_imovel": _value_below(words, "Alienação Fiduciária de Imóvel:", MONEY, 15),
        "caixa_fundo_despesas": _value_below(words, "Caixa Fundo de Despesas:"),
        "caixa_fundo_retencao": _value_below(words, "Caixa Fundo de Retenção:"),
        "recebiveis_vencidos": overdue,
        "aderencia_itens": str(len(adherence)),
        "aderencia_nao_aderentes": str(len(not_ok)),
    }


def money(value: str) -> float | None:
    found = re.search(r"-?[\d.]+,\d+", value or "")
    return float(found.group(0).replace(".", "").replace(",", ".")) if found else None
