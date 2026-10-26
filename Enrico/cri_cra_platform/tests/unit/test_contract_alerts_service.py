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


def _versioned(value, valid_from=None, valid_to=None):
    return {"parameter_value": value, "source_reference": "ref", "valid_from": valid_from, "valid_to": valid_to}


def test_parameter_validity_selects_version_in_force():
    from credit_assets.services.contract_alerts_service import parameter_row
    params = {"x": [_versioned("65000000", None, "2025-06-16"), _versioned("10000000", "2025-06-17")]}
    assert parameter_row(params, "x", "2024-12-31")["parameter_value"] == "65000000"
    assert parameter_row(params, "x", "2025-12-31")["parameter_value"] == "10000000"


def test_cessao_variant_after_assembly_adds_conta_garantia():
    params = {
        "cessao_fiduciaria_minima_na_verificacao": [_versioned("65000000.00", None, "2025-06-16")],
        "cessao_fiduciaria_mais_conta_minima_2sem": [_versioned("10000000.00", "2025-06-17")],
    }
    rule = {"months": ["12"], "variants": [
        {"parameter": "cessao_fiduciaria_minima_na_verificacao", "facts": ["garantia_cessao_fiduciaria_valor"]},
        {"parameter": "cessao_fiduciaria_mais_conta_minima_2sem",
         "facts": ["garantia_cessao_fiduciaria_valor", "saldo_em_conta"]},
    ]}
    [evaluation] = cessao_fiduciaria_minima(FACTS, params, rule)
    assert evaluation["evidence"]["parametro"] == "cessao_fiduciaria_mais_conta_minima_2sem"
    assert evaluation["evidence"]["valor"] == "2400424.38" and evaluation["compliant"] is False


def test_new_alert_supersedes_previous_open_alert_of_same_key(tmp_path):
    from credit_assets.database.connection import connect, initialize_database
    from credit_assets.models.asset import Asset
    from credit_assets.repositories.asset_repository import AssetRepository
    from credit_assets.services.data_quality_alerts_service import upsert_alert
    connection = connect(tmp_path / "a.db")
    initialize_database(connection)
    asset_id = AssetRepository(connection).upsert(Asset("CRA022009VM", "CRA", "Eco", "1", "190", "1", isin="BRECOACRABX0"))
    alert = {"month": "2025-12", "instance_key": None, "message": "m", "evidence": {"v": 1}}
    with connection:
        upsert_alert(connection, "contractual", "r", "0.1.0", "d", asset_id, alert, "warning", "run1", "now")
        upsert_alert(connection, "contractual", "r", "0.2.0", "d", asset_id, {**alert, "evidence": {"v": 2}}, "warning", "run2", "now")
    statuses = [row[0] for row in connection.execute("SELECT alert_status FROM data_quality_alerts ORDER BY alert_id")]
    assert statuses == ["resolved", "open"]
