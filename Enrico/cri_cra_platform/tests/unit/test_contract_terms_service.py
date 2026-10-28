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


def test_preferred_pages_uses_native_text_and_falls_back_to_ocr():
    import sqlite3
    from credit_assets.services.contract_terms_service import preferred_pages

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE document_text_pages (document_version_id INTEGER, page_number INTEGER,
           text TEXT, text_sha256 TEXT, extractor TEXT, extracted_at TEXT)"""
    )
    rows = [
        (1, 1, "texto nativo", "a", "pdftotext", "t"),
        (1, 1, "texto ocr", "b", "ocr: x", "t"),
        (1, 2, "", "c", "pdftotext", "t"),
        (1, 2, "so ocr", "d", "ocr: x", "t"),
        (1, 3, "", "e", "pdftotext", "t"),
    ]
    connection.executemany("INSERT INTO document_text_pages VALUES (?, ?, ?, ?, ?, ?)", rows)
    chosen = {row["page_number"]: (row["text"], row["extractor"]) for row in preferred_pages(connection, 1)}
    assert chosen == {1: ("texto nativo", "pdftotext"), 2: ("so ocr", "ocr: x"), 3: ("", "pdftotext")}
    assert [r["page_number"] for r in preferred_pages(connection, 1, 2)] == [2]
