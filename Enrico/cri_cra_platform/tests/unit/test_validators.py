import pytest
from credit_assets.utils.validators import (
    format_cnpj,
    is_valid_cnpj,
    normalize_cnpj,
    only_digits,
    validate_asset_type,
)

def test_only_digits():
    assert only_digits("10.753.164/0001-43") == "10753164000143"

# CNPJ reais lidos na CVM e no ativos_piloto.csv; o ultimo da lista de
# invalidos (cedente do Cafe Brasil no informe da CVM) reprova no modulo 11.
VALID_CNPJ = [
    "02.773.542/0001-22",
    "82.120.676/0001-83",
    "10.753.164/0001-43",
    "01.486.546/0001-67",
    "31.943.818/0001-71",
]
INVALID_CNPJ = [
    "23.357.072/0001-81",
    "00000000000000",
    "11111111111111",
    "0277354200012",
    "027735420001220",
    "111.444.777-35",
    "0",
    "",
    ",",
    "02.773.542/0001-2A",
    "A02773542000122",
]

@pytest.mark.parametrize("value", VALID_CNPJ)
def test_is_valid_cnpj_accepts_real_cnpj_with_or_without_mask(value):
    assert is_valid_cnpj(value)
    assert is_valid_cnpj(only_digits(value))
    assert is_valid_cnpj(f"  {value}  ")

@pytest.mark.parametrize("value", INVALID_CNPJ)
def test_is_valid_cnpj_rejects_bad_check_digits_length_cpf_and_letters(value):
    assert not is_valid_cnpj(value)
    assert normalize_cnpj(value) is None

def test_is_valid_cnpj_rejects_none():
    assert not is_valid_cnpj(None)
    assert normalize_cnpj(None) is None

def test_normalize_cnpj_returns_the_fourteen_digits_and_format_cnpj_restores_the_mask():
    assert normalize_cnpj(" 02.773.542/0001-22 ") == "02773542000122"
    assert format_cnpj("02773542000122") == "02.773.542/0001-22"

@pytest.mark.parametrize("digits", ["", "0277354200012", "02.773.542/0001-22", "0277354200012A"])
def test_format_cnpj_refuses_anything_but_fourteen_digits(digits):
    with pytest.raises(ValueError):
        format_cnpj(digits)

def test_validate_asset_type():
    assert validate_asset_type("cra") == "CRA"
    with pytest.raises(ValueError):
        validate_asset_type("debenture")
