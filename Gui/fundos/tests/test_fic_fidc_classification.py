from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_fic_fidc import FIAGRO
from apoio_fic_fidc import OCT
from apoio_fic_fidc import OTHER_TAB_I_FIELD
from apoio_fic_fidc import SEP
from apoio_fic_fidc import SyntheticFicFidc

from fundos.fic_fidc.classification import ABOVE_100
from fundos.fic_fidc.classification import DENOMINATOR
from fundos.fic_fidc.classification import FIAGRO_IN_CADASTRO
from fundos.fic_fidc.classification import FIC_FIDC
from fundos.fic_fidc.classification import MANUAL_REVIEW
from fundos.fic_fidc.classification import NOT_CLASSIFIED
from fundos.fic_fidc.classification import NUMERATOR
from fundos.fic_fidc.classification import OPEN_CONFLICT
from fundos.fic_fidc.classification import REASON_NEGATIVE_NUMERATOR
from fundos.fic_fidc.classification import REASON_NO_INFORME
from fundos.fic_fidc.classification import RULE
from fundos.fic_fidc.classification import RULE_TEXT
from fundos.fic_fidc.classification import band
from fundos.fic_fidc.classification import classify
from fundos.indicators.reading import open_read_only
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_NEGATIVE_DENOMINATOR
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.indicators.values import REASON_ZERO_DENOMINATOR


@pytest.fixture
def informe(full_connection):
    return SyntheticFicFidc(full_connection)


def only(results):
    assert len(results) == 1
    return results[0]


def classified(informe, cotas, ativo, n=1):
    subject = informe.typed_class(n)
    informe.put_ratio(subject, cotas, ativo)
    return only(classify(informe.connection, SEP, [subject]))


@pytest.mark.parametrize(
    "cotas, ativo, expected",
    [
        ("95", "100", FIC_FIDC),  # 95% exato
        ("9499", "10000", MANUAL_REVIEW),  # 94,99%
        ("67", "100", MANUAL_REVIEW),  # 67% exato
        ("6699", "10000", NOT_CLASSIFIED),  # 66,99%
        ("0", "100", NOT_CLASSIFIED),  # zero informado e zero
        ("100", "100", FIC_FIDC),
    ],
)
def test_cuts_of_decision_6(informe, cotas, ativo, expected):
    result = classified(informe, cotas, ativo)

    assert result.band == expected
    assert result.reason is None
    assert result.flags == ()
    assert result.numerator.value == Decimal(cotas)
    assert result.denominator.value == Decimal(ativo)
    assert result.share.state == PRESENT


def test_above_100_classifies_without_cutting(informe):
    result = classified(informe, "130", "100")

    assert result.band == FIC_FIDC
    assert result.flags == (ABOVE_100,)
    assert result.share.value == Decimal(130)


@pytest.mark.parametrize(
    "cotas, ativo, reason",
    [
        ("10", "0", REASON_ZERO_DENOMINATOR),
        ("10", "-1", REASON_NEGATIVE_DENOMINATOR),
        ("-1", "100", REASON_NEGATIVE_NUMERATOR),
        ("10", None, REASON_MISSING),  # ativo ausente, cotas presentes
        (None, "100", REASON_MISSING),  # cotas ausentes, ativo positivo
    ],
)
def test_no_data_with_reason_never_zero(informe, cotas, ativo, reason):
    result = classified(informe, cotas, ativo)

    assert result.band == NO_DATA
    assert result.label == "sem dado"
    assert result.reason == reason
    assert result.share.state == NO_DATA
    assert result.share.value is None
    assert result.share.reason == reason


def test_both_fields_missing_in_a_subject_with_the_informe(informe):
    subject = informe.typed_class(1)
    informe.put(subject, {OTHER_TAB_I_FIELD: "500"})

    result = only(classify(informe.connection, SEP))

    assert result.subject == subject
    assert result.band == NO_DATA
    assert result.reason == REASON_MISSING
    assert result.numerator.state == NO_DATA
    assert result.denominator.state == NO_DATA


def test_value_that_is_not_a_number_is_unexpected_type(informe):
    subject = informe.typed_class(1)
    informe.put_ratio(subject, cotas="90")
    informe.put(subject, {DENOMINATOR: "texto ficticio"}, value_type="text")

    result = only(classify(informe.connection, SEP))

    assert result.band == NO_DATA
    assert result.reason == REASON_UNEXPECTED_TYPE
    assert "texto ficticio" not in repr(result)


def test_subject_without_informe_in_the_competence(informe):
    with_informe = informe.typed_class(1)
    informe.put_ratio(with_informe, "96", "100")
    without = informe.typed_class(2)

    results = classify(informe.connection, SEP, [with_informe, without])

    assert [r.band for r in results] == [FIC_FIDC, NO_DATA]
    assert results[1].reason == REASON_NO_INFORME
    assert results[1].numerator.reason == REASON_NO_INFORME
    assert results[1].denominator.reason == REASON_NO_INFORME
    # Sem subjects, so os assuntos com tab_I na competencia.
    assert [r.subject for r in classify(informe.connection, SEP)] == [with_informe]


def test_cross_multiplication_is_exact_where_float_would_round(informe):
    # Montados por codigo: 94 seguido de 21 noves e ,99 sobre 10 elevado a 23.
    cotas = "94" + "9" * 21 + ".99"
    ativo = "1" + "0" * 23

    # A divisao em float daria 95% e classificaria como FIC-FIDC.
    assert float(cotas) / float(ativo) >= 0.95

    result = classified(informe, cotas, ativo)

    assert result.band == MANUAL_REVIEW
    assert result.share.value < 95
    assert band(Decimal(cotas), Decimal(ativo)) == MANUAL_REVIEW


def test_band_takes_only_decimal_with_positive_asset():
    with pytest.raises(TypeError):
        band(0.95, 1.0)

    with pytest.raises(TypeError):
        band(Decimal(1), 2)

    with pytest.raises(ValueError):
        band(Decimal(1), Decimal(0))

    with pytest.raises(ValueError):
        band(Decimal(-1), Decimal(1))

    with pytest.raises(ValueError):
        band(Decimal("NaN"), Decimal(1))


def test_each_number_carries_field_competence_source_and_observation(informe):
    subject = informe.typed_class(1)
    ids = informe.put_ratio(subject, "80", "100")

    result = only(classify(informe.connection, SEP))

    assert result.rule == RULE
    assert result.rule_text == RULE_TEXT
    assert result.label == "em revisao manual"
    assert result.reference_date == SEP

    for amount, name in ((result.numerator, NUMERATOR), (result.denominator, DENOMINATOR)):
        (part,) = amount.parts
        assert part.field_name == name
        assert part.reference_date == SEP
        assert part.source_code == "CVM_DADOS_ABERTOS"
        assert part.observation_id == ids[name]
        assert part.open_conflict is False


def test_source_priority_inside_the_competence_and_open_conflict(informe):
    subject = informe.typed_class(1)
    cvm = informe.put_ratio(subject, "50", "100")
    manual = informe.put_ratio(subject, "96", "100", source="manual", collected_at=T1)
    informe.open_conflict(NUMERATOR, SEP, cvm[NUMERATOR], manual[NUMERATOR])

    result = only(classify(informe.connection, SEP))

    assert result.band == FIC_FIDC
    assert result.numerator.parts[0].source_code == "MANUAL"
    assert result.numerator.parts[0].observation_id == manual[NUMERATOR]
    assert result.flags == (OPEN_CONFLICT,)


def test_competences_never_mix(informe):
    subject = informe.typed_class(1)
    informe.put_ratio(subject, "96", "100", reference_date=SEP)
    informe.put_ratio(subject, "50", "100", reference_date=OCT)
    only_october = informe.typed_class(2)
    informe.put_ratio(only_october, "99", "100", reference_date=OCT)

    september = classify(informe.connection, SEP)
    october = classify(informe.connection, OCT)

    assert [(r.subject, r.band) for r in september] == [(subject, FIC_FIDC)]
    assert [r.band for r in october] == [NOT_CLASSIFIED, FIC_FIDC]
    assert {r.numerator.parts[0].reference_date for r in october} == {OCT}
    # O assunto so de outubro, pedido em setembro, nao le o valor de outubro.
    assert only(classify(informe.connection, SEP, [only_october])).reason == REASON_NO_INFORME


def test_fiagro_class_with_the_fidc_informe_is_classified_and_flagged(informe):
    subject = informe.typed_class(1, kind=FIAGRO, fund_kind=FIAGRO)
    informe.put_ratio(subject, "97", "100")

    result = only(classify(informe.connection, SEP))

    assert result.band == FIC_FIDC
    assert result.cadastro_type == "FIAGRO"
    assert result.flags == (FIAGRO_IN_CADASTRO,)


def test_fund_subject_of_the_informe(informe):
    fund = informe.typed_fund(1)
    informe.put_ratio(fund, "70", "100")

    result = only(classify(informe.connection, SEP))

    assert result.subject.kind == FUND_SUBJECT
    assert result.band == MANUAL_REVIEW
    assert result.cadastro_type == "FIDC"


def test_competence_must_be_the_last_day_of_the_month(informe):
    with pytest.raises(ValueError):
        classify(informe.connection, "2026-09-29")

    with pytest.raises(ValueError):
        classify(informe.connection, "30/09/2026")


def test_empty_subject_list_returns_nothing(informe):
    informe.put_ratio(informe.typed_class(1), "96", "100")

    assert classify(informe.connection, SEP, []) == ()


def test_no_cnpj_in_repr_or_str(informe):
    for n in (1, 2, 3):
        informe.put_ratio(informe.typed_class(n), str(60 + 15 * n), "100")

    text = repr(classify(informe.connection, SEP)) + str(classify(informe.connection, SEP))

    for n in (1, 2, 3):
        assert make_test_cnpj(n) not in text


def test_classification_only_reads(full_db):
    connection = full_db.connect()

    try:
        informe = SyntheticFicFidc(connection)
        informe.put_ratio(informe.typed_class(1), "80", "100")
    finally:
        connection.close()

    reader = open_read_only(full_db.database_path)

    try:
        before = reader.total_changes
        result = only(classify(reader, SEP))
        assert reader.total_changes == before
        assert reader.in_transaction is False
    finally:
        reader.close()

    assert result.band == MANUAL_REVIEW
