"""Cliente das páginas públicas de emissões da Canal Companhia de Securitização (www.canalsecuritizadora.com.br).

O site é PHP renderizado no servidor (sem API JSON) e os documentos são públicos, sem login:
  - ``emissoes?p=N``: catálogo com um cartão por série (CETIP, devedor, número da emissão, série, categoria,
    lastro, agente fiduciário, datas de emissão e de vencimento), 18 por página;
  - ``emissao-documentos/<cetip em minúsculas>/relatorios``: os "Relatório Mensal <Mês>/<AAAA>" da série, cada um com
    link direto para ``uploads/emissoes_documentos/<id>/<nome livre>.pdf`` (nome com acentos e "ª": vai codificado).
O PDF ("Relatório investidor") traz RESUMO por série (CETIP e ISIN), PAGAMENTOS e o quadro de GARANTIAS com os
fundos e índices (exigido × apurado × Enquadrado/Desenquadrado). Séries da mesma emissão costumam repetir o mesmo
PDF em uploads diferentes. A publicação costuma atrasar meses: a competência fica registrada.
O curl do Windows (schannel) recusa o certificado do site como revogado (CRYPT_E_REVOKED); o urllib do Python, que
não consulta revogação, responde normalmente. Site da securitizadora é a fonte de menor prioridade (regra 3 do
projeto): complementa, nunca sobrescreve CVM nem Termo. Cada arquivo baixado guarda URL, SHA-256 e data de obtenção.
"""
from __future__ import annotations

import calendar
import hashlib
import html
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

SITE = "https://www.canalsecuritizadora.com.br/"
USER_AGENT = "pense-al-m-cri-cra/0.1 (uso interno de research)"
MONTHS = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
          "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
CARD = re.compile(r'<a class="emissao-bloco-home[^"]*"\s+href="[^"]*/emissao/([0-9a-zA-Z]+)"(.*?)</a>', re.DOTALL)
CARD_HEADER = re.compile(r'emissao-home-header-info">(.*?)</div>', re.DOTALL)
CARD_FIELD = re.compile(r"<label>(.*?)</label>\s*<span>(.*?)</span>", re.DOTALL)
LAST_PAGE = re.compile(r"emissoes\?p=(\d+)")
DOCUMENT = re.compile(r'<a href="([^"]*uploads/emissoes_documentos/(\d+)/[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
DOCUMENT_TITLE = re.compile(r'download-bl-tit">(.*?)</div>', re.DOTALL)
MONTHLY = re.compile(r"Relat[óo]rio\s+(?:Mensal|investidor)", re.IGNORECASE)
TITLE_MONTH = re.compile(r"(" + "|".join(MONTHS) + r")\s*[/\-]?\s*(\d{4})", re.IGNORECASE)
NUMERIC_MONTH = re.compile(r"(?<!\d)(0[1-9]|1[0-2])\s*[/_.\-]\s*(20\d{2})(?!\d)")
FIELDS = {"Emissão": "emissao", "Oferta": "oferta", "Série": "serie", "Classe": "classe", "Categoria": "categoria",
          "Concentração": "concentracao", "Segmento": "segmento", "Lastro": "lastro",
          "Agente fiduciário": "agente_fiduciario", "Remuneração": "remuneracao", "Volume emitido": "volume_emitido",
          "Quantidade": "quantidade", "Data Emissão": "data_emissao", "Data Vencimento": "data_vencimento"}


@dataclass(frozen=True)
class Download:
    document_id: int
    content: bytes
    url: str
    sha256: str
    fetched_at: str


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_catalog_page(page: str) -> tuple[list[dict], int]:
    """Cartões (um por série) e o número da última página do catálogo."""

    cards = []
    for cetip, body in CARD.findall(page):
        header = CARD_HEADER.search(body)
        head = _text(header.group(1)) if header else ""
        code, _, debtor = head.partition(" ")
        card = {"codigo_cetip": cetip.upper(), "devedor": debtor.strip() if code.upper() == cetip.upper() else head}
        for label, value in CARD_FIELD.findall(body):
            key = FIELDS.get(_text(label))
            if key:
                card[key] = _text(value)
        cards.append(card)
    pages = [int(n) for n in LAST_PAGE.findall(page)]
    return cards, max(pages, default=1)


def competencia(title: str, url: str = "") -> str:
    """"AAAA-MM" pelo título ("Relatório Mensal Novembro/2024") ou, sem ele, pelo nome do arquivo ("... 03_2026.pdf",
    "Relatorio investidor_06_2024_99ªE.pdf", "... - 12.2025.pdf")."""

    match = TITLE_MONTH.search(title)
    if match:
        return f"{match.group(2)}-{MONTHS[match.group(1).lower()]:02d}"
    for text in (title, urllib.parse.unquote(url.rsplit("/", 1)[-1])):
        match = NUMERIC_MONTH.search(text)
        if match:
            return f"{match.group(2)}-{match.group(1)}"
    return ""


def parse_documents(page: str) -> list[dict]:
    """Documentos de uma aba (id do upload, título, URL codificada, competência quando o título traz)."""

    found = {}
    for href, ident, body in DOCUMENT.findall(page):
        title = DOCUMENT_TITLE.search(body)
        title_text = _text(title.group(1)) if title else ""
        url = html.unescape(href)
        if not url.startswith("http"):
            url = urllib.parse.urljoin(SITE, url)
        parts = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, urllib.parse.quote(urllib.parse.unquote(parts.path)),
                                       "", ""))
        found[int(ident)] = {"document_id": int(ident), "titulo": title_text, "url": url,
                             "competencia": competencia(title_text, url)}
    return list(found.values())


def is_live(card: dict, today: date | None = None) -> bool:
    """Série com vencimento hoje ou adiante (o catálogo não informa situação; sem data, conta como viva)."""

    today = today or date.today()
    due = str(card.get("data_vencimento") or "")
    try:
        return datetime.strptime(due, "%d/%m/%Y").date() >= today
    except ValueError:
        return True


def monthly_reports(documents: list[dict], today: date | None = None, max_age_days: int = 365) -> list[dict]:
    """Relatórios mensais com competência (último dia do mês) até ``max_age_days`` atrás, do mais recente ao mais
    antigo; na mesma competência, o upload mais novo (maior id) primeiro."""

    today = today or date.today()
    found = []
    for doc in documents:
        month = doc.get("competencia") or ""
        if not MONTHLY.search(doc.get("titulo") or "") and not MONTHLY.search(urllib.parse.unquote(doc.get("url") or "")):
            continue
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            continue
        year, number = int(month[:4]), int(month[5:])
        if (today - date(year, number, calendar.monthrange(year, number)[1])).days <= max_age_days:
            found.append(doc)
    return sorted(found, key=lambda d: (d["competencia"], d["document_id"]), reverse=True)


class CanalPortal:
    def __init__(self, min_interval_seconds: float = 1.0, opener: Callable[[urllib.request.Request], bytes] | None = None):
        self.min_interval = min_interval_seconds
        self._last = 0.0
        self._opener = opener or (lambda request: urllib.request.urlopen(request, timeout=120).read())

    def _get(self, url: str) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            return self._opener(request)
        finally:
            self._last = time.monotonic()

    def catalog(self, max_pages: int = 60) -> list[dict]:
        """Todos os cartões do catálogo (uma série por cartão), na ordem do site."""

        cards, last, page = [], 1, 1
        while page <= min(last, max_pages):
            found, last_seen = parse_catalog_page(self._get(f"{SITE}emissoes?p={page}").decode("utf-8", "replace"))
            if not found:
                break
            cards.extend(found)
            last = max(last, last_seen)
            page += 1
        return cards

    def reports(self, cetip: str) -> list[dict]:
        page = self._get(f"{SITE}emissao-documentos/{cetip.lower()}/relatorios").decode("utf-8", "replace")
        return parse_documents(page)

    def download(self, document: dict) -> Download:
        data = self._get(document["url"])
        return Download(int(document["document_id"]), data, document["url"], hashlib.sha256(data).hexdigest(),
                        datetime.now(timezone.utc).isoformat())
