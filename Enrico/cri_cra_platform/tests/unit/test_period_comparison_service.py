import pytest

from credit_assets.services.period_comparison_service import compare_pair


def _v(value, state="present_value", data_type="decimal", scale="1"):
    return {"normalized_value": value, "field_state": state, "data_type": data_type, "scale": scale}


def test_numeric_change_is_exact_decimal():
    result = compare_pair(_v("44397440.53"), _v("45048086.96"))
    assert result["comparison_status"] == "changed"
    assert result["absolute_change"] == "650646.43"
    assert result["relative_change"] == "0.014655"


def test_zero_to_value_is_numeric_change_without_relative():
    result = compare_pair(_v("0", state="zero"), _v("30000000"))
    assert result["comparison_status"] == "changed"
    assert result["relative_change"] is None


@pytest.mark.parametrize("before, after", [
    (_v("100000", scale="unknown"), _v("100000000")),
    (_v("100000000"), _v("100000", scale="unknown")),
])
def test_unknown_scale_is_never_compared_numerically(before, after):
    result = compare_pair(before, after)
    assert result["comparison_status"] == "excluded_scale_unknown"
    assert result["absolute_change"] is None


def test_text_and_state_changes():
    assert compare_pair(
        _v("Adimplente", data_type="text", scale=None), _v("Em atraso", data_type="text", scale=None)
    )["comparison_status"] == "changed"
    assert compare_pair(
        _v(None, state="present_empty", data_type="text", scale=None),
        _v("A.br (sf)", data_type="text", scale=None),
    )["comparison_status"] == "state_changed"
    assert compare_pair(None, _v("1"))["comparison_status"] == "only_one_side"
