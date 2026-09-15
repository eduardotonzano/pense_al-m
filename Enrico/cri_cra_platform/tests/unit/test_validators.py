import pytest
from credit_assets.utils.validators import only_digits, validate_asset_type

def test_only_digits():
    assert only_digits("10.753.164/0001-43") == "10753164000143"

def test_validate_asset_type():
    assert validate_asset_type("cra") == "CRA"
    with pytest.raises(ValueError):
        validate_asset_type("debenture")
