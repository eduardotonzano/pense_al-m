import pytest

from credit_assets.services.xml_value_normalizer import normalize

MONEY = {"data_type": "decimal", "currency": "BRL", "scale": "1"}
FRACTION = {"data_type": "decimal", "unit": "fraction"}


@pytest.mark.parametrize("raw, state, normalized", [
    ("45048086.96", "present_value", "45048086.96"),
    ("108830.3693", "present_value", "108830.3693"),
    ("100000000", "present_value", "100000000"),
    ("-0.01", "present_value", "-0.01"),
    ("0", "zero", "0"),
    ("", "present_empty", None),
    (None, "absent", None),
])
def test_money_keeps_precision_and_distinguishes_states(raw, state, normalized):
    result = normalize(raw, MONEY)
    assert result["field_state"] == state
    assert result["normalized_value"] == normalized
    assert result["currency"] == "BRL" and result["scale"] == "1"


@pytest.mark.parametrize("raw", ["4,5", "1.234,56", "R$ 10", "1e3", "12.5.3"])
def test_synthetic_invalid_numbers_are_flagged_not_guessed(raw):
    result = normalize(raw, MONEY)
    assert result["field_state"] == "invalid"
    assert result["automatic_validation_status"] == "invalid"
    assert result["normalized_value"] is None


def test_fraction_is_not_rescaled():
    assert normalize("0.0147", FRACTION)["normalized_value"] == "0.0147"
    assert normalize("1", FRACTION)["unit"] == "fraction"


def test_identifier_of_zeros_is_not_zero():
    result = normalize("00000000000000", {"data_type": "identifier"})
    assert result["field_state"] == "present_value"
    assert result["normalized_value"] == "00000000000000"


@pytest.mark.parametrize("raw, state", [
    ("2022-10-30", "present_value"),
    ("2023-02-01", "present_value"),
    ("2023-02-29", "invalid"),
    ("30/10/2022", "invalid"),
])
def test_dates_are_literal_and_validated(raw, state):
    result = normalize(raw, {"data_type": "date"})
    assert result["field_state"] == state
    if state == "present_value":
        assert result["normalized_value"] == raw
