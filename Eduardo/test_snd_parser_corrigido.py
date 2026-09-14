from decimal import Decimal
from pathlib import Path

import pytest

from debenture_search.parsers.snd_parser import ParsedDebenture
from debenture_search.parsers.snd_parser import SndParser


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_exemplo.html"
)


def load_fixture():
    return FIXTURE_PATH.read_text(encoding="utf-8")


def observation_map(parsed):
    return {
        item.field_name: item
        for item in parsed.observations
    }


def test_parse_identity_fields():
    parsed = SndParser.parse(load_fixture())

    assert isinstance(parsed, ParsedDebenture)
    assert parsed.asset_code == "EXMP12"
    assert parsed.isin == "BREXMPDBS001"
    assert parsed.issuer_legal_name == (
        "Companhia Exemplo de Energia S.A."
    )
    assert parsed.issuer_cnpj == "12345678000199"
    assert parsed.issue_number == "1"
    assert parsed.series == "2"
    assert parsed.status == "active"


def test_parse_text_observations():
    parsed = SndParser.parse(load_fixture())
    observations = observation_map(parsed)

    assert observations["indexador"].value == "DI"
    assert observations["garantia"].value == "Quirografaria"
    assert observations["classe"].value == "Simples"
    assert observations["rating"].value == "AA-"
    assert observations["agente_fiduciario"].value == (
        "Agente Fiduciario Exemplo"
    )


def test_parse_numeric_observations():
    parsed = SndParser.parse(load_fixture())
    observations = observation_map(parsed)

    assert observations["spread"].value == Decimal("2.35")
    assert observations["spread"].unit == "percentual"
    assert observations["quantidade_emitida"].value == Decimal(
        "100000"
    )
    assert observations["quantidade_em_mercado"].value == Decimal(
        "98500"
    )
    assert observations["valor_nominal"].value == Decimal("1000.00")
    assert observations["valor_nominal"].unit == "BRL"


def test_parse_date_observations():
    parsed = SndParser.parse(load_fixture())
    observations = observation_map(parsed)

    assert observations["data_emissao"].value == "2025-08-15"
    assert observations["data_vencimento"].value == "2030-08-15"


def test_unknown_fields_are_ignored():
    document = load_fixture().replace(
        "</table>",
        "<tr><th>Campo Desconhecido</th><td>Valor</td></tr></table>",
    )
    parsed = SndParser.parse(document)

    assert "campo_desconhecido" not in observation_map(parsed)


def test_missing_optional_field_does_not_fail():
    document = load_fixture().replace(
        "<tr><th>Rating</th><td>AA-</td></tr>",
        "",
    )
    parsed = SndParser.parse(document)

    assert "rating" not in observation_map(parsed)


def test_invalid_isin_is_ignored_when_code_exists():
    document = load_fixture().replace(
        "BREXMPDBS001",
        "ISIN-INVALIDO",
    )
    parsed = SndParser.parse(document)

    assert parsed.asset_code == "EXMP12"
    assert parsed.isin is None


def test_rejects_page_without_identifier():
    document = load_fixture()

    document = document.replace(
        "<tr><th>Codigo do Ativo</th><td>EXMP12</td></tr>",
        "",
    )

    document = document.replace(
        "<tr><th>ISIN</th><td>BREXMPDBS001</td></tr>",
        "",
    )

    with pytest.raises(
        ValueError,
        match="codigo do ativo nem ISIN",
    ):
        SndParser.parse(document)


def test_rejects_empty_html():
    with pytest.raises(
        ValueError,
        match="nao pode ficar vazio",
    ):
        SndParser.parse("   ")


def test_definition_list_is_supported():
    document = """
    <html>
        <body>
            <dl>
                <dt>Codigo do Ativo</dt>
                <dd>DLST12</dd>
                <dt>Emissor</dt>
                <dd>Empresa Definition List</dd>
                <dt>Situacao</dt>
                <dd>Vencida</dd>
            </dl>
        </body>
    </html>
    """

    parsed = SndParser.parse(document)

    assert parsed.asset_code == "DLST12"
    assert parsed.issuer_legal_name == "Empresa Definition List"
    assert parsed.status == "matured"
