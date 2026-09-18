import argparse
import sys
from dataclasses import dataclass

from debenture_search.database import database
from debenture_search.parsers.snd_parser import SndParser
from debenture_search.parsers.snd_tabular_parser import SndTabularParser
from debenture_search.providers.snd_provider import SndProvider
from debenture_search.providers.snd_provider import SndProviderError
from debenture_search.services.backup_service import BackupService


DEFAULT_ASSET_CODE = "PETR27"


@dataclass(frozen=True)
class PreviewResult:
    asset_code: str
    url: str
    http_status: int
    content_type: str
    response_size_bytes: int
    parsed_asset_code: str | None
    parsed_isin: str | None
    issuer_name: str | None
    observation_count: int


def is_tabular_response(response):
    content_type = str(response.content_type or "").lower()
    return (
        content_type in {"application/vnd.ms-excel", "text/plain"}
        or (
            "\t" in response.text
            and "codigo do ativo" in response.text.lower()
        )
    )


def preview(asset_code, provider):
    code = provider.normalize_asset_code(asset_code)
    response = provider.fetch_html(code)

    if is_tabular_response(response):
        parsed = SndTabularParser.parse(response.text, code)
    else:
        parsed = SndParser.parse(response.text)

    if parsed.asset_code != code:
        raise ValueError(
            "O codigo encontrado nao corresponde ao codigo solicitado."
        )

    return PreviewResult(
        asset_code=code,
        url=response.url,
        http_status=response.status,
        content_type=response.content_type,
        response_size_bytes=response.size_bytes,
        parsed_asset_code=parsed.asset_code,
        parsed_isin=parsed.isin,
        issuer_name=parsed.issuer_legal_name,
        observation_count=len(parsed.observations),
    )


def print_preview(result):
    print("PRE-VISUALIZACAO SND")
    print("Ativo solicitado:", result.asset_code)
    print("Ativo encontrado:", result.parsed_asset_code)
    print("ISIN:", result.parsed_isin)
    print("Emissor:", result.issuer_name)
    print("Status HTTP:", result.http_status)
    print("Formato:", result.content_type)
    print("Tamanho da resposta:", result.response_size_bytes)
    print("Campos extraidos:", result.observation_count)
    print("Gravacao no banco: NAO EXECUTADA")


def print_commit(result, backup_path):
    print("IMPORTACAO SND CONCLUIDA")
    print("Backup criado:", backup_path)
    print("Status da coleta:", result.status)
    print("ID do emissor:", result.issuer_id)
    print("ID da debenture:", result.debenture_id)
    print("ID do registro bruto:", result.raw_record_id)
    print("Observacoes criadas:", result.observations_created)
    print("Observacoes reutilizadas:", result.observations_reused)
    print("Conflitos criados:", result.conflicts_created)
    print("Integridade SQLite:", database.integrity_check())
    print("Foreign keys:", database.foreign_key_check())


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Pre-visualiza ou importa um unico ativo do SND."
    )
    parser.add_argument(
        "asset_code",
        nargs="?",
        default=DEFAULT_ASSET_CODE,
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Autoriza backup e gravacao no banco.",
    )
    return parser


def run(asset_code, commit=False, provider=None, backup_service=None):
    selected_provider = provider or SndProvider(database)

    if not commit:
        return preview(asset_code, selected_provider)

    selected_backup = backup_service or BackupService(database)
    backup = selected_backup.create_backup()
    result = selected_provider.collect(asset_code)

    if database.integrity_check() != "ok":
        raise RuntimeError("A integridade do banco falhou apos a importacao.")

    if database.foreign_key_check():
        raise RuntimeError(
            "Foram encontradas violacoes de chaves estrangeiras."
        )

    return result, backup.path


def main(argv=None):
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)

    try:
        result = run(
            arguments.asset_code,
            commit=arguments.commit,
        )
    except (ValueError, SndProviderError, RuntimeError) as error:
        print("Falha:", error, file=sys.stderr)
        return 1

    if arguments.commit:
        import_result, backup_path = result
        print_commit(import_result, backup_path)
    else:
        print_preview(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
