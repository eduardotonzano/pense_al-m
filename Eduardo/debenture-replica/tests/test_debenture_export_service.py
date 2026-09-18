import csv
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from debenture_search.services.debenture_export_service import (
    DebentureExportService,
)


class QueryService:
    def list_all(self):
        return [
            SimpleNamespace(id=1, asset_code="PETR27"),
            SimpleNamespace(id=2, asset_code="CEPEA1"),
        ]

    def find_by_code(self, code):
        code = str(code).strip().upper()
        return next(
            (item for item in self.list_all() if item.asset_code == code),
            None,
        )

    def get_details(self, code, by="code"):
        summary = self.find_by_code(code)
        if summary is None:
            return None
        debenture = SimpleNamespace(
            id=summary.id,
            asset_code=summary.asset_code,
            isin="BRPETRDBS0C2" if summary.id == 1 else "BRCEPEDBS0E2",
            issuer_name="PETROBRAS" if summary.id == 1 else "CELPE",
            issuer_cnpj="33000167000101" if summary.id == 1 else "10835932000108",
            issue_number="007",
            series="002",
            status="active",
        )
        current = {
            "valor_nominal": SimpleNamespace(value=Decimal("1465.04499")),
            "incentivada": SimpleNamespace(value=True),
        }
        return SimpleNamespace(
            debenture=debenture,
            current_values=current,
            open_conflicts=0,
        )

    @staticmethod
    def row_value(row):
        if row["value_type"] == "numeric":
            return Decimal(str(row["value_numeric"]))
        return row["value_text"]


class Database:
    def fetch_all(self, sql, parameters=()):
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


def service():
    return DebentureExportService(
        Database(),
        query_service=QueryService(),
    )


def test_exports_all_consolidated_rows(tmp_path):
    result = service().export("csv", tmp_path / "all.csv")
    assert result["rows"] == 2
    with result["path"].open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["asset_code"] == "PETR27"
    assert rows[0]["valor_nominal"] == "1465.04499"
    assert rows[0]["incentivada"] == "Sim"


def test_exports_single_asset(tmp_path):
    result = service().export(
        "csv",
        tmp_path / "one.csv",
        asset_code="PETR27",
    )
    assert result["rows"] == 1


def test_exports_json_with_unicode(tmp_path):
    result = service().export("json", tmp_path / "all.json")
    data = json.loads(result["path"].read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["issuer_name"] == "PETROBRAS"


def test_exports_history(tmp_path):
    result = service().export(
        "csv",
        tmp_path / "history.csv",
        asset_code="PETR27",
        history=True,
    )
    assert result["history"] is True
    assert result["rows"] == 1
    text = result["path"].read_text(encoding="utf-8-sig")
    assert "valor_nominal" in text
    assert "1465.04499" in text


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "debentures.csv"
    result = service().export("csv", path)
    assert result["path"].exists()


def test_rejects_invalid_format(tmp_path):
    with pytest.raises(ValueError, match="Formato de exportacao invalido"):
        service().export("xlsx", tmp_path / "file.xlsx")


def test_rejects_missing_asset(tmp_path):
    with pytest.raises(ValueError, match="Debenture nao encontrada"):
        service().export(
            "csv",
            tmp_path / "missing.csv",
            asset_code="INEX12",
        )


def test_csv_has_utf8_bom(tmp_path):
    result = service().export("csv", tmp_path / "bom.csv")
    assert result["path"].read_bytes().startswith(b"\xef\xbb\xbf")


def test_serialize_values():
    export = service()
    assert export.serialize_value(Decimal("1.2300")) == "1.2300"
    assert export.serialize_value(True) == "Sim"
    assert export.serialize_value(False) == "Nao"
    assert export.serialize_value(None) == ""
