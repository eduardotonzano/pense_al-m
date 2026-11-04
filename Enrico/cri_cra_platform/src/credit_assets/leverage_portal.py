"""Portal público de emissões da Leverage Companhia Securitizadora: https://portal.leveragesec.com.br/emissoes/escolha.

O portal (SPA React sobre ``https://api.leveragesec.com.br``) abre sozinho uma sessão anônima de "Visitante" e, com ela,
mostra todas as emissões, o Enquadramento e os Documentos, sem login. A API não aceita chamada fora do portal (o
``POST /auth/guest`` direto volta 403), então o cliente usa o navegador headless (Playwright) no fluxo normal de um
visitante, sem forjar cabeçalho: abre as páginas e lê as respostas JSON que o próprio portal carrega.
  - ``/emissoes/escolha`` carrega ``GET /v1/emissoes/?detalhes=true``: emissões, séries, CETIP e situação (sem ISIN);
  - ``/emissoes/<id>/documentos`` carrega ``GET /v1/arquivos?dim_emissao_id=<id>``: documentos (id, tipo,
    ``nome_original``, ``enviado_em``); o clique no nome baixa ``/v1/arquivos/<id>/download``.
A aba Obrigações exige conta e não é usada. Site da securitizadora é a fonte de menor prioridade (regra 3 do projeto).
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone

PORTAL = "https://portal.leveragesec.com.br"
API = "https://api.leveragesec.com.br"
USER_AGENT = "pense-al-m-cri-cra/0.1 (uso interno de research)"
LIVE_TYPES = ("CRI", "CRA")
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
# nome_original: "011E_CRI Yvy Supreme-Relatório Mensal-09-2026.pdf" (o portal exibe "... - Relatório Mensal - set/2026.pdf")
MONTHLY_REPORT = re.compile(r"Relat[óo]rio Mensal\s*-\s*(\d{2})-(\d{4})", re.IGNORECASE)


@dataclass(frozen=True)
class Download:
    arquivo_id: int
    nome_original: str
    enviado_em: str
    content: bytes
    url: str
    sha256: str
    fetched_at: str


def live_emissions(emissions: list[dict]) -> list[dict]:
    """CRI/CRA com ao menos uma série "Ativa" (as "Não Iniciada" ainda não têm relatório)."""

    return [e for e in emissions if e.get("emissao_tipo") in LIVE_TYPES
            and any((s.get("situacao") or "") == "Ativa" for s in e.get("detalhes") or [])]


def monthly_reports(files: list[dict]) -> list[tuple[str, dict]]:
    """("AAAA-MM", arquivo) dos relatórios mensais de acompanhamento, do mais recente ao mais antigo."""

    found = []
    for item in files:
        match = MONTHLY_REPORT.search(str(item.get("nome_original") or ""))
        if match and item.get("tipo") == "Relatorios" and not item.get("privado"):
            found.append((f"{match.group(2)}-{match.group(1)}", item))
    return sorted(found, key=lambda pair: (pair[0], str(pair[1].get("enviado_em") or ""), int(pair[1]["id"])), reverse=True)


def recent_enough(month: str, today: date, max_age_days: int = 180) -> bool:
    """Competência "AAAA-MM" cujo último dia está a até ``max_age_days`` de hoje."""

    year, number = int(month[:4]), int(month[5:7])
    last_day = date(year + (number == 12), number % 12 + 1, 1).toordinal() - 1
    return today.toordinal() - last_day <= max_age_days


def display_label(month: str) -> re.Pattern:
    """Texto que o portal mostra para o relatório ("Relatório Mensal - set/2026"), usado para clicar no link."""

    return re.compile(rf"Relat[óo]rio Mensal\s*-\s*{MONTHS[int(month[5:7]) - 1]}/{month[:4]}", re.IGNORECASE)


class LeveragePortal:
    """Navegador headless no fluxo de visitante; uma ação (página ou clique) por ``min_interval_seconds``.

    Uso: ``with LeveragePortal() as portal: portal.emissions(); portal.documents(id); portal.download(month, arquivo)``.
    """

    def __init__(self, min_interval_seconds: float = 1.0, timeout_seconds: float = 60.0):
        self.min_interval = min_interval_seconds
        self.timeout_ms = int(timeout_seconds * 1000)
        self._last = 0.0
        self._play = self._browser = self._page = None
        self._current: int | None = None  # emissão cuja página de documentos está aberta

    def __enter__(self) -> "LeveragePortal":
        from playwright.sync_api import sync_playwright

        self._play = sync_playwright().start()
        self._browser = self._play.chromium.launch()
        context = self._browser.new_context(user_agent=USER_AGENT, accept_downloads=True)
        context.set_default_timeout(self.timeout_ms)
        self._page = context.new_page()
        return self

    def __exit__(self, *_exc) -> None:
        if self._browser:
            self._browser.close()
        if self._play:
            self._play.stop()

    def _pause(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)

    def _open(self, path: str, wanted) -> object:
        """Abre a página e devolve o JSON da resposta da API que satisfaz ``wanted(response)``."""

        self._pause()
        try:
            with self._page.expect_response(lambda r: r.url.startswith(API) and r.request.method == "GET" and wanted(r),
                                            timeout=self.timeout_ms) as response:
                self._page.goto(PORTAL + path, wait_until="domcontentloaded", timeout=self.timeout_ms)
            value = response.value
            if value.status != 200:
                raise RuntimeError(f"HTTP {value.status} em {value.url}")
            return value.json()
        finally:
            self._last = time.monotonic()

    def emissions(self) -> list[dict]:
        self._current = None
        return self._open("/emissoes/escolha", lambda r: "/v1/emissoes" in r.url)

    def documents(self, emissao_id: int) -> list[dict]:
        self._current = None
        files = self._open(f"/emissoes/{emissao_id}/documentos",
                           lambda r: f"/v1/arquivos?dim_emissao_id={emissao_id}" in r.url)
        self._current = int(emissao_id)
        return files

    def download(self, month: str, item: dict) -> Download:
        """Clica no relatório da competência na página de documentos aberta por ``documents()``."""

        if self._current != int(item["dim_emissao_id"]):
            raise RuntimeError("abra antes a página de documentos da emissão")
        self._pause()
        try:
            link = self._page.get_by_text(display_label(month)).first
            link.wait_for(state="visible", timeout=self.timeout_ms)
            with self._page.expect_response(lambda r: r.url.startswith(API) and "/download" in r.url,
                                            timeout=self.timeout_ms) as response:
                with self._page.expect_download(timeout=self.timeout_ms) as pending:
                    link.click()
            # o link clicado tem de ser o arquivo escolhido (dois uploads da mesma competência, por exemplo)
            if f"/v1/arquivos/{item['id']}/download" not in response.value.url:
                raise RuntimeError(f"o portal baixou outro arquivo: {response.value.url}")
            path = pending.value.path()
            with open(path, "rb") as handle:
                data = handle.read()
        finally:
            self._last = time.monotonic()
        if not data.startswith(b"%PDF"):
            raise RuntimeError("download não é PDF")
        return Download(int(item["id"]), str(item.get("nome_original") or ""), str(item.get("enviado_em") or ""), data,
                        f"{API}/v1/arquivos/{item['id']}/download", hashlib.sha256(data).hexdigest(),
                        datetime.now(timezone.utc).isoformat())
