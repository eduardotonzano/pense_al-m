import pytest
from credit_assets.utils.validators import (
    format_cnpj,
    is_valid_cnpj,
    normalize_cnpj,
    only_digits,
    validate_asset_type,
)
from tests.cnpj_amostras import (
    CNPJ_ALFA_1,
    CNPJ_RECEITA,
    CNPJ_RECEITA_MASCARA,
    com_mascara,
    dv_errado,
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
    "02.773.542/0001-2A",  # letra no DV
    "A02773542000122",  # 15 caracteres
]

@pytest.mark.parametrize("value", VALID_CNPJ)
def test_is_valid_cnpj_accepts_real_cnpj_with_or_without_mask(value):
    assert is_valid_cnpj(value)
    assert is_valid_cnpj(only_digits(value))
    assert is_valid_cnpj(f"  {value}  ")

@pytest.mark.parametrize("value", INVALID_CNPJ)
def test_is_valid_cnpj_rejects_bad_check_digits_length_cpf_and_letter_in_check_digit(value):
    assert not is_valid_cnpj(value)
    assert normalize_cnpj(value) is None

def test_is_valid_cnpj_rejects_none():
    assert not is_valid_cnpj(None)
    assert normalize_cnpj(None) is None

def test_normalize_cnpj_returns_the_fourteen_digits_and_format_cnpj_restores_the_mask():
    assert normalize_cnpj(" 02.773.542/0001-22 ") == "02773542000122"
    assert format_cnpj("02773542000122") == "02.773.542/0001-22"

@pytest.mark.parametrize(
    "digits", ["", "0277354200012", "02.773.542/0001-22", "0277354200012A", "12abc34501de35"]
)
def test_format_cnpj_refuses_anything_but_the_canonical_fourteen_characters(digits):
    with pytest.raises(ValueError):
        format_cnpj(digits)

def test_validate_asset_type():
    assert validate_asset_type("cra") == "CRA"
    with pytest.raises(ValueError):
        validate_asset_type("debenture")


# --------------------------------------------- CNPJ alfanumerico (ADR-011)
# A regra e a de credit_assets/cnpj.py; os vetores sao ficticios (tests/cnpj_amostras.py),
# menos o exemplo da Receita (12ABC34501DE35).

@pytest.mark.parametrize(
    "value",
    [
        CNPJ_RECEITA,
        CNPJ_RECEITA_MASCARA,
        CNPJ_RECEITA.lower(),
        CNPJ_RECEITA_MASCARA.lower(),
        f"  {CNPJ_RECEITA_MASCARA}  ",
        "12.ABC.345/01DE35",  # mascara parcial
    ],
)
def test_alphanumeric_cnpj_is_valid_and_normalized_to_uppercase(value):
    assert is_valid_cnpj(value)
    assert normalize_cnpj(value) == CNPJ_RECEITA

def test_normalize_cnpj_keeps_every_letter_of_the_fictitious_alphanumeric_cnpj():
    assert CNPJ_ALFA_1 == "ZZZZZZZ1ZZZZ04"
    assert normalize_cnpj(com_mascara(CNPJ_ALFA_1)) == CNPJ_ALFA_1

@pytest.mark.parametrize(
    "value",
    [
        dv_errado(CNPJ_RECEITA),
        "12ABC 34501DE35",  # espaco interno
        "12.ABC.345 / 01DE-35",  # espaco em volta da barra, com letra
        "12ıBC34501DE10",  # i sem ponto; com I ASCII o DV vale
    ],
)
def test_alphanumeric_cnpj_with_wrong_check_digit_inner_space_or_non_ascii_letter_is_rejected(value):
    assert not is_valid_cnpj(value)
    assert normalize_cnpj(value) is None

ASCII_CNPJ = "02773542000122"

def _shift_digits(text, zero):
    return "".join(chr(ord(character) - 48 + zero) for character in text)

# Corpo em digitos fora do ASCII e DV em ASCII: o DV vale quando os digitos sao
# convertidos. \d e int() aceitam esses digitos; a regra de credit_assets/cnpj.py
# exige ASCII.
NON_ASCII_DIGITS = {
    "largura-total": _shift_digits(ASCII_CNPJ[:12], 0xFF10) + ASCII_CNPJ[12:],
    "arabe-indico": _shift_digits(ASCII_CNPJ[:12], 0x0660) + ASCII_CNPJ[12:],
    "largura-total-mascara": com_mascara(_shift_digits(ASCII_CNPJ[:12], 0xFF10) + ASCII_CNPJ[12:]),
    "arabe-indico-mascara": com_mascara(_shift_digits(ASCII_CNPJ[:12], 0x0660) + ASCII_CNPJ[12:]),
}

@pytest.mark.parametrize("value", NON_ASCII_DIGITS.values(), ids=NON_ASCII_DIGITS.keys())
def test_digits_outside_ascii_with_valid_check_digits_are_rejected(value):
    assert "".join(str(int(character)) for character in value if character.isdigit()) == ASCII_CNPJ
    assert not value.isascii()
    assert not is_valid_cnpj(value)
    assert normalize_cnpj(value) is None

@pytest.mark.parametrize("value", [2773542000122, 2773542000122.0, b"02773542000122", ["02773542000122"]])
def test_cnpj_that_is_not_text_is_rejected_without_raising(value):
    assert not is_valid_cnpj(value)
    assert normalize_cnpj(value) is None

def test_format_cnpj_keeps_the_letters():
    assert format_cnpj(CNPJ_RECEITA) == CNPJ_RECEITA_MASCARA
    assert format_cnpj(CNPJ_ALFA_1) == "ZZ.ZZZ.ZZ1/ZZZZ-04"
    assert format_cnpj(normalize_cnpj(CNPJ_RECEITA_MASCARA.lower())) == CNPJ_RECEITA_MASCARA

@pytest.mark.parametrize(
    "value", ["12abc34501de35", "12ABC34501DE3A", CNPJ_RECEITA_MASCARA, "0277354200012", None, 2773542000122]
)
def test_format_cnpj_error_never_repeats_the_value(value):
    with pytest.raises(ValueError) as error:
        format_cnpj(value)
    assert str(value) not in str(error.value)
