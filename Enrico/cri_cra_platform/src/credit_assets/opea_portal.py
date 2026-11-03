"""Cliente da API pública do portal de emissões da Opea (https://app.opea.com.br/pt/emissoes).

O portal é um app em JavaScript sobre a API ``https://app.opea.com.br/bff/v1/api/``, que responde sem login:
  - ``emissao/passivosoperacoes``: todas as emissões numa chamada (código Opea, CETIP, ISIN, devedor, situação);
  - ``evento/diariobordo/eventos`` (POST): o "diário de bordo" da emissão, com atas, editais, Informe Mensal CVM e o
    "Relatório Mensal Gestão Fiduciária - MM/AAAA";
  - ``evento/diariobordo/anexos?idDiarioBordo=``: o anexo de um evento, como ZIP em base64.

Site da securitizadora é a fonte de menor prioridade (regra 3 do projeto): complementa, nunca sobrescreve CVM nem Termo.
Cada arquivo baixado guarda URL, SHA-256 e data de obtenção.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

API = "https://app.opea.com.br/bff/v1/api/"
USER_AGENT = "pense-al-m-cri-cra/0.1 (portal de emissoes Opea; uso interno de research)"
MONTHLY_REPORT = re.compile(r"Relat[óo]rio Mensal Gest[ãa]o Fiduci[áa]ria\s*-\s*(\d{2})/(\d{4})", re.IGNORECASE)


@dataclass(frozen=True)
class Attachment:
    event_id: int
    title: str
    occurred_on: str
    file_name: str
    content: bytes
    url: str
    sha256: str
    fetched_at: str


class OpeaPortal:
    def __init__(self, min_interval_seconds: float = 1.0, opener: Callable[[urllib.request.Request], bytes] | None = None):
        self.min_interval = min_interval_seconds
        self._last = 0.0
        self._opener = opener or (lambda request: urllib.request.urlopen(request, timeout=120).read())

    def _call(self, path: str, body: dict | None = None) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(API + path, data=data, headers=headers, method="POST" if body is not None else "GET")
        try:
            return self._opener(request)
        finally:
            self._last = time.monotonic()

    def emissions(self) -> list[dict]:
        payload = json.loads(self._call("emissao/passivosoperacoes"))
        return payload["content"]["emissoes"]["items"]

    def events(self, codigo_opea: str, page_size: int = 100) -> list[dict]:
        items, page = [], 1
        while True:
            payload = json.loads(self._call("evento/diariobordo/eventos", {
                "pagina": page, "tamanhoPagina": page_size, "codigoOpea": codigo_opea, "tiposEventos": None}))
            block = (payload.get("content") or {}).get("eventosDiarioBordoPortal") or {}
            items.extend(block.get("items") or [])
            if not block.get("hasItems") or len(items) >= int(block.get("totalCount") or 0) or page >= 50:
                return items
            page += 1

    def attachments(self, event: dict) -> list[Attachment]:
        """Arquivos dos anexos de um evento (o portal entrega um ZIP em base64 por anexo)."""

        found = []
        for anexo in event.get("diarioBordoAnexoList") or []:
            ident = str(anexo.get("idDiarioBordo") or "")
            if not ident:
                continue
            path = "evento/diariobordo/anexos?" + urllib.parse.urlencode({"idDiarioBordo": ident})
            payload = json.loads(self._call(path))
            content = payload.get("content")
            if not isinstance(content, str):
                continue
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(content))) as archive:
                for name in archive.namelist():
                    data = archive.read(name)
                    found.append(Attachment(
                        int(event["id"]), str(event.get("titulo") or ""), str(event.get("dataOcorrencia") or ""),
                        name, data, API + path, hashlib.sha256(data).hexdigest(),
                        datetime.now(timezone.utc).isoformat()))
        return found


def monthly_reports(events: list[dict]) -> list[tuple[str, dict]]:
    """("AAAA-MM", evento) dos relatórios mensais de gestão fiduciária, do mais recente ao mais antigo."""

    reports = []
    for event in events:
        match = MONTHLY_REPORT.search(str(event.get("titulo") or event.get("tituloPortal") or ""))
        if match:
            reports.append((f"{match.group(2)}-{match.group(1)}", event))
    return sorted(reports, key=lambda item: (item[0], int(item[1]["id"])), reverse=True)
