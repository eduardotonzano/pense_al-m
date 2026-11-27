import json

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_quota_classes import OCT
from apoio_quota_classes import SEP
from apoio_quota_classes import SyntheticSeries

from fundos.quota_classes.mapping import PROPOSED
from fundos.quota_classes.mapping import REASON_UNMAPPED
from fundos.quota_classes.mapping import REJECTED
from fundos.quota_classes.mapping import REVIEWED
from fundos.quota_classes.report import format_review_report
from fundos.quota_classes.review import ACTION
from fundos.quota_classes.review import ENTITY_TYPE
from fundos.quota_classes.review import REVIEWERS
from fundos.quota_classes.review import ReviewError
from fundos.quota_classes.review import check_note
from fundos.quota_classes.review import check_reviewer
from fundos.quota_classes.review import plan_review
from fundos.quota_classes.review import review_report
from fundos.quota_classes.review import review_rule


REVIEWED_AT = "2026-11-26T15:00:00.000000+00:00"
NOTE = "conferido contra a secao 10.6 (nota ficticia)"


@pytest.fixture
def informe(full_connection):
    return SyntheticSeries(full_connection)


def rule_id(connection, pattern):
    return connection.execute(
        "SELECT id FROM quota_class_map WHERE pattern = ?", (pattern,)
    ).fetchone()[0]


def in_transaction(connection, function, *args, **kwargs):
    connection.execute("BEGIN")

    try:
        result = function(connection, *args, **kwargs)
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise

    return result


def populate(informe):
    """Classe 1: senior, mezanino e subordinada; classe 2: duas subordinadas sem
    mezanino; classe 3: so senior; classe 4: um rotulo fora do molde; uma
    subclasse de FIAGRO na classe 5; classe 6: mezanino e duas subordinadas."""

    _, first = informe.fund_and_class(1)
    informe.series(first, "Subclasse Senior S\u00e9rie 1")
    informe.series(first, "Subclasse Subordinada Mezanino 1 |")
    informe.series(first, "Subclasse Subordinada Subordinada 1 |")
    _, second = informe.fund_and_class(2)
    informe.series(second, "Subclasse Senior")
    informe.series(second, "Subclasse Subordinada Subordinada 1 |")
    informe.series(second, "Subclasse Subordinada |")
    _, third = informe.fund_and_class(3)
    informe.series(third, "Subclasse Senior")
    _, fourth = informe.fund_and_class(4)
    informe.series(fourth, "Cota Unica Ficticia")
    _, fifth = informe.fund_and_class(5)
    informe.fiagro_series(fifth, "Subclasse 1 (ou classe unica)")
    _, sixth = informe.fund_and_class(6)
    informe.series(sixth, "Subclasse Senior")
    informe.series(sixth, "Subclasse Subordinada Mezanino 1 |")
    informe.series(sixth, "Subclasse Subordinada Subordinada 1 |")
    informe.series(sixth, "Subclasse Subordinada Subordinada 2 |")


def test_report_counts_by_rule_unmapped_and_subjects(informe):
    populate(informe)

    report = review_report(informe.connection)
    (september,) = report.competences
    counted = {rule: (series, keys) for rule, series, keys in september.by_rule}
    connection = informe.connection

    assert september.reference_date == SEP
    assert september.series == 12
    assert counted[rule_id(connection, "subclasse senior")] == (4, 2)
    assert counted[rule_id(connection, "subclasse subordinada mezanino")] == (2, 1)
    assert counted[rule_id(connection, "subclasse subordinada subordinada")] == (4, 2)
    assert counted[rule_id(connection, "subclasse subordinada")] == (1, 1)
    assert [(u.label_key, u.series, u.variants, u.reason) for u in september.unmapped] == [
        ("cota unica ficticia", 1, 1, REASON_UNMAPPED)
    ]
    # (b): classe 2 (subordinada e ausente, sem mezanino) e classe 6 (duas
    # subordinadas com mezanino). (a): so a classe 2.
    assert september.subjects_order_not_informed == 2
    assert september.subjects_without_mezzanine == 1
    assert (september.absent_subtype_series, september.absent_subtype_subjects) == (1, 1)
    assert report.fiagro_series == 1
    assert report.last_review is None
    assert report.new_labels is None
    assert report.label_keys_total == 7


def test_report_by_competence(informe):
    _, fund_class = informe.fund_and_class(1)
    informe.series(fund_class, "Subclasse Senior", reference_date=SEP)
    informe.series(fund_class, "Subclasse Senior", reference_date=OCT, collected_at=T1)

    report = review_report(informe.connection)

    assert [c.reference_date for c in report.competences] == [SEP, OCT]
    assert [c.reference_date for c in review_report(informe.connection, [OCT]).competences] == [OCT]


def test_new_labels_since_the_last_review(informe):
    _, fund_class = informe.fund_and_class(1)
    informe.series(fund_class, "Subclasse Senior")
    connection = informe.connection
    in_transaction(
        connection,
        review_rule,
        rule_id(connection, "subclasse senior"),
        REVIEWED,
        "papel:revisor_fundos",
        NOTE,
        reviewed_at=REVIEWED_AT,
    )
    later = "2026-11-27T10:00:00.000000+00:00"
    informe.series(fund_class, "Subclasse Senior S\u00e9rie 9", reference_date=OCT, collected_at=later)
    informe.series(fund_class, "Cota Nova Ficticia", reference_date=OCT, collected_at=later)

    report = review_report(connection)

    assert report.last_review == REVIEWED_AT
    assert [(n.label_key, n.series, n.rule_id) for n in report.new_labels] == [
        ("cota nova ficticia", 1, None),
        ("subclasse senior serie 9", 1, rule_id(connection, "subclasse senior")),
    ]


def test_report_lines_have_only_counts_and_normalized_labels(informe):
    populate(informe)

    text = "\n".join(format_review_report(review_report(informe.connection)))

    assert "Regras: 4 (proposto 4, revisado 0, rejeitado 0)" in text
    assert "Ultima revisao: nenhuma revisao registrada" in text
    assert "Sem regra (ausente (rotulo nao mapeado)): 1 serie(s), 1 rotulo(s)" in text
    assert "    cota unica ficticia: 1 serie(s), 1 variante(s) original(is), rotulo_nao_mapeado" in text
    assert (
        "  Ordem entre subordinadas nao informada (assuntos com 2 ou mais series de subtipo"
        " subordinada ou ausente, com ou sem mezanino): 2"
    ) in text
    assert "  Assuntos com 2 ou mais series nao seniores e nenhum mezanino: 1" in text
    assert "FIAGRO (fora desta etapa): 1 serie(s) de FIAGRO sem mapa" in text
    assert "nenhuma revisao registrada; 7 rotulo(s) normalizado(s) de FIDC sem revisao" in text
    # Nunca o CNPJ, nem o rotulo original fora do molde com caixa e acento.
    for n in range(1, 7):
        assert make_test_cnpj(n) not in text

    assert "Cota Unica Ficticia" not in text
    assert "Subclasse Senior S\u00e9rie 1" not in text


def test_review_rule_writes_the_status_and_the_audit_log(informe):
    connection = informe.connection
    target = rule_id(connection, "subclasse senior")

    result = in_transaction(
        connection, review_rule, target, REVIEWED, "papel:revisor_fundos", NOTE, reviewed_at=REVIEWED_AT
    )

    assert (result.plan.before, result.plan.after, result.plan.changes) == (PROPOSED, REVIEWED, True)
    row = connection.execute(
        "SELECT review_status, reviewer, reviewed_at, review_note FROM quota_class_map WHERE id = ?",
        (target,),
    ).fetchone()
    assert tuple(row) == (REVIEWED, "papel:revisor_fundos", REVIEWED_AT, NOTE)
    audit = connection.execute(
        "SELECT actor, action, entity_type, entity_id, before_data, after_data, reason FROM audit_log"
        " WHERE id = ?",
        (result.audit_id,),
    ).fetchone()
    assert tuple(audit[:4]) == ("papel:revisor_fundos", ACTION, ENTITY_TYPE, target)
    assert json.loads(audit[4])["review_status"] == PROPOSED
    assert json.loads(audit[5]) == {
        "review_note": NOTE,
        "review_status": REVIEWED,
        "reviewed_at": REVIEWED_AT,
        "reviewer": "papel:revisor_fundos",
    }
    assert audit[6] == NOTE


def test_same_review_again_changes_nothing(informe):
    connection = informe.connection
    target = rule_id(connection, "subclasse senior")
    in_transaction(connection, review_rule, target, REVIEWED, "papel:revisor_fundos", NOTE)
    before = connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

    again = in_transaction(connection, review_rule, target, REVIEWED, "papel:dono_da_frente_fundos", NOTE)

    assert again.plan.changes is False
    assert again.audit_id is None
    assert connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before
    assert plan_review(connection, target, REVIEWED).changes is False


def test_review_transitions_and_errors(informe):
    connection = informe.connection
    target = rule_id(connection, "subclasse senior")
    in_transaction(connection, review_rule, target, REJECTED, "papel:dono_da_frente_fundos", NOTE)

    with pytest.raises(ReviewError, match="nao pode ir para revisado"):
        plan_review(connection, target, REVIEWED)

    with pytest.raises(ReviewError, match="Situacao recusada"):
        plan_review(connection, target, PROPOSED)

    with pytest.raises(ReviewError, match="Regra nao encontrada"):
        plan_review(connection, 999, REVIEWED)

    with pytest.raises(ReviewError, match="dentro de uma transacao"):
        review_rule(connection, rule_id(connection, "subclasse subordinada"), REVIEWED, REVIEWERS[0], NOTE)


@pytest.mark.parametrize(
    "reviewer",
    ["Pessoa Ficticia", "papel:outro_papel", "papel:Revisor_Fundos", "", None],
)
def test_reviewer_outside_the_closed_list_is_refused_without_echo(reviewer):
    with pytest.raises(ReviewError) as error:
        check_reviewer(reviewer)

    if reviewer:
        assert reviewer not in str(error.value)


def test_reviewers_are_the_two_roles():
    assert REVIEWERS == ("papel:dono_da_frente_fundos", "papel:revisor_fundos")


@pytest.mark.parametrize(
    "note, reason",
    [
        ("", "obrigatoria"),
        ("   ", "obrigatoria"),
        ("linha um\nlinha dois", "quebra de linha"),
        ("linha um\rlinha dois", "quebra de linha"),
        ("nota com acentua\u00e7\u00e3o", "ASCII imprimivel"),
        ("nota\tcom tab", "ASCII imprimivel"),
        ("x" * 201, "ate 200 caracteres"),
        ("documento " + "1" * 11, "11 digitos"),
        # Mascaras montadas por codigo, para o texto do teste nao ter nenhuma.
        ("cpf " + ".".join(["123", "456", "789"]) + "-09 ficticio", "mascara"),
        ("cnpj " + ".".join(["12", "345", "678"]) + "/" + "0001-95 ficticio", "mascara"),
        ("cnpj " + ".".join(["12", "ABC", "345"]) + "/" + "01DE-35 ficticio", "mascara"),
    ],
)
def test_note_is_refused_without_echo(note, reason):
    with pytest.raises(ReviewError, match=reason) as error:
        check_note(note)

    if note.strip():
        assert note.strip() not in str(error.value)


def test_note_at_the_limit_is_accepted():
    assert check_note("x" * 200) == "x" * 200
    assert check_note("  nota com 10 digitos 1234567890  ") == "nota com 10 digitos 1234567890"


def test_review_rule_checks_the_note_and_the_reviewer_first(informe):
    connection = informe.connection
    target = rule_id(connection, "subclasse senior")

    with pytest.raises(ReviewError, match="Nota recusada"):
        in_transaction(connection, review_rule, target, REVIEWED, "papel:revisor_fundos", "a\nb")

    with pytest.raises(ReviewError, match="Revisor recusado"):
        in_transaction(connection, review_rule, target, REVIEWED, "Pessoa Ficticia", NOTE)

    assert connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0


def test_report_only_reads(informe):
    populate(informe)
    before = informe.connection.total_changes

    review_report(informe.connection)

    assert informe.connection.total_changes == before
