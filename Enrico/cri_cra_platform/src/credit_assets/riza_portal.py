"""Cliente da API pública do portal do investidor da Riza (ex-Virgo): https://investidor.rizasec.com/operations.

O portal (Next.js) chama ``https://aks-prod.virgo.inc/mtr/bff-portal/``, que responde sem login para:
  - ``v1/operations?pageNumber=N&pageSize=50``: operações (paginação começa em 0; ``page=`` é ignorado);
  - ``v1/operations/{id}/documents``: documentos com tipo, data e link de download;
  - ``v1/documents/{id}/download``: o arquivo.
Obrigações e garantias da API exigem login; o dado público é o "Relatório do Investidor" mensal, com o bloco
"Garantias & Covenants". Site da securitizadora é a fonte de menor prioridade (regra 3 do projeto).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

API = "https://aks-prod.virgo.inc/mtr/bff-portal/"
HEADERS = {"User-Agent": "pense-al-m-cri-cra/0.1 (portal do investidor Riza; uso interno de research)",
           "Accept": "application/json", "Origin": "https://investidor.rizasec.com"}
INVESTOR_REPORT = re.compile(r"Relat[óo]rio (?:do )?Investidor", re.IGNORECASE)


@dataclass(frozen=True)
class Download:
    document_id: int
    description: str
    issued_on: str
    content: bytes
    url: str
    sha256: str
    fetched_at: str


class RizaPortal:
    def __init__(self, min_interval_seconds: float = 1.0, opener: Callable[[urllib.request.Request], bytes] | None = None):
        self.min_interval = min_interval_seconds
        self._last = 0.0
        self._opener = opener or (lambda request: urllib.request.urlopen(request, timeout=180).read())

    def _get(self, url: str) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            return self._opener(urllib.request.Request(url, headers=HEADERS))
        finally:
            self._last = time.monotonic()

    def operations(self) -> list[dict]:
        items, page = [], 0
        while True:
            payload = json.loads(self._get(f"{API}v1/operations?pageNumber={page}&pageSize=50"))
            items.extend(payload.get("content") or [])
            meta = payload.get("metadata") or {}
            page += 1
            if page >= int(meta.get("totalPages") or 0) or not payload.get("content"):
                return list({item["id"]: item for item in items}.values())

    def documents(self, operation_id: str) -> list[dict]:
        payload = json.loads(self._get(f"{API}v1/operations/{operation_id}/documents"))
        return payload.get("content", payload) if isinstance(payload, dict) else payload

    def download(self, document: dict) -> Download:
        url = document["download"]
        data = self._get(url)
        return Download(int(document["id"]), str(document.get("description") or ""), str(document.get("emissionDate") or ""),
                        data, url, hashlib.sha256(data).hexdigest(), datetime.now(timezone.utc).isoformat())


def investor_reports(documents: list[dict]) -> list[dict]:
    """Relatórios do investidor (acompanhamento mensal), do mais recente ao mais antigo."""

    found = [d for d in documents if INVESTOR_REPORT.search(f"{d.get('type') or ''} {d.get('description') or ''}")]
    return sorted(found, key=lambda d: (str(d.get("emissionDate") or ""), int(d.get("id") or 0)), reverse=True)
