from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from debenture_search.services.snd_import_service import SndImportService


@dataclass(frozen=True)
class SndHttpResponse:
    url: str
    status: int
    content_type: str
    text: str
    size_bytes: int


class SndProviderError(RuntimeError):
    pass


class SndProvider:
    DEFAULT_BASE_URL = "https://www.debentures.com.br"

    def __init__(self, db, import_service=None, http_open=None, base_url=None,
                 timeout_seconds=20, max_response_bytes=5 * 1024 * 1024,
                 user_agent="debenture-search/1.0"):
        self.db = db
        self.import_service = import_service or SndImportService(db)
        self.http_open = http_open or urlopen
        self.base_url = str(base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = int(max_response_bytes)
        self.user_agent = str(user_agent).strip()
        if self.timeout_seconds <= 0:
            raise ValueError("O timeout deve ser maior que zero.")
        if self.max_response_bytes <= 0:
            raise ValueError("O tamanho maximo deve ser maior que zero.")
        if not self.user_agent:
            raise ValueError("O User-Agent e obrigatorio.")

    @staticmethod
    def normalize_asset_code(value):
        if value is None:
            raise ValueError("O codigo do ativo e obrigatorio.")
        normalized = "".join(str(value).strip().upper().split())
        if not normalized:
            raise ValueError("O codigo do ativo e obrigatorio.")
        return normalized

    def build_url(self, asset_code):
        code = quote(self.normalize_asset_code(asset_code), safe="")
        return (self.base_url + "/exploreosnd/consultaadados/"
                "emissoesdedebentures/caracteristicas_e.asp?Ativo=" + code)

    @staticmethod
    def _content_type(response):
        headers = getattr(response, "headers", None)
        if headers is None:
            return ""
        if hasattr(headers, "get_content_type"):
            return str(headers.get_content_type()).lower()
        return str(headers.get("Content-Type", "")).split(";", 1)[0].lower()

    @staticmethod
    def _charset(response):
        headers = getattr(response, "headers", None)
        if headers is not None and hasattr(headers, "get_content_charset"):
            return headers.get_content_charset() or "latin-1"
        return "latin-1"

    def fetch_html(self, asset_code):
        url = self.build_url(asset_code)
        request = Request(url, headers={"User-Agent": self.user_agent,
                          "Accept": "text/html,application/vnd.ms-excel,text/plain"})
        try:
            response = self.http_open(request, timeout=self.timeout_seconds)
            try:
                status = int(getattr(response, "status", 200))
                content_type = self._content_type(response)
                payload = response.read(self.max_response_bytes + 1)
                charset = self._charset(response)
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
        except HTTPError as error:
            raise SndProviderError(f"O SND respondeu com erro HTTP {error.code}.") from error
        except (TimeoutError, URLError) as error:
            raise SndProviderError("Nao foi possivel consultar o SND.") from error

        if not 200 <= status < 300:
            raise SndProviderError(f"O SND respondeu com status HTTP {status}.")
        if len(payload) > self.max_response_bytes:
            raise SndProviderError("A resposta do SND excedeu o tamanho permitido.")
        if not payload:
            raise SndProviderError("O SND retornou uma resposta vazia.")
        try:
            text = payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            text = payload.decode("latin-1", errors="replace")

        html_like = "html" in content_type or "<html" in text.lower() or "<table" in text.lower()
        tabular_like = (content_type in {"application/vnd.ms-excel", "text/plain"}
                        and "	" in text and "codigo do ativo" in text.lower())
        if not (html_like or tabular_like):
            raise SndProviderError("A resposta do SND nao possui formato reconhecido.")
        return SndHttpResponse(url, status, content_type or "text/plain", text, len(payload))

    def collect(self, asset_code, parser_version="2.0.0", observed_at=None,
                actor="snd_provider"):
        code = self.normalize_asset_code(asset_code)
        response = self.fetch_html(code)
        return self.import_service.import_document(
            response.text, asset_code=code, content_type=response.content_type,
            request_url=response.url, request_parameters={"asset_code": code},
            http_status=response.status, parser_version=parser_version,
            observed_at=observed_at, actor=actor)
