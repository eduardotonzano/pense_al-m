from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen

from debenture_search.services.snd_import_service import SndImportService


@dataclass(frozen=True)
class SndHttpResponse:
    """Representa uma resposta HTTP obtida pelo provider."""

    url: str
    status: int
    content_type: str
    text: str
    size_bytes: int


class SndProviderError(RuntimeError):
    """Erro controlado durante uma consulta ao SND."""


class SndProvider:
    """Obtem HTML do SND e envia o conteudo para importacao."""

    DEFAULT_BASE_URL = "https://www.debentures.com.br"
    DEFAULT_TIMEOUT_SECONDS = 20
    DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
    DEFAULT_USER_AGENT = "debenture-search/1.0"

    def __init__(
        self,
        db,
        import_service=None,
        http_open=None,
        base_url=None,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
        user_agent=DEFAULT_USER_AGENT,
    ):
        self.db = db
        self.import_service = import_service or SndImportService(db)
        self.http_open = http_open or urlopen
        self.base_url = str(
            base_url or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = int(max_response_bytes)
        self.user_agent = str(user_agent).strip()

        if self.timeout_seconds <= 0:
            raise ValueError("O timeout deve ser maior que zero.")

        if self.max_response_bytes <= 0:
            raise ValueError(
                "O tamanho maximo deve ser maior que zero."
            )

        if not self.user_agent:
            raise ValueError("O User-Agent e obrigatorio.")

    @staticmethod
    def normalize_asset_code(asset_code):
        """Normaliza e valida o codigo do ativo."""

        if asset_code is None:
            raise ValueError("O codigo do ativo e obrigatorio.")

        normalized = "".join(
            str(asset_code).strip().upper().split()
        )

        if not normalized:
            raise ValueError("O codigo do ativo e obrigatorio.")

        return normalized

    def build_url(self, asset_code):
        """Constroi a URL de consulta sem executar a requisicao."""

        normalized = self.normalize_asset_code(asset_code)
        encoded = quote(normalized, safe="")
        return self.base_url + "/exploreosnd/consultaadados/emissoesdedebentures/caracteristicas_d.asp?tip_deb=publicas&op_exc=Nada&ativo=" + encoded

    @staticmethod
    def response_status(response):
        """Extrai o status HTTP da resposta."""

        status = getattr(response, "status", None)

        if status is None and hasattr(response, "getcode"):
            status = response.getcode()

        return int(status or 200)

    @staticmethod
    def response_content_type(response):
        """Extrai o Content-Type da resposta."""

        headers = getattr(response, "headers", None)

        if headers is None:
            return ""

        if hasattr(headers, "get_content_type"):
            return str(headers.get_content_type())

        if hasattr(headers, "get"):
            raw = headers.get("Content-Type", "")
            return str(raw).split(";", 1)[0].strip().lower()

        return ""

    @staticmethod
    def response_charset(response):
        """Descobre o charset informado pela resposta."""

        headers = getattr(response, "headers", None)

        if headers is not None and hasattr(
            headers,
            "get_content_charset",
        ):
            return headers.get_content_charset() or "utf-8"

        return "utf-8"

    def fetch_html(self, asset_code):
        """Consulta o SND e devolve uma resposta validada."""

        url = self.build_url(asset_code)
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
            method="GET",
        )

        try:
            response = self.http_open(
                request,
                timeout=self.timeout_seconds,
            )

            try:
                status = self.response_status(response)
                content_type = self.response_content_type(response)
                payload = response.read(
                    self.max_response_bytes + 1
                )
                charset = self.response_charset(response)
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()

        except HTTPError as error:
            raise SndProviderError(
                "O SND respondeu com erro HTTP "
                + str(error.code)
                + "."
            ) from error
        except (TimeoutError, URLError) as error:
            raise SndProviderError(
                "Nao foi possivel consultar o SND."
            ) from error

        if status < 200 or status >= 300:
            raise SndProviderError(
                "O SND respondeu com status HTTP "
                + str(status)
                + "."
            )

        if len(payload) > self.max_response_bytes:
            raise SndProviderError(
                "A resposta do SND excedeu o tamanho permitido."
            )

        if not payload:
            raise SndProviderError(
                "O SND retornou uma resposta vazia."
            )

        try:
            text = payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            text = payload.decode("utf-8", errors="replace")

        looks_like_html = (
            "html" in content_type
            or "<html" in text.lower()
            or "<table" in text.lower()
        )

        if not looks_like_html:
            raise SndProviderError(
                "A resposta do SND nao parece ser HTML."
            )

        return SndHttpResponse(
            url=url,
            status=status,
            content_type=content_type or "text/html",
            text=text,
            size_bytes=len(payload),
        )

    def collect(
        self,
        asset_code,
        parser_version="1.0.0",
        observed_at=None,
        actor="snd_provider",
    ):
        """Consulta e importa os dados de uma debenture."""

        normalized = self.normalize_asset_code(asset_code)
        response = self.fetch_html(normalized)

        return self.import_service.import_html(
            response.text,
            request_url=response.url,
            request_parameters={"asset_code": normalized},
            http_status=response.status,
            parser_version=parser_version,
            observed_at=observed_at,
            actor=actor,
        )
