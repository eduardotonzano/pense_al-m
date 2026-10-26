import pytest

from credit_assets.services.contract_alerts_service import (
    ParameterNotApproved,
    cessao_fiduciaria_minima,
    razao_garantia_minima,
)

PARAMS = {
    "cessao_fiduciaria_minima_na_verificacao": {"parameter_value": "65000000.00", "source_reference": "Termo p.20"},
    "razao_garantia_minima_jan_ago": {"parameter_value": "0.70", "source_reference": "Termo p.20"},
    "razao_garantia_minima_set_dez": {"parameter_value": "1.20", "source_reference": "Termo p.20"},
}


def _fact(value):
    return [{"value": value, "page_number": 2, "source_document_id": "af"}]


FACTS = {
    "2025-12-31": {
        "garantia_cessao_fiduciaria_valor": _fact("2243443.20"),
        "garantia_af_estoque_valor": _fact("37884631.95"),
        "garantia_af_imovel_valor": _fact("49980777.00"),
        "saldo_em_conta": _fact("156981.18"),
        "saldo_devedor_cra": _fact("30926620.08"),
    }
}
CESSAO_RULE = {"parameter": "cessao_fiduciaria_minima_na_verificacao",
               "fact": "garantia_cessao_fiduciaria_valor", "months": ["12"]}
RAZAO_RULE = {
    "parameters": {"01-08": "razao_garantia_minima_jan_ago", "09-12": "razao_garantia_minima_set_dez"},
    "numerator_facts": ["garantia_cessao_fiduciaria_valor", "garantia_af_estoque_valor",
                        "garantia_af_imovel_valor", "saldo_em_conta"],
    "denominator_fact": "saldo_devedor_cra",
}


def test_cessao_below_minimum_is_not_compliant():
    [evaluation] = cessao_fiduciaria_minima(FACTS, PARAMS, CESSAO_RULE)
    assert evaluation["compliant"] is False and evaluation["month"] == "2025-12"


def test_razao_uses_period_minimum_and_exact_decimal():
    [evaluation] = razao_garantia_minima(FACTS, PARAMS, RAZAO_RULE)
    assert evaluation["compliant"] is True
    assert evaluation["evidence"]["parametro"] == "razao_garantia_minima_set_dez"
    assert evaluation["evidence"]["razao"] == "2.9187"


def test_missing_or_unapproved_parameter_stops_rule():
    with pytest.raises(ParameterNotApproved):
        cessao_fiduciaria_minima(FACTS, {}, CESSAO_RULE)
