"""Cliente da API pública do portal VERT Data da Vert Companhia Securitizadora (https://data.vert-capital.app).

O portal (React Router) carrega os dados por JSON público, sem login:
  - ``api/emission-table?page=0&page_size=400``: todas as emissões numa chamada (id interno, external_id, nome,
    título CRI/CRA/DEB…, séries com código CETIP, ISIN, vencimento e ``isClosed``);
  - ``api/documents-table/{id}?category=Relatórios``: documentos da emissão, do mais recente ao mais antigo; o
    ``category`` é obrigatório (sem ele: "invalid Category") e vai em UTF-8 com percent-encoding;
  - ``s3PublicUrl`` de cada documento: URL pré-assinada da AWS S3 que expira em minutos, então é pedida de novo a
    cada coleta e guardada no manifesto sem a assinatura; a resposta fica mais lenta quanto maior o ``page_size``.
O id interno do VERT Data não é o número da emissão (/emissao/131 é a 107ª CRI). Site da securitizadora é a fonte de
menor prioridade (regra 3 do projeto): complementa, nunca sobrescreve CVM nem Termo.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

API = "https://data.vert-capital.app/api/"
USER_AGENT = "pense-al-m-cri-cra/0.1 (uso interno de research)"
REPORTS = "Relatórios"
# "Relatório Mensal de Acompanhamento (2026.09)"; a versão "- Excel"/"RMA Excel" fica de fora (o leitor é de PDF)
MONTHLY_REPORT = re.compile(r"Relat[óo]rio\s+Mensal\s+de\s+Acompanhamento", re.IGNORECASE)
EXCEL = re.compile(r"excel|\.xlsx?\b", re.IGNORECASE)


@dataclass(frozen=True)
class Download:
    document_id: int
    name: str
    reference_date: str
    content: bytes
    url: str  # sem a assinatura (query string) da S3
    sha256: str
    fetched_at: str


class VertPortal:
    def __init__(self, min_interval_seconds: float = 1.0, opener: Callable[[urllib.request.Request], bytes] | None = None):
        self.min_interval = min_interval_seconds
        self._last = 0.0
        self._opener = opener or (lambda request: urllib.request.urlopen(request, timeout=120).read())

    def _get(self, url: str) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
        try:
            return self._opener(request)
        finally:
            self._last = time.monotonic()

    def emissions(self) -> list[dict]:
        payload = json.loads(self._get(API + "emission-table?page=0&page_size=1000"))
        return payload.get("registros") or []

    def documents(self, emission_id: int, category: str = REPORTS, page_size: int = 10) -> list[dict]:
        """Os ``page_size`` documentos mais recentes da categoria. A API gera uma URL assinada por documento e leva
        ~0,45 s por item (100 itens = 20 s), então a coleta pede só a primeira página curta."""

        query = urllib.parse.urlencode({"page": 0, "page_size": page_size, "category": category})
        payload = json.loads(self._get(f"{API}documents-table/{int(emission_id)}?{query}"))
        return payload.get("registros") or []

    def download(self, document: dict) -> Download:
        data = self._get(document["s3PublicUrl"])
        return Download(int(document["id"]), str(document.get("name") or ""), str(document.get("referenceDate") or ""),
                        data, str(document["s3PublicUrl"]).split("?")[0], hashlib.sha256(data).hexdigest(),
                        datetime.now(timezone.utc).isoformat())


def is_live(emission: dict, today: date | None = None) -> bool:
    """CRI/CRA com ao menos uma série aberta (``isClosed`` falso e vencimento não passado)."""

    if str(emission.get("financialTitle") or "").upper() not in ("CRI", "CRA"):
        return False
    today = today or date.today()
    for series in emission.get("series") or []:
        due = str(series.get("due_date") or "")[:10]
        if not series.get("isClosed") and (not due or due >= today.isoformat()):
            return True
    return False


def monthly_reports(documents: list[dict], today: date | None = None, max_age_days: int = 180) -> list[dict]:
    """Relatórios Mensais de Acompanhamento em PDF com data-base até ``max_age_days`` atrás, do mais recente ao mais
    antigo (empate: o publicado por último)."""

    today = today or date.today()
    found = []
    for doc in documents:
        name, url = str(doc.get("name") or ""), str(doc.get("s3PublicUrl") or "").split("?")[0]
        ref = str(doc.get("referenceDate") or "")[:10]
        if not MONTHLY_REPORT.search(name) or EXCEL.search(name) or EXCEL.search(url) or doc.get("isNeedInfoDownload"):
            continue
        try:
            age = (today - date.fromisoformat(ref)).days
        except ValueError:
            continue
        if age <= max_age_days:
            found.append(doc)
    return sorted(found, key=lambda d: (str(d.get("referenceDate") or ""), str(d.get("createdAt") or ""),
                                        int(d.get("id") or 0)), reverse=True)
