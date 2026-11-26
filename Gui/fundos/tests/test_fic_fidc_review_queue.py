import json

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_fic_fidc import OCT
from apoio_fic_fidc import SEP
from apoio_fic_fidc import SyntheticFicFidc

from fundos.fic_fidc.classification import DENOMINATOR
from fundos.fic_fidc.classification import FIC_FIDC
from fundos.fic_fidc.classification import NUMERATOR
from fundos.fic_fidc.classification import RULE
from fundos.fic_fidc.classification import classify
from fundos.fic_fidc.review_queue import ACTION
from fundos.fic_fidc.review_queue import ACTOR
from fundos.fic_fidc.review_queue import DECISION_SOURCE
from fundos.fic_fidc.review_queue import REASON
from fundos.fic_fidc.review_queue import STALE
from fundos.fic_fidc.review_queue import canonical_json
from fundos.fic_fidc.review_queue import enqueue
from fundos.fic_fidc.review_queue import queue_entry
from fundos.fic_fidc.review_queue import queued
from fundos.fic_fidc.review_queue import scan_created
from fundos.fic_fidc.review_queue import to_enqueue


@pytest.fixture
def informe(full_connection):
    return SyntheticFicFidc(full_connection)


def audit_rows(connection):
    return [tuple(row) for row in connection.execute("SELECT * FROM audit_log ORDER BY id")]


def in_transaction(connection, function, *args):
    connection.execute("BEGIN")

    try:
        result = function(connection, *args)
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise

    return result


def four_bands(informe):
    """FIC-FIDC, revisao (2), nao classificado e sem dado; devolve as duas em revisao."""

    informe.put_ratio(informe.typed_class(1), "96", "100")
    review = [informe.typed_class(2), informe.typed_class(3)]
    informe.put_ratio(review[0], "8123", "10000")
    informe.put_ratio(review[1], "7001", "10000")
    informe.put_ratio(informe.typed_class(4), "10", "100")
    informe.put_ratio(informe.typed_class(5), "10", "0")
    return review


def test_only_manual_review_enters_the_queue(informe):
    review = four_bands(informe)

    new, already = to_enqueue(informe.connection, classify(informe.connection, SEP))

    assert [(e.entity_type, e.entity_id) for e in new] == [
        ("fund_classes", review[0].id),
        ("fund_classes", review[1].id),
    ]
    assert already == ()
    assert {e.reference_date for e in new} == {SEP}


def test_after_data_is_canonical_with_manual_as_the_deciding_source(informe):
    subject = informe.typed_class(1)
    ids = informe.put_ratio(subject, "8123", "10000")

    (entry,) = to_enqueue(informe.connection, classify(informe.connection, SEP))[0]
    data = json.loads(entry.after_data)

    assert entry.after_data == canonical_json(data)
    assert data == {
        "competencia": SEP,
        "regra": RULE,
        "fonte_da_decisao": DECISION_SOURCE,
        "numerador": {"campo": NUMERATOR, "observation_id": ids[NUMERATOR]},
        "denominador": {"campo": DENOMINATOR, "observation_id": ids[DENOMINATOR]},
    }
    assert DECISION_SOURCE == "MANUAL"
    # Nenhum valor, CNPJ nem nome: so os ids das observacoes.
    assert "8123" not in entry.after_data
    assert "10000" not in entry.after_data
    assert make_test_cnpj(1) not in entry.after_data


def test_enqueue_is_idempotent_and_only_inserts(informe):
    review = four_bands(informe)
    connection = informe.connection

    first = in_transaction(connection, enqueue, classify(connection, SEP))
    rows = audit_rows(connection)
    second = in_transaction(connection, enqueue, classify(connection, SEP))

    assert len(first.created) == 2
    assert first.already == 0
    assert second.created == ()
    assert second.already == 2
    assert audit_rows(connection) == rows

    stored = connection.execute(
        "SELECT actor, action, entity_type, entity_id, before_data, reason FROM audit_log ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in stored] == [
        (ACTOR, ACTION, "fund_classes", subject.id, None, REASON) for subject in review
    ]
    assert scan_created(connection, first.created) == 0


def test_classifying_and_reading_the_queue_never_write(informe):
    four_bands(informe)
    connection = informe.connection
    before = connection.total_changes

    classifications = classify(connection, SEP)
    to_enqueue(connection, classifications)
    queued(connection, SEP, classifications)

    assert connection.total_changes == before
    assert audit_rows(connection) == []


def test_enqueue_writes_only_inside_the_callers_transaction(informe):
    four_bands(informe)

    with pytest.raises(ValueError):
        enqueue(informe.connection, classify(informe.connection, SEP))

    assert audit_rows(informe.connection) == []


def test_reapresentation_adds_a_line_and_keeps_the_old_one(informe):
    subject = informe.typed_class(1)
    informe.put_ratio(subject, "80", "100")
    connection = informe.connection
    in_transaction(connection, enqueue, classify(connection, SEP))
    old = audit_rows(connection)

    later = informe.new_raw("reapresentacao", T1)
    new_ids = informe.put(subject, {NUMERATOR: "81"}, collected_at=T1, raw=later)
    second = in_transaction(connection, enqueue, classify(connection, SEP))

    assert len(second.created) == 1
    assert audit_rows(connection)[: len(old)] == old
    (review,) = queued(connection, SEP, classify(connection, SEP))
    assert review.entries == 2
    assert review.audit_id == second.created[0]
    assert review.numerator_observation_id == new_ids[NUMERATOR]
    assert review.flags == ()


def test_stale_flag_when_the_current_band_is_no_longer_review(informe):
    subject = informe.typed_class(1)
    informe.put_ratio(subject, "80", "100")
    connection = informe.connection
    in_transaction(connection, enqueue, classify(connection, SEP))

    later = informe.new_raw("reapresentacao", T1)
    informe.put(subject, {NUMERATOR: "96"}, collected_at=T1, raw=later)
    classifications = classify(connection, SEP)

    assert classifications[0].band == FIC_FIDC
    (review,) = queued(connection, SEP, classifications)
    assert review.flags == (STALE,)
    assert to_enqueue(connection, classifications) == ((), ())
    # Sem as classificacoes, nada e marcado.
    assert queued(connection, SEP)[0].flags == ()


def test_queue_entry_refuses_other_bands(informe):
    informe.put_ratio(informe.typed_class(1), "96", "100")

    with pytest.raises(ValueError):
        queue_entry(classify(informe.connection, SEP)[0])


def test_queue_is_read_by_competence(informe):
    subject = informe.typed_class(1)
    informe.put_ratio(subject, "80", "100", reference_date=SEP)
    informe.put_ratio(subject, "70", "100", reference_date=OCT)
    connection = informe.connection
    in_transaction(connection, enqueue, classify(connection, SEP))

    assert [r.reference_date for r in queued(connection, SEP)] == [SEP]
    assert queued(connection, OCT) == ()

    in_transaction(connection, enqueue, classify(connection, OCT))

    assert len(queued(connection, OCT)) == 1
    assert len(audit_rows(connection)) == 2


def test_fund_subject_goes_to_the_queue_as_funds(informe):
    fund = informe.typed_fund(1)
    informe.put_ratio(fund, "75", "100")

    (entry,) = to_enqueue(informe.connection, classify(informe.connection, SEP))[0]

    assert (entry.entity_type, entry.entity_id) == ("funds", fund.id)


def test_scan_counts_lines_out_of_format(informe):
    connection = informe.connection
    long_digits = "1" * 11
    bad = connection.execute(
        "INSERT INTO audit_log (actor, action, entity_type, entity_id, after_data)"
        " VALUES (?, ?, ?, ?, ?)",
        (ACTOR, ACTION, "fund_classes", 1, '{"x":"' + long_digits + '"}'),
    ).lastrowid

    assert scan_created(connection, [bad]) == 1
    assert scan_created(connection, [bad + 1]) == 1
