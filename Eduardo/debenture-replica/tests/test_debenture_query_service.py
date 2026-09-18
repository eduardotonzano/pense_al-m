from decimal import Decimal

import pytest

from debenture_search.services.debenture_query_service import (
    DebentureQueryService,
)


class FakeDatabase:
    def __init__(self):
        self.debentures = [
            {
                "id": 1,
                "asset_code": "PETR27",
                "isin": "BRPETRDBS0C2",
                "issuer_id": 1,
                "issuer_name": "PETROLEO BRASILEIRO S/A - PETROBRAS",
                "issuer_cnpj": "33000167000101",
                "issue_number": "007",
                "series": "002",
                "status": "active",
            },
            {
                "id": 2,
                "asset_code": "CEPEA1",
                "isin": "BRCEPEDBS0E2",
                "issuer_id": 2,
                "issuer_name": "COMPANHIA ENERGETICA DE PERNAMBUCO-CELPE",
                "issuer_cnpj": "10835932000108",
                "issue_number": "011",
                "series": "001",
                "status": "active",
            },
        ]

    def fetch_one(self, sql, parameters=()):
        if "FROM data_conflicts" in sql:
            return {"total": 0}
        if "WHERE d.asset_code = ?" in sql:
            return next(
                (row for row in self.debentures if row["asset_code"] == parameters[0]),
                None,
            )
        if "WHERE d.isin = ?" in sql:
            return next(
                (row for row in self.debentures if row["isin"] == parameters[0]),
                None,
            )
        return None

    def fetch_all(self, sql, parameters=()):
        if "FROM observations" in sql:
            return [
                {
                    "field_name": "valor_nominal",
                    "value_type": "numeric",
                    "value_text": None,
                    "value_numeric": "1465.04499",
                    "value_date": None,
                    "value_boolean": None,
                    "unit": "BRL",
                    "observed_at": "2026-09-11T12:00:00+00:00",
                    "confidence": "reported",
                    "source_code": "SND",
                }
            ]
        if "LIKE ?" in sql:
            term = parameters[0].strip("%").casefold()
            return [
                row for row in self.debentures
                if term in row["issuer_name"].casefold()
            ]
        return sorted(self.debentures, key=lambda row: row["asset_code"])


def test_lists_all_debentures():
    items = DebentureQueryService(FakeDatabase()).list_all()
    assert [item.asset_code for item in items] == ["CEPEA1", "PETR27"]


def test_finds_by_code_case_insensitive():
    item = DebentureQueryService(FakeDatabase()).find_by_code(" petr27 ")
    assert item.isin == "BRPETRDBS0C2"
    assert item.status == "active"


def test_finds_by_isin():
    item = DebentureQueryService(FakeDatabase()).find_by_isin(" brpetrdbs0c2 ")
    assert item.asset_code == "PETR27"


def test_searches_by_issuer():
    items = DebentureQueryService(FakeDatabase()).search_by_issuer("petrobras")
    assert len(items) == 1
    assert items[0].asset_code == "PETR27"


def test_returns_consolidated_details():
    details = DebentureQueryService(FakeDatabase()).get_details("PETR27")
    assert details.debenture.asset_code == "PETR27"
    assert details.open_conflicts == 0
    assert details.current_values["valor_nominal"].value == Decimal("1465.04499")
    assert details.current_values["valor_nominal"].source_code == "SND"


def test_returns_field_history():
    items = DebentureQueryService(FakeDatabase()).history(
        "PETR27",
        "valor_nominal",
    )
    assert len(items) == 1
    assert items[0].value == Decimal("1465.04499")


def test_missing_debenture_returns_none():
    service = DebentureQueryService(FakeDatabase())
    assert service.find_by_code("INEX12") is None
    assert service.get_details("INEX12") is None


def test_rejects_invalid_query_type():
    with pytest.raises(ValueError, match="Tipo de consulta invalido"):
        DebentureQueryService(FakeDatabase()).get_details(
            "PETR27",
            by="invalid",
        )


def test_rejects_empty_search():
    with pytest.raises(ValueError, match="obrigatorio"):
        DebentureQueryService(FakeDatabase()).find_by_code(" ")

