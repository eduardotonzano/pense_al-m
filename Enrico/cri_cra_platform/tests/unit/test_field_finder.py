from __future__ import annotations

import json
import re

from credit_assets.contract_fields import load_catalog
from credit_assets.field_finder import found, hit_pages, load_topics
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "config" / "contract_terms"


def test_every_catalog_field_has_search_patterns():
    catalog = load_catalog(CONFIG / "standard_fields.json")
    topics = load_topics(CONFIG / "field_topics.json")
    assert {f["id"] for f in catalog["fields"]} <= set(topics)
    assert all(topics[f["id"]] for f in catalog["fields"])


def test_hit_pages_and_tolerance():
    pages = [(1, "capa"), (2, "A Data de Vencimento dos CRA é 30/09/2027"), (9, "Fundo de Despesas mínimo")]
    patterns = [re.compile("data de vencimento", re.IGNORECASE)]
    assert hit_pages(pages, patterns) == [2]
    assert found(3, [2], tolerance=1) and not found(5, [2], tolerance=1)
    assert not found(1, [])


def test_real_patterns_find_typical_clauses():
    topics = load_topics(CONFIG / "field_topics.json")
    sample = [
        (1, "DA 190ª (CENTÉSIMA NONAGÉSIMA) EMISSÃO, EM SÉRIE ÚNICA"),
        (2, "5.19.1. Não será atribuída nota de classificação de risco aos CRA."),
        (3, "O Fundo de Despesas deverá ser recomposto em 5 Dias Úteis"),
        (4, "multa moratória não compensatória de 2% e juros de mora de 1% ao mês"),
    ]
    assert hit_pages(sample, topics["identificacao.numero_emissao"]) == [1]
    assert hit_pages(sample, topics["obrigacoes.rating"]) == [2]
    assert hit_pages(sample, topics["garantias.fundo_despesas"]) == [3]
    assert hit_pages(sample, topics["remuneracao.encargos_moratorios"]) == [4]
