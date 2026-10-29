from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from credit_assets.contract_fields import coverage, load_catalog, match_field, summarize

CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "contract_terms" / "standard_fields.json"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG_PATH)


@pytest.mark.parametrize("name, expected", [
    ("isin_serie_1", "identificacao.isin"),
    ("data_vencimento_final_cdca_cra", "emissao.data_vencimento"),
    ("vencimento_serie_3", "emissao.data_vencimento"),
    ("remuneracao_serie_3_spread", "remuneracao.taxa"),
    ("razao_garantia_minima_set_dez", "garantias.razao_minima"),
    ("fundo_despesas_valor_minimo", "garantias.fundo_despesas"),
    ("covenant_divida_liquida_ebitda_max", "covenants.indices_financeiros"),
    ("va_cross_default_limite", "vencimento_antecipado.limites_e_prazos"),
    ("va_pagamento_prazo", "vencimento_antecipado.pagamento_e_quorum"),
    ("obrigacao_relatorio_rating", "obrigacoes.rating"),
    ("obrigacao_relatorio_destinacao_recursos", "obrigacoes.destinacao_recursos"),
    ("waiver_fee_2024", "resgate.waiver_fee"),
    ("quorum_waiver", "governanca.quorum_assembleia"),
])
def test_known_parameter_names_map_to_exactly_one_field(catalog, name, expected):
    assert match_field(name, catalog) == [expected]


def test_unknown_name_maps_to_nothing(catalog):
    assert match_field("nome_que_ninguem_conhece", catalog) == []


def test_catalog_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(
        '{"catalog_version": "x", "fields": ['
        '{"id": "a", "importance": "core", "aliases": ["^a$"]},'
        '{"id": "a", "importance": "core", "aliases": ["^b$"]}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicado"):
        load_catalog(path)


def _database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """CREATE TABLE assets (asset_id INTEGER, codigo_cetip TEXT, tipo_ativo TEXT);
           CREATE TABLE contract_parameters (asset_id INTEGER, parameter_name TEXT, review_status TEXT);
           INSERT INTO assets VALUES (1, 'A1', 'CRA'), (2, 'SEM', 'CRI');
           INSERT INTO contract_parameters VALUES
             (1, 'isin_serie_1', 'approved'),
             (1, 'valor_total_emissao', 'pending'),
             (1, 'nome_estranho', 'approved');"""
    )
    return connection


def test_coverage_distinguishes_approved_pending_and_missing(catalog):
    report = coverage(_database(), catalog)
    assert [a["codigo_cetip"] for a in report["assets"]] == ["A1"]  # ativo sem parâmetros não entra
    fields = report["assets"][0]["fields"]
    assert fields["identificacao.isin"]["status"] == "approved"
    assert fields["emissao.valor_total"]["status"] == "pending"
    assert fields["emissao.data_emissao"]["status"] == "missing"
    assert report["assets"][0]["unmapped_parameters"] == ["nome_estranho"]
    assert summarize(report, catalog)[0]["core"]["approved"] == 1


def test_coverage_does_not_modify_the_database(catalog):
    connection = _database()
    before = connection.execute("SELECT COUNT(*) FROM contract_parameters").fetchone()[0]
    coverage(connection, catalog)
    assert connection.execute("SELECT COUNT(*) FROM contract_parameters").fetchone()[0] == before
