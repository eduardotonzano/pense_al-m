"""Cliente do portal de emissões da Bari Securitizadora (https://barisec.com.br/emissoes).

O site (Next.js) lê os dados de um Strapi CMS do Banco Bari, tudo aberto sem login:
  - ``strapicms.bancobari.com.br/api/emissions``: catálogo paginado (100 por página), uma linha por série, com código
    CETIP (``code``), ISIN (às vezes "-"), número da emissão e da série, lastro e situação ("Ativo", "Inativo",
    "Resgatado antecipadamente", "Vencido");
  - ``barisec.com.br/_next/data/<buildId>/emissoes/<CETIP>.json``: a página da série, com ``emissionCrisDocuments``
    (nome, data, ``documentType`` Termos/Comunicados/Assembleia/Relatório, ``reportType`` Mensais/Fiduciário/
    Performance e ``file.url``); o ``buildId`` sai do HTML da página e muda a cada deploy do site;
  - ``strapicms.bancobari.com.br/uploads/<hash>.pdf``: o arquivo, sem assinatura.
Na mesma lista "Mensais" convivem o relatório de gestão (o que interessa: "Relatório de Gestão", "Relatório
gerencial", "Relatório Mensal", arquivos ``CRI_41_E_Relatorio_gerencial_10_2026``, ``Relatorio_Razao_Garantia_42_
Emissao_08_26``…) e o Informe Mensal da CVM (Suplemento E, já coletado no Fundos.NET), que às vezes também vem com o
nome "Relatório Mensal"; o que separa os dois é o arquivo do informe (``20251101_42_CRI_42``).
Site da securitizadora é a fonte de menor prioridade (regra 3 do projeto): complementa, nunca sobrescreve CVM nem Termo.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

CMS = "https://strapicms.bancobari.com.br/api/"
SITE = "https://barisec.com.br/"
USER_AGENT = "pense-al-m-cri-cra/0.1 (uso interno de research)"
LIVE = "Ativo"
CETIP = re.compile(r"^(\d{2}[A-L]\d{7}|[A-Z]{3,4}\d{8}|CR[AI]\d{3}[0-9A-Z]{5})$")
INFORME_FILE = re.compile(r"^\d{8}_\d+_CR[IA]_")
MANAGEMENT = re.compile(r"gest[ãa]o|gerencial|relat[óo]rio\s+mensal|acompanhamento|raz[ãa]o\s+de\s+garantia|performance",
                        re.IGNORECASE)
NOT_MANAGEMENT = re.compile(r"informe|fiduci[áa]rio|anual|demonstra[çc]|assembl|edital|\bata\b|termo", re.IGNORECASE)
# competência no nome do documento ("- 10.2026", "- 09/2025", "Relatório Mensal 01.2025") ou do arquivo
# ("_gerencial_10_2026_", "_Relatorio_Mensal_2026_08_", "_Mensal_CRI_39_E_202512_", "_Emissao_08_26_")
NAME_MONTH = re.compile(r"(?<!\d)(\d{1,2})[./](20\d{2})(?!\d)")
FILE_PATTERNS = (
    re.compile(r"_(\d{1,2})_(20\d{2})(?:_|$)"),
    re.compile(r"_(20\d{2})_(\d{2})(?:_|$)"),
    re.compile(r"_(20\d{2})(\d{2})(?:_|$)"),
    re.compile(r"_(\d{2})_(\d{2})(?:_|$)"),
)


@dataclass(frozen=True)
class Download:
    content: bytes
    url: str
    sha256: str
    fetched_at: str


class BariPortal:
    def __init__(self, min_interval_seconds: float = 1.0, opener: Callable[[urllib.request.Request], bytes] | None = None):
        self.min_interval = min_interval_seconds
        self._last = 0.0
        self._opener = opener or (lambda request: urllib.request.urlopen(request, timeout=120).read())
        self._build_id = ""

    def _get(self, url: str) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
        try:
            return self._opener(request)
        finally:
            self._last = time.monotonic()

    def emissions(self, page_size: int = 100) -> list[dict]:
        items, page = [], 1
        while True:
            query = urllib.parse.urlencode({"pagination[pageSize]": page_size, "pagination[page]": page})
            payload = json.loads(self._get(CMS + "emissions?" + query))
            items.extend(payload.get("data") or [])
            pages = int(((payload.get("meta") or {}).get("pagination") or {}).get("pageCount") or 1)
            if page >= pages or page >= 20:
                return items
            page += 1

    def build_id(self, code: str, refresh: bool = False) -> str:
        if refresh or not self._build_id:
            html = self._get(SITE + "emissoes/" + urllib.parse.quote(code)).decode("utf-8", "replace")
            match = re.search(r'"buildId":"([^"]+)"', html)
            if not match:
                raise ValueError("buildId não encontrado na página da emissão")
            self._build_id = match.group(1)
        return self._build_id

    def series_page(self, code: str) -> dict:
        """``pageProps`` da página da série (``emission``, ``emissionCrisDocuments``, ``emissionFinancialStatements``).
        Se o site foi publicado de novo no meio da coleta, o buildId antigo dá 404: busca o novo e tenta uma vez."""

        for refresh in (False, True):
            url = f"{SITE}_next/data/{self.build_id(code, refresh)}/emissoes/{urllib.parse.quote(code)}.json"
            try:
                return json.loads(self._get(url)).get("pageProps") or {}
            except urllib.error.HTTPError as error:
                if error.code != 404 or refresh:
                    raise
        return {}

    def download(self, url: str) -> Download:
        data = self._get(url)
        return Download(data, url, hashlib.sha256(data).hexdigest(), datetime.now(timezone.utc).isoformat())


def is_live(series: dict) -> bool:
    """Série "Ativo" com código CETIP válido (o catálogo tem um registro de teste com code "emission" e uma série com
    code "-", sem página própria)."""

    return series.get("emissionStatus") == LIVE and bool(CETIP.match(str(series.get("code") or "").strip()))


def file_url(document: dict) -> str:
    file = document.get("file") or {}
    if isinstance(file.get("data"), dict):  # formato antigo do Strapi (``data.attributes``)
        file = file["data"].get("attributes") or file["data"]
    return str(file.get("url") or "")


def is_management_report(document: dict) -> bool:
    """Relatório de gestão/acompanhamento da Bari (não o Informe Mensal da CVM nem o relatório anual do agente
    fiduciário)."""

    name = str(document.get("documentName") or "")
    url = file_url(document)
    stem = url.rsplit("/", 1)[-1]
    if not url.lower().endswith(".pdf") or INFORME_FILE.match(stem):
        return False
    if str(document.get("reportType") or "") == "Fiduciário" or NOT_MANAGEMENT.search(name):
        return False
    is_report = document.get("documentType") == "Relatório" or document.get("reportType") in ("Mensais", "Performance")
    return is_report and bool(MANAGEMENT.search(name) or MANAGEMENT.search(stem.replace("_", " ")))


def competencia(document: dict) -> str:
    """"AAAA-MM" do nome do documento, do arquivo ou, por último, da data do documento."""

    name = str(document.get("documentName") or "")
    match = NAME_MONTH.search(name)
    if match and 1 <= int(match.group(1)) <= 12:
        return f"{match.group(2)}-{int(match.group(1)):02d}"
    stem = file_url(document).rsplit("/", 1)[-1].rsplit(".", 1)[0]
    stem = re.sub(r"_[0-9a-f]{10}$", "", stem)  # sufixo de hash do Strapi
    for number, pattern in enumerate(FILE_PATTERNS):
        match = pattern.search(stem)
        if not match:
            continue
        a, b = match.group(1), match.group(2)
        year, month = (b, a) if number == 0 else (a, b) if number in (1, 2) else ("20" + b, a)
        if 1 <= int(month) <= 12:
            return f"{year}-{int(month):02d}"
    return str(document.get("date") or "")[:7]


def management_reports(documents: list[dict], today: date | None = None, max_age_days: int = 180) -> list[dict]:
    """Relatórios de gestão em PDF com data até ``max_age_days`` atrás, do mais recente ao mais antigo (pela
    competência; empate: o publicado por último, que costuma ser a versão corrigida). Repetidos pela URL saem."""

    today = today or date.today()
    found, seen = [], set()
    for doc in documents:
        url = file_url(doc)
        if url in seen or not is_management_report(doc):
            continue
        seen.add(url)
        try:
            age = (today - date.fromisoformat(str(doc.get("date") or "")[:10])).days
        except ValueError:
            continue
        if age <= max_age_days:
            found.append(doc)
    return sorted(found, key=lambda d: (competencia(d), str(d.get("date") or ""), str(d.get("createdAt") or ""),
                                        int(d.get("id") or 0)), reverse=True)
