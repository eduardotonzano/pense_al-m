import argparse
import sys
from dataclasses import dataclass

from debenture_search.parsers.snd_parser import SndParser
from debenture_search.parsers.snd_tabular_parser import SndTabularParser
from debenture_search.providers.snd_provider import SndProvider
from debenture_search.providers.snd_provider import SndProviderError


DEFAULT_ASSET_CODE = "PETR27"


@dataclass(frozen=True)
class SmokeTestResult:
    """Resume uma verificacao de conectividade com o SND."""

    asset_code: str
    url: str
    http_status: int
    content_type: str
    response_size_bytes: int
    parsed_asset_code: str | None
    parsed_isin: str | None
    observation_count: int


class DisabledImportService:
    """Impede gravacao acidental durante o smoke test."""

    def import_document(self, document, **kwargs):
        raise RuntimeError(
            "O smoke test nao permite importacao no banco."
        )

    def import_html(self, document, **kwargs):
        return self.import_document(document, **kwargs)


def build_provider(http_open=None):
    """Cria um provider configurado somente para leitura."""

    return SndProvider(
        db=object(),
        import_service=DisabledImportService(),
        http_open=http_open,
        timeout_seconds=20,
        max_response_bytes=5 * 1024 * 1024,
        user_agent="debenture-search-smoke-test/2.0",
    )


def is_tabular_response(response):
    """Identifica o formato tabular retornado pelo SND."""

    content_type = str(response.content_type or "").lower()
    text = response.text

    return (
        content_type in {
            "application/vnd.ms-excel",
            "text/plain",
        }
        or (
            "\t" in text
            and "codigo do ativo" in text.lower()
        )
    )


def run_smoke_test(
    asset_code,
    provider=None,
    parser=None,
):
    """Executa uma unica consulta sem gravar no banco."""

    selected_provider = provider or build_provider()
    normalized_code = selected_provider.normalize_asset_code(
        asset_code
    )
    response = selected_provider.fetch_html(normalized_code)

    if parser is not None:
        parsed = parser.parse(response.text)
    elif is_tabular_response(response):
        parsed = SndTabularParser.parse(
            response.text,
            normalized_code,
        )
    else:
        parsed = SndParser.parse(response.text)

    return SmokeTestResult(
        asset_code=normalized_code,
        url=response.url,
        http_status=response.status,
        content_type=response.content_type,
        response_size_bytes=response.size_bytes,
        parsed_asset_code=parsed.asset_code,
        parsed_isin=parsed.isin,
        observation_count=len(parsed.observations),
    )


def print_result(result):
    """Exibe o resultado de forma legivel."""

    print("SND SMOKE TEST")
    print("Codigo solicitado:", result.asset_code)
    print("URL consultada:", result.url)
    print("Status HTTP:", result.http_status)
    print("Content-Type:", result.content_type)
    print("Tamanho da resposta:", result.response_size_bytes)
    print("Codigo encontrado:", result.parsed_asset_code)
    print("ISIN encontrado:", result.parsed_isin)
    print("Campos extraidos:", result.observation_count)
    print("Gravacao no banco: desativada")


def build_argument_parser():
    """Configura os argumentos da linha de comando."""

    parser = argparse.ArgumentParser(
        description=(
            "Realiza uma unica consulta de diagnostico ao SND "
            "sem gravar dados no banco."
        )
    )
    parser.add_argument(
        "asset_code",
        nargs="?",
        default=DEFAULT_ASSET_CODE,
        help="Codigo do ativo. Padrao: PETR27.",
    )
    return parser


def main(argv=None):
    """Ponto de entrada do script."""

    parser = build_argument_parser()
    arguments = parser.parse_args(argv)

    try:
        result = run_smoke_test(arguments.asset_code)
    except (ValueError, SndProviderError) as error:
        print("Falha no smoke test:", error, file=sys.stderr)
        return 1
    except Exception as error:
        print(
            "Falha inesperada no smoke test:",
            type(error).__name__ + ": " + str(error),
            file=sys.stderr,
        )
        return 2

    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
