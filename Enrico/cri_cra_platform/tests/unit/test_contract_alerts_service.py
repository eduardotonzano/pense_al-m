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


def _unit_fact(value, unit):
    return [{"value": value, "unit": unit, "page_number": 17, "source_document_id": "df"}]


def test_fact_minimum_converts_thousands_and_accepts_exact_minimum():
    from credit_assets.services.contract_alerts_service import fact_minimum
    params = {"fundo_despesas_valor_minimo": {"parameter_value": "95000.00", "source_reference": "Termo"}}
    rule = {"parameter": "fundo_despesas_valor_minimo", "facts": ["caixa"], "label": "Fundo de despesas"}
    [at_minimum] = fact_minimum({"2026-06-30": {"caixa": _unit_fact("95", "BRL_mil")}}, params, rule)
    assert at_minimum["compliant"] is True and at_minimum["evidence"]["valor_brl"] == "95000"
    [below] = fact_minimum({"2026-06-30": {"caixa": _unit_fact("94999.99", "BRL")}}, params, rule)
    assert below["compliant"] is False
    with pytest.raises(ValueError, match="sem conversão"):
        fact_minimum({"2026-06-30": {"caixa": _unit_fact("1", "fração")}}, params, rule)


def test_fact_flag_alerts_only_on_listed_values_and_requires_approved_obligation():
    from credit_assets.services.contract_alerts_service import fact_flag
    params = {"garantias": {"parameter_value": "AF e CF", "source_reference": "Termo p.38"}}
    rule = {"parameter": "garantias", "facts": ["constituida"], "alert_values": ["NÃO"], "label": "Garantia"}
    facts = {"2025-12-31": {"constituida": _unit_fact("não ", "texto")},
             "2026-12-31": {"constituida": _unit_fact("SIM", "texto")}}
    results = {item["month"]: item["compliant"] for item in fact_flag(facts, params, rule)}
    assert results == {"2025-12": False, "2026-12": True}
    with pytest.raises(ParameterNotApproved):
        fact_flag(facts, {}, rule)


def test_obligation_fulfilled_by_approved_fact_is_compliant():
    from credit_assets.services.contract_alerts_service import obligation_deadlines
    params = {"dfs_ps": {"parameter_value": "90", "source_reference": "Termo"}}
    rule = {"warn_days": 30, "obligations": [
        {"parameter": "dfs_ps", "due": "2026-09-28", "label": "DFs do PS",
         "fulfilled_by_fact": {"fact": "df_total_ativo", "reference_date": "2026-06-30"}}]}
    facts = {"2026-06-30": {"df_total_ativo": _unit_fact("759167", "BRL_mil")}}
    [ok] = obligation_deadlines(params, rule, "2026-10-28", facts)
    assert ok["compliant"] is True
    [missing] = obligation_deadlines(params, rule, "2026-10-28", {})
    assert missing["compliant"] is False and "vencido há 30" in missing["message"]


def test_contract_rules_ignore_pending_facts(tmp_path):
    from credit_assets.database.connection import connect, initialize_database
    from credit_assets.services.contract_alerts_service import facts_by_date
    connection = connect(tmp_path / "f.db")
    initialize_database(connection)
    connection.execute("INSERT INTO executions (run_id, started_at, status) VALUES ('r', 'now', 'success')")
    connection.execute(
        """INSERT INTO assets (codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora, emissao, serie,
               created_at, updated_at) VALUES ('X', 'CRA', 'S', '1', '1', '1', 'now', 'now')""")
    connection.execute(
        """INSERT INTO documents (source_document_id, asset_id, category, document_name, publication_date,
               source, source_url, run_id) VALUES ('1', 1, 'Outro', 'DF', 'x', 'Fundos.NET', 'https://t/1', 'r')""")
    connection.execute(
        """INSERT INTO document_versions (document_id, local_file_path, file_format, file_size_bytes, file_hash,
               source_version, is_current, validation_status) VALUES (1, 'f.pdf', 'pdf', 1, ?, '1', 1, 'valid')""",
        ("a" * 64,))
    for name, status in (("aprovado", "approved"), ("pendente", "pending"), ("rejeitado", "rejected")):
        connection.execute(
            """INSERT INTO reported_facts (asset_id, document_version_id, page_number, page_text_sha256, fact_name,
                   reference_date, value, unit, excerpt, extraction_method, proposed_by, review_status)
               VALUES (1, 1, 1, 's', ?, '2026-06-30', '1', 'BRL', 'e', 'm', 'p', ?)""", (name, status))
    connection.commit()
    assert set(facts_by_date(connection, 1)["2026-06-30"]) == {"aprovado"}
