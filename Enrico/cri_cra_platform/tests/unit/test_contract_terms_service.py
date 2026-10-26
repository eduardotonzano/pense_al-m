import json
from pathlib import Path

from credit_assets.services.contract_terms_service import find_candidates

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "config" / "contract_terms" / "termo_securitizacao.json").read_text(encoding="utf-8"))

PAGE = """“Razão de Garantia”     (i) no período compreendido entre janeiro e agosto de cada
                        ano, a Emitente deverá manter o valor do somatório das
                        garantias correspondente a, no mínimo 70% (setenta por cento) do valor
                        nominal dos CRA; e (ii) no mínimo, 120% (cento e vinte por
                        cento), observado que a Cessão Fiduciária deverá
                        corresponder a, no mínimo, R$ 65.000.000,00 (sessenta e cinco
                        milhões de reais), nos termos do CDCA.
“Recebíveis”: outra definição"""


def test_candidate_keeps_literal_excerpt_page_and_tokens():
    candidates = find_candidates([(20, PAGE, "hash")], CONFIG)
    razao = [c for c in candidates if c["topic"] == "razao_garantia"]
    assert len(razao) == 1
    candidate = razao[0]
    assert candidate["page_number"] == 20 and candidate["line_start"] == 1
    assert "no mínimo 70% (setenta por cento)" in candidate["excerpt"]
    assert candidate["values_found"]["percentual"] == ["70%", "120%"]
    assert candidate["values_found"]["moeda"] == ["R$ 65.000.000,00"]
    assert "CDCA" in candidate["values_found"]["referencia_documento"]


def test_no_match_returns_nothing():
    assert find_candidates([(1, "texto sem cláusulas relevantes", "h")], CONFIG) == []
