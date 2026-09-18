from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError

import pytest

from debenture_search.providers.snd_provider import SndProvider
from debenture_search.providers.snd_provider import SndProviderError


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_exemplo.html"
)


class FakeResponse:
    def __init__(
        self,
        payload,
        status=200,
        content_type="text/html; charset=utf-8",
    ):
        self.payload = payload
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.closed = False

    def read(self, size=-1):
        return self.payload[:size]

    def close(self):
        self.closed = True


class FakeImportService:
    def __init__(self):
        self.calls = []

    def import_document(self, document, **kwargs):
        self.calls.append((document, kwargs))

        return {
            "imported": True,
            "kwargs": kwargs,
        }

    def import_html(self, document, **kwargs):
        return self.import_document(
            document,
            **kwargs,
        )


def fixture_bytes():
    return FIXTURE_PATH.read_bytes()


def test_normalizes_asset_code():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: None,
        import_service=FakeImportService(),
    )

    assert provider.normalize_asset_code("  exmp12 ") == "EXMP12"


def test_rejects_empty_asset_code():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: None,
        import_service=FakeImportService(),
    )

    with pytest.raises(ValueError, match="obrigatorio"):
        provider.normalize_asset_code("   ")


def test_builds_encoded_url():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: None,
        import_service=FakeImportService(),
        base_url="https://example.test/",
    )

    url = provider.build_url("exmp12")

    assert url.startswith("https://example.test/")
    assert "Ativo=EXMP12" in url


def test_fetches_html_with_timeout_and_headers():
    captured = {}

    def fake_open(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(fixture_bytes())

    provider = SndProvider(
        db=object(),
        http_open=fake_open,
        import_service=FakeImportService(),
        timeout_seconds=7,
    )

    response = provider.fetch_html("EXMP12")

    assert response.status == 200
    assert response.size_bytes == len(fixture_bytes())
    assert captured["timeout"] == 7
    assert captured["request"].get_header("User-agent") == (
        "debenture-search/1.0"
    )


def test_rejects_http_error():
    def fake_open(request, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            None,
        )

    provider = SndProvider(
        db=object(),
        http_open=fake_open,
        import_service=FakeImportService(),
    )

    with pytest.raises(SndProviderError, match="HTTP 404"):
        provider.fetch_html("EXMP12")


def test_rejects_server_status():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: FakeResponse(
            fixture_bytes(),
            status=500,
        ),
        import_service=FakeImportService(),
    )

    with pytest.raises(SndProviderError, match="HTTP 500"):
        provider.fetch_html("EXMP12")


def test_rejects_timeout():
    def fake_open(request, timeout):
        raise URLError("timed out")

    provider = SndProvider(
        db=object(),
        http_open=fake_open,
        import_service=FakeImportService(),
    )

    with pytest.raises(SndProviderError, match="consultar o SND"):
        provider.fetch_html("EXMP12")


def test_rejects_empty_response():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: FakeResponse(b""),
        import_service=FakeImportService(),
    )

    with pytest.raises(SndProviderError, match="resposta vazia"):
        provider.fetch_html("EXMP12")


def test_rejects_non_html_response():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: FakeResponse(
            b'{"error":true}',
            content_type="application/json",
        ),
        import_service=FakeImportService(),
    )

    with pytest.raises(SndProviderError, match="nao possui formato reconhecido"):
        provider.fetch_html("EXMP12")


def test_rejects_oversized_response():
    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: FakeResponse(
            b"<html>123456789</html>"
        ),
        import_service=FakeImportService(),
        max_response_bytes=10,
    )

    with pytest.raises(SndProviderError, match="tamanho permitido"):
        provider.fetch_html("EXMP12")


def test_collect_sends_response_to_import_service():
    importer = FakeImportService()

    provider = SndProvider(
        db=object(),
        http_open=lambda request, timeout: FakeResponse(
            fixture_bytes()
        ),
        import_service=importer,
        base_url="https://example.test",
    )

    result = provider.collect(
        "exmp12",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    assert result["imported"] is True
    assert len(importer.calls) == 1

    document, kwargs = importer.calls[0]
    assert "EXMP12" in document
    assert kwargs["request_parameters"] == {
        "asset_code": "EXMP12"
    }
    assert kwargs["http_status"] == 200
    assert kwargs["observed_at"] == (
        "2026-09-10T12:00:00+00:00"
    )


def test_tests_do_not_use_real_network():
    calls = []

    def fake_open(request, timeout):
        calls.append(request.full_url)
        return FakeResponse(fixture_bytes())

    provider = SndProvider(
        db=object(),
        http_open=fake_open,
        import_service=FakeImportService(),
    )

    provider.fetch_html("EXMP12")

    assert len(calls) == 1

