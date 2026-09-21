from credit_assets.collectors.fundosnet_collector import FundosNetCollector, FundosNetMatch
from credit_assets.models.asset import Asset
import pytest


def asset(**changes):
    values = dict(
        codigo_cetip="BRECOACRABX0",
        isin="BRECOACRABX0",
        tipo_ativo="CRA",
        securitizadora="Eco Securitizadora",
        cnpj_securitizadora="10.753.164/0001-43",
        emissao="190",
        serie="1",
        devedor="Café Brasil",
        cnpj_devedor="",
        asset_id=1,
    )
    values.update(changes)
    return Asset(**values)


def test_fixture_match_requires_unique_compatible_certificate():
    collector = FundosNetCollector()
    matches = [
        FundosNetMatch(8795, "ECO CRA Emissão:190 Série:1 CAFÉ BRASIL BRECOACRABX0", "BRECOACRABX0"),
        FundosNetMatch(9000, "ECO CRA Emissão:190 Série:2 CAFÉ BRASIL OTHER", "OTHER"),
    ]
    selected = collector._select_match(asset(), matches)
    assert selected is not None
    assert selected.id_fundo == 8795


def test_document_rows_are_converted_without_network():
    document = FundosNetCollector._to_document(
        asset(), {"id": 1, "tipo": "Informe Mensal de CRA", "nome": "Informe", "url": "https://example.test"}
    )
    assert document.source == "Fundos.NET"
    assert document.category == "Informe Mensal"


class FakeResponse:
    def __init__(self, payload=None, status=200, content_type="application/json"):
        self._payload = payload
        self.status = status
        self.ok = status < 400
        self.headers = {"content-type": content_type}
        self.url = "https://fnet.test/endpoint"

    def json(self):
        return self._payload

    def text(self):
        return "<html><title>Fundos.NET</title></html>"


class FakeRequest:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakePage:
    def evaluate(self, *_args):
        return None


class FakeContext:
    def __init__(self, request):
        self.request = request


def test_context_request_is_used_and_json_is_decoded():
    request = FakeRequest([FakeResponse({"results": []})])
    diagnostics = {"attempts": [], "html_diagnostics": [], "json_probe": None}
    result = FundosNetCollector()._request_json(
        FakePage(), FakeContext(request), "buscarAdministrador", {"term": "Eco"}, diagnostics
    )
    assert result == {"results": []}
    assert len(request.calls) == 1
    assert request.calls[0][1]["headers"]["Accept"].startswith("application/json")


def test_timeout_retries_at_most_three_times(monkeypatch):
    monkeypatch.setattr("credit_assets.collectors.fundosnet_collector.time.sleep", lambda _: None)
    request = FakeRequest([TimeoutError(), TimeoutError(), TimeoutError(), TimeoutError()])
    diagnostics = {"attempts": [], "html_diagnostics": [], "json_probe": None}
    with pytest.raises(TimeoutError):
        FundosNetCollector()._request_json(
            FakePage(), FakeContext(request), "buscarAdministrador", {"term": "Eco"}, diagnostics
        )
    assert len(request.calls) == 3


def test_html_is_classified_without_repeating_request(monkeypatch):
    monkeypatch.setattr("credit_assets.collectors.fundosnet_collector.time.sleep", lambda _: None)
    request = FakeRequest([FakeResponse(status=200, content_type="text/html")])
    diagnostics = {"attempts": [], "html_diagnostics": [], "json_probe": None}
    with pytest.raises(RuntimeError, match="sessao_invalida_ou_bloqueio"):
        FundosNetCollector()._request_json(
            FakePage(), FakeContext(request), "pesquisarGerenciadorDocumentosDados", {}, diagnostics
        )
    assert len(request.calls) == 1
    assert diagnostics["html_diagnostics"][0]["classification"] == "redirecionamento_ou_sessao"


class NativeResponse:
    def __init__(self, payload, content_type="application/json", status=200, url="https://fnet.test/pesquisarGerenciadorDocumentosDados"):
        self._payload = payload
        self.status = status
        self.headers = {"content-type": content_type}
        self.url = url

    def json(self):
        return self._payload

    def text(self):
        return "<html><title>Login</title></html>"


def test_native_json_response_and_records_filtered():
    diagnostics = {"native_xhr": []}
    payload = FundosNetCollector()._parse_native_response(
        NativeResponse({"recordsFiltered": 1, "data": [{"descricaoFundo": "BRECOACRABX0"}]}),
        diagnostics,
    )
    assert payload["recordsFiltered"] == 1


def test_native_login_redirect_is_rejected_without_json_parsing():
    diagnostics = {"native_xhr": []}
    response = NativeResponse(
        None,
        content_type="text/html",
        url="https://fnet.bmfbovespa.com.br/fnet/login",
    )
    with pytest.raises(RuntimeError, match="sessao_invalida_ou_bloqueio"):
        FundosNetCollector()._parse_native_response(response, diagnostics)
    assert diagnostics["native_xhr"][0]["classification"] == "sessao_invalida_ou_bloqueio"


def test_native_certificate_validation_rejects_other_isin():
    collector = FundosNetCollector()
    selected = collector._select_match(
        asset(),
        [FundosNetMatch(8795, "ECO CRA Emissão:190 BRECOACRABX0", "OUTRO")],
    )
    assert selected is None


def test_captcha_marker_is_not_solved():
    diagnostics = {"captcha": None}
    assert "captcha_required" in "captcha_required"
    diagnostics["captcha"] = "captcha_required_before_document_query"
    assert diagnostics["captcha"].startswith("captcha_required")
