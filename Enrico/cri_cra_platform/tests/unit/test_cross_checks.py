from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from credit_assets.cross_checks import load_checks, normalize, run_checks

CHECKS_PATH = Path(__file__).resolve().parents[2] / "config" / "contract_terms" / "cross_checks.json"


@pytest.fixture(scope="module")
def config():
    return load_checks(CHECKS_PATH)


def test_normalize_numbers_dates_and_codes():
    assert normalize("100000000.00", "number") == normalize("100000000", "number")
    assert normalize("0.0150", "number") == normalize("0.015", "number")
    assert normalize("abc", "number") is None
    assert normalize("2025-12-15", "date") == "2025-12-15"
    assert normalize("15/12/2025", "date") is None
    assert normalize(" bre co ", "code") == "BRECO"
    assert normalize("", "number") is None


def _database():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """CREATE TABLE assets (asset_id INTEGER, codigo_cetip TEXT, tipo_ativo TEXT);
           CREATE TABLE contract_parameters (parameter_id INTEGER PRIMARY KEY, asset_id INTEGER,
               parameter_name TEXT, parameter_value TEXT, unit TEXT, review_status TEXT, source_reference TEXT,
               valid_to TEXT);
           CREATE TABLE extracted_reports (report_id INTEGER PRIMARY KEY, asset_id INTEGER, document_id INTEGER,
               reference_date TEXT, is_current INTEGER, human_review_status TEXT);
           CREATE TABLE extracted_values (extracted_value_id INTEGER PRIMARY KEY, report_id INTEGER,
               xml_path TEXT, instance_key TEXT, original_value TEXT);
           CREATE TABLE reported_facts (fact_id INTEGER PRIMARY KEY, asset_id INTEGER, document_version_id INTEGER,
               page_number INTEGER, fact_name TEXT, value TEXT, unit TEXT, review_status TEXT);
           CREATE TABLE document_versions (version_id INTEGER PRIMARY KEY, document_id INTEGER);
           CREATE TABLE documents (document_pk INTEGER PRIMARY KEY, source_document_id TEXT, category TEXT, document_name TEXT);
           INSERT INTO assets VALUES (1, 'A1', 'CRA');
           INSERT INTO documents VALUES (1, '111', 'Outro', 'Aviso'), (2, '222', 'Outro', 'AF');
           INSERT INTO document_versions VALUES (1, 1), (2, 2);"""
    )
    return c


def _param(c, name, value, unit="BRL", status="approved"):
    c.execute("INSERT INTO contract_parameters (asset_id, parameter_name, parameter_value, unit, review_status, source_reference) VALUES (1, ?, ?, ?, ?, 'Termo')", (name, value, unit, status))


def _fact(c, name, value, unit="BRL", status="approved", version=1):
    c.execute("INSERT INTO reported_facts (asset_id, document_version_id, page_number, fact_name, value, unit, review_status) VALUES (1, ?, 1, ?, ?, ?, ?)", (version, name, value, unit, status))


def _result(results, check_id, group="-"):
    return next(r for r in results if r["check_id"] == check_id and r["group"] == group)


def test_agreement_divergence_and_single_source(config):
    c = _database()
    _param(c, "valor_total_emissao", "750000000.00")
    _fact(c, "aviso_valor_total_oferta", "750000000")            # concorda
    _param(c, "quantidade_serie_1", "233142", "CRA")
    _fact(c, "af_serie_1_quantidade_emitida", "0", "CRA", version=2)  # diverge
    _param(c, "data_emissao", "2025-12-15", "data")               # só uma fonte
    results = run_checks(c, config)
    assert _result(results, "valor_total_emissao")["verdict"] == "concordam"
    divergent = _result(results, "quantidade_serie", "1")
    assert divergent["verdict"] == "divergem" and divergent["values"] == ["0", "233142"]
    assert _result(results, "data_emissao")["verdict"] == "uma_fonte"


def test_rejected_values_and_other_units_are_ignored(config):
    c = _database()
    _param(c, "valor_total_emissao", "100.00")
    _fact(c, "aviso_valor_total_oferta", "999.00", status="rejected")
    _fact(c, "af_volume_emitido", "100000", unit="BRL_mil", version=2)
    results = run_checks(c, config)
    assert _result(results, "valor_total_emissao")["verdict"] == "uma_fonte"


def test_series_are_grouped_separately(config):
    c = _database()
    for n, qty in (("1", "10"), ("2", "20")):
        _param(c, f"quantidade_serie_{n}", qty, "CRA")
        _fact(c, f"anuncio_serie_{n}_quantidade", qty, "CRA", version=2)
    results = run_checks(c, config)
    assert _result(results, "quantidade_serie", "1")["verdict"] == "concordam"
    assert _result(results, "quantidade_serie", "2")["verdict"] == "concordam"


def test_checks_never_write(config):
    c = _database()
    _param(c, "valor_total_emissao", "1")
    before = c.execute("SELECT COUNT(*) FROM contract_parameters").fetchone()[0]
    run_checks(c, config)
    assert c.execute("SELECT COUNT(*) FROM contract_parameters").fetchone()[0] == before


def test_tokenize_separates_multiplier_from_rate():
    from credit_assets.cross_checks import tokenize
    assert tokenize("100% da Taxa DI + spread 1,50% a.a.", "remuneracao") == {"idx=DI", "mult=100", "taxa=1.5"}
    assert tokenize("1,5% a.a. sobre 100% do CDI", "remuneracao") == {"idx=DI", "mult=100", "taxa=1.5"}
    assert tokenize("100% da variação do indexador (CDI) + 4,5% a.a.", "remuneracao") == {"idx=DI", "mult=100", "taxa=4.5"}
    assert tokenize("Prefixada 14,80% a.a.", "remuneracao") == {"idx=PREFIXADA", "taxa=14.8"}
    assert tokenize("IPCA + 8,88% a.a.", "remuneracao") == {"idx=IPCA", "taxa=8.88"}
    assert tokenize("108% da Taxa DI", "remuneracao") == {"idx=DI", "mult=108"}


def test_tokenize_names_and_cnpj():
    from credit_assets.cross_checks import tokenize
    tokens = tokenize("Alibem Alimentos S.A.; CNPJ 03.941.052/0001-50; NIRE 43", "nome")
    assert "cnpj=03941052000150" in tokens and "w=ALIBEM" in tokens and "w=ALIMENTOS" in tokens
    assert "w=NIRE" not in tokens


def _text_database(entries):
    c = _database()
    for kind, name, value in entries:
        (_param if kind == "p" else _fact)(c, name, value, unit="texto")
    return c


def test_text_verdict_agree_compatible_and_conflict(config):
    # concordam
    c = _text_database([("p", "remuneracao_serie_3", "100% da Taxa DI + 1,5% a.a."),
                        ("f", "af_serie_3_remuneracao", "100% do CDI + 1,50%")])
    assert _result(run_checks(c, config), "remuneracao_serie_texto", "3")["verdict"] == "concordam"
    # compatíveis: uma fonte traz só parte
    c = _text_database([("p", "remuneracao_serie_3", "100% da Taxa DI + 1,5% a.a."),
                        ("f", "af_serie_3_remuneracao", "CDI + 1,5%")])
    assert _result(run_checks(c, config), "remuneracao_serie_texto", "3")["verdict"] == "compativeis"
    # divergem: indexador diferente
    c = _text_database([("p", "remuneracao_serie_1", "Prefixada 14,80% a.a."),
                        ("f", "af_serie_1_remuneracao", "CDI")])
    assert _result(run_checks(c, config), "remuneracao_serie_texto", "1")["verdict"] == "divergem"
    # divergem: taxa diferente
    c = _text_database([("p", "remuneracao_serie_4", "100% da Taxa DI + 2,5% a.a."),
                        ("f", "af_serie_4_remuneracao", "CDI + 3,5%")])
    assert _result(run_checks(c, config), "remuneracao_serie_texto", "4")["verdict"] == "divergem"


def test_text_check_requires_tokenizer(tmp_path):
    path = tmp_path / "c.json"
    path.write_text('{"version": "x", "checks": [{"id": "a", "label": "a", "kind": "text"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="tokenizer"):
        load_checks(path)


def test_tokenize_pre_means_prefixada():
    from credit_assets.cross_checks import tokenize
    assert tokenize("PRÉ 14,8000 % a.a", "remuneracao") == {"idx=PREFIXADA", "taxa=14.8"}


def _informe_database():
    c = _database()
    c.executescript(
        """INSERT INTO extracted_reports VALUES (1, 1, 1, '2026-01-31', 1, 'approved'),
                                                (2, 1, 2, '2026-02-28', 1, 'approved');
           INSERT INTO extracted_values VALUES
             (1, 1, '/InformeMensalCRA/DadosGerais/Series/Serie/DataVencimento', '1', '2020-01-01'),
             (2, 2, '/InformeMensalCRA/DadosGerais/Series/Serie/DataVencimento', '1', '2029-07-16'),
             (3, 2, '/InformeMensalCRA/DadosGerais/Series/Serie/DataVencimento', '2', '2030-07-15');"""
    )
    return c


def test_informe_uses_latest_current_report_and_groups_by_series(config):
    c = _informe_database()
    _param(c, "vencimento_serie_1", "2030-12-18", "data")
    _param(c, "vencimento_serie_2", "2030-07-15", "data")
    results = run_checks(c, config)
    one = _result(results, "vencimento_serie", "1")
    assert one["verdict"] == "divergem" and one["values"] == ["2029-07-16", "2030-12-18"]
    assert {e["origin"] for e in one["entries"]} == {"parâmetro", "informe"}
    assert _result(results, "vencimento_serie", "2")["verdict"] == "concordam"


def test_superseded_parameters_are_ignored(config):
    c = _informe_database()
    _param(c, "data_vencimento_termo_original", "2027-09-30", "data")
    c.execute("UPDATE contract_parameters SET valid_to = '2024-03-13'")
    _param(c, "data_vencimento_final_cdca_cra", "2026-12-30", "data")
    c.execute("DELETE FROM extracted_values")
    c.execute("INSERT INTO extracted_values VALUES (9, 2, '/InformeMensalCRA/DadosGerais/Series/Serie/DataVencimento', '1', '2026-12-30')")
    result = _result(run_checks(c, config), "data_vencimento")
    assert result["verdict"] == "concordam" and result["values"] == ["2026-12-30"]


def test_fixed_spread_next_to_an_index_is_not_a_prefixed_series():
    from credit_assets.cross_checks import tokenize
    assert tokenize("100% da variação do indexador (DI) + taxa prefixada 1,5% a.a.", "remuneracao") == {
        "idx=DI", "mult=100", "taxa=1.5"}
    assert tokenize("Taxa prefixada 8,88% a.a. (indexador IPCA)", "remuneracao") == {"idx=IPCA", "taxa=8.88"}
    assert tokenize("108% da variação do indexador (DI)", "remuneracao") == {"idx=DI", "mult=108"}
    assert tokenize("Taxa prefixada 14,8% a.a.", "remuneracao") == {"idx=PREFIXADA", "taxa=14.8"}


def test_multiplier_with_number_in_words_before_the_index():
    from credit_assets.cross_checks import tokenize
    assert tokenize("108,00% (cento e oito por cento) da Taxa DI", "remuneracao") == {"idx=DI", "mult=108"}


def test_long_wording_between_multiplier_and_index():
    from credit_assets.cross_checks import tokenize
    text = "108,00% (cento e oito por cento) da variação acumulada das taxas médias diárias dos DI"
    assert tokenize(text, "remuneracao") == {"idx=DI", "mult=108"}
    assert tokenize("8,88% ao ano acima da variação do IPCA", "remuneracao") == {"idx=IPCA", "taxa=8.88"}
    assert tokenize("1,5% a.a. sobre 100% do CDI", "remuneracao") == {"idx=DI", "mult=100", "taxa=1.5"}
