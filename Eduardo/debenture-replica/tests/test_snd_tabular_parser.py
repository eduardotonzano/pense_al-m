from decimal import Decimal
from pathlib import Path

import pytest

from debenture_search.parsers.snd_tabular_parser import SndTabularParser


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_tabular_exemplo.txt"
)


def load_fixture():
    return FIXTURE_PATH.read_text(encoding="utf-8")


def observation_map(parsed):
    return {item.field_name: item for item in parsed.observations}


def test_parse_identity_fields():
    parsed = SndTabularParser.parse(load_fixture(), "PETR27")

    assert parsed.asset_code == "PETR27"
    assert parsed.isin == "BRPETRDBS0C2"
    assert parsed.issuer_legal_name == "PETROLEO BRASILEIRO S/A - PETROBRAS"
    assert parsed.issuer_cnpj == "33000167000101"
    assert parsed.issue_number == "007"
    assert parsed.series == "002"


def test_parse_numeric_values():
    observations = observation_map(
        SndTabularParser.parse(load_fixture(), "PETR27")
    )

    assert observations["quantidade_emitida"].value == Decimal("1478670")
    assert observations["quantidade_em_mercado"].value == Decimal("1478670")
    assert observations["valor_nominal"].value == Decimal("1465.04499")
    assert observations["spread"].value == Decimal("3.9")


def test_parse_dates_and_text():
    observations = observation_map(
        SndTabularParser.parse(load_fixture(), "PETR27")
    )

    assert observations["data_emissao"].value == "2019-08-15"
    assert observations["data_vencimento"].value == "2034-09-15"
    assert observations["indexador"].value == "IPCA"
    assert observations["garantia"].value == "Quirografaria"


def test_parse_boolean_fields():
    observations = observation_map(
        SndTabularParser.parse(load_fixture(), "PETR27")
    )

    assert observations["incentivada"].value is True
    assert observations["resgate_antecipado"].value is False


def test_parse_all_records():
    records = SndTabularParser.parse_all(load_fixture())

    assert len(records) == 1
    assert records[0].asset_code == "PETR27"


def test_rejects_missing_header():
    with pytest.raises(ValueError, match="cabecalho esperado"):
        SndTabularParser.parse("texto sem tabela")


def test_rejects_header_without_data():
    with pytest.raises(ValueError, match="nao contem dados"):
        SndTabularParser.parse("Codigo do Ativo\tEmpresa")


def test_rejects_missing_requested_asset():
    with pytest.raises(ValueError, match="nao foi encontrado"):
        SndTabularParser.parse(load_fixture(), "INEX12")


def test_rejects_empty_document():
    with pytest.raises(ValueError, match="nao pode ficar vazia"):
        SndTabularParser.parse("   ")


def test_multiple_assets_require_selection():
    document = load_fixture() + (
        "OUTR12\tOUTRA EMPRESA\t001\t001\tRegistrado\tBROUTRDBS001\n"
    )

    with pytest.raises(ValueError, match="mais de um ativo"):
        SndTabularParser.parse(document)
