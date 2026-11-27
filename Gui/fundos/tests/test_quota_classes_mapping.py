import pytest

from conftest import create_schema

from fundos.quota_classes.mapping import ABSENT
from fundos.quota_classes.mapping import EQUALS
from fundos.quota_classes.mapping import MEZZANINE
from fundos.quota_classes.mapping import NOT_APPLICABLE
from fundos.quota_classes.mapping import NOT_SENIOR
from fundos.quota_classes.mapping import PROPOSED
from fundos.quota_classes.mapping import REASON_CONFLICT
from fundos.quota_classes.mapping import REASON_UNMAPPED
from fundos.quota_classes.mapping import REJECTED
from fundos.quota_classes.mapping import REVIEWED
from fundos.quota_classes.mapping import SENIOR
from fundos.quota_classes.mapping import STARTS_WITH
from fundos.quota_classes.mapping import SUBORDINATE
from fundos.quota_classes.mapping import QuotaClassRule
from fundos.quota_classes.mapping import all_rules
from fundos.quota_classes.mapping import classify_label
from fundos.quota_classes.mapping import load_rules
from fundos.quota_classes.mapping import map_table_exists
from fundos.quota_classes.mapping import normalized


def rule(rule_id, pattern, match_type, level, subtype, status=PROPOSED, valid_from=None, valid_to=None):
    return QuotaClassRule(
        id=rule_id,
        pattern=pattern,
        match_type=match_type,
        level=level,
        subtype=subtype,
        review_status=status,
        valid_from=valid_from,
        valid_to=valid_to,
    )


@pytest.fixture
def rules(full_connection):
    return load_rules(full_connection)


@pytest.mark.parametrize(
    "label, level, subtype",
    [
        # Os rotulos mais frequentes da secao 10.6 (09/2026), como vem.
        ("Subclasse Subordinada Subordinada 1 |", NOT_SENIOR, SUBORDINATE),
        ("Subclasse Senior S\u00e9rie 1", SENIOR, NOT_APPLICABLE),
        ("Subclasse Senior Subclasse 1", SENIOR, NOT_APPLICABLE),
        ("Subclasse Senior", SENIOR, NOT_APPLICABLE),
        ("Subclasse Subordinada |", NOT_SENIOR, ABSENT),
        ("Subclasse Senior S\u00e9rie 15", SENIOR, NOT_APPLICABLE),
        ("Subclasse Subordinada Mezanino 1 |", NOT_SENIOR, MEZZANINE),
        # Acento, caixa, espaco duplo e '|' em outros lugares.
        ("Subclasse S\u00eanior S\u00e9rie 2", SENIOR, NOT_APPLICABLE),
        ("SUBCLASSE   SENIOR  SERIE 3", SENIOR, NOT_APPLICABLE),
        ("subclasse|subordinada|mezanino 2", NOT_SENIOR, MEZZANINE),
        ("  Subclasse Subordinada  ", NOT_SENIOR, ABSENT),
    ],
)
def test_initial_rules_classify_the_usual_labels(rules, label, level, subtype):
    result = classify_label(label, rules)

    assert result.mapped
    assert (result.level, result.subtype) == (level, subtype)
    assert result.review_status == PROPOSED
    assert result.reason is None
    assert result.label_key == normalized(label)


def test_mezzanine_wins_over_the_generic_rule_even_with_a_prefix_generic():
    # Mesmo se a regra generica casasse por inicio, a mais especifica vence.
    prefix_generic = (
        rule(1, "subclasse subordinada", STARTS_WITH, NOT_SENIOR, ABSENT),
        rule(2, "subclasse subordinada mezanino", STARTS_WITH, NOT_SENIOR, MEZZANINE),
    )

    result = classify_label("Subclasse Subordinada Mezanino 1", prefix_generic)

    assert result.subtype == MEZZANINE
    assert result.rule.id == 2


def test_mezzanine_label_with_the_seeded_rules(rules):
    result = classify_label("Subclasse Subordinada Mezanino 1", rules)

    assert result.subtype == MEZZANINE
    assert result.rule.pattern == "subclasse subordinada mezanino"


@pytest.mark.parametrize(
    "label",
    [
        "Subclasse Subordinada Junior 1",  # fora do molde: nada de palpite
        "Cota Unica Ficticia",
        "Serie 1",
        "Subclasse Seniorx",  # o inicio so vale com espaco depois do padrao
    ],
)
def test_label_outside_the_template_is_not_guessed(rules, label):
    result = classify_label(label, rules)

    assert not result.mapped
    assert result.reason == REASON_UNMAPPED
    assert (result.level, result.subtype, result.review_status) == (None, None, None)


def test_rejected_rule_is_ignored():
    rejected = (rule(1, "subclasse senior", STARTS_WITH, SENIOR, NOT_APPLICABLE, status=REJECTED),)

    assert classify_label("Subclasse Senior", rejected).reason == REASON_UNMAPPED


def test_two_rules_of_the_same_length_are_a_conflict():
    both = (
        rule(1, "subclasse senior", STARTS_WITH, SENIOR, NOT_APPLICABLE),
        rule(2, "subclasse senior", EQUALS, NOT_SENIOR, SUBORDINATE),
    )

    result = classify_label("Subclasse Senior", both)

    assert result.reason == REASON_CONFLICT
    assert not result.mapped
    # Com outro texto so a regra de inicio casa.
    assert classify_label("Subclasse Senior Serie 1", both).rule.id == 1


def test_validity_is_respected(full_connection):
    full_connection.execute(
        "INSERT INTO quota_class_map (pattern, match_type, level, subtype, valid_from, valid_to)"
        " VALUES ('cota ficticia', 'inicio', 'senior', 'nao_se_aplica', '2026-10-31', '2026-12-31')"
    )

    september = load_rules(full_connection, "2026-09-30")
    october = load_rules(full_connection, "2026-10-31")
    january = load_rules(full_connection, "2027-01-31")

    assert classify_label("Cota Ficticia 1", september).reason == REASON_UNMAPPED
    assert classify_label("Cota Ficticia 1", october).level == SENIOR
    assert classify_label("Cota Ficticia 1", january).reason == REASON_UNMAPPED
    # As 4 regras iniciais tem vigencia aberta.
    assert len(september) == len(january) == 4


def test_load_rules_skips_rejected_and_all_rules_keeps_them(full_connection):
    rule_id = full_connection.execute(
        "SELECT id FROM quota_class_map WHERE pattern = 'subclasse senior'"
    ).fetchone()[0]
    full_connection.execute(
        "UPDATE quota_class_map SET review_status = 'rejeitado', reviewer = 'papel:revisor_fundos',"
        " reviewed_at = '2026-11-26T15:00:00.000000+00:00', review_note = 'nota ficticia' WHERE id = ?",
        (rule_id,),
    )

    assert [r.pattern for r in load_rules(full_connection)] == [
        "subclasse subordinada mezanino",
        "subclasse subordinada subordinada",
        "subclasse subordinada",
    ]
    assert len(all_rules(full_connection)) == 4
    assert all_rules(full_connection)[0].reviewer == "papel:revisor_fundos"


def test_reviewed_rule_carries_its_status():
    reviewed = (rule(1, "subclasse senior", STARTS_WITH, SENIOR, NOT_APPLICABLE, status=REVIEWED),)

    assert classify_label("Subclasse Senior", reviewed).review_status == REVIEWED


def test_classification_is_idempotent_and_only_reads(full_connection):
    before = full_connection.total_changes
    rules = load_rules(full_connection)
    first = [classify_label(label, rules) for label in ("Subclasse Senior", "Cota Unica Ficticia")]
    second = [classify_label(label, load_rules(full_connection)) for label in ("Subclasse Senior", "Cota Unica Ficticia")]

    assert first == second
    assert classify_label(first[0].label_key, rules) == first[0]
    assert full_connection.total_changes == before


def test_map_table_exists_only_with_the_006(full_connection, tmp_path):
    only_001 = create_schema(tmp_path / "so_001.db").connect()

    try:
        assert map_table_exists(full_connection)
        assert not map_table_exists(only_001)
    finally:
        only_001.close()


def test_empty_label_is_refused(rules):
    with pytest.raises(ValueError):
        classify_label(" | ", rules)
