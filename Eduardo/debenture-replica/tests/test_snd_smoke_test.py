import importlib.util
from email.message import Message
from pathlib import Path

import pytest

from debenture_search.parsers.snd_parser import SndParser
from debenture_search.providers.snd_provider import SndProvider
from debenture_search.providers.snd_provider import SndProviderError


PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "snd_smoke_test.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_exemplo.html"
)


def load_script_module():
    specification = importlib.util.spec_from_file_location(
        "snd_smoke_test",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def read(self, size=-1):
        return self.payload[:size]

    def close(self):
        return None


def create_offline_provider():
    payload = FIXTURE_PATH.read_bytes()

    def fake_open(request, timeout):
        return FakeResponse(payload)

    module = load_script_module()
    return SndProvider(
        db=object(),
        import_service=module.DisabledImportService(),
        http_open=fake_open,
        base_url="https://example.test",
    )


def test_run_smoke_test_offline():
    module = load_script_module()
    result = module.run_smoke_test(
        "exmp12",
        provider=create_offline_provider(),
        parser=SndParser(),
    )

    assert result.asset_code == "EXMP12"
    assert result.http_status == 200
    assert result.parsed_asset_code == "EXMP12"
    assert result.parsed_isin == "BREXMPDBS001"
    assert result.observation_count > 0


def test_smoke_test_does_not_import():
    module = load_script_module()
    disabled = module.DisabledImportService()

    with pytest.raises(RuntimeError, match="nao permite importacao"):
        disabled.import_html("<html></html>")


def test_print_result(capsys):
    module = load_script_module()
    result = module.run_smoke_test(
        "EXMP12",
        provider=create_offline_provider(),
    )

    module.print_result(result)
    output = capsys.readouterr().out

    assert "SND SMOKE TEST" in output
    assert "Codigo solicitado: EXMP12" in output
    assert "Status HTTP: 200" in output
    assert "Gravacao no banco: desativada" in output


def test_default_asset_code():
    module = load_script_module()
    parser = module.build_argument_parser()
    arguments = parser.parse_args([])

    assert arguments.asset_code == "PETR27"


def test_custom_asset_code():
    module = load_script_module()
    parser = module.build_argument_parser()
    arguments = parser.parse_args(["CEPEA1"])

    assert arguments.asset_code == "CEPEA1"


def test_rejects_empty_asset_code():
    module = load_script_module()

    with pytest.raises(ValueError, match="obrigatorio"):
        module.run_smoke_test(
            "   ",
            provider=create_offline_provider(),
        )


def test_provider_error_is_not_hidden():
    module = load_script_module()

    class FailingProvider:
        def normalize_asset_code(self, value):
            return value

        def fetch_html(self, value):
            raise SndProviderError("falha controlada")

    with pytest.raises(SndProviderError, match="falha controlada"):
        module.run_smoke_test(
            "EXMP12",
            provider=FailingProvider(),
        )


def test_parser_error_is_not_hidden():
    module = load_script_module()

    class InvalidHtmlProvider:
        def normalize_asset_code(self, value):
            return value

        def fetch_html(self, value):
            class Response:
                url = "https://example.test"
                status = 200
                content_type = "text/html"
                text = "<html>sem identificadores</html>"
                size_bytes = 33

            return Response()

    with pytest.raises(ValueError, match="codigo do ativo nem ISIN"):
        module.run_smoke_test(
            "EXMP12",
            provider=InvalidHtmlProvider(),
        )
