from decimal import Decimal

import pytest

from apoio_indicadores import SyntheticInforme

from fundos.indicators.overdue import BUCKET_FIELDS as DELINQUENCY_FIELDS
from fundos.indicators.prazo_de_vencimento import BUCKET_FIELDS
from fundos.indicators.prazo_de_vencimento import LABELS
from fundos.indicators.prazo_de_vencimento import OFFICIAL_NAME
from fundos.indicators.prazo_de_vencimento import TOTAL
from fundos.indicators.prazo_de_vencimento import fields
from fundos.indicators.prazo_de_vencimento import por_prazo_de_vencimento
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCK_TOTAL
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_ZERO_DENOMINATOR


SEP = "2026-09-30"
AUG = "2026-08-31"


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def put(informe, subject, block, total, buckets, reference_date=SEP):
    values = {TOTAL[block]: total} if total is not None else {}
    values.update({BUCKET_FIELDS[block][index - 1]: value for index, value in buckets.items()})
    informe.put(subject, values, reference_date=reference_date)


def test_official_name_fields_and_labels():
    assert OFFICIAL_NAME == "Por Prazo de Vencimento (R$)"
    assert TOTAL == {
        BLOCK_A: "tab_V.TAB_V_A_VL_DIRCRED_PRAZO",
        BLOCK_B: "tab_VI.TAB_VI_A_VL_DIRCRED_PRAZO",
    }
    assert BUCKET_FIELDS[BLOCK_A][0] == "tab_V.TAB_V_A1_VL_PRAZO_VENC_30"
    assert BUCKET_FIELDS[BLOCK_A][9] == "tab_V.TAB_V_A10_VL_PRAZO_VENC_MAIOR_1080"
    assert BUCKET_FIELDS[BLOCK_B][8] == "tab_VI.TAB_VI_A9_VL_PRAZO_VENC_1080"
    assert (LABELS[0], LABELS[9], len(LABELS)) == ("Ate 30 dias", "Acima de 1080 dias", 10)
    assert not set(fields()) & set(DELINQUENCY_FIELDS[BLOCK_A] + DELINQUENCY_FIELDS[BLOCK_B])
    assert not any(name.startswith("inf_mensal_fiagro") or "CEDENTE" in name for name in fields())


def test_distribution_as_reported_with_the_share_of_each_bucket(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, BLOCK_A, "200", {1: "50", 2: "150", **{i: "0" for i in range(3, 11)}})
    put(informe, klass, BLOCK_B, "0", {i: "0" for i in range(1, 11)})

    [result] = por_prazo_de_vencimento(full_connection, SEP)
    block_a = result.block(BLOCK_A)

    assert (result.subject, result.reference_date, result.name) == (klass, SEP, OFFICIAL_NAME)
    assert [b.label for b in block_a.buckets] == list(LABELS)
    assert [b.amount.value for b in block_a.buckets[:3]] == [Decimal("50"), Decimal("150"), Decimal("0")]
    assert [b.share.value for b in block_a.buckets[:2]] == [Decimal("25"), Decimal("75")]
    assert all(b.share.reason == REASON_ZERO_DENOMINATOR for b in result.block(BLOCK_B).buckets)
    assert result.block(BLOCK_TOTAL).total.value == Decimal("200")
    assert result.block(BLOCK_TOTAL).buckets[1].amount.fields == (BUCKET_FIELDS[BLOCK_A][1], BUCKET_FIELDS[BLOCK_B][1])


def test_total_is_never_rebuilt_from_the_buckets(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, BLOCK_A, "100", {1: "10", 2: "20"})

    [result] = por_prazo_de_vencimento(full_connection, SEP)

    assert result.block(BLOCK_A).total.value == Decimal("100")
    assert result.block(BLOCK_A).buckets[0].share.value == Decimal("10")
    assert (result.block(BLOCK_A).buckets[2].amount.state, result.block(BLOCK_A).buckets[2].amount.reason) == (
        NO_DATA,
        REASON_MISSING,
    )
    assert (result.block(BLOCK_B).total.state, result.block(BLOCK_TOTAL).total.state) == (NO_DATA, NO_DATA)


def test_missing_total_leaves_the_buckets_without_share(informe, full_connection):
    _, klass = informe.fund_and_class(1)
    put(informe, klass, BLOCK_A, None, {1: "10"})

    [result] = por_prazo_de_vencimento(full_connection, SEP)

    assert result.block(BLOCK_A).buckets[0].amount.value == Decimal("10")
    assert result.block(BLOCK_A).buckets[0].share.reason == REASON_MISSING


def test_each_competence_on_its_own_and_subject_filter(informe, full_connection):
    fund, klass = informe.fund_and_class(1)
    put(informe, klass, BLOCK_A, "100", {1: "100"}, reference_date=AUG)
    put(informe, klass, BLOCK_A, "300", {2: "300"}, reference_date=SEP)
    put(informe, fund, BLOCK_A, "7", {1: "7"}, reference_date=SEP)

    september = por_prazo_de_vencimento(full_connection, SEP, [klass])

    assert [r.subject for r in september] == [klass]
    assert september[0].block(BLOCK_A).total.value == Decimal("300")
    assert september[0].block(BLOCK_A).buckets[0].amount.reason == REASON_MISSING
    assert [r.subject for r in por_prazo_de_vencimento(full_connection, SEP)] == [klass, fund]
