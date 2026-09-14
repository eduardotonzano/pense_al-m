import argparse
from dataclasses import dataclass

from debenture_search.parsers.snd_parser import SndParser
from debenture_search.parsers.snd_tabular_parser import SndTabularParser
from debenture_search.providers.snd_provider import SndProvider


@dataclass(frozen=True)
class SmokeTestResult:
    asset_code: str
    url: str
    http_status: int
    content_type: str
    response_size_bytes: int
    parsed_asset_code: str | None
    parsed_isin: str | None
    observation_count: int


def run_smoke_test(asset_code, provider=None):
    provider = provider or SndProvider(object(), import_service=object())
    code = provider.normalize_asset_code(asset_code)
    response = provider.fetch_html(code)
    tabular = (response.content_type in {"application/vnd.ms-excel", "text/plain"}
               or ("	" in response.text and "codigo do ativo" in response.text.lower()))
    parsed = (SndTabularParser.parse(response.text, code)
              if tabular else SndParser.parse(response.text))
    return SmokeTestResult(code, response.url, response.status, response.content_type,
                           response.size_bytes, parsed.asset_code, parsed.isin,
                           len(parsed.observations))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_code", nargs="?", default="PETR27")
    args = parser.parse_args(argv)
    result = run_smoke_test(args.asset_code)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
