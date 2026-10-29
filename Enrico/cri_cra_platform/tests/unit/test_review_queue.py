from __future__ import annotations

import json

from credit_assets.review_queue import (
    classify_fact, classify_parameter, fact_names_in_rules,
)

FACT = {"extraction_method": "leitura_manual_com_trecho_literal"}


def test_divergence_visual_problem_and_flagged_note_go_first():
    assert classify_fact(FACT, None, None, True, False)[0] == 1
    assert classify_fact(FACT, None, {"verdict": "inconclusivo"}, False, False)[0] == 1
    assert classify_fact(FACT, None, {"verdict": "diverge"}, False, False)[0] == 1
    tier, reasons = classify_fact(FACT, "CONTRADIZ a nota 7.v", {"verdict": "confere"}, False, False)
    assert tier == 1 and "contradição" in reasons[0]


def test_alert_feed_and_ocr_are_tier_two():
    assert classify_fact(FACT, None, {"verdict": "confere"}, False, True)[0] == 2
    ocr = {"extraction_method": "ocr_com_conferencia_visual"}
    assert classify_fact(ocr, None, {"verdict": "confere"}, False, False)[0] == 2


def test_visual_check_decides_the_lower_tiers():
    confere = {"verdict": "confere"}
    assert classify_fact(FACT, "colunas pelo cabeçalho", confere, False, False)[0] == 3
    assert classify_fact(FACT, None, confere, False, False)[0] == 4
    assert classify_fact(FACT, None, None, False, False)[0] == 5
    assert classify_fact(FACT, "observação", None, False, False)[0] == 5


def test_parameters_follow_divergence_core_and_default():
    parameter = {"parameter_name": "x", "justification": ""}
    assert classify_parameter(parameter, set(), True)[0] == 1
    assert classify_parameter({**parameter, "justification": "Interpretação: inferido"}, set(), False)[0] == 1
    assert classify_parameter(parameter, {"x"}, False)[0] == 2
    assert classify_parameter(parameter, set(), False)[0] == 5


def test_fact_names_in_rules_reads_nested_rule_files(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"rules": {
        "r": {"facts": ["f1", "f2"], "fact": "f3",
              "obligations": [{"fulfilled_by_fact": {"fact": "f4", "reference_date": "2026"}}]},
        "s": {"parameter": "not_a_fact"}}}), encoding="utf-8")
    assert fact_names_in_rules(tmp_path) == {"f1", "f2", "f3", "f4"}
