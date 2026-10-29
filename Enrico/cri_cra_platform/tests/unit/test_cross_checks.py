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
               parameter_name TEXT, parameter_value TEXT, unit TEXT, review_status TEXT, source_reference TEXT);
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
