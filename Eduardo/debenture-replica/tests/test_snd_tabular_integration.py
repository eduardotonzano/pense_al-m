from pathlib import Path
from email.message import Message

from debenture_search.providers.snd_provider import SndProvider
from debenture_search.services.snd_import_service import SndImportService


FIXTURE = Path(__file__).parent / "fixtures" / "snd_caracteristicas_tabular_exemplo.txt"


class Response:
    status = 200
    def __init__(self):
        self.headers = Message()
        self.headers["Content-Type"] = "application/vnd.ms-excel"
    def read(self, size=-1):
        return FIXTURE.read_bytes()[:size]
    def close(self):
        pass


class Importer:
    def __init__(self):
        self.call = None
    def import_document(self, document, **kwargs):
        self.call = (document, kwargs)
        return kwargs


def test_provider_accepts_tabular_response():
    importer = Importer()
    provider = SndProvider(object(), import_service=importer,
                           http_open=lambda request, timeout: Response())
    response = provider.fetch_html("PETR27")
    assert response.content_type == "application/vnd.ms-excel"
    assert "PETR27" in response.text


def test_provider_sends_tabular_document_to_importer():
    importer = Importer()
    provider = SndProvider(object(), import_service=importer,
                           http_open=lambda request, timeout: Response())
    provider.collect("petr27")
    _, kwargs = importer.call
    assert kwargs["asset_code"] == "PETR27"
    assert kwargs["content_type"] == "application/vnd.ms-excel"
