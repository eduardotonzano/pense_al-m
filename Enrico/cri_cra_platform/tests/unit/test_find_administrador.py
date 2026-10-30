from __future__ import annotations

from credit_assets.collectors.fundosnet_collector import FundosNetCollector
from credit_assets.utils.fundosnet_normalization import normalize_text


def _collector(rows_by_term):
    collector = FundosNetCollector.__new__(FundosNetCollector)
    collector._request_json = lambda page, context, endpoint, params, diagnostics: {
        "results": rows_by_term.get(params["term"], [])
    }
    collector._extract_rows = lambda payload: (payload["results"], len(payload["results"]), 1)
    return collector


def _find(rows_by_term, name):
    return _collector(rows_by_term)._find_administrador(None, None, name, {"json_probe": None})


def test_normalization_treats_slash_and_dots_in_sa_alike():
    assert normalize_text("Travessia Securitizadora S/A") == normalize_text("Travessia Securitizadora S.A")


def test_exact_name_breaks_a_tie_between_similar_names():
    rows = [{"id": 1366, "text": "Vert Companhia Securitizadora"},
            {"id": 9692, "text": "VERT COMPANHIA SECURITIZADORA DE CRÉDITOS FINANCEIROS"}]
    found = _find({"Vert": rows, "Vert Companhia Securitizadora": rows}, "Vert Companhia Securitizadora")
    assert found == {"id": 1366, "nome": "Vert Companhia Securitizadora"}


def test_slash_variant_of_sa_is_located():
    rows = [{"id": 8323, "text": "TRAVESSIA SECURITIZADORA DE CRÉDITOS FINANCEIROS XXII S.A."},
            {"id": 8325, "text": "TRAVESSIA SECURITIZADORA II S.A"},
            {"id": 1356, "text": "Travessia Securitizadora S/A"}]
    found = _find({"Travessia": rows, "Travessia Securitizadora S.A": rows}, "Travessia Securitizadora S.A")
    assert found["id"] == 1356


def test_ambiguous_without_exact_match_stays_unlocated():
    rows = [{"id": 1, "text": "Vert Alfa Securitizadora"}, {"id": 2, "text": "Vert Beta Securitizadora"}]
    assert _find({"Vert": rows}, "Vert Securitizadora") is None
