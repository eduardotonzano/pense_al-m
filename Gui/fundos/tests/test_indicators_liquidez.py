import dataclasses
import hashlib
from decimal import Decimal

import pytest

from apoio import T1
from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme
from conftest import create_full_schema

from fundos.indicators.liquidez import ALL_ZERO
from fundos.indicators.liquidez import BUCKETS
from fundos.indicators.liquidez import NEGATIVE_BUCKET
from fundos.indicators.liquidez import NOTE
from fundos.indicators.liquidez import OPEN_CONFLICT
from fundos.indicators.liquidez import LiquidityResult
from fundos.indicators.liquidez import fields
from fundos.indicators.liquidez import liquidez
from fundos.indicators.reading import check_field_names
from fundos.indicators.reading import open_read_only
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.informe_fidc.columns import HEADERS
from fundos.informe_fidc.columns import LEADING


SEP = "2026-09-30"
AUG = "2026-08-31"
LABELS = [label for label, _ in BUCKETS]


@pytest.fixture
def informe(full_connection):
    return SyntheticInforme(full_connection)


def row(*values):
    """As 7 faixas na ordem do modelo (None = sem linha); valores ficticios."""

    return {name: value for name, value in zip(fields(), values) if value is not None}


def only(results):
    assert len(results) == 1
    return results[0]


def result_for(informe, values, n=1, reference_date=SEP):
    _, klass = informe.fund_and_class(n)
    informe.put(klass, values, reference_date=reference_date)
    return only(liquidez(informe.connection, reference_date, [klass]))


def test_fields_labels_and_note():
    assert fields() == tuple("tab_X_5." + column for column in HEADERS["tab_X_5"][len(LEADING):])
    assert check_field_names(fields()) == fields()
    assert LABELS[0] == "Ativos com liquidez imediata"
    assert LABELS[1] == "Ativos que podem ser liquidados em ate 30 dias"
    assert LABELS[-1] == "Ativos que podem ser liquidados em mais de 360 dias"
    assert all(label.isascii() for label in LABELS)
    assert NOTE == "Suplemento G, item X.5: preenchimento compulsorio apenas para os fundos abertos"


def test_buckets_as_informed_with_provenance(informe):
    _, klass = informe.fund_and_class(1)
    ids = informe.put(klass, row("10", "20.5", "0", "30", "40", "50", "60"))

    result = only(liquidez(informe.connection, SEP))

    assert (result.subject, result.reference_date, result.note) == (klass, SEP, NOTE)
    assert [label for label, _ in result.buckets] == LABELS
    assert [value.value for _, value in result.buckets] == [Decimal(v) for v in ("10", "20.5", "0", "30", "40", "50", "60")]
    assert result.bucket(LABELS[1]).observation_id == ids[fields()[1]]
    assert result.bucket(LABELS[1]).source_code == "CVM_DADOS_ABERTOS"
    assert result.flags == ()


def test_all_zero_is_zero_with_the_flag(informe):
    result = result_for(informe, row(*["0"] * 7))

    assert all((value.state, value.value) == (PRESENT, Decimal(0)) for _, value in result.buckets)
    assert result.flags == (ALL_ZERO,)


def test_negative_bucket_is_kept_and_flagged(informe):
    result = result_for(informe, row("-5", "0", "0", "0", "0", "0", "10"))

    assert result.bucket(LABELS[0]).value == Decimal(-5)
    assert result.flags == (NEGATIVE_BUCKET,)


def test_missing_bucket_is_no_data_never_zero(informe):
    result = result_for(informe, row("0", "0", "0", None, "0", "0", "0"))
    missing = result.bucket(LABELS[3])

    assert (missing.state, missing.value, missing.reason) == (NO_DATA, None, REASON_MISSING)
    assert ALL_ZERO not in result.flags


def test_text_value_is_unexpected_type_and_never_repeated(informe):
    _, klass = informe.fund_and_class(1)
    informe.put(klass, row("1", "2", "3", "4", "5", "6", None))
    informe.put(klass, {fields()[-1]: "texto ficticio"}, value_type="text")

    result = only(liquidez(informe.connection, SEP))

    assert result.bucket(LABELS[-1]).reason == REASON_UNEXPECTED_TYPE
    assert "texto ficticio" not in repr(result) + str(result)


def test_nothing_is_summed_or_divided():
    names = [item.name for item in dataclasses.fields(LiquidityResult)]

    assert names == ["subject", "reference_date", "buckets", "flags", "name", "note"]


def test_competences_subjects_and_the_condominium_field_changes_nothing(informe):
    fund, klass = informe.fund_and_class(1)
    informe.put(klass, row(*["1"] * 7), reference_date=AUG)
    informe.put(klass, row(*["2"] * 7))
    informe.put(klass, {"tab_I.CONDOM": "FECHADO"}, value_type="text")
    informe.put(fund, row(*["0"] * 7))

    september = liquidez(informe.connection, SEP)
    august = only(liquidez(informe.connection, AUG, [klass]))

    assert [result.subject for result in september] == [klass, fund]
    assert september[0].bucket(LABELS[0]).value == Decimal(2)
    assert september[0].flags == ()
    assert september[1].flags == (ALL_ZERO,)
    assert august.bucket(LABELS[0]).value == Decimal(1)
    assert liquidez(informe.connection, SEP, []) == ()
    assert liquidez(informe.connection, "2026-07-31") == ()


def test_priority_source_latest_collection_and_open_conflict(informe):
    _, klass = informe.fund_and_class(1)
    first = informe.put(klass, row(*["1"] * 7))
    informe.put(klass, {fields()[0]: "9"}, source="manual")
    later = informe.put(klass, {fields()[1]: "7"}, collected_at=T1, raw=informe.new_raw("reapresentacao", T1))
    informe.open_conflict(fields()[1], SEP, first[fields()[1]], later[fields()[1]])

    result = only(liquidez(informe.connection, SEP))

    assert (result.bucket(LABELS[0]).value, result.bucket(LABELS[0]).source_code) == (Decimal(9), "MANUAL")
    assert (result.bucket(LABELS[1]).value, result.bucket(LABELS[1]).collected_at) == (Decimal(7), T1)
    assert result.flags == (OPEN_CONFLICT,)


def test_exact_decimal_with_25_digits(informe):
    # Montado por codigo: 23 noves e 2 casas.
    big = "9" * 23 + ".25"
    result = result_for(informe, row(big, "0", "0", "0", "0", "0", "0"))

    assert result.bucket(LABELS[0]).value == Decimal(big)


def test_competence_must_be_month_end(informe):
    with pytest.raises(ValueError):
        liquidez(informe.connection, "2026-09-29")


def test_no_cnpj_in_repr_and_only_reads(informe):
    for n in (1, 2):
        _, klass = informe.fund_and_class(n)
        informe.put(klass, row(*["1"] * 7))

    before = informe.connection.total_changes
    results = liquidez(informe.connection, SEP)

    assert informe.connection.total_changes == before
    assert len(results) == 2

    for n in (1, 2):
        assert make_test_cnpj(n) not in repr(results) + str(results)


def test_reading_through_open_read_only_leaves_the_file_unchanged(tmp_path):
    path = tmp_path / "fundos.db"
    writer = create_full_schema(path).connect()

    try:
        informe = SyntheticInforme(writer)
        _, klass = informe.fund_and_class(1)
        informe.put(klass, row(*["3"] * 7))
    finally:
        writer.close()

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = open_read_only(path)

    try:
        assert only(liquidez(connection, SEP)).bucket(LABELS[0]).value == Decimal(3)
        assert connection.in_transaction is False
    finally:
        connection.close()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fundos.db"]
