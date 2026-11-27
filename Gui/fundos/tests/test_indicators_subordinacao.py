from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_quota_classes import OCT
from apoio_quota_classes import SEP
from apoio_quota_classes import SyntheticSeries
from conftest import create_schema

from fundos.indicators.subordinacao import ABSENT_SUBTYPE
from fundos.indicators.subordinacao import CALCULATED
from fundos.indicators.subordinacao import FORMULA
from fundos.indicators.subordinacao import LAYER_MEZZANINE
from fundos.indicators.subordinacao import LAYER_SENIOR
from fundos.indicators.subordinacao import MULTIPLE_MEZZANINE
from fundos.indicators.subordinacao import NO_SUBORDINATE
from fundos.indicators.subordinacao import OPEN_CONFLICT
from fundos.indicators.subordinacao import ORDER_NOT_INFORMED
from fundos.indicators.subordinacao import OUTSIDE_1PCT
from fundos.indicators.subordinacao import PART_ABSENT
from fundos.indicators.subordinacao import PART_MEZZANINE
from fundos.indicators.subordinacao import PART_SENIOR
from fundos.indicators.subordinacao import PART_SUBORDINATE
from fundos.indicators.subordinacao import PL
from fundos.indicators.subordinacao import PL_ABSENT
from fundos.indicators.subordinacao import PL_NOT_POSITIVE
from fundos.indicators.subordinacao import PROPOSED_MAP
from fundos.indicators.subordinacao import QUANTITY
from fundos.indicators.subordinacao import REASON_NEGATIVE
from fundos.indicators.subordinacao import REASON_NO_MAP
from fundos.indicators.subordinacao import REASON_NO_TAB_X_2
from fundos.indicators.subordinacao import REASON_ZERO_TOTAL
from fundos.indicators.subordinacao import SUM_OUTSIDE_PL
from fundos.indicators.subordinacao import UNIT_VALUE
from fundos.indicators.subordinacao import WITHIN_1PCT
from fundos.indicators.subordinacao import subordinacao
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.quota_classes.mapping import PROPOSED
from fundos.quota_classes.mapping import REASON_UNMAPPED
from fundos.quota_classes.mapping import REVIEWED


SENIOR = "Subclasse Senior S\u00e9rie 1"
MEZZANINE = "Subclasse Subordinada Mezanino 1 |"
SUBORDINATE = "Subclasse Subordinada Subordinada 1 |"
SUBORDINATE_2 = "Subclasse Subordinada Subordinada 2 |"
GENERIC = "Subclasse Subordinada |"


@pytest.fixture
def informe(full_connection):
    return SyntheticSeries(full_connection)


def build(informe, n, series, pl="AUTO", reference_date=SEP):
    """Classe ficticia com as series (rotulo, quantidade, valor da cota) e o PL.

    pl "AUTO" grava o PL igual a soma das series; None nao grava o PL.
    """

    _, fund_class = informe.fund_and_class(n)
    total = Decimal(0)
    ids = []

    for label, quantity, unit_value in series:
        ids.append(
            informe.series(
                fund_class, label, quantity=quantity, unit_value=unit_value, reference_date=reference_date
            )
        )

        if quantity is not None and unit_value is not None:
            try:
                total += Decimal(quantity) * Decimal(unit_value)
            except ArithmeticError:
                pass

    if pl == "AUTO":
        pl = str(total)

    if pl is not None:
        informe.put(fund_class, {PL: pl}, reference_date=reference_date)

    return fund_class, ids


def only(results):
    assert len(results) == 1
    return results[0]


def result_for(informe, subject, reference_date=SEP):
    return only(subordinacao(informe.connection, reference_date, [subject]))


def review_all(connection):
    connection.execute(
        "UPDATE quota_class_map SET review_status = 'revisado', reviewer = 'papel:revisor_fundos',"
        " reviewed_at = '2026-11-27T12:00:00.000000+00:00', review_note = 'nota ficticia'"
    )


def test_only_senior_series_is_zero_with_the_explanation(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "100", "1")])

    result = result_for(informe, fund_class)

    assert result.state == CALCULATED
    assert result.subordinacao_total.value == Decimal(0)
    assert NO_SUBORDINATE in result.flags
    assert [layer.name for layer in result.layers] == [LAYER_SENIOR]
    assert [part.name for part in result.parts] == [PART_SENIOR]
    assert result.formula == FORMULA


def test_senior_and_subordinate(informe):
    fund_class, ids = build(informe, 1, [(SENIOR, "100", "1"), (SUBORDINATE, "25", "1")])

    result = result_for(informe, fund_class)

    assert result.state == CALCULATED
    assert result.total == Decimal(125)
    assert result.subordinacao_total.value == Decimal(20)
    assert result.part(PART_SUBORDINATE).value == Decimal(25)
    assert result.part(PART_SUBORDINATE).series_ids == (ids[1],)
    assert result.part(PART_SENIOR).share.value == Decimal(80)
    assert [layer.name for layer in result.layers] == [LAYER_SENIOR]
    assert result.layer(LAYER_SENIOR).cushion.value == Decimal(20)
    assert result.pl_check == WITHIN_1PCT
    assert result.flags == (PROPOSED_MAP,)


def test_senior_mezzanine_and_subordinate_have_the_mezzanine_layer(informe):
    fund_class, _ = build(
        informe, 1, [(SENIOR, "60", "1"), (MEZZANINE, "25", "1"), (SUBORDINATE, "15", "1")]
    )

    result = result_for(informe, fund_class)

    assert result.subordinacao_total.value == Decimal(40)
    assert result.layer(LAYER_SENIOR).cushion.value == Decimal(40)
    assert result.layer(LAYER_MEZZANINE).cushion.value == Decimal(15)
    assert result.part(PART_MEZZANINE).share.value == Decimal(25)
    assert ORDER_NOT_INFORMED not in result.flags


def test_mezzanine_and_two_subordinates_has_the_flag_and_the_mezzanine_layer(informe):
    fund_class, _ = build(
        informe,
        1,
        [(SENIOR, "50", "1"), (MEZZANINE, "20", "1"), (SUBORDINATE, "20", "1"), (SUBORDINATE_2, "10", "1")],
    )

    result = result_for(informe, fund_class)

    assert ORDER_NOT_INFORMED in result.flags
    # A marca so avisa: nao muda a subordinacao total nem o colchao do mezanino.
    assert result.subordinacao_total.value == Decimal(50)
    assert result.layer(LAYER_MEZZANINE).cushion.value == Decimal(30)


def test_two_subordinates_without_mezzanine_has_the_flag_and_no_mezzanine_layer(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "70", "1"), (SUBORDINATE, "20", "1"), (GENERIC, "10", "1")])

    result = result_for(informe, fund_class)

    assert ORDER_NOT_INFORMED in result.flags
    assert result.subordinacao_total.value == Decimal(30)
    assert result.layer(LAYER_MEZZANINE) is None
    assert ABSENT_SUBTYPE in result.flags


def test_absent_subtype_has_no_mezzanine_layer_even_with_mezzanine(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "70", "1"), (MEZZANINE, "20", "1"), (GENERIC, "10", "1")])

    result = result_for(informe, fund_class)

    assert ABSENT_SUBTYPE in result.flags
    assert ORDER_NOT_INFORMED not in result.flags
    assert result.part(PART_ABSENT).value == Decimal(10)
    assert result.layer(LAYER_MEZZANINE) is None
    assert result.subordinacao_total.value == Decimal(30)


def test_two_mezzanines_are_one_layer_with_a_flag(informe):
    fund_class, _ = build(
        informe,
        1,
        [(SENIOR, "60", "1"), (MEZZANINE, "10", "1"), ("Subclasse Subordinada Mezanino 2 |", "10", "1"), (SUBORDINATE, "20", "1")],
    )

    result = result_for(informe, fund_class)

    assert MULTIPLE_MEZZANINE in result.flags
    assert result.part(PART_MEZZANINE).value == Decimal(20)
    assert result.layer(LAYER_MEZZANINE).cushion.value == Decimal(20)


def test_unmapped_label_gives_no_partial_result(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "100", "1"), ("Cota Unica Ficticia", "10", "1")])

    result = result_for(informe, fund_class)

    assert result.state == NO_DATA
    assert result.reason == REASON_UNMAPPED
    assert result.total is None
    assert result.subordinacao_total is None
    assert len(result.series) == 2


def test_rejected_rule_leaves_the_label_unmapped(informe):
    informe.connection.execute(
        "UPDATE quota_class_map SET review_status = 'rejeitado', reviewer = 'papel:revisor_fundos',"
        " reviewed_at = '2026-11-27T12:00:00.000000+00:00', review_note = 'nota ficticia'"
        " WHERE pattern = 'subclasse subordinada subordinada'"
    )
    fund_class, _ = build(informe, 1, [(SENIOR, "100", "1"), (SUBORDINATE, "25", "1")])

    assert result_for(informe, fund_class).reason == REASON_UNMAPPED


@pytest.mark.parametrize(
    "pl, check, flag",
    [
        (None, PL_ABSENT, PL_ABSENT),
        ("0", PL_NOT_POSITIVE, PL_NOT_POSITIVE),
        ("-10", PL_NOT_POSITIVE, PL_NOT_POSITIVE),
        ("101", WITHIN_1PCT, None),  # soma 100: diferenca de R$ 1, exatamente 1% do PL
        ("98.99", OUTSIDE_1PCT, SUM_OUTSIDE_PL),  # diferenca de R$ 1,01, acima de 1% do PL
    ],
)
def test_pl_is_only_a_check(informe, pl, check, flag):
    fund_class, _ = build(informe, 1, [(SENIOR, "80", "1"), (SUBORDINATE, "20", "1")], pl=pl)

    result = result_for(informe, fund_class)

    # A formula nao usa o PL: o resultado continua calculado, com a marca.
    assert result.state == CALCULATED
    assert result.subordinacao_total.value == Decimal(20)
    assert result.pl_check == check

    if flag is None:
        assert not {PL_ABSENT, PL_NOT_POSITIVE, SUM_OUTSIDE_PL} & set(result.flags)
    else:
        assert flag in result.flags


def test_pl_one_percent_plus_a_cent_is_outside(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "101", "1"), (SUBORDINATE, "0.01", "1")], pl="100")

    result = result_for(informe, fund_class)

    assert result.total == Decimal("101.01")
    assert result.pl_check == OUTSIDE_1PCT


def test_competence_without_tab_X_2(informe):
    _, fund_class = informe.fund_and_class(1)
    informe.put(fund_class, {"tab_I.TAB_I_VL_ATIVO": "100", PL: "100"})

    result = only(subordinacao(informe.connection, SEP))

    assert result.state == NO_DATA
    assert result.reason == REASON_NO_TAB_X_2
    assert result.pl.value == Decimal(100)


@pytest.mark.parametrize(
    "quantity, unit_value, kind, reason",
    [
        (None, "1", "numeric", REASON_MISSING),
        ("10", None, "numeric", REASON_MISSING),
        ("-10", "1", "numeric", REASON_NEGATIVE),
        ("10", "-1", "numeric", REASON_NEGATIVE),
    ],
)
def test_series_input_problems_give_no_data(informe, quantity, unit_value, kind, reason):
    fund_class, _ = build(informe, 1, [(SENIOR, "100", "1"), (SUBORDINATE, quantity, unit_value)], pl=None)

    result = result_for(informe, fund_class)

    assert result.state == NO_DATA
    assert result.reason == reason


def test_text_value_is_unexpected_type(informe):
    fund_class, ids = build(informe, 1, [(SENIOR, "100", "1"), (SUBORDINATE, "10", None)], pl=None)
    informe.series_field(ids[1], UNIT_VALUE, "texto ficticio", value_type="text")

    result = result_for(informe, fund_class)

    assert result.reason == REASON_UNEXPECTED_TYPE
    assert "texto ficticio" not in repr(result)


def test_zero_total(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "0", "1"), (SUBORDINATE, "0", "5")])

    result = result_for(informe, fund_class)

    assert result.state == NO_DATA
    assert result.reason == REASON_ZERO_TOTAL


def test_exact_product_without_rounding(informe):
    # Montados por codigo: 12 seguido de 20 noves, vezes 1,5.
    quantity = "12" + "9" * 20
    fund_class, _ = build(informe, 1, [(SENIOR, quantity, "1.5"), (SUBORDINATE, quantity, "0.5")])

    result = result_for(informe, fund_class)

    assert result.total == Decimal(quantity) * 2
    assert result.series[0].value == Decimal(quantity) * Decimal("1.5")
    assert result.subordinacao_total.value == Decimal(25)


def test_each_input_carries_its_provenance(informe):
    fund_class, ids = build(informe, 1, [(SENIOR, "100", "1")])

    (line,) = result_for(informe, fund_class).series

    assert line.series_id == ids[0]
    assert line.label_key == "subclasse senior serie 1"
    assert (line.level, line.subtype, line.rule_status) == ("senior", "nao_se_aplica", PROPOSED)

    for field, name in ((line.quantity, QUANTITY), (line.unit_value, UNIT_VALUE)):
        assert field.field_name == name
        assert field.reference_date == SEP
        assert field.source_code == "CVM_DADOS_ABERTOS"
        assert field.observation_id is not None


def test_map_review_status(informe):
    fund_class, _ = build(informe, 1, [(SENIOR, "100", "1"), (SUBORDINATE, "25", "1")])

    proposed = result_for(informe, fund_class)
    review_all(informe.connection)
    reviewed = result_for(informe, fund_class)

    assert proposed.map_review == PROPOSED
    assert PROPOSED_MAP in proposed.flags
    assert reviewed.map_review == REVIEWED
    assert PROPOSED_MAP not in reviewed.flags
    assert len(reviewed.rules_used) == 2


def test_open_conflict_is_flagged(informe):
    fund_class, ids = build(informe, 1, [(SENIOR, "100", "1")])
    first = informe.connection.execute(
        "SELECT id FROM observations WHERE quota_series_id = ? AND field_name = ?", (ids[0], QUANTITY)
    ).fetchone()[0]
    second = informe.series_field(ids[0], QUANTITY, "101", collected_at=T1)
    informe.open_conflict(QUANTITY, SEP, first, second)

    result = result_for(informe, fund_class)

    assert OPEN_CONFLICT in result.flags
    assert result.total == Decimal(101)


def test_competences_and_fund_parent(informe):
    fund, _ = informe.fund_and_class(1)
    informe.series(fund, SENIOR, quantity="80", unit_value="1", reference_date=OCT)
    informe.series(fund, SUBORDINATE, quantity="20", unit_value="1", reference_date=OCT)

    october = only(subordinacao(informe.connection, OCT))

    assert october.subject.kind == FUND_SUBJECT
    assert october.subordinacao_total.value == Decimal(20)
    assert subordinacao(informe.connection, SEP) == ()


def test_database_without_the_map(tmp_path):
    connection = create_schema(tmp_path / "so_001.db").connect()

    try:
        informe = SyntheticSeries(connection)
        _, fund_class = informe.fund_and_class(1)
        informe.series(fund_class, SENIOR)

        result = only(subordinacao(connection, SEP))
    finally:
        connection.close()

    assert result.state == NO_DATA
    assert result.reason == REASON_NO_MAP


def test_competence_must_be_month_end(informe):
    with pytest.raises(ValueError):
        subordinacao(informe.connection, "2026-09-29")


def test_no_cnpj_in_repr_and_only_reads(informe):
    for n in (1, 2):
        build(informe, n, [(SENIOR, "100", "1"), (SUBORDINATE, "25", "1")])

    before = informe.connection.total_changes
    results = subordinacao(informe.connection, SEP)

    assert informe.connection.total_changes == before
    assert len(results) == 2

    for n in (1, 2):
        assert make_test_cnpj(n) not in repr(results) + str(results)
